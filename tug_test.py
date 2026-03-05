#!/usr/bin/env python3
"""
Timed Up and Go (TUG) Test — Frailty Assessment System
=======================================================
Real-time TUG timer using Azure Kinect DK (pyk4a) + YOLO + MediaPipe.

Clinical Protocol:
    Person starts SEATED in a chair (~3.5-4.5m from camera).
    On "Go": stands up, walks toward camera, turns around,
    walks back, sits down.
    Timer = stand-up → fully seated again.

How it works:
    1. YOLO detects all persons → click to LOCK onto one
    2. MediaPipe Pose detects hip/knee positions → sitting vs standing
    3. Azure Kinect depth measures distance from camera
    4. Real-time state machine:
       WAITING → SEATED → WALKING (timer running) → COMPLETED

Usage:
    python tug_test.py --output tug_001

Author: Kashif (NCAI/NCRA, NUST Pakistan)
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# ── Fix Windows DPI scaling (MUST be before cv2 import) ──────────
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-monitor DPI aware
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

import cv2
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from pyk4a import PyK4A, Config, ColorResolution, DepthMode, FPS
from ultralytics import YOLO

# Use compatibility wrapper for mediapipe (works with both old and new API)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontend.PhysicalFrailtyAssessmentV2.mp_pose_compat import create_pose_detector


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
# TUG STATE MACHINE
# ═══════════════════════════════════════════════════════════════════

ST_WAITING      = "WAITING"
ST_SEATED       = "SEATED"
ST_WALKING      = "WALKING"
ST_COMPLETED    = "COMPLETED"

STATE_COLORS = {
    ST_WAITING:   (200, 200, 200),
    ST_SEATED:    (0, 200, 0),
    ST_WALKING:   (0, 165, 255),
    ST_COMPLETED: (255, 200, 0),
}

# ── Thresholds ────────────────────────────────────────────────────
SIT_HIP_KNEE_THRESHOLD = 40    # hip-knee Y pixel diff < this = sitting
STAND_CONFIRM_FRAMES   = 10
SIT_CONFIRM_FRAMES     = 15
AUTO_STOP_DELAY_S      = 3.0
LOCK_TOLERANCE         = 200   # pixel distance for re-matching

# Display size (all coordinates are in this space)
DISPLAY_W = 1280
DISPLAY_H = 720

# YOLO is only run every N-th frame to keep FPS high
YOLO_EVERY_N_FRAMES = 3


# ═══════════════════════════════════════════════════════════════════
# MAIN TUG TRACKER
# ═══════════════════════════════════════════════════════════════════

class TUGTracker:
    """
    Timed Up and Go test with click-to-select person locking.
    All detection/display uses a fixed DISPLAY_W×DISPLAY_H image
    so mouse clicks always align with bounding boxes.
    """

    MP_LEFT_HIP    = 23
    MP_RIGHT_HIP   = 24
    MP_LEFT_KNEE   = 25
    MP_RIGHT_KNEE  = 26

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
        self.selection_mode = True
        self.mouse_click_pos: Optional[Tuple[int, int]] = None

        # State machine
        self.state = ST_WAITING
        self.sit_counter = 0
        self.stand_counter = 0

        # Timer / depth
        self.walk_start_time = 0.0
        self.tug_time_final: Optional[float] = None
        self.initial_depth_mm = 0.0
        self.min_depth_mm = 99999.0
        self.max_depth_mm = 0.0
        self.current_depth_mm = 0.0
        self.completed_wall_time: Optional[float] = None

        # Recording
        self.frame_count = 0
        self.start_time: Optional[float] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.csv_rows: list = []

        # Scale factors (set when first frame arrives)
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
            print(f"  [CLICK] Mouse at ({x}, {y})")
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
        if persons:
            print(f"  [YOLO] {len(persons)} person(s): " +
                  ", ".join(f"({p.x1},{p.y1})-({p.x2},{p.y2})" for p in persons))
        return persons

    def _check_click(self, persons: List[PersonBBox]) -> Optional[int]:
        """Check if mouse click is inside any person bbox."""
        if self.mouse_click_pos is None:
            return None
        cx, cy = self.mouse_click_pos
        self.mouse_click_pos = None
        print(f"  [CLICK CHECK] Testing ({cx},{cy}) against {len(persons)} persons")
        for person in persons:
            print(f"    Person {person.id}: ({person.x1},{person.y1})-({person.x2},{person.y2})", end="")
            if person.x1 <= cx <= person.x2 and person.y1 <= cy <= person.y2:
                print(" → HIT!")
                return person.id
            else:
                print(" → miss")
        return None

    def _find_by_proximity(self, persons: List[PersonBBox]) -> Optional[PersonBBox]:
        if self.selected_person is None:
            return None
        best, min_dist = None, float('inf')
        for p in persons:
            dist = np.sqrt(
                (p.center_x - self.selected_person.center_x) ** 2 +
                (p.center_y - self.selected_person.center_y) ** 2
            )
            if dist < min_dist and dist < LOCK_TOLERANCE:
                min_dist = dist
                best = p
        return best

    def _reset_selection(self):
        self.selected_person = None
        self.selection_mode = True
        self.state = ST_WAITING
        self.sit_counter = 0
        self.stand_counter = 0
        self.tug_time_final = None
        self.completed_wall_time = None
        print("[TUG] Person deselected — state reset")

    # ──────────────────────────────────────────────────────────────
    # DEPTH (uses original-resolution depth image)
    # ──────────────────────────────────────────────────────────────

    def _get_depth_at_bbox(self, depth_image: np.ndarray,
                           bbox: PersonBBox) -> float:
        """Get median depth (mm) at center of bbox.
        bbox is in display coords, depth is in original coords."""
        dh, dw = depth_image.shape[:2]

        # Map display coords → original coords
        ox1 = int(bbox.x1 * self.scale_x)
        oy1 = int(bbox.y1 * self.scale_y)
        ox2 = int(bbox.x2 * self.scale_x)
        oy2 = int(bbox.y2 * self.scale_y)

        # Center 40%
        bw, bh = ox2 - ox1, oy2 - oy1
        margin = 0.3
        cx1 = int(ox1 + bw * margin)
        cx2 = int(ox2 - bw * margin)
        cy1 = int(oy1 + bh * margin)
        cy2 = int(oy2 - bh * margin)

        cx1, cy1 = max(0, cx1), max(0, cy1)
        cx2, cy2 = min(dw, cx2), min(dh, cy2)

        if cx2 <= cx1 or cy2 <= cy1:
            return 0.0

        region = depth_image[cy1:cy2, cx1:cx2]
        valid = region[(region > 300) & (region < 10000)]
        return float(np.median(valid)) if len(valid) > 0 else 0.0

    # ──────────────────────────────────────────────────────────────
    # POSTURE (MediaPipe on cropped display image)
    # ──────────────────────────────────────────────────────────────

    def _detect_posture(self, display_img: np.ndarray,
                        bbox: PersonBBox) -> Tuple[bool, float]:
        """Detect sitting via hip-knee Y pixel difference."""
        h, w = display_img.shape[:2]
        pad = 20
        x1 = max(0, bbox.x1 - pad)
        y1 = max(0, bbox.y1 - pad)
        x2 = min(w, bbox.x2 + pad)
        y2 = min(h, bbox.y2 + pad)

        cropped = display_img[y1:y2, x1:x2]
        if cropped.size == 0:
            return False, 999.0

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return False, 999.0

        lm = results.pose_landmarks.landmark
        crop_h, crop_w = cropped.shape[:2]

        diffs = []
        for hip_idx, knee_idx in [(self.MP_LEFT_HIP, self.MP_LEFT_KNEE),
                                   (self.MP_RIGHT_HIP, self.MP_RIGHT_KNEE)]:
            hip_lm = lm[hip_idx]
            knee_lm = lm[knee_idx]
            if hip_lm.visibility > 0.3 and knee_lm.visibility > 0.3:
                hip_y = hip_lm.y * crop_h
                knee_y = knee_lm.y * crop_h
                diffs.append(abs(knee_y - hip_y))

        if not diffs:
            return False, 999.0

        avg_diff = float(np.mean(diffs))
        is_sitting = avg_diff < SIT_HIP_KNEE_THRESHOLD
        return is_sitting, avg_diff

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
        cv2.putText(image, "TUG TEST - Click on the SEATED person to lock",
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
            lw_s, lh_s = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
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
                            is_sitting: bool, hk_diff: float,
                            elapsed_s: float) -> np.ndarray:
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

        # State banner
        labels = {
            ST_WAITING:   "WAITING - Lock a person first",
            ST_SEATED:    "SEATED - Waiting for stand-up...",
            ST_WALKING:   "WALKING - Timer running",
            ST_COMPLETED: "COMPLETED - Test finished!",
        }
        banner = labels.get(self.state, self.state)

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        cv2.putText(image, banner, (15, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2, cv2.LINE_AA)

        # Timer
        if self.state == ST_WALKING:
            cv2.putText(image, f"{elapsed_s:.1f}s", (w - 200, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3, cv2.LINE_AA)
        elif self.state == ST_COMPLETED and self.tug_time_final is not None:
            cv2.putText(image, f"TUG: {self.tug_time_final:.2f}s",
                        (w - 300, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3, cv2.LINE_AA)

        # Info panel
        y_off = 80
        depth_m = self.current_depth_mm / 1000.0
        if depth_m > 0.2:
            cv2.putText(image, f"Distance: {depth_m:.2f} m", (15, y_off),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            y_off += 28

        posture = "SITTING" if is_sitting else "STANDING"
        pc = (0, 200, 0) if is_sitting else (200, 200, 0)
        cv2.putText(image, f"Posture: {posture} (diff={hk_diff:.0f}px)",
                    (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.55, pc, 2)
        y_off += 25

        if self.state in (ST_WALKING, ST_COMPLETED):
            im = self.initial_depth_mm / 1000
            mm = self.min_depth_mm / 1000
            if im > 0.2:
                cv2.putText(image, f"Chair: {im:.2f} m", (15, y_off),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                y_off += 22
            if mm < 90:
                cv2.putText(image, f"Closest: {mm:.2f} m", (15, y_off),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                y_off += 22
            if im > 0.2 and depth_m > 0.2:
                cv2.putText(image, f"Walk dist: {abs(im - depth_m):.2f} m",
                            (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (255, 255, 0), 1)

        # Bottom
        cv2.putText(image, "RIGHT-CLICK: deselect | Q: quit",
                    (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (160, 160, 160), 1)
        return image

    # ──────────────────────────────────────────────────────────────
    # CSV
    # ──────────────────────────────────────────────────────────────

    CSV_HEADER = [
        'frame_number', 'timestamp_sec', 'state',
        'depth_mm', 'is_sitting', 'hip_knee_diff_px', 'elapsed_s',
    ]

    def _log_row(self, timestamp: float, is_sitting: bool,
                 hk_diff: float, elapsed_s: float):
        self.csv_rows.append({
            'frame_number': self.frame_count,
            'timestamp_sec': round(timestamp, 4),
            'state': self.state,
            'depth_mm': round(self.current_depth_mm, 1),
            'is_sitting': int(is_sitting),
            'hip_knee_diff_px': round(hk_diff, 1),
            'elapsed_s': round(elapsed_s, 3),
        })

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self) -> Optional[dict]:
        if not self.initialize():
            return None

        self.start_time = time.time()

        print("\n" + "=" * 60)
        print("TIMED UP AND GO TEST")
        print("=" * 60)
        print("Setup: Person sits on chair, 3.5-4.5 m from camera")
        print("")
        print("  1. Click on the SEATED person to LOCK")
        print("  2. System auto-detects SITTING")
        print("  3. Timer STARTS when person STANDS UP")
        print("  4. Timer STOPS when person SITS BACK DOWN")
        print("  5. Result auto-saves after completion")
        print("")
        print("  RIGHT-CLICK  = deselect person")
        print("  Q / ENTER    = quit manually")
        print("=" * 60 + "\n")

        window = "TUG Test"
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, self._mouse_callback)

        video_path = str(self.output_dir / "video.mp4")
        csv_path = str(self.output_dir / "tug_joint_data.csv")
        result_path = str(self.output_dir / "tug_live_result.json")

        fps_start = time.time()
        fps_count = 0
        current_fps = 0
        last_persons: List[PersonBBox] = []

        capture_errors = 0
        try:
            while True:
                try:
                    capture = self.k4a.get_capture()
                except Exception as e:
                    capture_errors += 1
                    if capture_errors > 20:
                        print(f"[ERROR] Too many capture errors ({capture_errors}), stopping.")
                        break
                    time.sleep(0.05)
                    continue

                if capture.color is None:
                    continue
                capture_errors = 0  # Reset on success

                self.frame_count += 1
                fps_count += 1
                now = time.time()
                if now - fps_start >= 1.0:
                    current_fps = fps_count
                    fps_count = 0
                    fps_start = now

                # ── Get images ────────────────────────────────────
                color_bgr = capture.color[:, :, :3]
                depth = capture.transformed_depth
                self.orig_h, self.orig_w = color_bgr.shape[:2]
                self.scale_x = self.orig_w / DISPLAY_W
                self.scale_y = self.orig_h / DISPLAY_H

                # Resize to fixed display size (ensures mouse coords match)
                display = cv2.resize(color_bgr, (DISPLAY_W, DISPLAY_H))
                timestamp = now - self.start_time

                # ── YOLO every N frames (faster) ──────────────────
                if self.frame_count % YOLO_EVERY_N_FRAMES == 1 or not last_persons:
                    persons = self._detect_persons(display)
                    last_persons = persons
                else:
                    persons = last_persons

                is_sitting = False
                hk_diff = 999.0
                elapsed_s = 0.0

                if self.selection_mode:
                    # ── SELECTION MODE ─────────────────────────────
                    display = self._draw_selection_mode(display, persons)

                    clicked_id = self._check_click(persons)
                    if clicked_id is not None and clicked_id < len(persons):
                        self.selected_person = persons[clicked_id]
                        self.selection_mode = False
                        self.state = ST_WAITING
                        self.sit_counter = 0
                        self.stand_counter = 0
                        print(f"[TUG] ✓ Locked Person {clicked_id + 1}")
                    else:
                        # Consume any unmatched click
                        self.mouse_click_pos = None

                else:
                    # ── TRACKING MODE ──────────────────────────────
                    matched = self._find_by_proximity(persons)

                    if matched:
                        self.selected_person = matched

                        # Depth
                        if depth is not None:
                            d = self._get_depth_at_bbox(depth, matched)
                            if d > 0:
                                self.current_depth_mm = d

                        # Posture
                        is_sitting, hk_diff = self._detect_posture(display, matched)

                        # ── STATE MACHINE ─────────────────────────
                        if self.state == ST_WAITING:
                            if is_sitting:
                                self.sit_counter += 1
                                if self.sit_counter >= 5:
                                    self.state = ST_SEATED
                                    self.initial_depth_mm = self.current_depth_mm
                                    print(f"[TUG] SEATED (depth={self.current_depth_mm/1000:.2f}m)")
                            else:
                                self.sit_counter = 0

                        elif self.state == ST_SEATED:
                            if not is_sitting:
                                self.stand_counter += 1
                                if self.stand_counter >= STAND_CONFIRM_FRAMES:
                                    self.state = ST_WALKING
                                    self.walk_start_time = time.time()
                                    self.min_depth_mm = self.current_depth_mm
                                    self.max_depth_mm = self.current_depth_mm

                                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                                    self.video_writer = cv2.VideoWriter(
                                        video_path, fourcc, 30,
                                        (self.orig_w, self.orig_h),
                                    )
                                    print("[TUG] STAND-UP — Timer STARTED!")
                            else:
                                self.stand_counter = 0
                                if self.current_depth_mm > 0:
                                    self.initial_depth_mm = self.current_depth_mm

                        elif self.state == ST_WALKING:
                            elapsed_s = time.time() - self.walk_start_time
                            if self.current_depth_mm > 0:
                                self.min_depth_mm = min(self.min_depth_mm,
                                                        self.current_depth_mm)
                                self.max_depth_mm = max(self.max_depth_mm,
                                                        self.current_depth_mm)
                            if is_sitting:
                                self.sit_counter += 1
                                if self.sit_counter >= SIT_CONFIRM_FRAMES:
                                    self.tug_time_final = time.time() - self.walk_start_time
                                    self.state = ST_COMPLETED
                                    self.completed_wall_time = time.time()
                                    elapsed_s = self.tug_time_final
                                    im = self.initial_depth_mm / 1000
                                    mm = self.min_depth_mm / 1000
                                    print(f"\n[TUG] SAT DOWN — Timer STOPPED!")
                                    print(f"  +==============================+")
                                    print(f"  |  TUG TIME: {self.tug_time_final:6.2f} seconds  |")
                                    print(f"  +==============================+")
                                    print(f"  Chair:   {im:.2f} m")
                                    print(f"  Closest: {mm:.2f} m")
                                    print(f"  Walk:    {abs(im - mm):.2f} m")
                            else:
                                self.sit_counter = 0

                        elif self.state == ST_COMPLETED:
                            elapsed_s = self.tug_time_final or 0.0
                            if (self.completed_wall_time and
                                    now - self.completed_wall_time > AUTO_STOP_DELAY_S):
                                print("[TUG] Auto-stopping...")
                                break

                        self._log_row(timestamp, is_sitting, hk_diff, elapsed_s)

                    else:
                        cv2.putText(display, "Person lost - searching...",
                                    (DISPLAY_W // 2 - 140, DISPLAY_H // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                                    (0, 165, 255), 2)

                    display = self._draw_tracking_hud(
                        display, persons, is_sitting, hk_diff, elapsed_s)

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
            print("\n[TUG] Interrupted")
        finally:
            self._save_and_cleanup(csv_path, result_path)

        return self._build_result()

    # ──────────────────────────────────────────────────────────────
    # SAVE & CLEANUP
    # ──────────────────────────────────────────────────────────────

    def _save_and_cleanup(self, csv_path: str, result_path: str):
        print("\n[TUG] Saving...")

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
        print(f"\n[TUG] Session: {duration:.1f}s, {self.frame_count} frames")

    def _build_result(self) -> Optional[dict]:
        if self.tug_time_final is None:
            return None
        t = self.tug_time_final
        if t < 10:
            a, r, d = "NORMAL", "LOW", "Freely mobile, low fall risk"
        elif t < 20:
            a, r, d = "MOSTLY INDEPENDENT", "MODERATE", "Some mobility issues"
        elif t < 30:
            a, r, d = "MOBILITY IMPAIRMENT", "HIGH", "Significant fall risk"
        else:
            a, r, d = "SEVERE IMPAIRMENT", "VERY HIGH", "Dependent mobility"

        im = self.initial_depth_mm / 1000
        mm = self.min_depth_mm / 1000
        return {
            'tug_time_s': round(t, 2),
            'assessment': a,
            'risk_level': r,
            'detail': d,
            'initial_depth_m': round(im, 3),
            'min_depth_m': round(mm, 3),
            'walk_distance_m': round(abs(im - mm), 3),
            'total_frames': self.frame_count,
            'source': 'real-time',
        }


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINTS (for GUI integration)
# ═══════════════════════════════════════════════════════════════════

def phase_record(output_dir: str, **kwargs) -> Optional[dict]:
    tracker = TUGTracker(output_dir=output_dir,
                         yolo_model=kwargs.get('yolo_model', 'yolov8n.pt'))
    return tracker.run()


def phase_analyze(input_dir: str, **kwargs) -> Optional[dict]:
    result_path = os.path.join(input_dir, "tug_live_result.json")
    if os.path.exists(result_path):
        with open(result_path) as f:
            result = json.load(f)
        print("\n" + "=" * 50)
        print("TUG RESULTS")
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
    parser = argparse.ArgumentParser(description="TUG Test")
    parser.add_argument('--output', '-o', required=True, help='Output dir')
    parser.add_argument('--model', '-m', default='yolov8n.pt', help='YOLO model')
    args = parser.parse_args()

    tracker = TUGTracker(output_dir=args.output, yolo_model=args.model)
    result = tracker.run()

    if result:
        print("\n" + "=" * 50)
        print("FINAL RESULT")
        print("=" * 50)
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == '__main__':
    main()