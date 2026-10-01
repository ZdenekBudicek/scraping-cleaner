def add_column_to_dataframes(dataframes, name, value):
    if not name.strip():
        raise ValueError("Enter a column name.")
    if any(name in frame.columns for frame in dataframes):
        raise ValueError(
            "The column already exists in at least one file; no files changed."
        )
    return [frame.assign(**{name: value}) for frame in dataframes]
