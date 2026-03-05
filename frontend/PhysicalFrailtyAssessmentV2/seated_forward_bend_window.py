# seated_forward_bend_window.py
"""
Seated Forward Bend Test — PyQt5 Window
=========================================
Launches the Python-based SFB test (seated_forward_bend_test.py)
via QProcess. Matches TUG/FRT window interface.
"""

import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QDesktopWidget, QTextEdit, QHBoxLayout,
    QSpacerItem, QSizePolicy, QLineEdit, QFileDialog
)
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, QDateTime, QProcess
import requests  # ✅ NEW

# ✅ NEW — FastAPI endpoint
API_BASE = "http://127.0.0.1:8000/physical-frailty"


class SeatedForwardBendWindow(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.n_id = getattr(self.main_window, "n_id", None)  # ✅ NEW
        self.setWindowTitle("Seated Forward Bend Test")
        self.setStyleSheet("background-color: #FFF8F0;")

        # Handle to the launched Python process
        self.proc: QProcess = None

        # ── Trial tracking ──
        self.current_trial = None  # 1 or 2
        self.distance1 = None
        self.distance2 = None

        # Screen geometry
        screen = QDesktopWidget().screenGeometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()

        # Left control panel ~ 1/3 of screen
        self.resize(int(self.screen_width * (1 / 3)), self.screen_height)
        self.move(0, 0)

        self._build_ui()

    def _build_ui(self):
        # ----- Title -----
        title_label = QLabel("Seated Forward Bend Test")
        title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        title_label.setFont(QFont("Yu Gothic UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #472573; margin-top: 10px; margin-bottom: 4px;")

        # ----- Instructions -----
        instr_label = QLabel("Instructions")
        instr_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        instr_label.setFont(QFont("Yu Gothic UI", 14, QFont.Bold))
        instr_label.setStyleSheet("color: #472573; margin-top: 6px; margin-bottom: 4px;")

        self.overlay_box = QTextEdit()
        self.overlay_box.setReadOnly(True)
        self.overlay_box.setFont(QFont("Consolas", 11))
        self.overlay_box.setFixedHeight(200)
        self.overlay_box.setStyleSheet("""
            QTextEdit {
                background-color: #F4F6F7;
                border: 2px solid #5B2C6F;
                border-radius: 8px;
                padding: 8px;
                color: #1C2833;
            }
        """)
        self.overlay_box.setPlainText(
            "Setup:\n"
            "  • Camera placed to the SIDE (perpendicular view)\n"
            "  • Person sits on chair, feet flat on floor\n"
            "  • Arms extended forward, palms down\n"
            "\n"
            "Test Flow:\n"
            "  1. Click on the person to LOCK tracking\n"
            "  2. Hold arms still — system calibrates wrist baseline\n"
            "  3. When prompted, BEND FORWARD as far as possible\n"
            "  4. System tracks wrist displacement in cm\n"
            "  5. Return to seated position → test auto-completes\n"
            "\n"
            "Controls:\n"
            "  • LEFT-CLICK = select person\n"
            "  • RIGHT-CLICK = deselect\n"
            "  • Q / ENTER = stop test"
        )

        # ----- Output Directory -----
        dir_label = QLabel("Output Directory:")
        dir_label.setFont(QFont("Yu Gothic UI", 11))
        dir_label.setStyleSheet("color: #472573; margin-top: 4px;")

        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setFont(QFont("Consolas", 10))
        self.dir_input.setPlaceholderText("Enter output folder name...")
        self.dir_input.setText(self._default_output_dir())
        self.dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #A569BD;
                border-radius: 6px;
                padding: 6px 8px;
                color: #1C2833;
            }
        """)

        browse_btn = QPushButton("Browse")
        browse_btn.setFont(QFont("Yu Gothic UI", 10))
        browse_btn.setFixedWidth(70)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #7D3C98;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover { background-color: #9B59B6; }
        """)
        browse_btn.clicked.connect(self._browse_directory)

        dir_row.addWidget(self.dir_input, 1)
        dir_row.addSpacing(6)
        dir_row.addWidget(browse_btn)

        # ----- Console / Log -----
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

        # ----- Results -----
        results_label = QLabel("Test Results")
        results_label.setFont(QFont("Yu Gothic UI", 11, QFont.Bold))
        results_label.setStyleSheet("color: #472573; margin-top: 4px;")

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

        # ----- Status -----
        self.status = QLabel("Status: Ready")
        self.status.setFont(QFont("Yu Gothic UI", 13))
        self.status.setStyleSheet("color: #5B2C6F; margin: 6px 10px;")

        # ----- Buttons -----
        btnRecord1 = QPushButton("▶  Record 1")
        btnRecord2 = QPushButton("▶  Record 2")
        btnStop  = QPushButton("⏹  Stop")
        btnBack  = QPushButton("◀  Back")
        for b in (btnRecord1, btnRecord2, btnStop, btnBack):
            b.setFont(QFont("Yu Gothic UI", 13, QFont.Bold))
            b.setFixedHeight(44)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #472573;
                    color: #FFFFFF;
                    border-radius: 22px;
                    padding: 8px 20px;
                }
                QPushButton:hover {
                    background-color: #705593;
                }
            """)

        btnRecord1.clicked.connect(lambda: self.handle_start(1))
        btnRecord2.clicked.connect(lambda: self.handle_start(2))
        btnStop.clicked.connect(self.handle_stop)
        btnBack.clicked.connect(self.go_back)

        buttons_row = QHBoxLayout()
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        buttons_row.addWidget(btnRecord1)
        buttons_row.addSpacing(10)
        buttons_row.addWidget(btnRecord2)
        buttons_row.addSpacing(10)
        buttons_row.addWidget(btnStop)
        buttons_row.addSpacing(10)
        buttons_row.addWidget(btnBack)
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ----- Layout -----
        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(instr_label)
        layout.addWidget(self.overlay_box)
        layout.addWidget(dir_label)
        layout.addLayout(dir_row)
        layout.addWidget(console_label)
        layout.addWidget(self.console, 1)  # Stretch console
        layout.addWidget(results_label)
        layout.addWidget(self.results_box)
        layout.addWidget(self.status)
        layout.addLayout(buttons_row)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)
        self.setLayout(layout)

    # ---------- Helpers ----------

    def _default_output_dir(self) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        return os.path.join(here, f"sfb_test_{ts}")

    def _browse_directory(self):
        here = os.path.dirname(os.path.abspath(__file__))
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", here)
        if path:
            self.dir_input.setText(path)

    def _timestamp(self):
        return QDateTime.currentDateTime().toString("hh:mm:ss")

    def _append_console(self, text: str):
        for line in (text or "").splitlines():
            stripped = line.strip()
            if stripped:
                self.console.append(f"[{self._timestamp()}] {stripped}")
        # Auto-scroll
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _wire_process_signals(self):
        if not self.proc:
            return
        self.proc.started.connect(
            lambda: self._append_console("✅ Test process started.")
        )
        self.proc.readyReadStandardOutput.connect(self._on_stdout)
        self.proc.readyReadStandardError.connect(self._on_stderr)
        self.proc.errorOccurred.connect(self._on_proc_error)
        self.proc.finished.connect(self._on_proc_finished)

    def _on_stdout(self):
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
        if data.strip():
            self._append_console(data.strip())

    def _on_stderr(self):
        data = bytes(self.proc.readAllStandardError()).decode(errors="ignore")
        if data.strip():
            self._append_console(data.strip())

    def _on_proc_error(self, err):
        error_strings = {
            QProcess.FailedToStart: "FailedToStart — Python or script not found",
            QProcess.Crashed: "Crashed — Process crashed after starting",
            QProcess.Timedout: "Timedout",
            QProcess.WriteError: "WriteError",
            QProcess.ReadError: "ReadError",
            QProcess.UnknownError: "UnknownError",
        }
        error_msg = error_strings.get(err, f"Error code {int(err)}")
        self.status.setText("Status: Error")
        self._append_console(f"❌ Process Error: {error_msg}")

    def _on_proc_finished(self, exit_code, exit_status):
        status_str = "Normal" if exit_status == QProcess.NormalExit else "Crashed"
        self._append_console(f"Process finished. Exit code: {exit_code}, Status: {status_str}")
        self.status.setText("Status: Test finished")
        self.proc = None

        # Try to load and display results
        self._load_results()
        self._update_trial_results()

    def _load_results(self):
        """Load results JSON after test completes."""
        output_dir = self.dir_input.text().strip()
        result_path = os.path.join(output_dir, "sfb_live_result.json")

        if not os.path.exists(result_path):
            return

        try:
            with open(result_path) as f:
                result = json.load(f)

            lines = []
            lines.append("═" * 40)
            lines.append("  SEATED FORWARD BEND — RESULTS")
            lines.append("═" * 40)

            key_map = {
                'right_wrist_max_cm': 'Right Wrist Max',
                'left_wrist_max_cm': 'Left Wrist Max',
                'best_reach_cm': 'Best Reach',
                'risk_level': 'Risk Level',
                'detail': 'Assessment',
            }
            for key, label in key_map.items():
                if key in result:
                    val = result[key]
                    if isinstance(val, float):
                        lines.append(f"  {label:.<25s} {val:.2f} cm")
                    else:
                        lines.append(f"  {label:.<25s} {val}")

            lines.append("═" * 40)
            self.results_box.setText("\n".join(lines))
            # ✅ NEW — Extract best reach and send to API
            best_reach = result.get("best_reach_cm")

            if best_reach is not None:
                if self.current_trial == 1:
                    self.distance1 = float(best_reach)
                elif self.current_trial == 2:
                    self.distance2 = float(best_reach)

                self._update_trial_results()
                self._send_to_api(float(best_reach))
            else:
                self._append_console("⚠️ best_reach_cm not found in result JSON.")
            self.results_box.setStyleSheet("""
                QTextEdit {
                    background-color: #1C2833;
                    border: 2px solid #1E8449;
                    border-radius: 8px;
                    padding: 8px;
                    color: #2ECC71;
                }
            """)
        except Exception as e:
            self._append_console(f"Could not load results: {e}")

    # ---------- Start / Stop / Back ----------

    def handle_start(self, trial=1):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_console("⚠️ Test already running!")
            return

        self.current_trial = trial

        output_dir = self.dir_input.text().strip()
        if not output_dir:
            self._append_console("❌ Please specify an output directory.")
            return

        # Find the test script
        here = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(here, "seated_forward_bend_test.py")
        script_path = os.path.normpath(script_path)

        if not os.path.isfile(script_path):
            self.status.setText("Status: Error — Script not found")
            self._append_console(f"❌ Script not found: {script_path}")
            # List available .py files for debugging
            try:
                py_files = [f for f in os.listdir(here) if f.endswith('.py')]
                self._append_console(f"Available .py files: {py_files}")
            except Exception:
                pass
            return

        # Find Python interpreter
        python_exe = sys.executable
        self._append_console(f"Python: {python_exe}")
        self._append_console(f"Script: {script_path}")
        self._append_console(f"Output: {output_dir}")

        # Prepare process
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(here)
        self._wire_process_signals()

        # Launch: python seated_forward_bend_test.py --output <dir>
        args = [script_path, "--output", output_dir]
        self._append_console(f"Starting: {python_exe} {' '.join(args)}")
        self.proc.start(python_exe, args)

        if not self.proc.waitForStarted(10000):
            error = self.proc.error()
            self.status.setText("Status: Error — Failed to start")
            self._append_console(f"❌ Failed to start process (error={error})")
            self.proc = None
            return

        self.status.setText(f"Status: Test running (Trial {self.current_trial})…")
        self.console.clear()
        self._append_console("✅ Test started — OpenCV window will open")
        self._append_console("Click on the person in the camera feed to begin")

        # Push GUI behind OpenCV window
        try:
            self.lower()
        except Exception:
            pass

    def handle_stop(self):
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_console("Stopping test…")
            self.proc.terminate()
            if not self.proc.waitForFinished(3000):
                self._append_console("Force-killing process…")
                self.proc.kill()
                self.proc.waitForFinished(2000)
            self._append_console("✅ Test stopped.")
            self.status.setText("Status: Test stopped")
            self.proc = None

            # Try to load partial results
            self._load_results()
        else:
            self.status.setText("Status: Not running")
            self._append_console("⚠️ No process to stop")

    def go_back(self):
        self.handle_stop()
        if self.main_window:
            self.main_window.showFullScreen()
            self.main_window.raise_()
            self.main_window.activateWindow()
        self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def _update_trial_results(self):
        """Update the results box with both trial values."""
        lines = ["<b style='color:#472573;'>Trial Values:</b>"]
        lines.append(f"<br><b>Distance 1:</b> {self.distance1:.2f} cm" if self.distance1 is not None else "<br><b>Distance 1:</b> —")
        lines.append(f"<br><b>Distance 2:</b> {self.distance2:.2f} cm" if self.distance2 is not None else "<br><b>Distance 2:</b> —")
        self.results_box.setHtml("".join(lines))

    # ✅ NEW — Send Seated Forward Bend result to backend
    def _send_to_api(self, value: float):
        if not self.n_id:
            self._append_console("❌ n_id not found. Cannot send to API.")
            return

        if self.current_trial == 1:
            endpoint = f"{API_BASE}/round1"
        elif self.current_trial == 2:
            endpoint = f"{API_BASE}/round2"
        else:
            self._append_console("❌ Unknown trial.")
            return

        payload = {
            "n_id": self.n_id,
            "test": "seated_forward_bend",  # MUST match API map
            "value": float(value)
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)

            if response.status_code == 200:
                self._append_console("✅ Result saved to database.")
            else:
                self._append_console(
                    f"❌ API Error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self._append_console(f"❌ API Connection Error: {e}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SeatedForwardBendWindow(None)
    w.showFullScreen()
    sys.exit(app.exec_())