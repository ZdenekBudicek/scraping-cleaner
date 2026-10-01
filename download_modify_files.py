"""Serialize one result per input file without silent truncation or name collisions."""

import zipfile
from io import BytesIO

from csv_io import safe_name


def dataframes_as_zip(dataframes, projects):
    if len(dataframes) != len(projects):
        raise ValueError("Every dataframe must have exactly one file name.")
    names = [
        safe_name(n if n.lower().endswith(".csv") else n + ".csv") for n in projects
    ]
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError("Output file names must be unique.")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, frame in zip(names, dataframes, strict=True):
            archive.writestr(name, frame.to_csv(index=False).encode("utf-8"))
    return buffer.getvalue()
