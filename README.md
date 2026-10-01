# Scraping Cleaner

A Streamlit tool for checking and bulk-editing batches of scraped CSV files. Upload a CSV or ZIP, or read a folder from S3; download the result as a ZIP.

I originally built this tool in November 2023 during my part-time Python role at BuiltMind. The team used it to review scraper output. This public edition is shared with the company's permission and contains no company datasets, bucket names or credentials.

[Portfolio and browser illustration](https://zdenekbudicek.github.io/#cleaner)

## Run locally

Requires Python 3.12 or newer. Tested on Python 3.12.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements-lock.txt
streamlit run main.py
```

Uploading files needs no AWS account. The app binds to `127.0.0.1` by default. It is a local tool, without authentication for public hosting.

## Workflow

1. Choose **Upload CSV / ZIP** or **S3**, then load the input explicitly.
2. Check duplicate IDs or find files missing a column.
3. Drop, rename or add a column, or rename files.
4. Download the result. Each action starts from the loaded input; upload a downloaded ZIP to chain changes.

Data stays in memory. The tool never updates S3 or overwrites input files. Nested folders are preserved. Renamed files get a numeric suffix to avoid collisions. All CSV cells are read as text, preserving leading zeros, decimal precision and values such as `NA`.

Missing `id` columns and blank IDs are reported separately from duplicates. `duplicate_rows` counts repetitions beyond the first occurrence of each ID. Adding an existing column or renaming onto an existing column fails before changing the batch. Dropping a missing column leaves that file in the output.

## S3 configuration

Use an AWS profile or IAM role, or set credentials in the environment. Alternatively copy `.env.example` to `.env` next to `main.py`, uncomment only the settings you use and fill them in locally. The app loads this ignored file without overriding existing environment variables.

For a profile, set `AWS_PROFILE` to its name. For temporary credentials, set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`. Configure the region through the profile or `AWS_DEFAULT_REGION`.

Enter a folder as `s3://your-bucket/your-prefix/`. The credential needs only `s3:ListBucket` for that prefix and `s3:GetObject` for its objects. No write permission is required. The loader paginates, ignores non-CSV objects and retains each relative key instead of guessing a company-specific project/date structure.

## Limits

- UTF-8, comma-separated CSV with unique, nonempty column headers and consistent row widths.
- Up to 200 CSV files, 10 MiB per CSV and 50 MiB per batch (uncompressed for ZIPs).
- No ZIP extraction to disk. Unsafe paths and colliding member names are rejected.
- No automatic correction of business values, formulas, encodings or CSV dialects.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
```

Regression coverage includes CSV → edit → ZIP round trips, missing columns, filename collisions, ID precision, malformed input, path traversal, S3 pagination and Streamlit session state. S3 tests use botocore Stubber and synthetic data; they make no live AWS requests. A live AWS account was not used for release validation.

## Provenance

The original application and workflow are my 2023 work. The 2026 publication pass used Claude Code and Codex for cleanup and review. It also refactored duplicated UI branches and fixed batch alignment, duplicate output names, session-state handling and input validation. This repository is a fresh public snapshot, not the original internal history.

| File | Purpose |
| --- | --- |
| `main.py` | Streamlit UI and session state |
| `csv_io.py`, `process_zipfile.py` | Bounded input and CSV validation |
| `S3_connection_and_load.py` | Read-only S3 adapter |
| `scraping_cleaner_scripts/` | Checks and bulk transformations |
| `download_modify_files.py` | ZIP export |
| `tests/test_cleaner.py` | Regression and UI tests |

— [Zdeněk Budíček](https://zdenekbudicek.github.io)
