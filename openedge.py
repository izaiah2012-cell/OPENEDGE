import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from openedge.engines.history_engine import get_historical_matches
from openedge.engines.macro_engine import calculate_macro_risk, get_macro_events
from openedge.engines.research_writer import generate_research_summary
from openedge.validation.journal import backfill_from_db, dedupe_entries
from openedge.validation.validation_engine import ValidationEngine
from openedge.workflows import MorningWorkflow

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "openedge_db.csv"
REPORTS_DIR = BASE_DIR / "reports"

# -----------------------------
# DATA
# -----------------------------

def opening_structure():
    spy = yf.Ticker("SPY").history(period="2d", interval="1m")

    if len(spy) < 10:
        return None

    open_price = spy["Open"].iloc[0]
    prev_close = spy["Close"].iloc[-2]

    gap_pct = ((open_price - prev_close) / prev_close) * 100

    first_5m = spy.head(5)
    high_5m = first_5m["High"].max()
    low_5m = first_5m["Low"].min()

    range_5m = ((high_5m - low_5m) / open_price) * 100

    return {
        "open": open_price,
        "prev_close": prev_close,
        "gap_pct": gap_pct,
        "range_5m": range_5m
    }


def classify_open(gap, range5):
    if abs(gap) > 0.5 and range5 < 0.4:
        return "TREND OPEN"

    if abs(gap) > 0.3 and range5 > 0.6:
        return "FAKEOUT OPEN"

    if range5 > 0.8:
        return "CHOP OPEN"

    return "NEUTRAL OPEN"


def similar_day_probability(df, today):
    scores = []

    for _, row in df.iterrows():
        try:
            score = abs(row["gap_pct"] - today["gap_pct"]) + abs(row["range_5m"] - today["range_5m"])
            scores.append((score, row["bias"], row["correct"]))
        except:
            continue

    scores = sorted(scores, key=lambda x: x[0])[:20]  # closest 20 days

    if len(scores) == 0:
        return None

    up = sum(1 for s in scores if s[1] == "UP")
    down = sum(1 for s in scores if s[1] == "DOWN")

    return {
        "up_prob": up / len(scores),
        "down_prob": down / len(scores),
        "sample_size": len(scores)
    }


def compute_open_type():
    open_data = opening_structure()
    if open_data:
        return classify_open(open_data["gap_pct"], open_data["range_5m"])
    return "NO DATA"


def price(ticker):
    return yf.Ticker(ticker).history(period="5d")["Close"].iloc[-1]

def pct(ticker):
    data = yf.Ticker(ticker).history(period="5d")
    return ((data["Close"].iloc[-1] - data["Close"].iloc[-2]) /
            data["Close"].iloc[-2]) * 100

# -----------------------------
# SIGNALS
# -----------------------------

def risk_on():
    return np.mean([pct("SPY"), pct("QQQ"), pct("DIA")])

def volatility():
    vix = price("^VIX")
    if vix < 15:
        return 2
    elif vix < 20:
        return 5
    elif vix < 25:
        return 7
    return 9

def leadership():
    stocks = ["JPM", "MSFT", "NVDA", "CAT", "UNH"]
    vals = []
    for s in stocks:
        try:
            vals.append(pct(s))
        except:
            pass
    return np.mean(vals)

# -----------------------------
# MODEL
# -----------------------------

def OAR(vix):
    return vix

def OOS(lead, risk):
    return (lead + risk) / 2

def direction(risk, lead):
    score = risk + lead
    if score > 1:
        return "UP"
    elif score < -1:
        return "DOWN"
    return "NEUTRAL"

# -----------------------------
# OUTCOME (NEW)
# -----------------------------

def get_market_outcome():
    # simple proxy: SPY direction from previous close to current close
    data = yf.Ticker("SPY").history(period="2d")
    change = data["Close"].iloc[-1] - data["Close"].iloc[-2]

    if change > 0:
        return "UP"
    elif change < 0:
        return "DOWN"
    return "NEUTRAL"

# -----------------------------
# SAVE
# -----------------------------

