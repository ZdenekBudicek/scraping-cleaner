from pathlib import PurePosixPath

from csv_io import safe_name


def rename_csv_files(names, new_name):
    new_name = safe_name(new_name.strip())
    if "/" in new_name:
        raise ValueError("Enter a base name, without a folder.")
    stem = new_name[:-4] if new_name.lower().endswith(".csv") else new_name
    safe_name(stem)
    # Retain directories and use stable numbering to prevent overwrites.
    return [
        str(PurePosixPath(n).parent / f"{stem}_{i:03d}.csv")
        for i, n in enumerate(names, 1)
    ]
