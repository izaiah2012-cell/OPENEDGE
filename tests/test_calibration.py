import pandas as pd

from openedge.validation.calibration import build_confidence_calibration, confidence_to_band


def test_confidence_to_band_thresholds():
    assert confidence_to_band(95) == "90-100"
    assert confidence_to_band(85) == "80-89"
    assert confidence_to_band(75) == "70-79"
    assert confidence_to_band(65) == "60-69"
    assert confidence_to_band(59) == "Below 60"


def test_build_confidence_calibration_empty():
    frame = pd.DataFrame(columns=["confidence", "correct"])
    result = build_confidence_calibration(frame)

    assert result["average_confidence"] == 0.0
    assert len(result["items"]) == 5
    assert sum(item["signals"] for item in result["items"]) == 0


def test_build_confidence_calibration_small_dataset():
    frame = pd.DataFrame(
        [
            {"confidence": 92, "correct": 1},
            {"confidence": 84, "correct": 0},
            {"confidence": 76, "correct": 1},
            {"confidence": 61, "correct": 1},
            {"confidence": 55, "correct": 0},
        ]
    )

    result = build_confidence_calibration(frame)

    lookup = {item["band"]: item for item in result["items"]}
    assert lookup["90-100"]["signals"] == 1
    assert lookup["90-100"]["correct"] == 1
    assert lookup["80-89"]["signals"] == 1
    assert lookup["80-89"]["correct"] == 0
    assert lookup["70-79"]["signals"] == 1
    assert lookup["60-69"]["signals"] == 1
    assert lookup["Below 60"]["signals"] == 1
