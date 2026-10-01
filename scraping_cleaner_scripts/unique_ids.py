def process_single_csv_file(frame):
    if "id" not in frame.columns:
        return {
            "status": "Missing id column",
            "duplicate_ids": [],
            "duplicate_rows": 0,
            "missing_ids": 0,
        }
    missing = frame["id"].isna() | frame["id"].astype(str).str.strip().eq("")
    ids = frame.loc[~missing, "id"]
    counts = ids.value_counts()
    repeated = counts[counts > 1]
    return {
        "status": "Checked",
        "duplicate_ids": repeated.index.tolist(),
        "duplicate_rows": int((repeated - 1).sum()),
        "missing_ids": int(missing.sum()),
    }


def process_csv_files(frames, names):
    return [
        {"file": name, **process_single_csv_file(frame)}
        for name, frame in zip(names, frames, strict=True)
    ]
