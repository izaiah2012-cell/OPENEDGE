# OPENEDGE
Trading automation analysis tool

## Testing

Run the lightweight regression suite:

```bash
pytest
```

## CLI Usage

Run the signal generator:

```bash
python openedge.py run
```

Analyze saved signals:

```bash
python openedge.py analyze
```

Run edge accuracy testing:

```bash
python openedge.py edge
```

Run feature importance analysis:

```bash
python openedge.py feature
```

> Note: `analyze`, `edge`, and `feature` require an existing `openedge_db.csv` dataset created by `python openedge.py run`.
>
> If `openedge_db.csv` is missing `correct` or `open_type`, the analytics output may skip some metrics.

