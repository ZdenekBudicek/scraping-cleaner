"""Bounded CSV/ZIP input and portable archive names; all processing stays in memory."""

import csv
import io
from pathlib import PurePosixPath

import pandas as pd

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_BATCH_BYTES = 50 * 1024 * 1024
MAX_FILES = 200


def safe_name(name):
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)
    }
    if (
        not name
        or PurePosixPath(name).is_absolute()
        or any(c in name for c in '\\:<>"|?*')
        or any(ord(c) < 32 for c in name)
        or any(
            p in ("", ".", "..")
            or p.endswith((" ", "."))
            or p.split(".")[0].upper() in reserved
            for p in parts
        )
    ):
        raise ValueError(
            "Use a relative file name without traversal or reserved characters."
        )
    return name


def read_csv_bytes(data):
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("A CSV exceeds the 10 MiB limit.")
    text = data.decode("utf-8-sig")
    rows = csv.reader(io.StringIO(text, newline=""), strict=True)
    header = next(rows, [])
    if (
        not header
        or any(not c.strip() for c in header)
        or len(header) != len(set(header))
    ):
        raise ValueError("CSV needs nonempty, unique column names.")
    if any(len(row) != len(header) for row in rows if row):
        raise ValueError("CSV rows must have the same number of fields as the header.")
    # Preserve IDs, leading zeros, NA-like strings and numeric precision.
    return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
