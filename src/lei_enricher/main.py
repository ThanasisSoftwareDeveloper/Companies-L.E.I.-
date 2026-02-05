from __future__ import annotations

import sys
from PySide6 import QtWidgets
from .gui import MainWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.resize(800, 520)
    w.show()
    sys.exit(app.exec())