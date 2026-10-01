"""Streamlit entry point for the public Scraping Cleaner edition."""

import csv
import os
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from csv_io import MAX_BATCH_BYTES, read_csv_bytes, safe_name
from download_modify_files import dataframes_as_zip
from process_zipfile import process_zipfile
from S3_connection_and_load import load_aws_data
from scraping_cleaner_scripts.add_column import add_column_to_dataframes
from scraping_cleaner_scripts.check_column_exist import files_without_column
from scraping_cleaner_scripts.drop_columns import delete_column_in_dataframes
from scraping_cleaner_scripts.rename_column import rename_column_in_dataframes
from scraping_cleaner_scripts.rename_files import rename_csv_files
from scraping_cleaner_scripts.unique_ids import process_csv_files

load_dotenv(Path(__file__).with_name(".env"), override=False)
st.set_page_config(page_title="Scraping Cleaner", layout="centered")
st.title("Scraping Cleaner")
st.caption(
    "Check and bulk-edit CSV batches. S3 access is read-only; results download as a ZIP."
)


def set_batch(frames, names):
    st.session_state.batch = (frames, names)
    st.session_state.pop("download", None)
    st.session_state.pop("report", None)


source = st.radio("Source", ["Upload CSV / ZIP", "S3"], horizontal=True)
if st.session_state.get("source") != source:
    st.session_state.source = source
    st.session_state.pop("batch", None)
    st.session_state.pop("download", None)
    st.session_state.pop("report", None)

try:
    if source == "Upload CSV / ZIP":
        upload = st.file_uploader("CSV or ZIP (UTF-8)", type=["csv", "zip"])
        if st.button("Load uploaded file"):
            st.session_state.pop("batch", None)
            st.session_state.pop("download", None)
            st.session_state.pop("report", None)
            if upload is None:
                raise ValueError("Choose a CSV or ZIP file first.")
            if upload.size > MAX_BATCH_BYTES:
                raise ValueError("The upload exceeds 50 MiB.")
            data = upload.getvalue()
            if upload.name.lower().endswith(".zip"):
                set_batch(*process_zipfile(BytesIO(data)))
            else:
                set_batch([read_csv_bytes(data)], [safe_name(upload.name)])
    else:
        path = st.text_input(
            "S3 folder",
            value=os.environ.get("SCRAPING_CLEANER_S3_PATH", ""),
            placeholder="s3://bucket/prefix/",
        )
        if st.button("Load S3 folder"):
            st.session_state.pop("batch", None)
            st.session_state.pop("download", None)
            st.session_state.pop("report", None)
            with st.spinner("Loading CSV files..."):
                set_batch(*load_aws_data(path))
except (BotoCoreError, ClientError):
    st.error(
        "S3 could not be loaded. Check your local AWS credentials, read permissions and folder."
    )
except (
    ValueError,
    UnicodeError,
    csv.Error,
    zipfile.BadZipFile,
    RuntimeError,
    pd.errors.ParserError,
) as error:
    st.error(str(error))

if "batch" not in st.session_state:
    st.info("Load a file or S3 folder to begin.")
    st.stop()

frames, names = st.session_state.batch
st.dataframe(
    pd.DataFrame(
        {
            "File": names,
            "Rows": [len(f) for f in frames],
            "Columns": [len(f.columns) for f in frames],
        }
    ),
    hide_index=True,
)
st.caption(
    "Each action uses the loaded input. It does not modify files on disk or in S3."
)
action = st.selectbox(
    "Action",
    [
        "Check duplicate IDs",
        "Check column exists",
        "Drop column",
        "Rename column",
        "Add column",
        "Rename files",
    ],
)
column = (
    st.text_input("Column name")
    if action in ("Check column exists", "Drop column", "Add column")
    else ""
)
old = st.text_input("Old column name") if action == "Rename column" else ""
new = st.text_input("New column name") if action == "Rename column" else ""
value = st.text_input("Value (may be empty)") if action == "Add column" else ""
base = st.text_input("New file base name") if action == "Rename files" else ""
if st.button("Run action", type="primary"):
    st.session_state.pop("download", None)
    st.session_state.pop("report", None)
    try:
        result, result_names = frames, names
        if action == "Check duplicate IDs":
            st.session_state.report = pd.DataFrame(process_csv_files(frames, names))
            result = []
        elif action == "Check column exists":
            result, result_names = files_without_column(frames, names, column)
            st.session_state.report = pd.DataFrame(
                {"File missing column": result_names}
            )
        elif action == "Drop column":
            result = delete_column_in_dataframes(frames, column)
        elif action == "Rename column":
            result = rename_column_in_dataframes(frames, old, new)
        elif action == "Add column":
            result = add_column_to_dataframes(frames, column, value)
        elif action == "Rename files":
            result_names = rename_csv_files(names, base)
        if result:
            st.session_state.download = (
                dataframes_as_zip(result, result_names),
                action,
            )
    except ValueError as error:
        st.error(str(error))

if "report" in st.session_state:
    st.dataframe(st.session_state.report, hide_index=True)
if "download" in st.session_state:
    payload, description = st.session_state.download
    st.download_button(
        f"Download result: {description}",
        payload,
        "cleaned-files.zip",
        "application/zip",
    )
