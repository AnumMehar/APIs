# functional_reach_window.py
import sys, os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QTextEdit, QSpacerItem, QSizePolicy, QFileDialog
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QDateTime, QProcess
import json
import requests

API_BASE = "http://127.0.0.1:8000/api/physical-frailty/"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(BASE_DIR, "tests")
FRT_SCRIPT = os.path.join(TESTS_DIR, "functional_reach_test.py")
FRT_DATA_DIR = os.path.join(BASE_DIR, "FunctionalReachData")


def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class FunctionalReachWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Functional Reach Test")
        self.setStyleSheet("background-color: #FFF8F0;")

        self.proc: QProcess = None

        # ── Trial tracking ──
        self.current_trial = None  # 1 or 2
        self.distance1 = None
        self.distance2 = None
        # ✅ NEW — n_id from logged-in user
        self.n_id = main_window.n_id if main_window and hasattr(main_window, "n_id") else None

        # --- Title + Instructions ---
        title_label = QLabel("Functional Reach Test")
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        title_label.setFont(QFont("Yu Gothic UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #472573; margin-top: 10px; margin-bottom: 4px;")

        instr_label = QLabel("Instructions")
        instr_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        instr_label.setFont(QFont("Yu Gothic UI", 14, QFont.Bold))
        instr_label.setStyleSheet("color: #472573; margin-top: 6px; margin-bottom: 4px;")

        self.instr_box = QTextEdit()
        self.instr_box.setReadOnly(True)
        self.instr_box.setFont(QFont("Consolas", 11))
        self.instr_box.setStyleSheet("""
            QTextEdit {
                background-color: #F4F6F7;
                border: 2px solid #5B2C6F;
                border-radius: 8px;
                padding: 10px;
                color: #1C2833;
            }
        """)
        self.instr_box.setHtml(
            "<b>How to perform:</b><br>"
            "• Camera placed PERPENDICULAR (side view).<br>"
            "• Click on the person to LOCK tracking.<br>"
            "• Press SPACE to start recording — person reaches forward.<br>"
            "• Press ENTER to stop.<br>"
            "—<br>"
            "<b>Buttons:</b><br>"
            "• <b>Record</b> — Capture wrist tracking data (pyk4a + YOLO + MediaPipe).<br>"
            "• <b>Analyze</b> — Compute reach distance from saved CSV.<br>"
            "• <b>Full Pipeline</b> — Record then Analyze in sequence."
        )

        # --- Console ---
        console_label = QLabel("Console Output")
        console_label.setFont(QFont("Yu Gothic UI", 11, QFont.Bold))
        console_label.setStyleSheet("color: #472573; margin-top: 8px;")

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1C2833;
                border: 2px solid #5B2C6F;
                border-radius: 8px;
                padding: 8px;
                color: #AED6F1;
            }
        """)

        # --- Status ---
        self.status = QLabel("Status: Ready")
        self.status.setFont(QFont("Yu Gothic UI", 13))
        self.status.setStyleSheet("color: #5B2C6F; margin: 6px 10px;")

        # --- Results ---
        results_label = QLabel("Test Results")
        results_label.setFont(QFont("Yu Gothic UI", 11, QFont.Bold))
        results_label.setStyleSheet("color: #472573; margin-top: 6px;")

        self.results_box = QTextEdit()
        self.results_box.setReadOnly(True)
        self.results_box.setFont(QFont("Consolas", 11))
        self.results_box.setFixedHeight(100)
        self.results_box.setStyleSheet("""
            QTextEdit {
                background-color: #1C2833;
                border: 2px solid #1E8449;
                border-radius: 8px;
                padding: 8px;
                color: #2ECC71;
            }
        """)
        self.results_box.setPlaceholderText("Results will appear after test completion...")

        # --- Buttons ---
        btnRecord1  = QPushButton("🔴  Record 1")
        btnRecord2  = QPushButton("🔴  Record 2")
        btnAnalyze  = QPushButton("📊  Analyze")
        btnFull     = QPushButton("▶  Full")
        btnStop     = QPushButton("Stop")
        btnBack     = QPushButton("Back")

        btn_style = """
            QPushButton {
                background-color: #472573;
                color: #FFFFFF;
                border-radius: 22px;
                padding: 8px 20px;
                min-width: 135px;
            }
            QPushButton:hover { background-color: #705593; }
        """
        for b in (btnRecord1, btnRecord2, btnAnalyze, btnFull, btnStop, btnBack):
            b.setFont(QFont("Yu Gothic UI", 13, QFont.Bold))
            b.setFixedHeight(44)
            b.setStyleSheet(btn_style)

        btnRecord1.clicked.connect(lambda: self.handle_record(1))
        btnRecord2.clicked.connect(lambda: self.handle_record(2))
        btnAnalyze.clicked.connect(self.handle_analyze)
        btnFull.clicked.connect(self.handle_full)
        btnStop.clicked.connect(self.handle_stop)
        btnBack.clicked.connect(self.go_back)

        buttons_row = QHBoxLayout()
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        buttons_row.addWidget(btnRecord1); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnRecord2); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnAnalyze); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnFull);    buttons_row.addSpacing(6)
        buttons_row.addWidget(btnStop);    buttons_row.addSpacing(6)
        buttons_row.addWidget(btnBack)
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # --- Layout ---
        left = QVBoxLayout()
        left.addWidget(title_label)
        left.addWidget(instr_label)
        left.addWidget(self.instr_box)
        left.addWidget(console_label)
        left.addWidget(self.console, 1)  # stretch
        left.addWidget(results_label)
        left.addWidget(self.results_box)
        left.addWidget(self.status)
        left.addLayout(buttons_row)
        left.setContentsMargins(12, 8, 12, 12)
        left.setSpacing(6)

        root = QHBoxLayout(self)
        root.addLayout(left, 1)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.showFullScreen()

    # --------- Helpers ----------
    def _timestamp(self):
        return QDateTime.currentDateTime().toString("hh:mm:ss")

    def _append_log(self, text: str):
        for line in (text or "").splitlines():
            self.console.append(f"[{self._timestamp()}] {_escape_html(line)}")

    def _wire_process_signals(self):
        if not self.proc:
            return
        self.proc.started.connect(lambda: self._append_log("✅ Process started."))
        self.proc.readyReadStandardOutput.connect(self._on_stdout)
        self.proc.readyReadStandardError.connect(self._on_stderr)
        self.proc.errorOccurred.connect(self._on_proc_error)
        self.proc.finished.connect(self._on_proc_finished)

    # def _on_stdout(self):
    #     data = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
    #     if data.strip():
    #         self._append_log(data.strip())

    def _on_stdout(self):
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
        if not data.strip():
            return

        self._append_log(data.strip())

        # ✅ NEW — Try to extract distance JSON
        try:
            result = json.loads(data)

            distance_value = None

            # Try common keys your test script may output
            for key in ["distance_cm", "reach_distance", "distance", "value"]:
                if key in result:
                    distance_value = float(result[key])
                    break

            if distance_value is not None:

                if self.current_trial == 1:
                    self.distance1 = distance_value
                elif self.current_trial == 2:
                    self.distance2 = distance_value

                self._update_trial_results()

                # ✅ Send THIS trial result (same structure as other GUIs)
                self._send_to_api(distance_value)

            else:
                self._append_log("⚠️ Could not detect distance value in result JSON.")

        except Exception:
            # Output was not JSON — ignore safely
            pass

    def _on_stderr(self):
        data = bytes(self.proc.readAllStandardError()).decode(errors="ignore")
        if data.strip():
            self._append_log(f"[stderr] {data.strip()}")

    def _on_proc_error(self, err):
        self.status.setText("Status: Error")
        self._append_log(f"❌ ERROR: QProcess error code {int(err)}")

    def _on_proc_finished(self, exit_code, exit_status):
        status_str = "Normal" if exit_status == QProcess.NormalExit else "Crashed"
        self._append_log(f"Finished. Exit code: {exit_code}, Status: {status_str}")
        self.status.setText("Status: Finished")
        self.proc = None
        self._update_trial_results()

    def _get_output_dir(self):
        os.makedirs(FRT_DATA_DIR, exist_ok=True)
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        return os.path.join(FRT_DATA_DIR, f"frt_{ts}")

    def _launch_script(self, args: list, label: str):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("⚠️ A process is already running!")
            return

        python = sys.executable
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(TESTS_DIR)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wire_process_signals()

        cmd_args = [FRT_SCRIPT] + args
        self._append_log(f"Launching: {label}")
        self.proc.start(python, cmd_args)

        if not self.proc.waitForStarted(10000):
            self.status.setText("Status: Error - Failed to start")
            self._append_log("❌ Failed to start script")
            self.proc = None
            return

        self.status.setText(f"Status: {label} running…")

    # --------- Button handlers ----------
    def handle_record(self, trial=1):
        self.current_trial = trial
        output_dir = self._get_output_dir()
        self._append_log(f"Output (Trial {trial}): {output_dir}")
        self._launch_script(
            ["record", "--output", output_dir],
            f"Recording Trial {trial}"
        )

    def handle_analyze(self):
        input_dir = QFileDialog.getExistingDirectory(
            self, "Select Recording Folder", FRT_DATA_DIR
        )
        if not input_dir:
            self._append_log("Cancelled — no folder selected.")
            return
        self._append_log(f"Analyzing: {input_dir}")
        self._launch_script(
            ["analyze", "--input", input_dir],
            "Analyzing"
        )

    def handle_full(self):
        output_dir = self._get_output_dir()
        self._append_log(f"Full pipeline → {output_dir}")
        self._launch_script(
            ["full", "--output", output_dir],
            "Full Pipeline"
        )

    def handle_stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("Stopping…")
            self.proc.terminate()
            if not self.proc.waitForFinished(3000):
                self.proc.kill()
                self.proc.waitForFinished(2000)
            self._append_log("✅ Stopped.")
            self.status.setText("Status: Stopped")
            self.proc = None
        else:
            self.status.setText("Status: Nothing running")

    def go_back(self):
        self.handle_stop()
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        self.close()

    # --------- Trial results display ----------
    def _update_trial_results(self):
        """Update the results box with both trial values."""
        lines = ["<b style='color:#472573;'>Trial Values:</b>"]
        lines.append(f"<br><b>Distance 1:</b> {self.distance1:.2f} cm" if self.distance1 is not None else "<br><b>Distance 1:</b> —")
        lines.append(f"<br><b>Distance 2:</b> {self.distance2:.2f} cm" if self.distance2 is not None else "<br><b>Distance 2:</b> —")
        self.results_box.setHtml("".join(lines))

    # ✅ NEW — Send Functional Reach result to backend
    def _send_to_api(self, value: float):
        if not self.n_id:
            self._append_log("❌ n_id not found. Cannot send to API.")
            return

        if self.current_trial == 1:
            endpoint = f"{API_BASE}/round1"
        elif self.current_trial == 2:
            endpoint = f"{API_BASE}/round2"
        else:
            self._append_log("❌ Unknown trial.")
            return

        payload = {
            "n_id": self.n_id,
            "test": "functional_reach",  # MUST match API mapping
            "value": float(value)
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=5)

            if response.status_code in (200, 201):
                self._append_log("✅ Result successfully sent to API.")
            else:
                self._append_log(
                    f"❌ API Error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self._append_log(f"❌ Failed to send to API: {e}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FunctionalReachWindow(None)
    sys.exit(app.exec_())