CANONICAL_COLUMNS = ["date", "risk", "leadership", "vix", "gap_pct", "range_5m", "open_type", "oar", "oos", "bias", "actual", "correct"]
LEGACY_RENAMES = {"volatility": "vix"}


def normalize_dataframe(df):
    for old_name, new_name in LEGACY_RENAMES.items():
        if old_name in df.columns and new_name not in df.columns:
            df = df.rename(columns={old_name: new_name})

    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    return df[CANONICAL_COLUMNS]


def migrate_database(file):
    file_path = Path(file)
    backup = file_path.with_suffix(file_path.suffix + ".bak")
    df = pd.read_csv(file_path, on_bad_lines="skip")
    df = normalize_dataframe(df)
    if backup.exists():
        backup.unlink()
    file_path.rename(backup)
    df.to_csv(file_path, index=False, columns=CANONICAL_COLUMNS)
    print(f"Migrated legacy dataset to new schema and backed up original to {backup}.")
    return df


def save(row):
    df_row = pd.DataFrame([row], columns=CANONICAL_COLUMNS)

    if DB_FILE.exists():
        with DB_FILE.open("r", encoding="utf-8") as f:
            existing_header = f.readline().strip().split(",")

        if existing_header != CANONICAL_COLUMNS:
            migrate_database(DB_FILE)

        df_row.to_csv(DB_FILE, mode="a", header=False, index=False, columns=CANONICAL_COLUMNS)
    else:
        df_row.to_csv(DB_FILE, index=False, columns=CANONICAL_COLUMNS)


def load_database(file):
    file_path = Path(file)
    try:
        df = pd.read_csv(file_path)
    except pd.errors.ParserError:
        df = pd.read_csv(file_path, on_bad_lines="skip")

    if set(df.columns) != set(CANONICAL_COLUMNS):
        df = normalize_dataframe(df)
        df.to_csv(file_path, index=False, columns=CANONICAL_COLUMNS)

    return df

# -----------------------------
# RUN
# -----------------------------

def run():

    risk = risk_on()
    lead = leadership()
    vix_score = volatility()

    oar = OAR(vix_score)
    oos = OOS(lead, risk)
    bias = direction(risk, lead)

    actual = get_market_outcome()

    correct = 1 if bias == actual else 0

    open_data = opening_structure()
    open_type = compute_open_type()

    row = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "risk": risk,
        "leadership": lead,
        "vix": vix_score,
        "gap_pct": None,
        "range_5m": None,
        "open_type": None,
        "oar": oar,
        "oos": oos,
        "bias": bias,
        "actual": actual,
        "correct": correct
    }

    if open_data:
        row["gap_pct"] = open_data["gap_pct"]
        row["range_5m"] = open_data["range_5m"]
        row["open_type"] = open_type

    if DB_FILE.exists():
        df = load_database(DB_FILE)
    else:
        df = pd.DataFrame(columns=CANONICAL_COLUMNS)

    weights = train_weights(df)
    score = weighted_score(row, weights)
    weighted_probs = score_to_prob(score)

    print("\n========================")
    print("OPENEDGE v0.9 WEIGHTED MODEL")
    print("========================")

    print("Score:", round(score, 4))
    print("UP Probability:", weighted_probs["UP"])
    print("DOWN Probability:", weighted_probs["DOWN"])

    print("\nFeature Weights:")
    for k, v in weights.items():
        print(k, round(v, 4))

    today = {
        "gap_pct": open_data["gap_pct"] if open_data else None,
        "range_5m": open_data["range_5m"] if open_data else None
    }

    probs = similar_day_probability(df, today)

    if probs:
        print("\n--- Similar Day Probability ---")
        print(f"UP Probability: {probs['up_prob']*100:.1f}%")
        print(f"DOWN Probability: {probs['down_prob']*100:.1f}%")
        print(f"Samples: {probs['sample_size']}")

    save(row)

    print("\nOPENEDGE v0.3\n")
    print(f"Open type: {open_type}\n")
    for k, v in row.items():
        print(f"{k}: {v}")

    print("\nAccuracy this run:", correct)

    feature_importance()


