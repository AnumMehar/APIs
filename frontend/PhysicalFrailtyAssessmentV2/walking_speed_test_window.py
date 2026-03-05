# walking_speed_test_window.py
import requests   # ✅ NEW
import sys, os, time
import cv2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QDesktopWidget, QTextEdit,
    QSpacerItem, QSizePolicy, QFileDialog
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QDateTime, QProcess, QThread, pyqtSignal, QTimer


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(BASE_DIR, "tests")
WS_SCRIPT = os.path.join(TESTS_DIR, "walking_speed_test.py")
WS_DEPTH_SCRIPT = os.path.join(TESTS_DIR, "video_depth_estimation.py")
WS_DATA_DIR = os.path.join(BASE_DIR, "WalkingSpeedData")
# ✅ NEW — FastAPI endpoint
API_BASE = "http://127.0.0.1:8000/physical-frailty"

# Import analyze_travel_time from local copy
from analyze_travel_time import analyze_travel_time


def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class VideoRecorderThread(QThread):
    """Background thread that records plain RGB video from the Azure Kinect via OpenCV."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, output_path: str, camera_index: int = 1):
        super().__init__()
        self.output_path = output_path
        self.camera_index = camera_index
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            # Try to find the USB webcam (skip index 0 = laptop cam)
            # Try both backends: DSHOW and MSMF
            cap = None
            used_index = -1
            used_backend = ""
            for backend, bname in [(cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF")]:
                for idx in range(1, 5):
                    test = cv2.VideoCapture(idx, backend)
                    if test.isOpened():
                        ret, _ = test.read()
                        if ret:
                            cap = test
                            used_index = idx
                            used_backend = bname
                            break
                    test.release()
                if cap is not None:
                    break

            if cap is None:
                self.error_signal.emit("❌ No USB camera found at indices 1-4. Trying index 0...")
                # Fall back to index 0 (might be the only camera)
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    self.error_signal.emit("❌ No camera available at all")
                    return
                used_index = 0
                used_backend = "default"

            # Request high resolution & FPS
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            cap.set(cv2.CAP_PROP_FPS, 30)

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(self.output_path, fourcc, fps, (w, h))

            # Check if cv2 GUI (imshow) is available (not headless)
            has_gui = True
            try:
                cv2.namedWindow("_test_gui_", cv2.WINDOW_NORMAL)
                cv2.destroyWindow("_test_gui_")
            except cv2.error:
                has_gui = False

            self.log_signal.emit(f"📹 Recording at {w}x{h} @ {fps:.0f} FPS (camera {used_index}, {used_backend})")
            self.log_signal.emit(f"   Saving to: {self.output_path}")
            if has_gui:
                self.log_signal.emit("   Press STOP or Q in preview to end.")
            else:
                self.log_signal.emit("   Press STOP button to end recording.")

            frame_count = 0
            t0 = time.time()

            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break
                writer.write(frame)
                frame_count += 1

                if has_gui:
                    cv2.imshow("Walking Speed - Recording (press Q to stop)", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        break

            elapsed = time.time() - t0
            actual_fps = frame_count / elapsed if elapsed > 0 else 0

            writer.release()
            cap.release()
            if has_gui:
                cv2.destroyAllWindows()

            self.log_signal.emit(f"✅ Saved {frame_count} frames in {elapsed:.1f}s (avg {actual_fps:.1f} FPS)")
            self.finished_signal.emit(self.output_path)

        except Exception as e:
            self.error_signal.emit(f"❌ Recording error: {e}")


class WalkingSpeedWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.n_id = getattr(self.main_window, "n_id", None)  # ✅ NEW
        self.setWindowTitle("Walking Speed Test")
        self.setStyleSheet("background-color: #FFF8F0;")

        self.proc: QProcess = None
        self.recorder_thread: VideoRecorderThread = None

        # ── Trial tracking ──
        self.current_trial = None  # 1 or 2
        self.time1 = None
        self.time2 = None

        # ── Separate depth estimation process (survives navigation) ──
        self.depth_proc: QProcess = None
        self.depth_input_dir: str = None  # folder being processed

        screen = QDesktopWidget().screenGeometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()
        self.resize(int(self.screen_width * (1 / 3)), self.screen_height)
        self.move(0, 0)

        # ---- Instructions (top) ----
        instr_title = QLabel("Walking Speed Test")
        instr_title.setAlignment(Qt.AlignCenter)
        instr_title.setFont(QFont("Yu Gothic UI", 18, QFont.Bold))
        instr_title.setStyleSheet("color: #472573; margin-top: 10px; margin-bottom: 4px;")

        instr_label = QLabel("Instructions")
        instr_label.setAlignment(Qt.AlignCenter)
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
            "• Camera FACING the person (front view).<br>"
            "• Person walks from ~8 m toward camera to ~3 m.<br>"
            "• Click RECORD to start, STOP or press Q to end.<br>"
            "—<br>"
            "<b>Buttons:</b><br>"
            "• <b>Record</b> — Plain RGB video at highest FPS.<br>"
            "• <b>Analyze</b> — Click-to-select person → depth estimation in background → auto-shows results.<br>"
            "• <b>Stop</b> — Stop recording or any running process."
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
        self.results_box.setFixedHeight(140)
        self.results_box.setStyleSheet("""
            QTextEdit {
                background-color: #1C2833;
                border: 2px solid #1E8449;
                border-radius: 8px;
                padding: 8px;
                color: #2ECC71;
            }
        """)
        self.results_box.setPlaceholderText("Results will appear after analysis...")

        # ---- Depth estimation status indicator ----
        self.depth_status = QLabel("⬤ Depth: idle")
        self.depth_status.setFont(QFont("Yu Gothic UI", 11, QFont.Bold))
        self.depth_status.setStyleSheet(
            "color: #808B96; background-color: #F0F0F0; "
            "border-radius: 10px; padding: 4px 12px; margin: 2px 0px;"
        )

        # ---- Status ----
        self.status = QLabel("Status: Ready")
        self.status.setFont(QFont("Yu Gothic UI", 13))
        self.status.setStyleSheet("color: #5B2C6F; margin: 6px 10px;")

        # ---- Buttons ----
        btnRecord1 = QPushButton("🔴  Record 1")
        btnRecord2 = QPushButton("🔴  Record 2")
        btnAnalyze = QPushButton("📊  Analyze")
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
        for b in (btnRecord1, btnRecord2, btnAnalyze, btnStop, btnBack):
            b.setFont(QFont("Yu Gothic UI", 13, QFont.Bold))
            b.setFixedHeight(44)
            b.setStyleSheet(btn_style)

        btnRecord1.clicked.connect(lambda: self.handle_record(1))
        btnRecord2.clicked.connect(lambda: self.handle_record(2))
        btnAnalyze.clicked.connect(self.handle_analyze)
        btnStop.clicked.connect(self.handle_stop)
        btnBack.clicked.connect(self.go_back)

        buttons = QHBoxLayout()
        buttons.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        buttons.addWidget(btnRecord1); buttons.addSpacing(8)
        buttons.addWidget(btnRecord2); buttons.addSpacing(8)
        buttons.addWidget(btnAnalyze); buttons.addSpacing(8)
        buttons.addWidget(btnStop);    buttons.addSpacing(8)
        buttons.addWidget(btnBack)
        buttons.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ---- Layout ----
        left = QVBoxLayout()
        left.addWidget(instr_title)
        left.addWidget(instr_label)
        left.addWidget(self.instr_box)
        left.addWidget(console_label)
        left.addWidget(self.console, 1)  # stretch
        left.addWidget(results_label)
        left.addWidget(self.results_box)
        left.addWidget(self.depth_status)
        left.addWidget(self.status)
        left.addLayout(buttons)
        left.setContentsMargins(12, 8, 12, 12)
        left.setSpacing(6)

        root = QHBoxLayout(self)
        root.addLayout(left, 1)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

    # ════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════

    def _timestamp(self):
        return QDateTime.currentDateTime().toString("hh:mm:ss")

    def _append_html(self, html: str):
        self.console.append(html)

    def _append_log(self, text: str):
        self.console.append(f"[{self._timestamp()}] { _escape_html(text or '') }")

    def _set_depth_status(self, label: str, color: str, bg: str):
        """Update the depth estimation status indicator."""
        self.depth_status.setText(label)
        self.depth_status.setStyleSheet(
            f"color: {color}; background-color: {bg}; "
            "border-radius: 10px; padding: 4px 12px; margin: 2px 0px;"
        )

    # ────── Generic QProcess helpers ──────────────────────────────

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
        self._append_log(f"Process finished. Exit code: {exit_code}, Status: {status_str}")
        self.status.setText("Status: Finished")
        self.proc = None

    def _get_output_dir(self):
        """Generate a timestamped output directory inside WalkingSpeedData."""
        os.makedirs(WS_DATA_DIR, exist_ok=True)
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        return os.path.join(WS_DATA_DIR, f"ws_{ts}")

    def _launch_script(self, args: list, label: str):
        """Launch a Python script with given args."""
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("⚠️ A process is already running!")
            return

        python = sys.executable
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(TESTS_DIR)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wire_process_signals()

        cmd_args = [WS_SCRIPT] + args
        self._append_log(f"Launching: {label}")
        self._append_log(f"  python {' '.join(cmd_args)}")
        self.proc.start(python, cmd_args)

        if not self.proc.waitForStarted(10000):
            self.status.setText("Status: Error - Failed to start")
            self._append_log("❌ Failed to start script within 10s")
            self.proc = None
            return

        self.status.setText(f"Status: {label} running…")

    # ════════════════════════════════════════════════════════════════
    # DEPTH ESTIMATION (independent background QProcess)
    # ════════════════════════════════════════════════════════════════

    def _wire_depth_signals(self):
        """Connect signals for the depth estimation QProcess."""
        if not self.depth_proc:
            return
        self.depth_proc.started.connect(lambda: self._append_log("✅ Depth estimation started."))
        self.depth_proc.readyReadStandardOutput.connect(self._on_depth_stdout)
        self.depth_proc.readyReadStandardError.connect(self._on_depth_stderr)
        self.depth_proc.errorOccurred.connect(self._on_depth_error)
        self.depth_proc.finished.connect(self._on_depth_finished)

    def _on_depth_stdout(self):
        if self.depth_proc is None:
            return
        data = bytes(self.depth_proc.readAllStandardOutput()).decode(errors="ignore")
        if data.strip():
            self._append_log(f"[depth] {data.strip()}")

    def _on_depth_stderr(self):
        if self.depth_proc is None:
            return
        data = bytes(self.depth_proc.readAllStandardError()).decode(errors="ignore")
        if data.strip():
            self._append_log(f"[depth-err] {data.strip()}")

    def _on_depth_error(self, err):
        self._set_depth_status("⬤ Depth: ERROR", "#E74C3C", "#FDEDEC")
        self._append_log(f"❌ Depth estimation error: QProcess code {int(err)}")

    def _on_depth_finished(self, exit_code, exit_status):
        """Called when depth estimation process finishes."""
        status_str = "Normal" if exit_status == QProcess.NormalExit else "Crashed"
        self._append_log(f"Depth estimation finished. Exit code: {exit_code}, Status: {status_str}")

        if exit_code == 0 and exit_status == QProcess.NormalExit:
            self._set_depth_status("⬤ Depth: DONE ✓", "#27AE60", "#EAFAF1")
            # Auto-run analysis on the processed folder
            if self.depth_input_dir:
                self._run_analysis(self.depth_input_dir)
        else:
            self._set_depth_status("⬤ Depth: FAILED", "#E74C3C", "#FDEDEC")

        # Clean up the process object
        try:
            self.depth_proc.deleteLater()
        except Exception:
            pass
        self.depth_proc = None

    def _launch_depth_estimation(self, input_dir: str):
        """Launch depth estimation in a background QProcess that survives navigation."""
        if self.depth_proc is not None and self.depth_proc.state() != QProcess.NotRunning:
            self._append_log("⚠️ Depth estimation is already running!")
            return

        video_path = os.path.join(input_dir, "video.mp4")
        output_csv = os.path.join(input_dir, "depth_data.csv")
        output_video = os.path.join(input_dir, "annotated_video.mp4")

        self.depth_input_dir = input_dir

        python = sys.executable
        self.depth_proc = QProcess(self)
        self.depth_proc.setWorkingDirectory(TESTS_DIR)
        self.depth_proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wire_depth_signals()

        cmd_args = [
            WS_DEPTH_SCRIPT,
            "--video", video_path,
            "--output", output_csv,
            "--output-video", output_video,
            "--interactive",  # click-to-select person
        ]
        self._append_log(f"Launching depth estimation (background)…")
        self._append_log(f"  Folder: {input_dir}")
        self.depth_proc.start(python, cmd_args)

        if not self.depth_proc.waitForStarted(15000):
            self._set_depth_status("⬤ Depth: FAILED", "#E74C3C", "#FDEDEC")
            self._append_log("❌ Failed to start depth estimation")
            self.depth_proc = None
            return

        self._set_depth_status("⬤ Depth: RUNNING…", "#2980B9", "#EBF5FB")
        self.status.setText("Status: Depth estimation running in background…")
        self._append_log("💡 You can navigate to other tests — depth runs in background.")

    # ════════════════════════════════════════════════════════════════
    # ANALYSIS (runs analyze_travel_time on depth_data.csv)
    # ════════════════════════════════════════════════════════════════

    def _run_analysis(self, input_dir: str):
        """Run analyze_travel_time on the given folder and display results."""
        # Check for video_depthazure.csv (legacy) or depth_data.csv
        csv_path = None
        for name in ("video_depthazure.csv", "depth_data.csv"):
            candidate = os.path.join(input_dir, name)
            if os.path.isfile(candidate):
                csv_path = candidate
                break

        if csv_path is None:
            self._append_log(f"❌ No depth CSV found in {input_dir}")
            self.status.setText("Status: Error - no depth CSV")
            return

        self._append_log(f"Analyzing: {csv_path}")
        self.status.setText("Status: Analyzing…")

        try:
            result = analyze_travel_time(csv_path)
        except Exception as e:
            self._append_log(f"❌ Analysis error: {e}")
            self.status.setText("Status: Analysis failed")
            return

        if result is None:
            self._append_log("❌ Analysis failed — person may not have reached 8m or 3m.")
            self.status.setText("Status: Analysis incomplete")
            return

        # Display results
        t = result["travel_time_s"]
        d = result["distance_m"]
        s = result["avg_speed_mps"]

        # Store value to the correct trial
        if self.current_trial == 1:
            self.time1 = t
        elif self.current_trial == 2:
            self.time2 = t

        html_parts = [
            "<b style='font-size:16px; color:#2E7D32;'>📊 WALKING SPEED RESULT</b>",
            "<table style='font-size:14px; margin:6px 0;'>"
            f"<tr><td><b>Travel time (8m → 3m):</b></td>"
            f"<td style='color:#1565C0;'><b>{t:.2f} s</b></td></tr>"
            f"<tr><td><b>Distance covered:</b></td>"
            f"<td>{d:.2f} m</td></tr>"
            f"<tr><td><b>Average walking speed:</b></td>"
            f"<td style='color:#C62828;'><b>{s:.2f} m/s</b></td></tr>"
            "</table>"
        ]

        if result.get("milestones"):
            rows = ""
            for m in result["milestones"]:
                rows += (
                    f"<tr><td>{m['depth_m']}m</td>"
                    f"<td>{m['timestamp_sec']:.2f}s</td>"
                    f"<td>+{m['time_from_8m']:.2f}s</td></tr>"
                )
            html_parts.append(
                "<b>Depth milestones:</b>"
                "<table border='1' cellpadding='4' style='font-size:12px;'>"
                "<tr><th>Depth</th><th>Time</th><th>From 8m</th></tr>"
                f"{rows}</table>"
            )

        # Show both trial values
        html_parts.append("<br><b style='font-size:14px; color:#472573;'>Trial Values:</b>")
        html_parts.append(f"<br><b>Time 1:</b> {self.time1:.2f} s" if self.time1 is not None else "<br><b>Time 1:</b> —")
        html_parts.append(f"<br><b>Time 2:</b> {self.time2:.2f} s" if self.time2 is not None else "<br><b>Time 2:</b> —")

        self.results_box.setHtml("".join(html_parts))
        self.status.setText(f"Status: Done — Speed: {s:.2f} m/s, Time: {t:.2f}s")
        # ✅ NEW — send result to API
        self._send_to_api(t)

    # ✅ NEW — Send walking speed result to API
    def _send_to_api(self, travel_time: float):
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
            "test": "walking_speed",
            "value": float(travel_time)
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)

            if response.status_code == 200:
                self._append_log("✅ Walking Speed saved to database successfully.")
            else:
                self._append_log(
                    f"❌ API Error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self._append_log(f"❌ API Connection Error: {e}")

    # ════════════════════════════════════════════════════════════════
    # BUTTON HANDLERS
    # ════════════════════════════════════════════════════════════════

    def handle_record(self, trial=1):
        """Record plain RGB video from default camera at high FPS."""
        if self.recorder_thread and self.recorder_thread.isRunning():
            self._append_log("⚠️ Already recording!")
            return
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("⚠️ A process is already running!")
            return

        self.current_trial = trial
        output_dir = self._get_output_dir()
        video_path = os.path.join(output_dir, "video.mp4")

        self.recorder_thread = VideoRecorderThread(video_path)
        self.recorder_thread.log_signal.connect(self._append_log)
        self.recorder_thread.error_signal.connect(self._on_record_error)
        self.recorder_thread.finished_signal.connect(self._on_record_done)
        self.recorder_thread.finished.connect(self._on_record_thread_ended)
        self.recorder_thread.start()
        self.status.setText(f"Status: Recording Trial {trial}…")

    def _on_record_error(self, msg: str):
        self._append_log(msg)
        self.status.setText("Status: Error")

    def _on_record_done(self, path: str):
        self._append_log(f"Video saved: {path}")
        self.status.setText("Status: Recording saved")

    def _on_record_thread_ended(self):
        self.recorder_thread = None

    def handle_analyze(self):
        """
        Merged Process + Analyze button.
        - Select a recording folder
        - If depth CSV already exists → show results immediately
        - Otherwise → launch depth estimation in background → auto-analyze on completion
        """
        input_dir = QFileDialog.getExistingDirectory(
            self, "Select Recording Folder", WS_DATA_DIR
        )
        if not input_dir:
            self._append_log("Cancelled — no folder selected.")
            return

        video_path = os.path.join(input_dir, "video.mp4")
        if not os.path.isfile(video_path):
            self._append_log(f"❌ No video.mp4 found in {input_dir}")
            self.status.setText("Status: Error - video.mp4 not found")
            return

        # Check if depth data already exists
        has_csv = any(
            os.path.isfile(os.path.join(input_dir, name))
            for name in ("video_depthazure.csv", "depth_data.csv")
        )

        if has_csv:
            self._append_log("Depth data found — running analysis directly.")
            self._run_analysis(input_dir)
        else:
            # Need to run depth estimation first
            if self.depth_proc is not None and self.depth_proc.state() != QProcess.NotRunning:
                self._append_log("⚠️ Depth estimation already running! Wait for it to finish.")
                return
            self._launch_depth_estimation(input_dir)

    def handle_stop(self):
        stopped_something = False
        # Stop recording thread if active
        if self.recorder_thread and self.recorder_thread.isRunning():
            self._append_log("Stopping recording…")
            self.recorder_thread.stop()
            self.recorder_thread.wait(5000)
            self._append_log("✅ Recording stopped.")
            stopped_something = True
        # Stop generic QProcess if active
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self._append_log("Stopping process…")
            self.proc.terminate()
            if not self.proc.waitForFinished(3000):
                self._append_log("Force killing…")
                self.proc.kill()
                self.proc.waitForFinished(2000)
            self._append_log("✅ Stopped.")
            self.proc = None
            stopped_something = True
        # Stop depth estimation ONLY if user explicitly clicks Stop
        if self.depth_proc and self.depth_proc.state() != QProcess.NotRunning:
            self._append_log("Stopping depth estimation…")
            self.depth_proc.terminate()
            if not self.depth_proc.waitForFinished(3000):
                self.depth_proc.kill()
                self.depth_proc.waitForFinished(2000)
            self._append_log("✅ Depth estimation stopped.")
            self._set_depth_status("⬤ Depth: stopped", "#808B96", "#F0F0F0")
            try:
                self.depth_proc.deleteLater()
            except Exception:
                pass
            self.depth_proc = None
            stopped_something = True

        if stopped_something:
            self.status.setText("Status: Stopped")
        else:
            self.status.setText("Status: Nothing running")

    def go_back(self):
        """Navigate back to main window. Does NOT stop depth estimation."""
        # Only stop recording and generic proc, NOT depth_proc
        if self.recorder_thread and self.recorder_thread.isRunning():
            self._append_log("Stopping recording…")
            self.recorder_thread.stop()
            self.recorder_thread.wait(5000)
        if self.proc and self.proc.state() != QProcess.NotRunning:
            self.proc.terminate()
            if not self.proc.waitForFinished(3000):
                self.proc.kill()
                self.proc.waitForFinished(2000)
            self.proc = None

        # Show notification if depth is still running
        if self.depth_proc and self.depth_proc.state() != QProcess.NotRunning:
            self._append_log("💡 Depth estimation continues in background.")

        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
        self.hide()  # hide instead of close so depth_proc signals still arrive

    # -------- show event: refresh depth status when returning --------
    def showEvent(self, event):
        super().showEvent(event)
        # Refresh depth status indicator when window becomes visible
        if self.depth_proc is not None:
            if self.depth_proc.state() != QProcess.NotRunning:
                self._set_depth_status("⬤ Depth: RUNNING…", "#2980B9", "#EBF5FB")
            else:
                self._set_depth_status("⬤ Depth: DONE ✓", "#27AE60", "#EAFAF1")
        else:
            if self.depth_input_dir and any(
                os.path.isfile(os.path.join(self.depth_input_dir, n))
                for n in ("video_depthazure.csv", "depth_data.csv")
            ):
                self._set_depth_status("⬤ Depth: DONE ✓", "#27AE60", "#EAFAF1")
            else:
                self._set_depth_status("⬤ Depth: idle", "#808B96", "#F0F0F0")

    # -------- slots / compatibility --------
    def update_status(self, text: str):
        self.status.setText(f"Status: {text}")
        self._append_log(text)

    def on_test_finished(self, t: float):
        self.status.setText(f"Test finished. Time: {t:.2f}s")
        self._append_html(f"<b>Test completed — Time: {t:.2f}s</b>")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = WalkingSpeedWindow(None)
    w.showFullScreen()
    sys.exit(app.exec_())
