def delete_column_in_dataframes(dataframes, name):
    if not name.strip():
        raise ValueError("Enter a column name.")
    if any(list(frame.columns) == [name] for frame in dataframes):
        raise ValueError("Cannot remove the only column in a file.")
    # Keep files that lack the column so data and names never become misaligned.
    return [frame.drop(columns=[name], errors="ignore") for frame in dataframes]
