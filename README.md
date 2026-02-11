Short repo description

Desktop tool that batch-validates and enriches LEI codes from Excel/LibreOffice spreadsheets using the GLEIF API (with optional fallback), writing Entity Status and Next Renewal Date back into adjacent columns.



Why this app exists

Banks, compliance teams, and analysts often keep large Excel/Calc lists of Legal Entity Identifiers (LEIs). Verifying whether each LEI is ACTIVE and tracking the Next Renewal Date is a repetitive, error-prone task when done manually via web searches or one-by-one API calls.

What it does

This app reads LEIs from a spreadsheet, queries GLEIF first, and (optionally) uses a secondary provider for misses. It then writes the results back to the same file into neighboring columns, so the spreadsheet becomes immediately actionable for KYC/AML checks and renewal monitoring.

How it improves the workflow

Compared to manual lookups or ad-hoc scripts, it provides:

One-click batch processing through a simple GUI

Consistent output columns (status/renewal date + helpful metadata)

Optional fallback for misses to improve coverage

Rate-limit / anti-blocking friendly behavior (delays/retries/backoff) to handle large lists more safely

Typical outcome: hours of repetitive checking become a predictable batch run that updates the spreadsheet automatically.

Short documentation (How to use) — English Quickstart
Quickstart

Prerequisites

Windows 10/11

Python 3.10+ (recommended 3.11+)

Install

Clone the repository

Create & activate a virtual environment

Install the package

Windows (PowerShell)

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .

Run
lei-enricher


(If you don’t have the console script available, try:)

python -m lei_enricher

Use the GUI

Select your Excel/Calc file

Choose the sheet (if prompted) and the column that contains LEIs

Click Start to enrich the file

The app writes results into the next columns (e.g., Entity Status, Next Renewal Date, etc.)

Notes

Enable “fallback for misses” only if you want extra coverage when GLEIF returns no result for some LEIs.

For very large files, use conservative rate settings (slower is safer).
