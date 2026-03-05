#!/usr/bin/env python3
"""
Standing On One Leg (Eyes Open) — Frailty Assessment System
============================================================
Real-time single-leg stance timer using Azure Kinect DK (pyk4a)
+ YOLO + MediaPipe Pose.

Clinical Protocol (matches C++ SOOLWEO):
    Person stands still → system detects foot stability
    "Raise right foot" → timer starts when ankle Y departs baseline
    Timer stops when foot returns to ground
    If right foot < 60 s → repeat for left foot
    Result = max(right_time, left_time)

How it works:
    1. YOLO detects all persons → click to LOCK onto one
    2. MediaPipe Pose detects ankle Y positions in cropped ROI
    3. Stability baseline from first N stable frames
    4. Real-time state machine:
       SELECTING → CALIBRATING → STABLE → RIGHT_UP → LEFT_PROMPT
       → LEFT_UP → COMPLETED

Usage:
    python standing_one_leg_test.py --output sool_001
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# ── Fix Windows DPI scaling (MUST be before cv2 import) ──────────
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import argparse
import csv
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List
from collections import deque

import cv2
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from pyk4a import PyK4A, Config, ColorResolution, DepthMode, FPS
from ultralytics import YOLO

# Use compatibility wrapper for mediapipe (works with both old and new API)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mp_pose_compat import create_pose_detector


# ═══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PersonBBox:
    """Detected person bounding box (in DISPLAY coordinates)."""
    id: int
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    center_x: int
    center_y: int


# ═══════════════════════════════════════════════════════════════════
# TEST STATES
# ═══════════════════════════════════════════════════════════════════

ST_SELECTING    = "SELECTING"
ST_CALIBRATING  = "CALIBRATING"
ST_STABLE       = "STABLE"
ST_RIGHT_UP     = "RIGHT_UP"
ST_LEFT_PROMPT  = "LEFT_PROMPT"
ST_LEFT_UP      = "LEFT_UP"
ST_COMPLETED    = "COMPLETED"

STATE_COLORS = {
    ST_SELECTING:   (200, 200, 200),
    ST_CALIBRATING: (0, 165, 255),
    ST_STABLE:      (0, 200, 0),
    ST_RIGHT_UP:    (0, 0, 255),
    ST_LEFT_PROMPT: (0, 200, 0),
    ST_LEFT_UP:     (0, 0, 255),
    ST_COMPLETED:   (255, 200, 0),
}

# ── Thresholds ────────────────────────────────────────────────────
STABILITY_FRAMES       = 20     # Frames of stable feet to confirm baseline
STABILITY_THRESHOLD_PX = 18     # Max ankle Y pixel range for "stable" (display-space)
RAISE_THRESHOLD_PX     = 25     # Ankle Y pixel change to count as "raised"
RAISE_HYSTERESIS       = 0.5    # Fraction of threshold for "returned"
MAX_TIME_PER_FOOT_S    = 60.0   # If right foot >= 60s, skip left
LOCK_TOLERANCE         = 120    # Pixel distance for re-matching (tight to avoid jumps)
AUTO_STOP_DELAY_S      = 3.0    # Auto-stop after completion

# Display size (all coordinates in this space)
DISPLAY_W = 1280
DISPLAY_H = 720

# YOLO runs every N-th frame to keep FPS high
YOLO_EVERY_N_FRAMES = 3


# ═══════════════════════════════════════════════════════════════════
# MAIN SOOL TRACKER
# ═══════════════════════════════════════════════════════════════════

class SOOLTracker:
    """
    Standing On One Leg test with click-to-select person locking.
    Same architecture as TUGTracker: pyk4a + YOLO + MediaPipe.
    All detection/display uses a fixed DISPLAY_W x DISPLAY_H image
    so mouse clicks always align with bounding boxes.
    """

    # MediaPipe landmark indices
    MP_LEFT_ANKLE  = 27
    MP_RIGHT_ANKLE = 28
    MP_LEFT_HEEL   = 29
    MP_RIGHT_HEEL  = 30

    def __init__(self, output_dir: str, yolo_model: str = "yolov8n.pt"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.yolo_model_name = yolo_model

        # Devices
        self.k4a: Optional[PyK4A] = None
        self.yolo: Optional[YOLO] = None
        self.pose = None

        # Person selection
        self.detected_persons: List[PersonBBox] = []
        self.selected_person: Optional[PersonBBox] = None
        self.locked_bbox_area: float = 0.0
        self.selection_mode = True
        self.mouse_click_pos: Optional[Tuple[int, int]] = None

        # State machine
        self.state = ST_SELECTING

        # Stability / baseline
        self.left_ankle_y_history: deque = deque(maxlen=STABILITY_FRAMES)
        self.right_ankle_y_history: deque = deque(maxlen=STABILITY_FRAMES)
        self.baseline_left_y: Optional[float] = None
        self.baseline_right_y: Optional[float] = None

        # Current ankle Y (in DISPLAY-space pixels)
        self.cur_left_ankle_y = 0.0
        self.cur_right_ankle_y = 0.0
        self.cur_left_conf = 0.0
        self.cur_right_conf = 0.0

        # Timers
        self.right_start_time = 0.0
        self.right_elapsed = 0.0
        self.left_start_time = 0.0
        self.left_elapsed = 0.0
        self.completed_wall_time: Optional[float] = None

        # Recording
        self.frame_count = 0
        self.start_time: Optional[float] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.csv_rows: list = []

        # Scale factors (set on first frame)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.orig_w = DISPLAY_W
        self.orig_h = DISPLAY_H

    # ──────────────────────────────────────────────────────────────
    # INITIALIZATION
    # ──────────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        try:
            print("[INIT] Starting Azure Kinect...")
            config = Config(
                color_resolution=ColorResolution.RES_720P,
                depth_mode=DepthMode.NFOV_UNBINNED,
                camera_fps=FPS.FPS_30,
                synchronized_images_only=True,
            )
            self.k4a = PyK4A(config)
            self.k4a.start()
            print("  ✓ Azure Kinect started (720p, NFOV, 30fps)")

            print(f"[INIT] Loading YOLO ({self.yolo_model_name})...")
            self.yolo = YOLO(self.yolo_model_name)
            print("  ✓ YOLO loaded")

            print("[INIT] Initializing MediaPipe Pose...")
            self.pose = create_pose_detector(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            print("  ✓ MediaPipe Pose ready")
            return True

        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ──────────────────────────────────────────────────────────────
    # MOUSE
    # ──────────────────────────────────────────────────────────────

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_click_pos = (x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._reset_selection()

    # ──────────────────────────────────────────────────────────────
    # PERSON DETECTION (on display-sized image)
    # ──────────────────────────────────────────────────────────────

    def _detect_persons(self, display_img: np.ndarray) -> List[PersonBBox]:
        """Run YOLO on the display-sized image. BBoxes in display coords."""
        results = self.yolo(display_img, classes=[0], conf=0.3, verbose=False)
        persons = []
        for result in results:
            for i, box in enumerate(result.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                persons.append(PersonBBox(
                    id=i, x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=conf,
                    center_x=(x1 + x2) // 2,
                    center_y=(y1 + y2) // 2,
                ))
        return persons

    def _check_click(self, persons: List[PersonBBox]) -> Optional[int]:
        """Check if mouse click is inside any person bbox."""
        if self.mouse_click_pos is None:
            return None
        cx, cy = self.mouse_click_pos
        self.mouse_click_pos = None
        for person in persons:
            if (person.x1 <= cx <= person.x2 and
                    person.y1 <= cy <= person.y2):
                return person.id
        return None

    def _find_by_proximity(self, persons: List[PersonBBox]) -> Optional[PersonBBox]:
        """Find the person closest to our locked selection.
        Rejects candidates whose bbox area differs too much."""
        if self.selected_person is None:
            return None
        best, min_dist = None, float('inf')
        for p in persons:
            dist = np.sqrt(
                (p.center_x - self.selected_person.center_x) ** 2 +
                (p.center_y - self.selected_person.center_y) ** 2
            )
            if dist >= LOCK_TOLERANCE:
                continue
            if self.locked_bbox_area > 0:
                p_area = (p.x2 - p.x1) * (p.y2 - p.y1)
                area_ratio = p_area / self.locked_bbox_area if self.locked_bbox_area > 0 else 1.0
                if area_ratio < 0.4 or area_ratio > 2.5:
                    continue
            if dist < min_dist:
                min_dist = dist
                best = p
        return best

    def _reset_selection(self):
        self.selected_person = None
        self.locked_bbox_area = 0.0
        self.selection_mode = True
        self.state = ST_SELECTING
        self.left_ankle_y_history.clear()
        self.right_ankle_y_history.clear()
        self.baseline_left_y = None
        self.baseline_right_y = None
        self.right_elapsed = 0.0
        self.left_elapsed = 0.0
        self.completed_wall_time = None
        print("[SOOL] Person deselected — state reset")

    # ──────────────────────────────────────────────────────────────
    # ANKLE DETECTION (MediaPipe on cropped display image)
    # ──────────────────────────────────────────────────────────────

    def _detect_ankles(self, display_img: np.ndarray,
                       bbox: PersonBBox) -> Tuple[float, float, float, float,
                                                   Optional[Tuple[int, int]],
                                                   Optional[Tuple[int, int]]]:
        """
        Detect ankle Y positions via MediaPipe Pose.
        Returns: (left_y, right_y, left_conf, right_conf,
                  left_pixel, right_pixel)

        IMPORTANT: Y values are in DISPLAY space (not crop-relative)
        so they are stable across frames even if the YOLO bbox shifts.
        """
        h, w = display_img.shape[:2]
        pad = 20
        x1 = max(0, bbox.x1 - pad)
        y1 = max(0, bbox.y1 - pad)
        x2 = min(w, bbox.x2 + pad)
        y2 = min(h, bbox.y2 + pad)

        cropped = display_img[y1:y2, x1:x2]
        if cropped.size == 0:
            return 0.0, 0.0, 0.0, 0.0, None, None

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return 0.0, 0.0, 0.0, 0.0, None, None

        lm = results.pose_landmarks.landmark
        crop_h, crop_w = cropped.shape[:2]

        la = lm[self.MP_LEFT_ANKLE]
        ra = lm[self.MP_RIGHT_ANKLE]

        # DISPLAY-space Y (crop-relative + offset)
        left_y = la.y * crop_h + y1
        right_y = ra.y * crop_h + y1

        # Display-space pixel coords for drawing
        left_px = (int(la.x * crop_w) + x1, int(left_y))
        right_px = (int(ra.x * crop_w) + x1, int(right_y))

        return left_y, right_y, la.visibility, ra.visibility, left_px, right_px

    # ──────────────────────────────────────────────────────────────
    # DRAWING
    # ──────────────────────────────────────────────────────────────

    def _draw_selection_mode(self, image: np.ndarray,
                              persons: List[PersonBBox]) -> np.ndarray:
        h, w = image.shape[:2]

        # Dim
        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)

        # Banner
        cv2.rectangle(image, (0, 0), (w, 60), (40, 40, 40), -1)
        cv2.putText(image, "STANDING ON ONE LEG - Click on the person to lock",
                    (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, f"Detected {len(persons)} person(s) | Q=quit",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (200, 200, 200), 1, cv2.LINE_AA)

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
                  (255, 255, 0), (255, 0, 255), (0, 255, 255)]

        for i, p in enumerate(persons):
            c = colors[i % len(colors)]
            cv2.rectangle(image, (p.x1, p.y1), (p.x2, p.y2), c, 3)

            label = f"Person {i + 1}"
            lw_s, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(image, (p.x1, p.y1 - 28),
                          (p.x1 + lw_s + 10, p.y1), c, -1)
            cv2.putText(image, label, (p.x1 + 5, p.y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cx, cy = p.center_x, p.center_y
            cv2.putText(image, "CLICK", (cx - 30, cy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)
            cv2.putText(image, "TO SELECT", (cx - 50, cy + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)

        if not persons:
            cv2.putText(image, "No persons detected - enter the frame",
                        (w // 2 - 200, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
        return image

    def _draw_tracking_hud(self, image: np.ndarray,
                            persons: List[PersonBBox],
                            left_px: Optional[Tuple[int, int]],
                            right_px: Optional[Tuple[int, int]]) -> np.ndarray:
        h, w = image.shape[:2]
        color = STATE_COLORS.get(self.state, (200, 200, 200))

        # Draw bboxes
        for p in persons:
            is_sel = (self.selected_person and
                      abs(p.center_x - self.selected_person.center_x) < 50 and
                      abs(p.center_y - self.selected_person.center_y) < 50)
            if is_sel:
                cv2.rectangle(image, (p.x1, p.y1), (p.x2, p.y2), (0, 255, 0), 3)
                cv2.putText(image, "LOCKED", (p.x1, p.y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.rectangle(image, (p.x1, p.y1), (p.x2, p.y2), (80, 80, 80), 1)

        # Draw ankle markers
        if left_px and self.cur_left_conf > 0.3:
            cv2.circle(image, left_px, 12, (255, 0, 0), -1)
            cv2.circle(image, left_px, 14, (255, 255, 255), 2)
            cv2.putText(image, "L", (left_px[0] + 16, left_px[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 0), 2)
        if right_px and self.cur_right_conf > 0.3:
            cv2.circle(image, right_px, 12, (0, 0, 255), -1)
            cv2.circle(image, right_px, 14, (255, 255, 255), 2)
            cv2.putText(image, "R", (right_px[0] + 16, right_px[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        # State banner
        labels = {
            ST_SELECTING:   "SELECTING - Click on person",
            ST_CALIBRATING: f"CALIBRATING - Stand still ({len(self.left_ankle_y_history)}/{STABILITY_FRAMES})",
            ST_STABLE:      "STABLE - Raise your RIGHT foot",
            ST_RIGHT_UP:    "RIGHT FOOT UP - Timer running",
            ST_LEFT_PROMPT: f"Right: {self.right_elapsed:.2f}s - Now raise LEFT foot",
            ST_LEFT_UP:     "LEFT FOOT UP - Timer running",
            ST_COMPLETED:   "TEST COMPLETED!",
        }
        banner = labels.get(self.state, self.state)

        # Show jitter info when calibration is full but not passing
        if (self.state == ST_CALIBRATING and
                len(self.left_ankle_y_history) >= STABILITY_FRAMES):
            l_range = max(self.left_ankle_y_history) - min(self.left_ankle_y_history)
            r_range = max(self.right_ankle_y_history) - min(self.right_ankle_y_history)
            banner = f"CALIBRATING - Hold still! (jitter: L={l_range:.0f} R={r_range:.0f} need <{STABILITY_THRESHOLD_PX})"

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        cv2.putText(image, banner, (15, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2, cv2.LINE_AA)

        # Big timer when foot is in air
        if self.state == ST_RIGHT_UP:
            cv2.putText(image, f"{self.right_elapsed:.1f}s",
                        (w - 200, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.putText(image, f"{self.right_elapsed:.1f}s",
                        (w // 2 - 80, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 255), 4, cv2.LINE_AA)

        elif self.state == ST_LEFT_UP:
            cv2.putText(image, f"{self.left_elapsed:.1f}s",
                        (w - 200, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.putText(image, f"{self.left_elapsed:.1f}s",
                        (w // 2 - 80, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 255), 4, cv2.LINE_AA)

        # Info panel
        y_off = 80
        if self.baseline_left_y is not None:
            l_diff = abs(self.cur_left_ankle_y - self.baseline_left_y)
            r_diff = abs(self.cur_right_ankle_y - self.baseline_right_y) if self.baseline_right_y else 0
            cv2.putText(image, f"L ankle dY: {l_diff:.1f}px  R ankle dY: {r_diff:.1f}px",
                        (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (200, 200, 200), 1)
            y_off += 25
            cv2.putText(image, f"Threshold: {RAISE_THRESHOLD_PX}px",
                        (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (160, 160, 160), 1)

        # Results panel
        if self.state in (ST_RIGHT_UP, ST_LEFT_PROMPT, ST_LEFT_UP, ST_COMPLETED):
            panel_y = h - 120
            overlay2 = image.copy()
            cv2.rectangle(overlay2, (10, panel_y), (350, h - 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay2, 0.7, image, 0.3, 0, image)

            cv2.putText(image, "RESULTS", (20, panel_y + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            r_color = (0, 255, 0) if self.right_elapsed >= MAX_TIME_PER_FOOT_S else (0, 200, 200)
            cv2.putText(image, f"Right foot: {self.right_elapsed:.2f}s",
                        (20, panel_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, r_color, 2)

            if self.left_elapsed > 0 or self.state in (ST_LEFT_UP, ST_COMPLETED):
                l_color = (0, 255, 0) if self.left_elapsed >= MAX_TIME_PER_FOOT_S else (0, 200, 200)
                cv2.putText(image, f"Left foot:  {self.left_elapsed:.2f}s",
                            (20, panel_y + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.55, l_color, 2)

            if self.state == ST_COMPLETED:
                best = max(self.right_elapsed, self.left_elapsed)
                cv2.putText(image, f"Best: {best:.2f}s",
                            (20, panel_y + 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        # Bottom
        cv2.putText(image, "RIGHT-CLICK: deselect | Q / ENTER: stop & save",
                    (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (160, 160, 160), 1)
        return image

    # ──────────────────────────────────────────────────────────────
    # CSV
    # ──────────────────────────────────────────────────────────────

    CSV_HEADER = [
        'frame_number', 'timestamp_sec', 'state',
        'left_ankle_y_px', 'left_ankle_conf',
        'right_ankle_y_px', 'right_ankle_conf',
        'left_disp_px', 'right_disp_px',
        'right_elapsed_s', 'left_elapsed_s',
    ]

    def _log_row(self, timestamp: float):
        l_disp = abs(self.cur_left_ankle_y - self.baseline_left_y) if self.baseline_left_y else 0
        r_disp = abs(self.cur_right_ankle_y - self.baseline_right_y) if self.baseline_right_y else 0
        self.csv_rows.append({
            'frame_number': self.frame_count,
            'timestamp_sec': round(timestamp, 4),
            'state': self.state,
            'left_ankle_y_px': round(self.cur_left_ankle_y, 1),
            'left_ankle_conf': round(self.cur_left_conf, 3),
            'right_ankle_y_px': round(self.cur_right_ankle_y, 1),
            'right_ankle_conf': round(self.cur_right_conf, 3),
            'left_disp_px': round(l_disp, 1),
            'right_disp_px': round(r_disp, 1),
            'right_elapsed_s': round(self.right_elapsed, 3),
            'left_elapsed_s': round(self.left_elapsed, 3),
        })

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self) -> Optional[dict]:
        if not self.initialize():
            return None

        self.start_time = time.time()

        print("\n" + "=" * 60)
        print("STANDING ON ONE LEG TEST (EYES OPEN)")
        print("=" * 60)
        print("Setup: Person stands facing camera, ~2-3 m away")
        print("")
        print("  1. Click on the person to LOCK")
        print("  2. Stand still — system calibrates ankle baseline")
        print("  3. When prompted, raise RIGHT foot")
        print("  4. Hold as long as possible, then put foot down")
        print("  5. If < 60s, repeat with LEFT foot")
        print("  6. Result auto-saves after completion")
        print("")
        print("  RIGHT-CLICK  = deselect person")
        print("  Q / ENTER    = quit manually")
        print("=" * 60 + "\n")

        window = "Standing On One Leg Test"
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, self._mouse_callback)

        video_path = str(self.output_dir / "video.mp4")
        csv_path = str(self.output_dir / "ankle_data.csv")
        result_path = str(self.output_dir / "sool_live_result.json")

        fps_start = time.time()
        fps_count = 0
        current_fps = 0
        last_persons: List[PersonBBox] = []

        capture_errors = 0
        try:
            while True:
                try:
                    capture = self.k4a.get_capture()
                except Exception:
                    capture_errors += 1
                    if capture_errors > 20:
                        print(f"[ERROR] Too many capture errors ({capture_errors}), stopping.")
                        break
                    time.sleep(0.05)
                    continue

                if capture.color is None:
                    continue
                capture_errors = 0

                self.frame_count += 1
                fps_count += 1
                now = time.time()
                if now - fps_start >= 1.0:
                    current_fps = fps_count
                    fps_count = 0
                    fps_start = now

                # ── Get images ────────────────────────────────────
                color_bgr = capture.color[:, :, :3]
                self.orig_h, self.orig_w = color_bgr.shape[:2]
                self.scale_x = self.orig_w / DISPLAY_W
                self.scale_y = self.orig_h / DISPLAY_H

                # Resize to fixed display size (mouse coords match YOLO)
                display = cv2.resize(color_bgr, (DISPLAY_W, DISPLAY_H))
                timestamp = now - self.start_time

                # ── YOLO every N frames ───────────────────────────
                if self.frame_count % YOLO_EVERY_N_FRAMES == 1 or not last_persons:
                    persons = self._detect_persons(display)
                    last_persons = persons
                else:
                    persons = last_persons

                left_px = None
                right_px = None

                if self.selection_mode:
                    # ── SELECTION MODE ─────────────────────────────
                    display = self._draw_selection_mode(display, persons)

                    clicked_id = self._check_click(persons)
                    if clicked_id is not None and clicked_id < len(persons):
                        self.selected_person = persons[clicked_id]
                        p = self.selected_person
                        self.locked_bbox_area = float((p.x2 - p.x1) * (p.y2 - p.y1))
                        self.selection_mode = False
                        self.state = ST_CALIBRATING
                        self.left_ankle_y_history.clear()
                        self.right_ankle_y_history.clear()
                        self.baseline_left_y = None
                        self.baseline_right_y = None
                        print(f"[SOOL] Locked Person {clicked_id + 1} (area={self.locked_bbox_area:.0f})")
                        print("[SOOL] Calibrating — stand still...")
                    else:
                        self.mouse_click_pos = None

                else:
                    # ── TRACKING MODE ──────────────────────────────
                    matched = self._find_by_proximity(persons)

                    if matched:
                        self.selected_person = matched
                        # Gradually update locked area (slow adaptation)
                        p_area = float((matched.x2 - matched.x1) * (matched.y2 - matched.y1))
                        self.locked_bbox_area = 0.9 * self.locked_bbox_area + 0.1 * p_area

                        # Detect ankles
                        (self.cur_left_ankle_y, self.cur_right_ankle_y,
                         self.cur_left_conf, self.cur_right_conf,
                         left_px, right_px) = self._detect_ankles(display, matched)

                        has_ankles = (self.cur_left_conf > 0.3 and
                                      self.cur_right_conf > 0.3)

                        # ── STATE MACHINE ─────────────────────────
                        if self.state == ST_CALIBRATING:
                            if has_ankles:
                                self.left_ankle_y_history.append(self.cur_left_ankle_y)
                                self.right_ankle_y_history.append(self.cur_right_ankle_y)

                            if (len(self.left_ankle_y_history) >= STABILITY_FRAMES and
                                    len(self.right_ankle_y_history) >= STABILITY_FRAMES):
                                l_range = max(self.left_ankle_y_history) - min(self.left_ankle_y_history)
                                r_range = max(self.right_ankle_y_history) - min(self.right_ankle_y_history)

                                if l_range < STABILITY_THRESHOLD_PX and r_range < STABILITY_THRESHOLD_PX:
                                    self.baseline_left_y = float(np.mean(list(self.left_ankle_y_history)))
                                    self.baseline_right_y = float(np.mean(list(self.right_ankle_y_history)))
                                    self.state = ST_STABLE

                                    # Start recording video
                                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                                    self.video_writer = cv2.VideoWriter(
                                        video_path, fourcc, 30,
                                        (self.orig_w, self.orig_h),
                                    )
                                    print(f"[SOOL] Feet stable! Baseline L={self.baseline_left_y:.1f} R={self.baseline_right_y:.1f}")
                                    print("[SOOL] Please raise your RIGHT foot")
                                else:
                                    if self.frame_count % 30 == 0:
                                        print(f"[SOOL] Calibrating... L_range={l_range:.1f}px R_range={r_range:.1f}px (need <{STABILITY_THRESHOLD_PX})")

                        elif self.state == ST_STABLE:
                            # Waiting for right foot raise
                            if has_ankles and self.baseline_right_y is not None:
                                r_diff = abs(self.cur_right_ankle_y - self.baseline_right_y)
                                if r_diff > RAISE_THRESHOLD_PX:
                                    self.state = ST_RIGHT_UP
                                    self.right_start_time = time.time()
                                    print(f"[SOOL] Right foot raised! (dY={r_diff:.1f}px) Timer started")

                        elif self.state == ST_RIGHT_UP:
                            self.right_elapsed = time.time() - self.right_start_time

                            if has_ankles and self.baseline_right_y is not None:
                                r_diff = abs(self.cur_right_ankle_y - self.baseline_right_y)
                                if r_diff < RAISE_THRESHOLD_PX * RAISE_HYSTERESIS:
                                    print(f"[SOOL] Right foot down! Time: {self.right_elapsed:.2f}s")

                                    if self.right_elapsed >= MAX_TIME_PER_FOOT_S:
                                        self.state = ST_COMPLETED
                                        self.completed_wall_time = time.time()
                                        print(f"[SOOL] Right foot >= {MAX_TIME_PER_FOOT_S:.0f}s — Test Complete!")
                                    else:
                                        self.state = ST_LEFT_PROMPT
                                        print(f"[SOOL] Right foot {self.right_elapsed:.2f}s < {MAX_TIME_PER_FOOT_S:.0f}s")
                                        print("[SOOL] Please raise your LEFT foot")

                        elif self.state == ST_LEFT_PROMPT:
                            if has_ankles and self.baseline_left_y is not None:
                                l_diff = abs(self.cur_left_ankle_y - self.baseline_left_y)
                                if l_diff > RAISE_THRESHOLD_PX:
                                    self.state = ST_LEFT_UP
                                    self.left_start_time = time.time()
                                    print(f"[SOOL] Left foot raised! (dY={l_diff:.1f}px) Timer started")

                        elif self.state == ST_LEFT_UP:
                            self.left_elapsed = time.time() - self.left_start_time

                            if has_ankles and self.baseline_left_y is not None:
                                l_diff = abs(self.cur_left_ankle_y - self.baseline_left_y)
                                if l_diff < RAISE_THRESHOLD_PX * RAISE_HYSTERESIS:
                                    self.state = ST_COMPLETED
                                    self.completed_wall_time = time.time()
                                    print(f"[SOOL] Left foot down! Time: {self.left_elapsed:.2f}s")
                                    print("[SOOL] Test Complete!")

                        elif self.state == ST_COMPLETED:
                            if (self.completed_wall_time and
                                    now - self.completed_wall_time > AUTO_STOP_DELAY_S):
                                print("[SOOL] Auto-stopping...")
                                break

                        self._log_row(timestamp)

                    else:
                        cv2.putText(display, "Person lost - searching...",
                                    (DISPLAY_W // 2 - 140, DISPLAY_H // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                                    (0, 165, 255), 2)

                    display = self._draw_tracking_hud(display, persons, left_px, right_px)

                # Record original-res video
                if self.video_writer is not None:
                    self.video_writer.write(color_bgr)

                # FPS
                cv2.putText(display, f"FPS: {current_fps}",
                            (DISPLAY_W - 100, DISPLAY_H - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                cv2.imshow(window, display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == ord('Q') or key == 13:
                    break

        except KeyboardInterrupt:
            print("\n[SOOL] Interrupted")
        finally:
            self._save_and_cleanup(csv_path, result_path)

        return self._build_result()

    # ──────────────────────────────────────────────────────────────
    # SAVE & CLEANUP
    # ──────────────────────────────────────────────────────────────

    def _save_and_cleanup(self, csv_path: str, result_path: str):
        print("\n[SOOL] Saving...")

        if self.video_writer:
            self.video_writer.release()
            print(f"  Video: {self.output_dir / 'video.mp4'}")

        if self.csv_rows:
            with open(csv_path, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=self.CSV_HEADER)
                w.writeheader()
                w.writerows(self.csv_rows)
            print(f"  CSV: {csv_path} ({len(self.csv_rows)} rows)")

        result = self._build_result()
        if result:
            with open(result_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"  Result: {result_path}")

        if self.pose:
            self.pose.close()
        if self.k4a:
            self.k4a.stop()
        cv2.destroyAllWindows()

        duration = time.time() - self.start_time if self.start_time else 0
        print(f"\n[SOOL] Session: {duration:.1f}s, {self.frame_count} frames")

    def _build_result(self) -> Optional[dict]:
        best = max(self.right_elapsed, self.left_elapsed)
        if best <= 0:
            return None

        if best >= 45:
            risk, desc = "Normal", "Balance within normal range"
        elif best >= 30:
            risk, desc = "Mild impairment", "Slight balance deficit"
        elif best >= 15:
            risk, desc = "Moderate impairment", "Moderate balance deficit, fall risk increased"
        elif best >= 5:
            risk, desc = "Significant impairment", "Significant balance deficit, high fall risk"
        else:
            risk, desc = "Severe impairment", "Severe balance deficit, very high fall risk"

        return {
            'right_foot_time_s': round(self.right_elapsed, 2),
            'left_foot_time_s': round(self.left_elapsed, 2),
            'best_time_s': round(best, 2),
            'risk_level': risk,
            'detail': desc,
            'test_completed': self.state == ST_COMPLETED,
            'total_frames': self.frame_count,
            'source': 'real-time',
        }


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINTS (for GUI integration)
# ═══════════════════════════════════════════════════════════════════

def phase_record(output_dir: str, **kwargs) -> Optional[dict]:
    tracker = SOOLTracker(output_dir=output_dir,
                          yolo_model=kwargs.get('yolo_model', 'yolov8n.pt'))
    return tracker.run()


def phase_analyze(input_dir: str, **kwargs) -> Optional[dict]:
    result_path = os.path.join(input_dir, "sool_live_result.json")
    if os.path.exists(result_path):
        with open(result_path) as f:
            result = json.load(f)
        print("\n" + "=" * 50)
        print("STANDING ON ONE LEG RESULTS")
        print("=" * 50)
        for k, v in result.items():
            print(f"  {k.replace('_',' ').title():.<30s} {v}")
        print("=" * 50)
        return result
    else:
        print(f"[Analyze] No result at: {result_path}")
        return None


def full_pipeline(output_dir: str, **kwargs) -> Optional[dict]:
    return phase_record(output_dir, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Standing On One Leg Test (Eyes Open)")
    parser.add_argument('--output', '-o', required=True, help='Output dir')
    parser.add_argument('--model', '-m', default='yolov8n.pt', help='YOLO model')
    args = parser.parse_args()

    tracker = SOOLTracker(output_dir=args.output, yolo_model=args.model)
    result = tracker.run()

    if result:
        print("\n" + "=" * 50)
        print("FINAL RESULT")
        print("=" * 50)
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == '__main__':
    main()


# ═══════════════════════════════════════════════════════════════════
# PyQt5 GUI WINDOW  (imported by test_main.py)
# ═══════════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QDesktopWidget, QTextEdit,
    QSpacerItem, QSizePolicy, QFileDialog
)
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, QDateTime, QProcess
import requests   # ✅ NEW

_GUI_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR    = os.path.join(_GUI_BASE_DIR, "tests")
SOOL_SCRIPT   = os.path.join(_TESTS_DIR, "standing_one_leg_test.py")
SOOL_DATA_DIR = os.path.join(_GUI_BASE_DIR, "StandingOnOneLegData")
# ✅ NEW — FastAPI endpoint
API_BASE = "http://127.0.0.1:8000/physical-frailty"


def _escape_html_sol(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class StandingOnOneLegWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.n_id = getattr(self.main_window, "n_id", None)  # ✅ NEW
        self.setWindowTitle("Standing On One Leg Test")
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
        title_label = QLabel("Standing On One Leg Test")
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
            "• Camera faces person at ~2-3 m.<br>"
            "• Click on person to LOCK tracking.<br>"
            "• Stand still — system calibrates ankle baseline.<br>"
            "• Raise RIGHT foot and hold as long as possible.<br>"
            "• If < 60 s, repeat with LEFT foot.<br>"
            "• Result = max(right, left) time.<br>"
            "—<br>"
            "<b>Buttons:</b><br>"
            "• <b>Start Test</b> — Real-time SOOL with auto-timer (pyk4a + YOLO + MediaPipe).<br>"
            "• <b>View Results</b> — Open saved result from a previous run."
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
        col.addWidget(self.console, 1)
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
        safe = _escape_html_sol(text or "")
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
                self.proc.disconnect()
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
        os.makedirs(SOOL_DATA_DIR, exist_ok=True)
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        return os.path.join(SOOL_DATA_DIR, f"sool_{ts}")

    def _launch_script(self, args: list, label: str):
        if self.proc is not None:
            if self.proc.state() != QProcess.NotRunning:
                self._append_log("⚠️ A process is already running!")
                return
            self._cleanup_proc()

        python = sys.executable
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(_TESTS_DIR)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self._wire_process_signals()

        cmd_args = [SOOL_SCRIPT] + args
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
        """Start the SOOL test — records and times in one go."""
        self.current_trial = trial
        output_dir = self._get_output_dir()
        self._append_log(f"Output (Trial {trial}): {output_dir}")
        self._launch_script(
            ["--output", output_dir],
            f"Standing On One Leg Trial {trial}"
        )

    def handle_view_results(self):
        """Open a previous SOOL result folder and display the result JSON."""
        input_dir = QFileDialog.getExistingDirectory(
            self, "Select SOOL Result Folder", SOOL_DATA_DIR
        )
        if not input_dir:
            self._append_log("Cancelled — no folder selected.")
            return

        result_path = os.path.join(input_dir, "sool_live_result.json")
        if not os.path.isfile(result_path):
            self._append_log(f"❌ No sool_live_result.json found in {input_dir}")
            self.status.setText("Status: No result found")
            return

        # try:
        #     with open(result_path, 'r') as f:
        #         result = json.load(f)
        #     lines = ["<b>═══ SOOL RESULT ═══</b>"]
        #     for k, v in result.items():
        #         lines.append(f"<b>{_escape_html_sol(str(k))}:</b> {_escape_html_sol(str(v))}")
        #     self.results_box.setHtml("<br>".join(lines))
        #     self.status.setText("Status: Result loaded")
        # except Exception as e:
        #     self._append_log(f"❌ Error reading result: {e}")
        #     self.status.setText("Status: Error")

        try:
            with open(result_path, 'r') as f:
                result = json.load(f)

            lines = ["<b>═══ SOOL RESULT ═══</b>"]
            for k, v in result.items():
                lines.append(f"<b>{_escape_html_sol(str(k))}:</b> {_escape_html_sol(str(v))}")

            # ✅ NEW — Extract best_time and send to API
            best_time = result.get("best_time_s")

            if best_time is not None:
                if self.current_trial == 1:
                    self.time1 = float(best_time)
                elif self.current_trial == 2:
                    self.time2 = float(best_time)

                self._update_trial_results()
                self._send_to_api(float(best_time))
            else:
                self._append_log("⚠️ best_time_s not found in result JSON.")

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

    # ✅ NEW — Send SOOL result to backend
    def _send_to_api(self, best_time: float):
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
            "test": "standing_on_one_leg",  # MUST match API TEST_COLUMN_MAP
            "value": float(best_time)
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=10)

            if response.status_code == 200:
                self._append_log("✅ SOOL result saved to database.")
            else:
                self._append_log(
                    f"❌ API Error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self._append_log(f"❌ API Connection Error: {e}")