def analyze():
    if not DB_FILE.exists():
        print("No dataset found yet.")
        return

    df = load_database(DB_FILE)

    if len(df) == 0:
        print("Dataset empty.")
        return

    has_correct_column = "correct" in df.columns
    has_bias = "bias" in df.columns
    has_vix = "vix" in df.columns

    print("\n========================")
    print("OPENEDGE v0.4 ANALYTICS")
    print("========================")

    total = len(df)
    print(f"\nTotal signals: {total}")

    if "open_type" in df.columns:
        open_type_counts = df["open_type"].dropna().value_counts()
        if len(open_type_counts) > 0:
            print("Open type breakdown:")
            for open_type, count in open_type_counts.items():
                print(f"  {open_type}: {count}")

    missing_gap = None
    missing_range = None

    if "gap_pct" in df.columns:
        gap_stats = df["gap_pct"].dropna()
        missing_gap = len(df) - len(gap_stats)
        if len(gap_stats) > 0:
            print("\nGap % summary:")
            print(f"  min: {gap_stats.min():.4f}")
            print(f"  max: {gap_stats.max():.4f}")
            print(f"  mean: {gap_stats.mean():.4f}")
        print(f"  missing gap_pct rows: {missing_gap}")

    if "range_5m" in df.columns:
        range_stats = df["range_5m"].dropna()
        missing_range = len(df) - len(range_stats)
        if len(range_stats) > 0:
            print("\n5m range % summary:")
            print(f"  min: {range_stats.min():.4f}")
            print(f"  max: {range_stats.max():.4f}")
            print(f"  mean: {range_stats.mean():.4f}")
        print(f"  missing range_5m rows: {missing_range}")

    if missing_gap is not None and missing_gap > 0:
        print("\nWARNING: Some rows are missing gap_pct values.")
    if missing_range is not None and missing_range > 0:
        print("WARNING: Some rows are missing range_5m values.")

    if has_correct_column and df["correct"].notna().any():
        valid_correct = df["correct"].dropna().astype(float)
        correct = int(valid_correct.sum())
        accuracy = (correct / total) * 100
        print(f"Correct signals: {correct}")
        print(f"Accuracy: {accuracy:.2f}%")
        has_correct = True
    else:
        print("Correct/accuracy metrics unavailable in this dataset.")
        has_correct = False

    print("\n--- Bias Breakdown ---")
    if has_bias:
        for b in ["UP", "DOWN", "NEUTRAL"]:
            subset = df[df["bias"] == b]
            if len(subset) > 0:
                if has_correct:
                    acc = subset["correct"].mean() * 100
                    print(f"{b}: {acc:.2f}% ({len(subset)} trades)")
                else:
                    print(f"{b}: {len(subset)} signals")
    else:
        print("Bias data unavailable.")

    if has_vix:
        print("\n--- Volatility Regime ---")

        low = df[df["vix"] < 20]
        high = df[df["vix"] >= 20]

        if len(low) > 0:
            if has_correct:
                low_correct = low["correct"].dropna().astype(float)
                if len(low_correct) > 0:
                    print(f"Low VIX accuracy: {low_correct.mean()*100:.2f}%")
                else:
                    print(f"Low VIX signals: {len(low)}")
            else:
                print(f"Low VIX signals: {len(low)}")

        if len(high) > 0:
            if has_correct:
                high_correct = high["correct"].dropna().astype(float)
                if len(high_correct) > 0:
                    print(f"High VIX accuracy: {high_correct.mean()*100:.2f}%")
                else:
                    print(f"High VIX signals: {len(high)}")
            else:
                print(f"High VIX signals: {len(high)}")

    if has_correct:
        if accuracy > 52:
            print("\nEDGE DETECTED (above random baseline)")
        else:
            print("\nNO EDGE (at or below random baseline)")

    latest = df.iloc[-1].to_dict()

    if latest.get("bias") == "UP" and float(latest.get("vix", 0) or 0) <= 5:
        market_regime = "Risk On"
    elif latest.get("bias") == "DOWN" or float(latest.get("vix", 0) or 0) >= 7:
        market_regime = "Risk Off"
    else:
        market_regime = "Neutral"

    macro_events = get_macro_events()
    macro_risk = calculate_macro_risk(macro_events)
    historical = get_historical_matches(DB_FILE, top_n=5)

    summary_payload = {
        "market_regime": market_regime,
        "confidence": 65 if latest.get("bias") in ("UP", "DOWN") else 55,
        "opening_auction_risk": latest.get("oar", "N/A"),
        "opportunity_score": latest.get("oos", "N/A"),
        "bias": latest.get("bias", "N/A"),
        "leadership": {"Aggregate": {"score": latest.get("leadership", "N/A"), "status": "Observed"}},
        "macro_events": macro_events,
        "macro_risk": macro_risk,
        "historical_match": historical.get("best_match", {}),
        "historical_similarity": historical.get("average_similarity", 0.0),
    }

    report_text = generate_research_summary(summary_payload)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_research.md"
    report_file.write_text(report_text, encoding="utf-8")

    print("\nResearch report generated.")
    print(f"Saved to:\n{report_file}")


