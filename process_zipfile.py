"""Read CSV members without extracting an archive to disk."""

import zipfile

from csv_io import MAX_BATCH_BYTES, MAX_FILE_BYTES, MAX_FILES, read_csv_bytes, safe_name


def process_zipfile(uploaded_zipfile):
    with zipfile.ZipFile(uploaded_zipfile) as archive:
        members = [
            item
            for item in archive.infolist()
            if not item.is_dir() and item.filename.lower().endswith(".csv")
        ]
        if not members:
            raise ValueError("The ZIP contains no CSV files.")
        if (
            len(members) > MAX_FILES
            or sum(m.file_size for m in members) > MAX_BATCH_BYTES
        ):
            raise ValueError(
                "A batch may contain at most 200 CSV files and 50 MiB uncompressed."
            )
        names, frames = [], []
        for member in members:
            name = safe_name(member.filename)
            if name.casefold() in {n.casefold() for n in names}:
                raise ValueError("The ZIP contains duplicate file names.")
            if member.file_size > MAX_FILE_BYTES:
                raise ValueError("A CSV exceeds the 10 MiB limit.")
            with archive.open(member) as stream:
                frames.append(read_csv_bytes(stream.read(MAX_FILE_BYTES + 1)))
            names.append(name)
        return frames, names
