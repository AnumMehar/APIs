# time_up_and_go_test_window.py

import sys, os
import requests   # ✅ NEW
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QDesktopWidget, QTextEdit,
    QSpacerItem, QSizePolicy, QFileDialog
)
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, QDateTime, QProcess


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(BASE_DIR, "tests")
TUG_SCRIPT = os.path.join(TESTS_DIR, "tug_test.py")
TUG_DATA_DIR = os.path.join(BASE_DIR, "TimeUpAndGoData")
# ✅ NEW — FastAPI endpoint
API_BASE = "http://127.0.0.1:8000/physical-frailty"

def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TimeUpAndGoWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.n_id = getattr(self.main_window, "n_id", None)
        self.setWindowTitle("Time Up & Go Test")
        self.setStyleSheet("background-color: #FFF8F0;")

        self.proc: QProcess = None

        # ── Trial tracking ──
        self.current_trial = None  # 1 or 2
        self.time1 = None
        self.time2 = None

        screen = QDesktopWidget().screenGeometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()
        self.resize(int(self.screen_width * (1 / 3)), self.screen_height)
        self.move(0, 0)

        # ---- Title + Instructions ----
        title_label = QLabel("Timed Up and Go Test")
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
            "• Camera faces the chair at ~3.5-4.5m.<br>"
            "• Click on person to LOCK tracking.<br>"
            "• Person sits → stands → walks → turns → walks back → sits.<br>"
            "• Timer starts on stand, auto-stops on sit.<br>"
            "—<br>"
            "<b>Buttons:</b><br>"
            "• <b>Start Test</b> — Real-time TUG with auto-timer (pyk4a + YOLO + MediaPipe).<br>"
            "• <b>View Results</b> — Open saved TUG result from a previous run."
        )

        # ---- Console ----
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

        # ---- Results ----
        results_label = QLabel("Test Results")
        results_label.setFont(QFont("Yu Gothic UI", 11, QFont.Bold))
        results_label.setStyleSheet("color: #472573; margin-top: 6px;")

        self.results_box = QTextEdit()
        self.results_box.setReadOnly(True)
        self.results_box.setFont(QFont("Consolas", 11))
        self.results_box.setFixedHeight(120)
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



        # ---- Status ----
        self.status = QLabel("Status: Ready")
        self.status.setFont(QFont("Yu Gothic UI", 13))
        self.status.setStyleSheet("color: #5B2C6F; margin: 6px 10px;")

        # ---- Buttons ----
        btnRecord1 = QPushButton("🔴  Record 1")
        btnRecord2 = QPushButton("🔴  Record 2")
        btnResults = QPushButton("📊  View Results")
        btnStop    = QPushButton("Stop")
        btnBack    = QPushButton("Back")

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
        for b in (btnRecord1, btnRecord2, btnResults, btnStop, btnBack):
            b.setFont(QFont("Yu Gothic UI", 13, QFont.Bold))
            b.setFixedHeight(44)
            b.setStyleSheet(btn_style)

        btnRecord1.clicked.connect(lambda: self.handle_start(1))
        btnRecord2.clicked.connect(lambda: self.handle_start(2))
        btnResults.clicked.connect(self.handle_view_results)
        btnStop.clicked.connect(self.handle_stop)
        btnBack.clicked.connect(self.go_back)

        buttons_row = QHBoxLayout()
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        buttons_row.addWidget(btnRecord1); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnRecord2); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnResults); buttons_row.addSpacing(6)
        buttons_row.addWidget(btnStop);    buttons_row.addSpacing(6)
        buttons_row.addWidget(btnBack)
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ---- Layout ----
        col = QVBoxLayout()
        col.addWidget(title_label)
        col.addWidget(instr_label)
        col.addWidget(self.instr_box)
        col.addWidget(console_label)
        col.addWidget(self.console, 1)  # stretch
        col.addWidget(results_label)
        col.addWidget(self.results_box)
        col.addWidget(self.status)
        col.addLayout(buttons_row)
        col.setContentsMargins(12, 8, 12, 12)
        col.setSpacing(6)

        root = QHBoxLayout(self)
        root.addLayout(col, 1)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

    # ---- helpers ----
    def _timestamp(self):
        return QDateTime.currentDateTime().toString("hh:mm:ss")

    def _append_html(self, html: str):
        self.console.append(html)

    def _append_log(self, text: str):
        safe = _escape_html(text or "")
        self._append_html(f"[{self._timestamp()}] {safe}")

    def _wire_process_signals(self):
        if not self.proc:
            return
        self.proc.started.connect(lambda: self._append_log("✅ Process started."))
        self.proc.readyReadStandardOutput.connect(self._on_stdout)
        self.proc.readyReadStandardError.connect(self._on_stderr)
        self.proc.errorOccurred.connect(self._on_proc_error)
        self.proc.finished.connect(self._on_proc_finished)

    def _on_stdout(self):
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
        if data.strip():
            self._append_log(data.strip())

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
        self._cleanup_proc()

    def _cleanup_proc(self):
        """Fully clean up the QProcess so the camera is released."""
        if self.proc is not None:
            try:
                self.proc.disconnect()  # disconnect all signals
            except Exception:
                pass
            try:
                if self.proc.state() != QProcess.NotRunning:
                    self.proc.kill()
                    self.proc.waitForFinished(3000)
            except Exception:
                pass
            self.proc.deleteLater()
            self.proc = None

    def _get_output_dir(self):
        os.makedirs(TUG_DATA_DIR, exist_ok=True)
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        return os.path.join(TUG_DATA_DIR, f"tug_{ts}")

    def _launch_script(self, args: list, label: str):
        # Force-cleanup any leftover process from a previous run
        if self.proc is not None:
            if self.proc.state() != QProcess.NotRunning:
                self._append_log("⚠️ A process is already running!")
                return
            # Old process finished but object wasn't deleted — clean up now
            self._cleanup_proc()

        python = sys.executable
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(TESTS_DIR)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wire_process_signals()

        cmd_args = [TUG_SCRIPT] + args
        self._append_log(f"Launching: {label}")
        self.proc.start(python, cmd_args)

        if not self.proc.waitForStarted(10000):
            self.status.setText("Status: Error - Failed to start")
            self._append_log("❌ Failed to start script")
            self._cleanup_proc()
            return

        self.status.setText(f"Status: {label} running…")

    # ---- button handlers ----
    def handle_start(self, trial=1):
        """Start the TUG test — records and times in one go."""
        self.current_trial = trial
        output_dir = self._get_output_dir()
        self._append_log(f"Output (Trial {trial}): {output_dir}")
        self._launch_script(
            ["--output", output_dir],
            f"TUG Test Trial {trial}"
        )

    def handle_view_results(self):
        """Open a previous TUG result folder and display the result JSON."""
        input_dir = QFileDialog.getExistingDirectory(
            self, "Select TUG Result Folder", TUG_DATA_DIR
        )
        if not input_dir:
            self._append_log("Cancelled — no folder selected.")
            return

        result_path = os.path.join(input_dir, "tug_result.json")
        if not os.path.isfile(result_path):
            self._append_log(f"❌ No tug_result.json found in {input_dir}")
            self.status.setText("Status: No result found")
            return

        try:
            import json
            with open(result_path, 'r') as f:
                result = json.load(f)
            lines = ["<b>═══ TUG RESULT ═══</b>"]
            for k, v in result.items():
                lines.append(f"<b>{_escape_html(str(k))}:</b> {_escape_html(str(v))}")
            # ✅ NEW — Extract time value and send to API
            time_value = None

            # Try common keys your tug_test.py may save
            for key in ["time_sec", "total_time", "tug_time", "Time", "time"]:
                if key in result:
                    time_value = result[key]
                    break

            if time_value is not None:
                if self.current_trial == 1:
                    self.time1 = float(time_value)
                elif self.current_trial == 2:
                    self.time2 = float(time_value)

                self._update_trial_results()
                self._send_to_api(float(time_value))
            else:
                self._append_log("⚠️ Could not detect time value in result JSON.")
            self.results_box.setHtml("<br>".join(lines))
            self.status.setText("Status: Result loaded")
        except Exception as e:
            self._append_log(f"❌ Error reading result: {e}")
            self.status.setText("Status: Error")


    def handle_stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("Stopping…")
            self.proc.terminate()
            if not self.proc.waitForFinished(3000):
                self.proc.kill()
                self.proc.waitForFinished(2000)
            self._append_log("✅ Stopped.")
            self.status.setText("Status: Stopped")
            self._cleanup_proc()
        else:
            self.status.setText("Status: Nothing running")
            self._append_log("⚠️ No process to stop")

    def go_back(self):
        self.handle_stop()
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        self.close()

    # ---- slots ----
    def update_status(self, text: str):
        self.status.setText(f"Status: {text}")
        self._append_log(text)

    def on_test_finished(self, time_sec: float):
        self.status.setText(f"Test finished. Time: {time_sec:.2f}s")
        self.results_box.append(f"Test completed — Time: {time_sec:.2f}s")

    def _update_trial_results(self):
        """Update the results box with both trial values."""
        lines = ["<b style='color:#472573;'>Trial Values:</b>"]
        lines.append(f"<br><b>Time 1:</b> {self.time1:.2f} s" if self.time1 is not None else "<br><b>Time 1:</b> —")
        lines.append(f"<br><b>Time 2:</b> {self.time2:.2f} s" if self.time2 is not None else "<br><b>Time 2:</b> —")
        self.results_box.setHtml("".join(lines))

    # ✅ NEW — Send TUG result to API
    def _send_to_api(self, time_value: float):
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
            "test": "time_up_and_go",  # MUST match API map
            "value": float(time_value)
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)

            if response.status_code == 200:
                self._append_log("✅ TUG result saved to database.")
            else:
                self._append_log(
                    f"❌ API Error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self._append_log(f"❌ API Connection Error: {e}")




if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = TimeUpAndGoWindow(None)
    w.showFullScreen()
    sys.exit(app.exec_())
