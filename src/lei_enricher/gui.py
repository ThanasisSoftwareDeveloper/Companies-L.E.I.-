from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from PySide6 import QtCore, QtWidgets

from .cache import LeiCache
from .core import GleifClient, LeiLookupFallback, LeiResult, is_valid_lei, normalize_lei, chunked
from .io_excel import read_table, write_table


@dataclass
class JobConfig:
    input_path: str
    output_path: str
    sheet: Optional[str]
    lei_col: Optional[str]
    status_col: str
    renewal_col: str
    cache_db: str
    cache_days: int
    gleif_batch_size: int
    gleif_throttle_s: float
    fallback_enabled: bool
    fallback_throttle_s: float


class EnrichWorker(QtCore.QThread):
    progress = QtCore.Signal(int, int)      # done, total
    message = QtCore.Signal(str)
    finished_ok = QtCore.Signal(str)        # output path
    failed = QtCore.Signal(str)

    def __init__(self, cfg: JobConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def run(self) -> None:
        try:
            self._do_work()
        except Exception as e:
            self.failed.emit(str(e))

    def _find_lei_column(self, df: pd.DataFrame) -> str:
        if self.cfg.lei_col and self.cfg.lei_col in df.columns:
            return self.cfg.lei_col

        # common names
        for c in df.columns:
            if str(c).strip().lower() in {"lei", "lei_number", "lei number", "lei code"}:
                return c

        for c in df.columns:
            if "lei" in str(c).strip().lower():
                return c

        raise ValueError("Δεν βρέθηκε στήλη LEI. Δήλωσε 'LEI column name'.")

    def _do_work(self) -> None:
        self.message.emit("Reading input file...")
        df = read_table(self.cfg.input_path, sheet=self.cfg.sheet)
        lei_col_name = self._find_lei_column(df)

        # Ensure output columns exist
        if self.cfg.status_col not in df.columns:
            df[self.cfg.status_col] = None
        if self.cfg.renewal_col not in df.columns:
            df[self.cfg.renewal_col] = None

        # Put output columns immediately to the right of LEI col
        cols = list(df.columns)
        lei_idx = cols.index(lei_col_name)
        cols.remove(self.cfg.status_col)
        cols.remove(self.cfg.renewal_col)
        cols = cols[:lei_idx + 1] + [self.cfg.status_col, self.cfg.renewal_col] + cols[lei_idx + 1:]
        df = df[cols]

        # Normalize and collect unique LEIs
        df[lei_col_name] = df[lei_col_name].map(normalize_lei)
        unique_leis = [x for x in df[lei_col_name].dropna().unique().tolist() if is_valid_lei(x)]
        unique_leis.sort()

        total = len(unique_leis)
        done = 0
        self.progress.emit(done, total)

        cache = LeiCache(self.cfg.cache_db)
        gleif = GleifClient(throttle_s=self.cfg.gleif_throttle_s)
        fallback = LeiLookupFallback(throttle_s=self.cfg.fallback_throttle_s)

        results: dict[str, LeiResult] = {}

        # Cache first
        self.message.emit("Cache lookup...")
        for lei in unique_leis:
            c = cache.get(lei, self.cfg.cache_days)
            if c:
                results[lei] = LeiResult(c.entity_status, c.next_renewal_date, source="cache")

        to_fetch = [lei for lei in unique_leis if lei not in results]

        # GLEIF batching
        self.message.emit("Querying GLEIF API (batched)...")
        for batch in chunked(to_fetch, self.cfg.gleif_batch_size):
            batch_res = gleif.lookup_batch(batch)
            for lei, res in batch_res.items():
                results[lei] = res
                cache.put(lei, res.entity_status, res.next_renewal_date, res.source or "gleif")

            done = min(total, len(results))
            self.progress.emit(done, total)

        # Misses: missing both fields
        misses = []
        for lei in to_fetch:
            r = results.get(lei)
            if not r or (not r.entity_status and not r.next_renewal_date):
                misses.append(lei)

        if self.cfg.fallback_enabled and misses:
            self.message.emit("Fallback to lei-lookup.com for misses (throttled)...")
            for i, lei in enumerate(misses, start=1):
                res = fallback.lookup(lei)
                existing = results.get(lei, LeiResult())
                merged = LeiResult(
                    entity_status=existing.entity_status or res.entity_status,
                    next_renewal_date=existing.next_renewal_date or res.next_renewal_date,
                    source=res.source if (res.entity_status or res.next_renewal_date) else (existing.source or res.source),
                )
                results[lei] = merged
                cache.put(lei, merged.entity_status, merged.next_renewal_date, merged.source or "lei-lookup")

                self.progress.emit(done + i, total)

        # Write results back
        self.message.emit("Writing results...")
        df[self.cfg.status_col] = df[lei_col_name].map(lambda x: results.get(x).entity_status if isinstance(x, str) and x in results else None)
        df[self.cfg.renewal_col] = df[lei_col_name].map(lambda x: results.get(x).next_renewal_date if isinstance(x, str) and x in results else None)

        write_table(df, self.cfg.output_path)
        self.finished_ok.emit(self.cfg.output_path)


class MainWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LEI Enricher")

        self.input_edit = QtWidgets.QLineEdit()
        self.output_edit = QtWidgets.QLineEdit()
        self.lei_col_edit = QtWidgets.QLineEdit()
        self.sheet_edit = QtWidgets.QLineEdit()

        self.fallback_chk = QtWidgets.QCheckBox("Enable fallback (lei-lookup.com) for misses")
        self.fallback_chk.setChecked(False)

        self.run_btn = QtWidgets.QPushButton("Run")
        self.pick_in_btn = QtWidgets.QPushButton("Browse...")
        self.pick_out_btn = QtWidgets.QPushButton("Save as...")

        self.progress = QtWidgets.QProgressBar()
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)

        form = QtWidgets.QFormLayout()
        in_row = QtWidgets.QHBoxLayout()
        in_row.addWidget(self.input_edit)
        in_row.addWidget(self.pick_in_btn)
        form.addRow("Input file (.xlsx/.ods/.csv)", in_row)

        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(self.pick_out_btn)
        form.addRow("Output file (.xlsx)", out_row)

        form.addRow("LEI column name (optional)", self.lei_col_edit)
        form.addRow("Sheet name (optional)", self.sheet_edit)
        form.addRow("", self.fallback_chk)

        v = QtWidgets.QVBoxLayout(self)
        v.addLayout(form)
        v.addWidget(self.run_btn)
        v.addWidget(self.progress)
        v.addWidget(self.log)

        self.pick_in_btn.clicked.connect(self.pick_input)
        self.pick_out_btn.clicked.connect(self.pick_output)
        self.run_btn.clicked.connect(self.start_job)

        self.worker: Optional[EnrichWorker] = None

    def append_log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    def pick_input(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select input file",
            "",
            "Data files (*.xlsx *.xls *.ods *.csv);;All files (*.*)",
        )
        if path:
            self.input_edit.setText(path)
            # default output
            p = Path(path)
            self.output_edit.setText(str(p.with_name(p.stem + "_enriched.xlsx")))

    def pick_output(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Select output file",
            "",
            "Excel (*.xlsx)",
        )
        if path:
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.output_edit.setText(path)

    def start_job(self) -> None:
        in_path = self.input_edit.text().strip()
        out_path = self.output_edit.text().strip()
        if not in_path or not Path(in_path).exists():
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a valid input file.")
            return
        if not out_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select an output file.")
            return

        cfg = JobConfig(
            input_path=in_path,
            output_path=out_path,
            sheet=self.sheet_edit.text().strip() or None,
            lei_col=self.lei_col_edit.text().strip() or None,
            status_col="Entity Status",
            renewal_col="Next Renewal Date",
            cache_db=str(Path.home() / "lei_cache.sqlite"),
            cache_days=14,
            gleif_batch_size=200,
            gleif_throttle_s=0.2,
            fallback_enabled=self.fallback_chk.isChecked(),
            fallback_throttle_s=1.0,
        )

        self.run_btn.setEnabled(False)
        self.progress.setValue(0)
        self.append_log("Starting...")

        self.worker = EnrichWorker(cfg)
        self.worker.message.connect(self.append_log)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished_ok)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, done: int, total: int) -> None:
        if total <= 0:
            self.progress.setValue(0)
            return
        pct = int((done / total) * 100)
        self.progress.setValue(max(0, min(100, pct)))

    def on_finished_ok(self, output_path: str) -> None:
        self.append_log(f"Done. Output: {output_path}")
        self.run_btn.setEnabled(True)
        QtWidgets.QMessageBox.information(self, "Completed", f"Saved: {output_path}")

    def on_failed(self, err: str) -> None:
        self.append_log(f"FAILED: {err}")
        self.run_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Failed", err)
        