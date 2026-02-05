from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def read_table(path: str, sheet: Optional[str] = None) -> pd.DataFrame:
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet)

    if suffix == ".ods":
        # requires: pip install ".[ods]"
        return pd.read_excel(path, sheet_name=sheet, engine="odf")

    raise ValueError(f"Unsupported input file type: {suffix}")


def write_table(df: pd.DataFrame, path: str) -> None:
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        df.to_csv(path, index=False)
        return

    # Default to xlsx for best compatibility
    if suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
        return

    if suffix == ".ods":
        # writing ods via pandas can be inconsistent; safest: write xlsx
        raise ValueError("ODS writing is not enabled by default. Use .xlsx output.")

    raise ValueError(f"Unsupported output file type: {suffix}")
