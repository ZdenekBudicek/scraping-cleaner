import zipfile
from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from streamlit.testing.v1 import AppTest

from csv_io import MAX_FILE_BYTES, read_csv_bytes, safe_name
from download_modify_files import dataframes_as_zip
from process_zipfile import process_zipfile
from S3_connection_and_load import load_aws_data, parse_s3_path
from scraping_cleaner_scripts.add_column import add_column_to_dataframes
from scraping_cleaner_scripts.check_column_exist import files_without_column
from scraping_cleaner_scripts.drop_columns import delete_column_in_dataframes
from scraping_cleaner_scripts.rename_column import rename_column_in_dataframes
from scraping_cleaner_scripts.rename_files import rename_csv_files
from scraping_cleaner_scripts.unique_ids import process_csv_files


def make_zip(entries):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    buffer.seek(0)
    return buffer


def test_upload_edit_download_preserves_every_file_and_exact_values():
    frames, names = process_zipfile(
        make_zip(
            [
                ("alpha/a.csv", "id,price,drop\n001,100.00,x\n001,NA,y\n"),
                ("beta/b.CSV", "id,price\n002,0.010000\n"),
            ]
        )
    )
    result = delete_column_in_dataframes(frames, "drop")
    result = rename_column_in_dataframes(result, "price", "amount")
    result = add_column_to_dataframes(result, "reviewed", "")
    payload = dataframes_as_zip(result, names)
    reopened, returned_names = process_zipfile(BytesIO(payload))
    assert returned_names == names
    assert reopened[0]["id"].tolist() == ["001", "001"]
    assert reopened[0]["amount"].tolist() == ["100.00", "NA"]
    assert reopened[1]["amount"].tolist() == ["0.010000"]
    assert "drop" in frames[0]  # Actions never mutate loaded data.
    assert reopened[1]["reviewed"].tolist() == [""]


def test_drop_does_not_shift_file_names_when_column_is_missing():
    frames = [pd.DataFrame({"id": ["a"]}), pd.DataFrame({"id": ["b"], "extra": ["x"]})]
    payload = dataframes_as_zip(
        delete_column_in_dataframes(frames, "extra"), ["a.csv", "b.csv"]
    )
    result, names = process_zipfile(BytesIO(payload))
    assert names == ["a.csv", "b.csv"]
    assert [f.id.iloc[0] for f in result] == ["a", "b"]


def test_rename_batch_names_are_unique_and_keep_directories():
    names = rename_csv_files(["a.csv", "folder/b.csv"], "result.csv")
    assert names == ["result_001.csv", "folder/result_002.csv"]
    result, returned = process_zipfile(
        BytesIO(
            dataframes_as_zip(
                [pd.DataFrame({"id": [1]}), pd.DataFrame({"id": [2]})], names
            )
        )
    )
    assert returned == names and len(result) == 2


def test_duplicate_checks_distinguish_missing_empty_and_repeated_ids():
    frames = [
        read_csv_bytes(b"id,value\n001,a\n001,b\n001,c\n,blank\n002,d\n"),
        pd.DataFrame({"value": ["x"]}),
    ]
    results = process_csv_files(frames, ["a.csv", "b.csv"])
    assert results[0]["duplicate_ids"] == ["001"]
    assert results[0]["duplicate_rows"] == 2
    assert results[0]["missing_ids"] == 1
    assert results[1]["status"] == "Missing id column"


def test_filter_and_rename_collision_are_atomic():
    frames = [pd.DataFrame({"id": ["1"], "new": ["x"]}), pd.DataFrame({"other": ["y"]})]
    filtered, names = files_without_column(frames, ["a.csv", "b.csv"], "id")
    assert names == ["b.csv"] and filtered[0].equals(frames[1])
    with pytest.raises(ValueError):
        rename_column_in_dataframes(frames, "id", "new")
    with pytest.raises(ValueError):
        add_column_to_dataframes(frames, "new", "overwrite")
    assert frames[0]["new"].tolist() == ["x"]


