def files_without_column(frames, names, column):
    if not column.strip():
        raise ValueError("Enter a column name.")
    pairs = [
        (frame, name)
        for frame, name in zip(frames, names, strict=True)
        if column not in frame.columns
    ]
    return [p[0] for p in pairs], [p[1] for p in pairs]