def main():
    parser = argparse.ArgumentParser(description="OPENEDGE signal generator and analytics")
    parser.add_argument("mode", nargs="?", default="run", choices=["run", "analyze", "edge", "feature", "morning", "validate"],
                        help="run the signal generator, analyze saved results, test edge accuracy, run feature importance, execute morning automation, or print validation metrics")
    parser.add_argument("--export-json", dest="export_json", default="",
                        help="when mode is validate, optionally write summary metrics JSON to this path")
    parser.add_argument("--backfill-journal", action="store_true",
                        help="when mode is validate, append missing journal rows from openedge_db.csv without overwriting existing entries")
    parser.add_argument("--dedupe-journal", action="store_true",
                        help="when mode is validate, deduplicate research_journal.csv by date and keep the latest row for each date")
    parser.add_argument("--dedupe-mode", choices=["date", "date-bias"], default="date",
                        help="when --dedupe-journal is set, choose dedupe key strategy")
    args = parser.parse_args()

    if args.mode == "analyze":
        analyze()
    elif args.mode == "morning":
        MorningWorkflow().run()
    elif args.mode == "validate":
        validate(
            export_json=args.export_json,
            backfill_journal=args.backfill_journal,
            dedupe_journal=args.dedupe_journal,
            dedupe_mode=args.dedupe_mode,
        )
    elif args.mode == "edge":
        if not DB_FILE.exists():
            print("No dataset found yet.")
            return
        df = load_database(DB_FILE)
        edge_evaluation(df)
    elif args.mode == "feature":
        if not DB_FILE.exists():
            print("No dataset found yet.")
            return
        feature_importance()
    else:
        run()


def edge_evaluation(df):
    print("\n========================")
    print("OPENEDGE v0.7 EDGE TEST")
    print("========================")

    if len(df) < 10:
        print("Not enough data yet (need at least 10 rows)")
        return

    overall = df["correct"].mean() * 100
    print(f"\nOverall Accuracy: {overall:.2f}%")

    if overall > 52:
        print("EDGE DETECTED (> random baseline)")
    else:
        print("NO EDGE (<= random)")

    print("\n--- Open Type Performance ---")
    for t in df["open_type"].dropna().unique():
        subset = df[df["open_type"] == t]
        if len(subset) > 0:
            acc = subset["correct"].mean() * 100
            print(f"{t}: {acc:.2f}% ({len(subset)} samples)")