@pytest.mark.parametrize(
    "name",
    [
        "../a.csv",
        "/a.csv",
        "C:/a.csv",
        "a\\b.csv",
        "a/../b.csv",
        "CON.csv",
        "dir/NUL.csv",
        "a//b.csv",
        "a\x00.csv",
        "a./b.csv",
    ],
)
def test_reject_unsafe_archive_paths(name):
    with pytest.raises(ValueError):
        safe_name(name)


@pytest.mark.parametrize(
    "data", [b"", b"id,id\n1,2", b",x\n1,2", b"id,x\n1,2,3", b"id,x\n1", b"id\n\xff"]
)
def test_reject_malformed_csv(data):
    with pytest.raises((ValueError, UnicodeError)):
        read_csv_bytes(data)


def test_reject_oversized_and_duplicate_archive_members():
    with pytest.raises(ValueError):
        read_csv_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError):
        process_zipfile(make_zip([("a.csv", "id\n1"), ("A.csv", "id\n2")]))
    with pytest.raises(ValueError):
        process_zipfile(make_zip([("note.txt", "no csv")]))
    with pytest.raises(ValueError):
        dataframes_as_zip([pd.DataFrame({"id": [1]})], [])
    with pytest.raises(ValueError):
        delete_column_in_dataframes([pd.DataFrame({"id": [1]})], "id")


@pytest.mark.parametrize(
    "path",
    [
        "https://example.com/path",
        "s3://bucket",
        "s3://bucket/../",
        "s3://user@bucket/a",
    ],
)
def test_invalid_s3_path(path):
    with pytest.raises(ValueError):
        parse_s3_path(path)


def s3_client():
    # Synthetic credentials used only with Stubber; no network requests are sent.
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",  # pragma: allowlist secret (Stubber dummy)
    )


def test_s3_pagination_keeps_two_files_with_same_date_and_ignores_non_csv():
    client = s3_client()
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": True,
                "NextContinuationToken": "next",
                "Contents": [
                    {"Key": "input/a/2023-01-01/one.csv", "Size": 5},
                    {"Key": "input/readme.txt", "Size": 20},
                ],
            },
            {"Bucket": "example-bucket", "Prefix": "input/"},
        )
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": False,
                "Contents": [{"Key": "input/b/2023-01-01/two.csv", "Size": 5}],
            },
            {
                "Bucket": "example-bucket",
                "Prefix": "input/",
                "ContinuationToken": "next",
            },
        )
        for suffix, value in [
            ("a/2023-01-01/one.csv", b"id\n01"),
            ("b/2023-01-01/two.csv", b"id\n02"),
        ]:
            stub.add_response(
                "get_object",
                {"Body": StreamingBody(BytesIO(value), len(value))},
                {"Bucket": "example-bucket", "Key": "input/" + suffix},
            )
        frames, names = load_aws_data("s3://example-bucket/input", client)
        assert names == ["a/2023-01-01/one.csv", "b/2023-01-01/two.csv"]
        assert [f.id.iloc[0] for f in frames] == ["01", "02"]
        stub.assert_no_pending_responses()


def test_empty_s3_prefix_is_reported_without_keyerror():
    client = s3_client()
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            {"IsTruncated": False},
            {"Bucket": "example-bucket", "Prefix": "input/"},
        )
        with pytest.raises(ValueError, match="No CSV"):
            load_aws_data("s3/example-bucket/input/", client)


def test_app_starts_and_reports_empty_upload_without_crashing():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "main.py")).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert "Choose" in app.error[0].value


def test_app_retains_loaded_batch_and_download_across_reruns():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "main.py")).run()
    app.session_state["batch"] = ([read_csv_bytes(b"id,x\n001,a\n")], ["sample.csv"])
    app.run()
    app.selectbox[0].select("Drop column").run()
    app.text_input[0].set_value("x").run()
    next(b for b in app.button if b.label == "Run action").click().run()
    assert not app.exception
    payload = app.session_state["download"][0]
    app.run()
    assert app.session_state["download"][0] == payload
    frames, names = process_zipfile(BytesIO(payload))
    assert names == ["sample.csv"] and list(frames[0].columns) == ["id"]
    app.radio[0].set_value("S3").run()
    assert "batch" not in app.session_state
    assert "download" not in app.session_state
