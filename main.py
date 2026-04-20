
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6 import QtWebEngineWidgets

from app import DocxAuditApp


def main():
    # Required for Qt WebEngine on macOS
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    # Collect dropped / passed files
    docx_files = [
        arg for arg in sys.argv[1:]
        if arg.lower().endswith(".docx")
    ]

    app = QApplication(sys.argv)

    window = DocxAuditApp(docx_files=docx_files)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
