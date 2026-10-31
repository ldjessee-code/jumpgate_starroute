"""Read and write the benchmark dataset in each serverless format."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED = ("csv", "parquet", "feather", "sqlite", "duckdb", "json", "ndjson")
OPTIONAL = ("npz",)
ALL = REQUIRED + OPTIONAL

EXTENSIONS = {
    "csv": ".csv",
    "parquet": ".parquet",
    "feather": ".feather",
    "sqlite": ".sqlite",
    "duckdb": ".duckdb",
    "json": ".json",
    "ndjson": ".ndjson",
    "npz": ".npz",
}


def as_text_frame(df: pd.DataFrame) -> pd.DataFrame:
    """String cells so every format round-trips identifiers exactly."""
    out = pd.DataFrame(index=df.index)
    for column in df.columns:
        series = df[column]
        text = series.astype(str)
        text = text.where(~series.isna(), "")
        lowered = text.str.strip().str.lower()
        text = text.mask(lowered.isin({"nan", "none", "<na>", "nat"}), "")
        out[column] = text
    return out.reset_index(drop=True)


def write_format(df: pd.DataFrame, fmt: str, path: str | Path) -> dict[str, Any]:
    """Write ``df`` to ``path``. Optional npz returns ok False instead of raising."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    frame = as_text_frame(df)
    try:
        if fmt == "csv":
            frame.to_csv(target, index=False)
        elif fmt == "parquet":
            _write_parquet(frame, target)
        elif fmt == "feather":
            _write_feather(frame, target)
        elif fmt == "sqlite":
            _write_sqlite(frame, target)
        elif fmt == "duckdb":
            _write_duckdb(frame, target)
        elif fmt == "json":
            _write_json(frame, target, lines=False)
        elif fmt == "ndjson":
            _write_json(frame, target, lines=True)
        elif fmt == "npz":
            _write_npz(frame, target)
        else:
            raise ValueError(f"unknown format {fmt}")
    except Exception as exc:
        if fmt in OPTIONAL:
            if target.exists():
                target.unlink()
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "bytes": 0, "rows": 0}
        raise
    return {"ok": True, "error": "", "bytes": target.stat().st_size, "rows": int(len(frame))}


def read_format(fmt: str, path: str | Path) -> pd.DataFrame:
    """Load a frame written by ``write_format``."""
    target = Path(path)
    if fmt == "csv":
        frame = pd.read_csv(target, dtype=str, keep_default_na=False)
    elif fmt == "parquet":
        frame = pd.read_parquet(target)
    elif fmt == "feather":
        frame = pd.read_feather(target)
    elif fmt == "sqlite":
        frame = _read_sqlite(target)
    elif fmt == "duckdb":
        frame = _read_duckdb(target)
    elif fmt == "json":
        frame = _read_json(target, lines=False)
    elif fmt == "ndjson":
        frame = _read_json(target, lines=True)
    elif fmt == "npz":
        frame = _read_npz(target)
    else:
        raise ValueError(f"unknown format {fmt}")
    return as_text_frame(frame)


def _arrow_table(frame: pd.DataFrame):
    """Every column is an Arrow string so identifiers are not inferred as numbers."""
    import pyarrow as pa

    columns = {
        column: pa.array(frame[column].tolist(), type=pa.string())
        for column in frame.columns
    }
    return pa.table(columns)


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    import pyarrow.parquet as pq

    pq.write_table(_arrow_table(frame), path)


def _write_feather(frame: pd.DataFrame, path: Path) -> None:
    import pyarrow.feather as feather

    feather.write_feather(_arrow_table(frame), path)


def _write_sqlite(frame: pd.DataFrame, path: Path) -> None:
    with sqlite3.connect(path) as con:
        columns = list(frame.columns)
        quoted = ", ".join(f'"{column}" TEXT' for column in columns)
        con.execute(f"CREATE TABLE stars ({quoted})")
        placeholders = ", ".join("?" for _ in columns)
        names = ", ".join(f'"{column}"' for column in columns)
        sql = f"INSERT INTO stars ({names}) VALUES ({placeholders})"
        batch: list[tuple] = []
        for row in frame.itertuples(index=False, name=None):
            batch.append(tuple(row))
            if len(batch) >= 50000:
                con.executemany(sql, batch)
                batch.clear()
        if batch:
            con.executemany(sql, batch)
        con.commit()


def _read_sqlite(path: Path) -> pd.DataFrame:
    with sqlite3.connect(path) as con:
        frame = pd.read_sql("SELECT * FROM stars", con)
    return frame


def _write_duckdb(frame: pd.DataFrame, path: Path) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    try:
        columns = list(frame.columns)
        quoted = ", ".join(f'"{column}" VARCHAR' for column in columns)
        con.execute(f"CREATE TABLE stars ({quoted})")
        con.register("incoming", frame)
        names = ", ".join(f'"{column}"' for column in columns)
        con.execute(f"INSERT INTO stars ({names}) SELECT {names} FROM incoming")
    finally:
        con.close()


def _read_duckdb(path: Path) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect(str(path), read_only=True)
    try:
        described = con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'stars' ORDER BY ordinal_position"
        ).fetchall()
        names = [str(row[0]) for row in described]
        casts = ", ".join(f'CAST("{column}" AS VARCHAR) AS "{column}"' for column in names)
        frame = con.execute(f"SELECT {casts} FROM stars").df()
    finally:
        con.close()
    return frame


def _write_json(frame: pd.DataFrame, path: Path, lines: bool) -> None:
    columns = list(frame.columns)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        if not lines:
            handle.write("[\n")
        first = True
        for values in frame.itertuples(index=False, name=None):
            record = {column: value for column, value in zip(columns, values)}
            text = json.dumps(record, ensure_ascii=False)
            if lines:
                handle.write(text + "\n")
            else:
                if not first:
                    handle.write(",\n")
                handle.write(text)
                first = False
        if not lines:
            handle.write("\n]\n")


def _read_json(path: Path, lines: bool) -> pd.DataFrame:
    """Parse JSON ourselves so large ids stay strings."""
    if lines:
        records = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    records.append(json.loads(text))
        return pd.DataFrame(records)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return pd.DataFrame(payload)


def _write_npz(frame: pd.DataFrame, path: Path) -> None:
    import numpy as np

    payload = {column: frame[column].to_numpy() for column in frame.columns}
    payload["__columns"] = np.array(list(frame.columns))
    np.savez_compressed(path, **payload)


def _read_npz(path: Path) -> pd.DataFrame:
    import numpy as np

    with np.load(path, allow_pickle=True) as bundle:
        columns = [str(column) for column in bundle["__columns"].tolist()]
        data = {column: bundle[column] for column in columns}
    return pd.DataFrame(data)
