def rename_column_in_dataframes(dataframes, old, new):
    if not old.strip() or not new.strip():
        raise ValueError("Enter both column names.")
    if old != new and any(old in f.columns and new in f.columns for f in dataframes):
        raise ValueError("The new column name already exists; no files changed.")
    return [frame.rename(columns={old: new}) for frame in dataframes]
