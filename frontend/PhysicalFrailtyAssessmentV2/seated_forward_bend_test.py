#!/usr/bin/env python3
"""
Seated Forward Bend Test — Frailty Assessment System
=====================================================
Real-time seated forward bend measurement using Azure Kinect DK (pyk4a)
+ YOLO + MediaPipe Pose.

Clinical Protocol (matches C++ SFB):
    Person sits on chair, arms extended forward (camera to the SIDE)
    System calibrates wrist baseline positions
    Person bends forward → wrist X moves in image
    Max displacement tracked in cm using depth
    When person returns to initial position → test complete

How it works:
    1. YOLO detects all persons → click to LOCK onto one
    2. MediaPipe Pose detects wrist positions in cropped ROI
    3. Azure Kinect depth gives real-world distance at wrist
    4. Real-time state machine:
       SELECTING → CALIBRATING → STABLE → BENDING → COMPLETED

Usage:
    python seated_forward_bend_test.py --output sfb_001

Author: Kashif (NCAI/NCRA, NUST Pakistan)
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
ST_BENDING      = "BENDING"
ST_COMPLETED    = "COMPLETED"

STATE_COLORS = {
    ST_SELECTING:   (200, 200, 200),
    ST_CALIBRATING: (0, 165, 255),
    ST_STABLE:      (0, 200, 0),
    ST_BENDING:     (0, 0, 255),
    ST_COMPLETED:   (255, 200, 0),
}

# ── Thresholds ────────────────────────────────────────────────────
STABILITY_FRAMES       = 20     # Frames of stable wrists to confirm baseline
STABILITY_THRESHOLD_PX = 18     # Max wrist X pixel range for "stable" (display-space)
BEND_START_PX          = 25     # Wrist X pixel change to count as "bending"
RETURN_THRESHOLD_PX    = 30     # Wrist X within this of baseline = returned
RETREAT_CONFIRM_FRAMES = 15     # Frames of retreating to confirm peak reached
LOCK_TOLERANCE         = 120    # Pixel distance for re-matching (tighter to avoid jumps)
AUTO_STOP_DELAY_S      = 3.0    # Auto-stop after completion

# Display size (all coordinates in this space)
DISPLAY_W = 1280
DISPLAY_H = 720

# YOLO runs every N-th frame to keep FPS high
YOLO_EVERY_N_FRAMES = 3

# Approximate camera intrinsics for pixel→cm conversion (720p)
FOCAL_LENGTH_PX = 600.0         # Approximate for Azure Kinect 720p


# ═══════════════════════════════════════════════════════════════════
# MAIN SFB TRACKER
# ═══════════════════════════════════════════════════════════════════

class SFBTracker:
    """
    Seated Forward Bend test with click-to-select person locking.
    Same architecture as TUGTracker / SOOLTracker.
    All detection/display uses a fixed DISPLAY_W x DISPLAY_H image
    so mouse clicks always align with bounding boxes.
    """

    # MediaPipe landmark indices
    MP_LEFT_WRIST  = 15
    MP_RIGHT_WRIST = 16
    MP_LEFT_ELBOW  = 13
    MP_RIGHT_ELBOW = 14

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
        self.locked_bbox_area: float = 0.0    # Area at lock time for size filtering
        self.selection_mode = True
        self.mouse_click_pos: Optional[Tuple[int, int]] = None

        # State machine
        self.state = ST_SELECTING

        # Stability / baseline
        self.left_wrist_x_history: deque = deque(maxlen=STABILITY_FRAMES)
        self.right_wrist_x_history: deque = deque(maxlen=STABILITY_FRAMES)
        self.baseline_left_x: Optional[float] = None
        self.baseline_right_x: Optional[float] = None
        self.baseline_depth_mm: float = 0.0  # Depth at baseline for px→cm

        # Current wrist positions (crop-relative X pixels)
        self.cur_left_wrist_x = 0.0
        self.cur_left_wrist_y = 0.0
        self.cur_right_wrist_x = 0.0
        self.cur_right_wrist_y = 0.0
        self.cur_left_conf = 0.0
        self.cur_right_conf = 0.0

        # Max distance tracking
        self.max_right_dist_px = 0.0
        self.max_left_dist_px = 0.0
        self.max_right_dist_cm = 0.0
        self.max_left_dist_cm = 0.0
        self.cur_right_dist_px = 0.0
        self.cur_left_dist_px = 0.0
        self.retreat_counter = 0    # Count frames where distance is decreasing

        # Completed
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
        Rejects candidates whose bbox area differs too much (different person)."""
        if self.selected_person is None:
            return None
        best, min_dist = None, float('inf')
        for p in persons:
            dist = np.sqrt(
                (p.center_x - self.selected_person.center_x) ** 2 +
                (p.center_y - self.selected_person.center_y) ** 2
            )
            # Reject if too far
            if dist >= LOCK_TOLERANCE:
                continue
            # Reject if bbox area is very different from locked person
            # (means YOLO detected a different person nearby)
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
        self.left_wrist_x_history.clear()
        self.right_wrist_x_history.clear()
        self.baseline_left_x = None
        self.baseline_right_x = None
        self.max_right_dist_px = 0.0
        self.max_left_dist_px = 0.0
        self.max_right_dist_cm = 0.0
        self.max_left_dist_cm = 0.0
        self.retreat_counter = 0
        self.completed_wall_time = None
        print("[SFB] Person deselected — state reset")

    # ──────────────────────────────────────────────────────────────
    # DEPTH
    # ──────────────────────────────────────────────────────────────

    def _get_depth_at_point(self, depth_image: np.ndarray,
                             display_x: int, display_y: int) -> float:
        """Get depth (mm) at a display-space point, mapped to original depth image."""
        if depth_image is None:
            return 0.0
        dh, dw = depth_image.shape[:2]
        ox = int(display_x * self.scale_x)
        oy = int(display_y * self.scale_y)
        ox = max(0, min(ox, dw - 1))
        oy = max(0, min(oy, dh - 1))

        # Median in 7x7 window
        half = 3
        y1, y2 = max(0, oy - half), min(dh, oy + half + 1)
        x1, x2 = max(0, ox - half), min(dw, ox + half + 1)
        window = depth_image[y1:y2, x1:x2]
        valid = window[(window > 300) & (window < 5000)]
        return float(np.median(valid)) if len(valid) > 0 else 0.0

    def _px_to_cm(self, px_displacement: float, depth_mm: float) -> float:
        """Convert pixel displacement to cm using depth and focal length."""
        if depth_mm <= 0:
            return 0.0
        # real_distance = pixel_disp * depth / focal_length
        return abs(px_displacement) * depth_mm / FOCAL_LENGTH_PX / 10.0  # mm→cm

    # ──────────────────────────────────────────────────────────────
    # WRIST DETECTION (MediaPipe on cropped display image)
    # ──────────────────────────────────────────────────────────────

    def _detect_wrists(self, display_img: np.ndarray,
                       bbox: PersonBBox) -> Tuple[float, float, float, float,
                                                   float, float,
                                                   Optional[Tuple[int, int]],
                                                   Optional[Tuple[int, int]]]:
        """
        Detect wrist positions via MediaPipe Pose.
        Returns: (left_x, left_y, right_x, right_y, left_conf, right_conf,
                  left_pixel, right_pixel)

        IMPORTANT: X/Y values are in DISPLAY space (not crop-relative)
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
            return 0, 0, 0, 0, 0, 0, None, None

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return 0, 0, 0, 0, 0, 0, None, None

        lm = results.pose_landmarks.landmark
        crop_h, crop_w = cropped.shape[:2]

        lw = lm[self.MP_LEFT_WRIST]
        rw = lm[self.MP_RIGHT_WRIST]

        # DISPLAY-space coordinates (crop-relative + offset)
        # This is stable across frames even when bbox jitters
        left_x = lw.x * crop_w + x1
        left_y = lw.y * crop_h + y1
        right_x = rw.x * crop_w + x1
        right_y = rw.y * crop_h + y1

        # Integer pixel coords for drawing
        left_px = (int(left_x), int(left_y))
        right_px = (int(right_x), int(right_y))

        return left_x, left_y, right_x, right_y, lw.visibility, rw.visibility, left_px, right_px

    # ──────────────────────────────────────────────────────────────
    # DRAWING
    # ──────────────────────────────────────────────────────────────

    def _draw_selection_mode(self, image: np.ndarray,
                              persons: List[PersonBBox]) -> np.ndarray:
        h, w = image.shape[:2]

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)

        cv2.rectangle(image, (0, 0), (w, 60), (40, 40, 40), -1)
        cv2.putText(image, "SEATED FORWARD BEND - Click on the SEATED person",
                    (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, f"Detected {len(persons)} person(s) | Camera should be to the SIDE | Q=quit",
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

        # Draw wrist markers
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

        # Draw baseline marker (vertical line at baseline X in display space)
        if self.baseline_left_x is not None and self.selected_person:
            base_display_x = int(self.baseline_left_x)
            bbox = self.selected_person
            cv2.line(image, (base_display_x, bbox.y1), (base_display_x, bbox.y2),
                     (0, 255, 255), 1, cv2.LINE_AA)

        # State banner
        labels = {
            ST_SELECTING:   "SELECTING - Click on seated person",
            ST_CALIBRATING: f"CALIBRATING - Hold arms steady ({len(self.left_wrist_x_history)}/{STABILITY_FRAMES})",
            ST_STABLE:      "STABLE - Please bend FORWARD",
            ST_BENDING:     "BENDING - Reach as far as you can!",
            ST_COMPLETED:   "TEST COMPLETED!",
        }
        banner = labels.get(self.state, self.state)

        # Add range info during calibration
        if (self.state == ST_CALIBRATING and
                len(self.left_wrist_x_history) >= STABILITY_FRAMES):
            l_range = max(self.left_wrist_x_history) - min(self.left_wrist_x_history)
            r_range = max(self.right_wrist_x_history) - min(self.right_wrist_x_history)
            banner = f"CALIBRATING - Hold still! (jitter: L={l_range:.0f} R={r_range:.0f} need <{STABILITY_THRESHOLD_PX})"

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        cv2.putText(image, banner, (15, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2, cv2.LINE_AA)

        # Live distance during bending
        if self.state == ST_BENDING:
            best_cm = max(self.max_right_dist_cm, self.max_left_dist_cm)
            cv2.putText(image, f"{best_cm:.1f} cm",
                        (w - 220, 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3, cv2.LINE_AA)
            # Large center distance
            cv2.putText(image, f"{best_cm:.1f} cm",
                        (w // 2 - 100, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 255), 4, cv2.LINE_AA)

        # Info panel
        y_off = 80
        if self.baseline_left_x is not None:
            cv2.putText(image, f"L wrist dX: {self.cur_left_dist_px:.1f}px ({self.max_left_dist_cm:.1f}cm max)",
                        (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (200, 200, 200), 1)
            y_off += 22
            cv2.putText(image, f"R wrist dX: {self.cur_right_dist_px:.1f}px ({self.max_right_dist_cm:.1f}cm max)",
                        (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (200, 200, 200), 1)
            y_off += 22
            if self.baseline_depth_mm > 0:
                cv2.putText(image, f"Depth: {self.baseline_depth_mm/1000:.2f}m",
                            (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            (160, 160, 160), 1)

        # Results panel
        if self.state in (ST_BENDING, ST_COMPLETED):
            panel_y = h - 130
            overlay2 = image.copy()
            cv2.rectangle(overlay2, (10, panel_y), (380, h - 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay2, 0.7, image, 0.3, 0, image)

            cv2.putText(image, "RESULTS", (20, panel_y + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.putText(image, f"Right wrist max: {self.max_right_dist_cm:.2f} cm",
                        (20, panel_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 200, 200), 2)
            cv2.putText(image, f"Left wrist max:  {self.max_left_dist_cm:.2f} cm",
                        (20, panel_y + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 200, 200), 2)

            best = max(self.max_right_dist_cm, self.max_left_dist_cm)
            bc = (0, 255, 0) if self.state == ST_COMPLETED else (0, 200, 200)
            cv2.putText(image, f"Best reach: {best:.2f} cm",
                        (20, panel_y + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        bc, 2)

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
        'left_wrist_x_px', 'left_wrist_y_px', 'left_wrist_conf',
        'right_wrist_x_px', 'right_wrist_y_px', 'right_wrist_conf',
        'left_disp_px', 'right_disp_px',
        'left_dist_cm', 'right_dist_cm',
        'max_left_cm', 'max_right_cm',
        'depth_mm',
    ]

    def _log_row(self, timestamp: float, depth_mm: float):
        self.csv_rows.append({
            'frame_number': self.frame_count,
            'timestamp_sec': round(timestamp, 4),
            'state': self.state,
            'left_wrist_x_px': round(self.cur_left_wrist_x, 1),
            'left_wrist_y_px': round(self.cur_left_wrist_y, 1),
            'left_wrist_conf': round(self.cur_left_conf, 3),
            'right_wrist_x_px': round(self.cur_right_wrist_x, 1),
            'right_wrist_y_px': round(self.cur_right_wrist_y, 1),
            'right_wrist_conf': round(self.cur_right_conf, 3),
            'left_disp_px': round(self.cur_left_dist_px, 1),
            'right_disp_px': round(self.cur_right_dist_px, 1),
            'left_dist_cm': round(self._px_to_cm(self.cur_left_dist_px, depth_mm), 2),
            'right_dist_cm': round(self._px_to_cm(self.cur_right_dist_px, depth_mm), 2),
            'max_left_cm': round(self.max_left_dist_cm, 2),
            'max_right_cm': round(self.max_right_dist_cm, 2),
            'depth_mm': round(depth_mm, 1),
        })

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    def run(self) -> Optional[dict]:
        if not self.initialize():
            return None

        self.start_time = time.time()

        print("\n" + "=" * 60)
        print("SEATED FORWARD BEND TEST")
        print("=" * 60)
        print("Setup: Camera to the SIDE, person sits on chair")
        print("       Arms extended forward, palms down")
        print("")
        print("  1. Click on the person to LOCK")
        print("  2. Hold arms extended — system calibrates baseline")
        print("  3. When prompted, BEND FORWARD as far as possible")
        print("  4. System tracks max wrist reach distance")
        print("  5. Return to seated position → test complete")
        print("")
        print("  RIGHT-CLICK  = deselect person")
        print("  Q / ENTER    = quit manually")
        print("=" * 60 + "\n")

        window = "Seated Forward Bend Test"
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, self._mouse_callback)

        video_path = str(self.output_dir / "video.mp4")
        csv_path = str(self.output_dir / "wrist_data.csv")
        result_path = str(self.output_dir / "sfb_live_result.json")

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
                        print(f"[ERROR] Too many capture errors, stopping.")
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
                depth = capture.transformed_depth
                self.orig_h, self.orig_w = color_bgr.shape[:2]
                self.scale_x = self.orig_w / DISPLAY_W
                self.scale_y = self.orig_h / DISPLAY_H

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
                cur_depth_mm = 0.0

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
                        self.left_wrist_x_history.clear()
                        self.right_wrist_x_history.clear()
                        self.baseline_left_x = None
                        self.baseline_right_x = None
                        print(f"[SFB] Locked Person {clicked_id + 1} (area={self.locked_bbox_area:.0f})")
                        print("[SFB] Calibrating — hold arms extended...")
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

                        # Detect wrists
                        (self.cur_left_wrist_x, self.cur_left_wrist_y,
                         self.cur_right_wrist_x, self.cur_right_wrist_y,
                         self.cur_left_conf, self.cur_right_conf,
                         left_px, right_px) = self._detect_wrists(display, matched)

                        has_wrists = (self.cur_left_conf > 0.3 and
                                      self.cur_right_conf > 0.3)

                        # Get depth at wrist for px→cm conversion
                        if left_px and depth is not None:
                            cur_depth_mm = self._get_depth_at_point(
                                depth, left_px[0], left_px[1])

                        # ── STATE MACHINE ─────────────────────────
                        if self.state == ST_CALIBRATING:
                            if has_wrists:
                                self.left_wrist_x_history.append(self.cur_left_wrist_x)
                                self.right_wrist_x_history.append(self.cur_right_wrist_x)

                            if (len(self.left_wrist_x_history) >= STABILITY_FRAMES and
                                    len(self.right_wrist_x_history) >= STABILITY_FRAMES):
                                l_range = max(self.left_wrist_x_history) - min(self.left_wrist_x_history)
                                r_range = max(self.right_wrist_x_history) - min(self.right_wrist_x_history)

                                if l_range < STABILITY_THRESHOLD_PX and r_range < STABILITY_THRESHOLD_PX:
                                    self.baseline_left_x = float(np.mean(list(self.left_wrist_x_history)))
                                    self.baseline_right_x = float(np.mean(list(self.right_wrist_x_history)))
                                    self.baseline_depth_mm = cur_depth_mm if cur_depth_mm > 0 else 2000.0
                                    self.state = ST_STABLE

                                    # Start recording
                                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                                    self.video_writer = cv2.VideoWriter(
                                        video_path, fourcc, 30,
                                        (self.orig_w, self.orig_h),
                                    )
                                    print(f"[SFB] Wrists stable! Baseline L_X={self.baseline_left_x:.1f} R_X={self.baseline_right_x:.1f}")
                                    print(f"[SFB] Depth: {self.baseline_depth_mm:.0f}mm")
                                    print("[SFB] Please BEND FORWARD")
                                else:
                                    # Debug: print ranges every 30 frames so user sees progress
                                    if self.frame_count % 30 == 0:
                                        print(f"[SFB] Calibrating... L_range={l_range:.1f}px R_range={r_range:.1f}px (need <{STABILITY_THRESHOLD_PX})")
                                    # If ranges are very large, the person is still moving
                                    # Keep the sliding window — it naturally clears old data

                        elif self.state == ST_STABLE:
                            if has_wrists and self.baseline_left_x is not None:
                                l_disp = abs(self.cur_left_wrist_x - self.baseline_left_x)
                                r_disp = abs(self.cur_right_wrist_x - self.baseline_right_x)
                                self.cur_left_dist_px = l_disp
                                self.cur_right_dist_px = r_disp

                                if l_disp > BEND_START_PX or r_disp > BEND_START_PX:
                                    self.state = ST_BENDING
                                    self.retreat_counter = 0
                                    print(f"[SFB] Bending detected! (L={l_disp:.1f}px R={r_disp:.1f}px)")

                        elif self.state == ST_BENDING:
                            if has_wrists and self.baseline_left_x is not None:
                                l_disp = abs(self.cur_left_wrist_x - self.baseline_left_x)
                                r_disp = abs(self.cur_right_wrist_x - self.baseline_right_x)
                                self.cur_left_dist_px = l_disp
                                self.cur_right_dist_px = r_disp

                                # Use depth for conversion (prefer current, fallback baseline)
                                d = cur_depth_mm if cur_depth_mm > 0 else self.baseline_depth_mm
                                l_cm = self._px_to_cm(l_disp, d)
                                r_cm = self._px_to_cm(r_disp, d)

                                # Update maximums
                                if l_cm > self.max_left_dist_cm:
                                    self.max_left_dist_cm = l_cm
                                    self.max_left_dist_px = l_disp
                                if r_cm > self.max_right_dist_cm:
                                    self.max_right_dist_cm = r_cm
                                    self.max_right_dist_px = r_disp

                                # Check if person is retreating (distance decreasing)
                                if (l_cm < self.max_left_dist_cm - 1.0 and
                                        r_cm < self.max_right_dist_cm - 1.0):
                                    self.retreat_counter += 1
                                else:
                                    self.retreat_counter = 0

                                # Check return to initial position
                                if (self.retreat_counter >= RETREAT_CONFIRM_FRAMES and
                                        l_disp < RETURN_THRESHOLD_PX and
                                        r_disp < RETURN_THRESHOLD_PX):
                                    self.state = ST_COMPLETED
                                    self.completed_wall_time = time.time()
                                    best = max(self.max_right_dist_cm, self.max_left_dist_cm)
                                    print(f"[SFB] Returned to position — Test Complete!")
                                    print(f"  Right wrist: {self.max_right_dist_cm:.2f} cm")
                                    print(f"  Left wrist:  {self.max_left_dist_cm:.2f} cm")
                                    print(f"  Best reach:  {best:.2f} cm")

                        elif self.state == ST_COMPLETED:
                            if has_wrists and self.baseline_left_x is not None:
                                self.cur_left_dist_px = abs(self.cur_left_wrist_x - self.baseline_left_x)
                                self.cur_right_dist_px = abs(self.cur_right_wrist_x - self.baseline_right_x)

                            if (self.completed_wall_time and
                                    now - self.completed_wall_time > AUTO_STOP_DELAY_S):
                                print("[SFB] Auto-stopping...")
                                break

                        self._log_row(timestamp, cur_depth_mm if cur_depth_mm > 0 else self.baseline_depth_mm)

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
            print("\n[SFB] Interrupted")
        finally:
            self._save_and_cleanup(csv_path, result_path)

        return self._build_result()

    # ──────────────────────────────────────────────────────────────
    # SAVE & CLEANUP
    # ──────────────────────────────────────────────────────────────

    def _save_and_cleanup(self, csv_path: str, result_path: str):
        print("\n[SFB] Saving...")

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
        print(f"\n[SFB] Session: {duration:.1f}s, {self.frame_count} frames")

    def _build_result(self) -> Optional[dict]:
        best = max(self.max_right_dist_cm, self.max_left_dist_cm)
        if best <= 0:
            return None

        # Clinical interpretation (Chair Sit-and-Reach normative data)
        # Values vary by age/sex; general thresholds:
        if best >= 25:
            risk, desc = "Normal", "Flexibility within normal range"
        elif best >= 15:
            risk, desc = "Mild deficit", "Slight flexibility deficit"
        elif best >= 5:
            risk, desc = "Moderate deficit", "Moderate flexibility deficit"
        elif best >= 0:
            risk, desc = "Significant deficit", "Significant flexibility limitation"
        else:
            risk, desc = "Severe deficit", "Severe flexibility limitation"

        return {
            'right_wrist_max_cm': round(self.max_right_dist_cm, 2),
            'left_wrist_max_cm': round(self.max_left_dist_cm, 2),
            'best_reach_cm': round(best, 2),
            'risk_level': risk,
            'detail': desc,
            'baseline_depth_m': round(self.baseline_depth_mm / 1000, 3),
            'test_completed': self.state == ST_COMPLETED,
            'total_frames': self.frame_count,
            'source': 'real-time',
        }


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINTS (for GUI integration)
# ═══════════════════════════════════════════════════════════════════

def phase_record(output_dir: str, **kwargs) -> Optional[dict]:
    tracker = SFBTracker(output_dir=output_dir,
                         yolo_model=kwargs.get('yolo_model', 'yolov8n.pt'))
    return tracker.run()


def phase_analyze(input_dir: str, **kwargs) -> Optional[dict]:
    result_path = os.path.join(input_dir, "sfb_live_result.json")
    if os.path.exists(result_path):
        with open(result_path) as f:
            result = json.load(f)
        print("\n" + "=" * 50)
        print("SEATED FORWARD BEND RESULTS")
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
    parser = argparse.ArgumentParser(description="Seated Forward Bend Test")
    parser.add_argument('--output', '-o', required=True, help='Output dir')
    parser.add_argument('--model', '-m', default='yolov8n.pt', help='YOLO model')
    args = parser.parse_args()

    tracker = SFBTracker(output_dir=args.output, yolo_model=args.model)
    result = tracker.run()

    if result:
        print("\n" + "=" * 50)
        print("FINAL RESULT")
        print("=" * 50)
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == '__main__':
    main()