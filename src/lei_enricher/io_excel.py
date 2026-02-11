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
        # If sheet is None, read FIRST sheet as DataFrame (not dict)
        if sheet is None:
            return pd.read_excel(path)
        return pd.read_excel(path, sheet_name=sheet)

    if suffix == ".ods":
        # requires: pip install ".[ods]"
        if sheet is None:
            return pd.read_excel(path, engine="odf")
        return pd.read_excel(path, sheet_name=sheet, engine="odf")

    raise ValueError(f"Unsupported input file type: {suffix}")


def write_table(df: pd.DataFrame, path: str) -> None:
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        df.to_csv(path, index=False)
        return

    if suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
        return

    # safest default: force xlsx output
    if suffix == ".ods":
        raise ValueError("ODS output is not enabled. Please save output as .xlsx")

    raise ValueError(f"Unsupported output file type: {suffix}")

