# KinectNumberWindow.py

import sys
import cv2
import numpy as np
import csv
import os
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QTextEdit, QSpacerItem, QSizePolicy, QLineEdit, QDialog, QMessageBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDateTime
from ultralytics import YOLO

KINECT_V2_AVAILABLE = False
KINECT_IMPORT_ERROR = ""
try:
    if sys.platform != "win32":
        raise ImportError("Kinect v2 (pykinect2) is only supported on Windows.")
    from pykinect2 import PyKinectRuntime, PyKinectV2
    KINECT_V2_AVAILABLE = True
except Exception as e:
    KINECT_IMPORT_ERROR = f"{type(e).__name__}: {e}"


# -----------------------------
# Worker Thread (NO GUI CODE HERE)
# -----------------------------
class Worker(QThread):
    frame_ready = pyqtSignal(QImage)      # Video frame to display
    status_update = pyqtSignal(str)       # Update status bar
    overlay_text = pyqtSignal(str)        # Log message
    test_finished = pyqtSignal(str)       # Final value logged
    error = pyqtSignal(str)

    def __init__(self, name):
        super().__init__()
        self.name = name          # Passed from GUI
        self.running = True
        self.kinect = None
        self.model = None

    def run(self):
        try:
            if not KINECT_V2_AVAILABLE:
                raise RuntimeError(
                    "Kinect v2 is unavailable. "
                    f"Import failed: {KINECT_IMPORT_ERROR}"
                )

            # Initialize Kinect
            self.kinect = PyKinectRuntime.PyKinectRuntime(PyKinectV2.FrameSourceTypes_Color)
            self.overlay_text.emit("🎮 Kinect initialized.")

            # Load YOLO model
            _base = os.path.dirname(os.path.abspath(__file__))
            self.model = YOLO(os.path.join(_base, "models", "best7.pt"))
            self.overlay_text.emit("✅ YOLO model loaded.")
            print("YOLO Model Class Map:", self.model.names)

            # Class map for best7.pt
            class_map = {
                1: '.', 2: '0', 3: '1', 4: '2', 5: '3', 6: '4',
                7: '5', 8: '6', 9: '7', 11: '8', 12: '9'
            }

            self.status_update.emit(f"Detecting for {self.name}...")
            self.overlay_text.emit(f"👤 User: {self.name}")
            self.overlay_text.emit("🔍 Detecting digits...")

            last_value = None
            stable_since = None
            STABLE_DURATION = 1.0

            while self.running:
                if self.kinect.has_new_color_frame():
                    # Get and process frame
                    frame = self.kinect.get_last_color_frame()
                    frame = frame.reshape((1080, 1920, 4)).astype('uint8')
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    frame = cv2.flip(frame, 1)
                    resized = cv2.resize(frame, (640, 360))

                    # Run YOLO
                    results = self.model(resized)

                    # Extract digits (your exact logic)
                    display_value = self.extract_digits(results, class_map, confidence_threshold=0.4, proximity_thresh=60)
                    self.status_update.emit(f"Value: {display_value}")
                    self.overlay_text.emit(f"[{self.timestamp()}] Raw: {display_value}")

                    # Annotate frame
                    annotated = results[0].plot()
                    cv2.putText(annotated, f"Value: {display_value}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Convert to QImage
                    rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                    self.frame_ready.emit(qimg)

                    # Stability check
                    if display_value != "None" and display_value == last_value:
                        if stable_since is None:
                            stable_since = time.time()
                        elif time.time() - stable_since >= STABLE_DURATION:
                            self.log_to_csv(self.name, display_value)
                            self.test_finished.emit(display_value)
                            return
                    else:
                        last_value = display_value
                        stable_since = None

                self.msleep(50)  # Prevent high CPU usage

        except Exception as e:
            self.error.emit(f"Worker crashed: {type(e).__name__}: {e}")
        finally:
            if self.kinect:
                self.kinect.close()

    def stop(self):
        self.running = False
        self.quit()
        self.wait()

    # -----------------------------
    # Your Exact Digit Extraction
    # -----------------------------
    def extract_digits(self, results, class_map, confidence_threshold=0.4, proximity_thresh=60):
        digits = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = box.conf[0]
            if cls_id in class_map and conf >= confidence_threshold:
                x1, x2 = box.xyxy[0][0], box.xyxy[0][2]
                center_x = int((x1 + x2) / 2)
                label = class_map[cls_id]
                digits.append((center_x, label))

        if not digits:
            return "None"

        digits.sort(key=lambda tup: tup[0])

        groups = []
        current_group = [digits[0]]
        for i in range(1, len(digits)):
            if abs(digits[i][0] - digits[i-1][0]) < proximity_thresh:
                current_group.append(digits[i])
            else:
                groups.append(current_group)
                current_group = [digits[i]]
        if current_group:
            groups.append(current_group)

        best_group = max(groups, key=len)
        stitched = ''.join([d[1] for d in best_group])

        if '.' not in stitched and len(stitched) >= 2:
            stitched = stitched[:-1] + '.' + stitched[-1]

        return stitched

    # -----------------------------
    # CSV Logging
    # -----------------------------
    def log_to_csv(self, name, value):
        filename = "digit_log.csv"
        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Date", "Time", "Name", "Value"])
            now = datetime.now()
            writer.writerow([now.date(), now.strftime("%H:%M:%S"), name, value])

    def timestamp(self):
        return QDateTime.currentDateTime().toString("hh:mm:ss")


# -----------------------------
# Main GUI Window
# -----------------------------
class KinectNumberWindow(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Digit Detection Test")
        self.setStyleSheet("background-color: #FFF8F0;")
        self.thread = None

        # --- Top: Instructions ---
        instr_label = QLabel("Instructions")
        instr_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        instr_label.setFont(QFont("Yu Gothic UI", 18, QFont.Bold))
        instr_label.setStyleSheet("color: #472573; margin-top: 10px; margin-bottom: 6px;")

        self.instr_box = QTextEdit()
        self.instr_box.setReadOnly(True)
        self.instr_box.setFont(QFont("Consolas", 11))
        self.instr_box.setStyleSheet("""
            QTextEdit {
                background-color: #F4F6F7;
                border: 2px solid #5B2C6F;
                border-radius: 8px;
                padding: 8px;
                color: #1C2833;
            }
        """)
        self.instr_box.setFixedHeight(240)
        self.instr_box.setHtml(
            "<b>How to use:</b><br>"
            "• Place the device in front of the digit display.<br>"
            "• Press <b>Start</b> to begin detection.<br>"
            "• A stable reading will be logged automatically.<br>"
            "• Press <b>Stop</b> to cancel.<br>"
            "—"
        )

        # --- Middle: Camera Feed ---
        self.video = QLabel("Camera feed will appear here…")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                border: 2px solid #A569BD;
                border-radius: 10px;
            }
        """)
        self.video.setMinimumHeight(480)

        # --- Bottom: Status & Buttons ---
        self.status = QLabel("Status: Not Started")
        self.status.setFont(QFont("Yu Gothic UI", 14))
        self.status.setStyleSheet("color: #5B2C6F; margin: 8px 10px;")

        btnStart = QPushButton("Start")
        btnStop = QPushButton("Stop")
        btnBack = QPushButton("Back")

        for btn in (btnStart, btnStop, btnBack):
            btn.setFont(QFont("Yu Gothic UI", 14))
            btn.setFixedHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #472573;
                    color: #FFFFFF;
                    border-radius: 20px;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background-color: #705593;
                }
            """)

        btnStart.clicked.connect(self.handle_start)
        btnStop.clicked.connect(self.handle_stop)
        btnBack.clicked.connect(self.go_back)

        buttons_row = QHBoxLayout()
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))
        buttons_row.addWidget(btnStart)
        buttons_row.addSpacing(10)
        buttons_row.addWidget(btnStop)
        buttons_row.addSpacing(10)
        buttons_row.addWidget(btnBack)
        buttons_row.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # --- Layout ---
        layout = QVBoxLayout()
        layout.addWidget(instr_label)
        layout.addWidget(self.instr_box)
        layout.addSpacing(8)
        layout.addWidget(self.video)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addLayout(buttons_row)

        root = QHBoxLayout(self)
        root.addLayout(layout, 1)

        self.showFullScreen()

    # -----------------------------
    # Name Input (Runs in GUI Thread)
    # -----------------------------
    def get_user_name(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Enter Name")
        dialog.setGeometry(600, 300, 300, 120)

        layout = QVBoxLayout()
        textbox = QLineEdit()
        textbox.setPlaceholderText("Type your name")
        submit_btn = QPushButton("Start Detection")

        layout.addWidget(textbox)
        layout.addWidget(submit_btn)
        dialog.setLayout(layout)

        submit_btn.clicked.connect(dialog.accept)
        textbox.returnPressed.connect(dialog.accept)

        if dialog.exec_() == QDialog.Accepted:
            name = textbox.text().strip()
            return name if name else None
        return None

    # -----------------------------
    # Button Handlers
    # -----------------------------
    def handle_start(self):
        if self.thread and self.thread.isRunning():
            return
        if not KINECT_V2_AVAILABLE:
            msg = (
                "Kinect v2 test is not available on this system.\n\n"
                f"Details: {KINECT_IMPORT_ERROR}"
            )
            self.status.setText("Status: Kinect v2 unavailable")
            self.append_log(f"❌ {msg}")
            QMessageBox.critical(self, "Kinect v2 Unavailable", msg)
            return

        name = self.get_user_name()
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter a name to start.")
            return

        self.status.setText(f"Status: Starting for {name}...")
        self.append_log("— Detection started —")

        self.thread = Worker(name)
        self.thread.frame_ready.connect(self.update_video)
        self.thread.status_update.connect(self.update_status)
        self.thread.overlay_text.connect(self.append_log)
        self.thread.test_finished.connect(self.on_test_finished)
        self.thread.error.connect(lambda e: self.append_log(f"❌ ERROR: {e}"))
        self.thread.start()

    def handle_stop(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.status.setText("Status: Stopped by user")
            self.append_log("⏹️ Detection stopped manually.")

    def go_back(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        if self.main_window:
            self.main_window.show()
        self.close()

    # -----------------------------
    # Logging & Updates
    # -----------------------------
    def append_log(self, text: str):
        if not text:
            return
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        for line in text.splitlines():
            self.instr_box.append(f"[{timestamp}] {line}")

    def update_status(self, text: str):
        self.status.setText(f"Status: {text}")

    def on_test_finished(self, value: str):
        self.status.setText(f"Status: Completed – {value}")
        self.append_log(f"<b>✅ Logged value: {value}</b>")

    def update_video(self, qimg: QImage):
        if not isinstance(qimg, QImage):
            return
        pix = QPixmap.fromImage(qimg)
        scaled = pix.scaled(
            self.video.width(),
            self.video.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.video.setPixmap(scaled)

    def resizeEvent(self, event):
        if self.video.pixmap():
            pix = self.video.pixmap()
            scaled = pix.scaled(
                self.video.width(),
                self.video.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video.setPixmap(scaled)
        super().resizeEvent(event)


# -----------------------------
# Run standalone
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KinectNumberWindow()
    sys.exit(app.exec_())
