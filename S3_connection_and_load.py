"""Read-only S3 loading using boto3's default credential chain."""

from urllib.parse import urlsplit

import boto3

from csv_io import MAX_BATCH_BYTES, MAX_FILE_BYTES, MAX_FILES, read_csv_bytes, safe_name


def parse_s3_path(path):
    if path.startswith("s3/"):
        path = "s3://" + path[3:]
    url = urlsplit(path)
    if (
        url.scheme != "s3"
        or not url.netloc
        or url.query
        or url.fragment
        or "@" in url.netloc
    ):
        raise ValueError("Enter s3://bucket/prefix/.")
    prefix = url.path.lstrip("/")
    if not prefix:
        raise ValueError("Provide a prefix; reading a whole bucket is disabled.")
    safe_name(prefix.rstrip("/"))
    return url.netloc, prefix.rstrip("/") + "/"


def load_aws_data(path, client=None):
    bucket, prefix = parse_s3_path(path)
    client = client if client is not None else boto3.client("s3")
    objects = []
    total = 0
    for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key.startswith(prefix) or not key.lower().endswith(".csv"):
                continue
            if item["Size"] > MAX_FILE_BYTES:
                raise ValueError("A CSV exceeds the 10 MiB limit.")
            total += item["Size"]
            objects.append(key)
            if len(objects) > MAX_FILES or total > MAX_BATCH_BYTES:
                raise ValueError(
                    "A batch may contain at most 200 CSV files and 50 MiB."
                )
    if not objects:
        raise ValueError("No CSV files found under that prefix.")
    names = [safe_name(key[len(prefix) :]) for key in sorted(objects)]
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError(
            "S3 file names would collide on a case-insensitive filesystem."
        )
    frames = []
    total = 0
    for key in sorted(objects):
        body = client.get_object(Bucket=bucket, Key=key)["Body"]
        try:
            data = body.read(MAX_FILE_BYTES + 1)
        finally:
            body.close()
        total += len(data)
        if total > MAX_BATCH_BYTES:
            raise ValueError("The downloaded batch exceeds 50 MiB.")
        frames.append(read_csv_bytes(data))
    return frames, names
