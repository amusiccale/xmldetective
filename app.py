
"""
app.py
Qt (PySide6) desktop front-end for the DOCX forensic analyzer.
Supports batch processing of multiple DOCX files.
"""

import os
import analyzer

from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QStatusBar,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl


class DocxAuditApp(QMainWindow):
    def __init__(self, docx_files=None):
        super().__init__()

        self.setWindowTitle("DOCX Forensic Revision Auditor")
        self.resize(1400, 900)

        self.webview = QWebEngineView()
        self.webview.setHtml(
            """
            <html>
            <body style="font-family:sans-serif; padding:2em;">
              <h2>DOCX Forensic Revision Auditor</h2>
              <p>Open one or more <b>.docx</b> files to analyze.</p>
              <p>When multiple files are provided, they are processed sequentially.</p>
            </body>
            </html>
            """
        )

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        open_button = QPushButton("Open DOCX File(s)")
        open_button.clicked.connect(self.open_files_dialog)

        layout = QVBoxLayout()
        layout.addWidget(open_button)
        layout.addWidget(self.webview)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.status.showMessage("Ready")

        # If files were dropped onto the app at launch, process them
        if docx_files:
            self.process_files(docx_files)

    # ---------------- UI Actions ----------------

    def open_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select DOCX File(s)",
            "",
            "Word Documents (*.docx)",
        )

        if paths:
            self.process_files(paths)

    # ---------------- Core Logic ----------------

    def process_files(self, paths):
        last_html = None
        errors = []

        for path in paths:
            try:
                self.status.showMessage(f"Analyzing {os.path.basename(path)}…")
                analyzer.run(path)

                html_path = os.path.splitext(path)[0] + "-1.html"
                if not os.path.exists(html_path):
                    raise RuntimeError("HTML report not generated")

                last_html = html_path

            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        # Load the last successfully generated report
        if last_html:
            self.webview.load(QUrl.fromLocalFile(os.path.abspath(last_html)))
            self.status.showMessage("Batch analysis complete")

        # Report any errors
        if errors:
            QMessageBox.warning(
                self,
                "Some files could not be analyzed",
                "\n".join(errors),
            )