def feature_importance():
    if not DB_FILE.exists():
        print("No dataset found")
        return

    df = load_database(DB_FILE)

    if "correct" not in df.columns:
        print("No correctness column found")
        return

    print("\n============================")
    print("OPENEDGE v0.8 FEATURE ANALYSIS")
    print("============================\n")

    total = len(df)
    print(f"Total samples: {total}\n")

    def lift(col):
        try:
            good = df[df["correct"] == 1][col].mean()
            bad = df[df["correct"] == 0][col].mean()
            return good - bad
        except:
            return None

    features = ["gap_pct", "range_5m", "vix", "risk", "leadership", "oos"]
    print("--- Numeric Feature Lift (good - bad) ---")
    for f in features:
        if f in df.columns:
            l = lift(f)
            if l is not None:
                print(f"{f}: {l:.4f}")

    print("\n--- Open Type Accuracy ---")
    if "open_type" in df.columns:
        for t in df["open_type"].dropna().unique():
            subset = df[df["open_type"] == t]
            acc = subset["correct"].mean() * 100
            print(f"{t}: {acc:.2f}% ({len(subset)})")

    print("\n--- Bias Accuracy ---")
    if "bias" in df.columns:
        for b in df["bias"].unique():
            subset = df[df["bias"] == b]
            acc = subset["correct"].mean() * 100
            print(f"{b}: {acc:.2f}% ({len(subset)})")

    overall = df["correct"].mean() * 100
    print("\n--- Summary ---")
    print(f"Overall Accuracy: {overall:.2f}%")
    if overall > 52:
        print("EDGE DETECTED (statistical advantage above baseline)")
    else:
        print("NO EDGE (at or below randomness)")


def train_weights(df):
    """
    Learn simple weights based on correlation with correctness.
    """

    features = ["gap_pct", "range_5m", "vix", "risk", "leadership", "oos"]

    weights = {}

    for f in features:
        if f in df.columns:
            try:
                corr = df[f].corr(df["correct"])
                if pd.isna(corr):
                    corr = 0
                weights[f] = corr
            except:
                weights[f] = 0

    # normalize weights (avoid dominance)
    total = sum(abs(v) for v in weights.values()) + 1e-9

    for k in weights:
        weights[k] = weights[k] / total

    return weights

def weighted_score(row, weights):
    score = 0

    for k, w in weights.items():
        if k in row and pd.notna(row[k]):
            score += row[k] * w

    return score

def score_to_prob(score):
    if score > 0.5:
        return {"UP": 0.65, "DOWN": 0.35}
    elif score < -0.5:
        return {"UP": 0.35, "DOWN": 0.65}
    else:
        return {"UP": 0.5, "DOWN": 0.5}


def validate(
    export_json: str = "",
    backfill_journal: bool = False,
    dedupe_journal: bool = False,
    dedupe_mode: str = "date",
):
    journal_path = BASE_DIR / "research_journal.csv"
    if backfill_journal:
        added = backfill_from_db(DB_FILE, journal_path, reports_dir=REPORTS_DIR)
        print(f"Backfill appended {added} journal row(s).")
    if dedupe_journal:
        removed = dedupe_entries(journal_path, mode=dedupe_mode)
        print(f"Dedupe ({dedupe_mode}) removed {removed} duplicate journal row(s).")

    engine = ValidationEngine(db_path=DB_FILE, journal_path=BASE_DIR / "research_journal.csv", reports_dir=REPORTS_DIR)
    metrics = engine.summary_metrics()

    print("\n========================")
    print("OPENEDGE VALIDATION")
    print("========================")
    print(f"Total Signals: {metrics['total_signals']}")
    print(f"Correct Signals: {metrics['correct_signals']}")
    print(f"Incorrect Signals: {metrics['incorrect_signals']}")
    print(f"Overall Accuracy: {metrics['overall_accuracy']:.2f}%")
    print(f"Rolling 20-session Accuracy: {float(metrics['rolling_20_accuracy']):.2f}%")
    print(f"Rolling 50-session Accuracy (if available): {float(metrics['rolling_50_accuracy']):.2f}%")
    print(f"Average Confidence: {float(metrics['average_confidence']):.2f}")
    print(f"Best Performing Regime: {metrics['best_performing_regime']}")
    print(f"Worst Performing Regime: {metrics['worst_performing_regime']}")
    print(f"Average Historical Similarity: {float(metrics['average_historical_similarity']):.2f}%")

    if export_json:
        output_path = Path(export_json)
        if not output_path.is_absolute():
            output_path = BASE_DIR / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Validation metrics exported to: {output_path}")


if __name__ == "__main__":
    main()
