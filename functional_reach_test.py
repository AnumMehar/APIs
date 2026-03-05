#!/usr/bin/env python3


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
# from mp_pose_compat import create_pose_detector
from frontend.PhysicalFrailtyAssessmentV2.mp_pose_compat import create_pose_detector

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════

DISPLAY_W = 1280
DISPLAY_H = 720
YOLO_EVERY_N = 3
LOCK_TOLERANCE = 200   # px for re-matching

# MediaPipe Pose landmark indices
MP_LEFT_WRIST   = 15
MP_RIGHT_WRIST  = 16
MP_LEFT_ELBOW   = 13
MP_RIGHT_ELBOW  = 14
MP_LEFT_SHOULDER = 11
MP_RIGHT_SHOULDER = 12

# Azure Kinect 720p color camera approximate intrinsics (fx, fy, cx, cy)
# These are used to convert pixel + depth → real-world mm
# NFOV_UNBINNED depth aligned to 720p color
AK_FX = 605.0
AK_FY = 605.0
AK_CX = 640.0
AK_CY = 360.0


@dataclass
class PersonBBox:
    """Detected person bounding box (in display coords)."""
    id: int
    x1: int; y1: int; x2: int; y2: int
    confidence: float
    center_x: int; center_y: int


# ═══════════════════════════════════════════════════════════════════
# FUNCTIONAL REACH TRACKER
# ═══════════════════════════════════════════════════════════════════

class FunctionalReachTracker:
    """
    Records wrist/elbow positions using pyk4a + YOLO + MediaPipe.
    Outputs CSV compatible with the existing phase_analyze.
    """

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

        # Recording
        self.recording = False
        self.frame_count = 0
        self.start_time: Optional[float] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.csv_rows: list = []

        # Scale factors
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

            # Get calibration for pixel → mm conversion
            try:
                calib = self.k4a.calibration
                cam = calib.get_camera_matrix(1)  # 1 = color camera
                global AK_FX, AK_FY, AK_CX, AK_CY
                AK_FX = cam[0, 0]
                AK_FY = cam[1, 1]
                AK_CX = cam[0, 2]
                AK_CY = cam[1, 2]
                print(f"  ✓ Calibration: fx={AK_FX:.1f} fy={AK_FY:.1f} "
                      f"cx={AK_CX:.1f} cy={AK_CY:.1f}")
            except Exception:
                print("  ⚠ Using default intrinsics (calibration unavailable)")

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
    # PERSON DETECTION
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
            if person.x1 <= cx <= person.x2 and person.y1 <= cy <= person.y2:
                print(f"  [CLICK] HIT Person {person.id}")
                return person.id
        print(f"  [CLICK] Miss — no person at ({cx},{cy})")
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
        print("[FRT] Person deselected")

    # ──────────────────────────────────────────────────────────────
    # DEPTH
    # ──────────────────────────────────────────────────────────────

    def _get_depth_at_point(self, depth_image: np.ndarray,
                             px: int, py: int, radius: int = 5) -> float:
        """Get median depth (mm) around a point in the depth image.
        px, py are in original image coordinates."""
        dh, dw = depth_image.shape[:2]
        x1 = max(0, px - radius)
        x2 = min(dw, px + radius)
        y1 = max(0, py - radius)
        y2 = min(dh, py + radius)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        region = depth_image[y1:y2, x1:x2]
        valid = region[(region > 300) & (region < 10000)]
        return float(np.median(valid)) if len(valid) > 0 else 0.0

    def _pixel_to_mm(self, px: float, py: float, depth_mm: float) -> Tuple[float, float, float]:
        """Convert pixel + depth → real-world mm using Kinect intrinsics.
        Output: (x_mm, y_mm, z_mm) in camera coordinate frame."""
        if depth_mm <= 0:
            return (0.0, 0.0, 0.0)
        x_mm = (px - AK_CX) * depth_mm / AK_FX
        y_mm = (py - AK_CY) * depth_mm / AK_FY
        return (x_mm, y_mm, depth_mm)

    # ──────────────────────────────────────────────────────────────
    # WRIST/ELBOW DETECTION
    # ──────────────────────────────────────────────────────────────

    def _detect_wrists(self, display_img: np.ndarray, bbox: PersonBBox,
                       depth_image: Optional[np.ndarray]) -> dict:
        """Detect wrist and elbow positions using MediaPipe Pose.
        Returns dict with wrist/elbow data in mm (for CSV)."""
        h, w = display_img.shape[:2]
        pad = 20
        x1 = max(0, bbox.x1 - pad)
        y1 = max(0, bbox.y1 - pad)
        x2 = min(w, bbox.x2 + pad)
        y2 = min(h, bbox.y2 + pad)

        cropped = display_img[y1:y2, x1:x2]
        if cropped.size == 0:
            return self._empty_wrist_row()

        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return self._empty_wrist_row()

        lm = results.pose_landmarks.landmark
        crop_h, crop_w = cropped.shape[:2]

        row = {}
        for side, wrist_idx, elbow_idx in [
            ('left',  MP_LEFT_WRIST,  MP_LEFT_ELBOW),
            ('right', MP_RIGHT_WRIST, MP_RIGHT_ELBOW),
        ]:
            wrist_lm = lm[wrist_idx]
            elbow_lm = lm[elbow_idx]

            if wrist_lm.visibility > 0.3:
                # Pixel in display coords
                wpx_disp = x1 + wrist_lm.x * crop_w
                wpy_disp = y1 + wrist_lm.y * crop_h

                # Pixel in original image coords (for depth lookup)
                wpx_orig = int(wpx_disp * self.scale_x)
                wpy_orig = int(wpy_disp * self.scale_y)

                # Get depth at wrist
                z_mm = 0.0
                if depth_image is not None:
                    z_mm = self._get_depth_at_point(depth_image, wpx_orig, wpy_orig)

                # Convert to real-world mm
                x_mm, y_mm, z_mm = self._pixel_to_mm(wpx_orig, wpy_orig, z_mm)

                conf = 2 if wrist_lm.visibility > 0.5 else 1  # Medium/Low

                row[f'wrist_{side}_x_mm'] = round(x_mm, 1)
                row[f'wrist_{side}_y_mm'] = round(y_mm, 1)
                row[f'wrist_{side}_z_mm'] = round(z_mm, 1)
                row[f'wrist_{side}_conf'] = conf
                row[f'wrist_{side}_px'] = int(wpx_disp)
                row[f'wrist_{side}_py'] = int(wpy_disp)
            else:
                row[f'wrist_{side}_x_mm'] = 0
                row[f'wrist_{side}_y_mm'] = 0
                row[f'wrist_{side}_z_mm'] = 0
                row[f'wrist_{side}_conf'] = 0
                row[f'wrist_{side}_px'] = -1
                row[f'wrist_{side}_py'] = -1

            if elbow_lm.visibility > 0.3:
                epx_disp = x1 + elbow_lm.x * crop_w
                epy_disp = y1 + elbow_lm.y * crop_h
                epx_orig = int(epx_disp * self.scale_x)
                epy_orig = int(epy_disp * self.scale_y)

                z_e = 0.0
                if depth_image is not None:
                    z_e = self._get_depth_at_point(depth_image, epx_orig, epy_orig)
                _, ey_mm, _ = self._pixel_to_mm(epx_orig, epy_orig, z_e)

                row[f'elbow_{side}_y_mm'] = round(ey_mm, 1)
                row[f'elbow_{side}_conf'] = 2 if elbow_lm.visibility > 0.5 else 1
            else:
                row[f'elbow_{side}_y_mm'] = 0
                row[f'elbow_{side}_conf'] = 0

        return row

    def _empty_wrist_row(self) -> dict:
        row = {}
        for side in ('left', 'right'):
            row[f'wrist_{side}_x_mm'] = 0
            row[f'wrist_{side}_y_mm'] = 0
            row[f'wrist_{side}_z_mm'] = 0
            row[f'wrist_{side}_conf'] = 0
            row[f'wrist_{side}_px'] = -1
            row[f'wrist_{side}_py'] = -1
            row[f'elbow_{side}_y_mm'] = 0
            row[f'elbow_{side}_conf'] = 0
        return row

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
        cv2.putText(image, "FUNCTIONAL REACH - Click on the person to lock",
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
                            wrist_data: dict) -> np.ndarray:
        h, w = image.shape[:2]

        # Draw locked person bbox
        if self.selected_person:
            p = self.selected_person
            cv2.rectangle(image, (p.x1, p.y1), (p.x2, p.y2), (0, 255, 0), 3)
            cv2.putText(image, "LOCKED", (p.x1, p.y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Draw wrist markers
        for side, color in [('left', (255, 0, 0)), ('right', (0, 0, 255))]:
            px = wrist_data.get(f'wrist_{side}_px', -1)
            py = wrist_data.get(f'wrist_{side}_py', -1)
            if px > 0 and py > 0:
                cv2.circle(image, (int(px), int(py)), 8, color, -1)
                cv2.circle(image, (int(px), int(py)), 10, (255, 255, 255), 2)
                label = f"{side[0].upper()}: X={wrist_data.get(f'wrist_{side}_x_mm', 0):.0f}mm"
                cv2.putText(image, label, (int(px) + 15, int(py)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Top banner
        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)

        status = "SELECTED — Press SPACE to start recording" if not self.recording else ""
        status_color = (0, 255, 0)

        if self.recording:
            status = f"● REC  Frame {self.frame_count}"
            status_color = (0, 0, 255)
            # Flashing red dot
            if self.frame_count % 30 < 15:
                cv2.circle(image, (25, 30), 10, (0, 0, 255), -1)

        cv2.putText(image, status, (45, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2, cv2.LINE_AA)

        # Wrist info panel
        y_off = 80
        for side in ('left', 'right'):
            conf = wrist_data.get(f'wrist_{side}_conf', 0)
            if conf > 0:
                x_mm = wrist_data.get(f'wrist_{side}_x_mm', 0)
                y_mm = wrist_data.get(f'wrist_{side}_y_mm', 0)
                z_mm = wrist_data.get(f'wrist_{side}_z_mm', 0)
                c = (255, 200, 0) if side == 'left' else (0, 200, 255)
                cv2.putText(image,
                            f"Wrist {side[0].upper()}: X={x_mm:.0f} Y={y_mm:.0f} Z={z_mm:.0f} mm",
                            (15, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2)
                y_off += 25

        # Bottom instructions
        if not self.recording:
            cv2.putText(image, "SPACE: start recording | RIGHT-CLICK: deselect | Q: quit",
                        (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        (160, 160, 160), 1)
        else:
            cv2.putText(image, "ENTER: stop & save | RIGHT-CLICK: deselect | Q: quit",
                        (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        (160, 160, 160), 1)

        return image

    # ──────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────

    CSV_HEADER = [
        'frame_number', 'timestamp_sec', 'body_id',
        'wrist_left_x_mm', 'wrist_left_y_mm', 'wrist_left_z_mm', 'wrist_left_conf',
        'wrist_left_px', 'wrist_left_py',
        'wrist_right_x_mm', 'wrist_right_y_mm', 'wrist_right_z_mm', 'wrist_right_conf',
        'wrist_right_px', 'wrist_right_py',
        'elbow_left_y_mm', 'elbow_left_conf',
        'elbow_right_y_mm', 'elbow_right_conf',
    ]

    def run(self) -> bool:
        if not self.initialize():
            return False

        self.start_time = time.time()

        print("\n" + "=" * 60)
        print("FUNCTIONAL REACH TEST — RECORDING")
        print("=" * 60)
        print("Camera: Placed PERPENDICULAR to person (side view)")
        print("")
        print("  1. Click on the person to LOCK")
        print("  2. Press SPACE to start recording")
        print("  3. Person raises arms, reaches forward, returns")
        print("  4. Press ENTER to stop and save")
        print("")
        print("  RIGHT-CLICK  = deselect person")
        print("  Q            = quit")
        print("=" * 60 + "\n")

        window = "Functional Reach Test"
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, self._mouse_callback)

        video_path = str(self.output_dir / "video.mp4")
        csv_path = str(self.output_dir / "wrist_data.csv")

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

                now = time.time()
                fps_count += 1
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
                frame_idx = fps_count + int(fps_start * 1000) % 10000  # avoids 0
                if frame_idx % YOLO_EVERY_N == 1 or not last_persons:
                    persons = self._detect_persons(display)
                    last_persons = persons
                else:
                    persons = last_persons

                wrist_data = self._empty_wrist_row()

                if self.selection_mode:
                    # ── SELECTION MODE ─────────────────────────────
                    display = self._draw_selection_mode(display, persons)

                    clicked_id = self._check_click(persons)
                    if clicked_id is not None and clicked_id < len(persons):
                        self.selected_person = persons[clicked_id]
                        self.selection_mode = False
                        print(f"[FRT] ✓ Locked Person {clicked_id + 1}")
                    else:
                        self.mouse_click_pos = None

                else:
                    # ── TRACKING MODE ──────────────────────────────
                    matched = self._find_by_proximity(persons)

                    if matched:
                        self.selected_person = matched
                        wrist_data = self._detect_wrists(display, matched, depth)

                    display = self._draw_tracking_hud(display, wrist_data)

                    # ── Record data ────────────────────────────────
                    if self.recording:
                        if self.video_writer is None:
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            self.video_writer = cv2.VideoWriter(
                                video_path, fourcc, 30,
                                (self.orig_w, self.orig_h),
                            )

                        self.video_writer.write(color_bgr)

                        row = {
                            'frame_number': self.frame_count,
                            'timestamp_sec': round(timestamp, 4),
                            'body_id': 0,
                        }
                        row.update(wrist_data)
                        self.csv_rows.append(row)
                        self.frame_count += 1

                # FPS
                cv2.putText(display, f"FPS: {current_fps}",
                            (DISPLAY_W - 100, DISPLAY_H - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                cv2.imshow(window, display)
                key = cv2.waitKey(1) & 0xFF

                if key == ord(' ') and not self.recording and not self.selection_mode:
                    if self.selected_person is not None:
                        self.recording = True
                        print("[FRT] Recording started!")
                    else:
                        print("[FRT] Select a person first!")
                elif key == 13:  # ENTER
                    break
                elif key == ord('q') or key == ord('Q'):
                    break

        except KeyboardInterrupt:
            print("\n[FRT] Interrupted")
        finally:
            self._save_and_cleanup(csv_path)

        return True

    # ──────────────────────────────────────────────────────────────
    # SAVE & CLEANUP
    # ──────────────────────────────────────────────────────────────

    def _save_and_cleanup(self, csv_path: str):
        print("\n[FRT] Saving...")

        if self.video_writer:
            self.video_writer.release()
            print(f"  Video: {self.output_dir / 'video.mp4'}")

        if self.csv_rows:
            with open(csv_path, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=self.CSV_HEADER)
                w.writeheader()
                w.writerows(self.csv_rows)
            print(f"  CSV: {csv_path} ({len(self.csv_rows)} rows)")

        if self.pose:
            self.pose.close()
        if self.k4a:
            self.k4a.stop()
        cv2.destroyAllWindows()

        duration = time.time() - self.start_time if self.start_time else 0
        print(f"\n[FRT] Session: {duration:.1f}s, {self.frame_count} frames recorded")


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: RECORD (entry point)
# ═══════════════════════════════════════════════════════════════════

def phase_record(output_dir: str, **kwargs) -> bool:
    tracker = FunctionalReachTracker(
        output_dir=output_dir,
        yolo_model=kwargs.get('yolo_model', 'yolov8n.pt'),
    )
    return tracker.run()


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: ANALYZE (unchanged logic, removed body_tracker dependency)
# ═══════════════════════════════════════════════════════════════════

# Confidence levels (replaces body_tracker.Confidence import)
CONF_NONE = 0
CONF_LOW = 1
CONF_MEDIUM = 2


def phase_analyze(
    input_dir: str,
    sg_window: int = 15,
    sg_order: int = 3,
    stability_window: int = 20,
    stability_threshold_mm: float = 15.0,
    reach_onset_mm: float = 30.0,
    show_plot: bool = True,
    save_plot: bool = True,
):
    """
    Analyze wrist CSV to compute functional reach distance.

    Reads:   <input_dir>/wrist_data.csv
    Saves:   <input_dir>/functional_reach_result.json
             <input_dir>/functional_reach_plot.png
    """
    from scipy.signal import savgol_filter
    import pandas as pd

    csv_path = os.path.join(input_dir, "wrist_data.csv")
    result_path = os.path.join(input_dir, "functional_reach_result.json")
    plot_path = os.path.join(input_dir, "functional_reach_plot.png")

    if not os.path.exists(csv_path):
        print(f"[Analyze] CSV not found: {csv_path}")
        return None

    df = pd.read_csv(csv_path)

    if len(df) < 30:
        print(f"[Analyze] Not enough frames ({len(df)}). Need at least 30.")
        return None

    timestamps = df['timestamp_sec'].values

    # ── Select the best wrist ─────────────────────────────────────
    left_valid = (df['wrist_left_conf'] >= CONF_MEDIUM).sum()
    right_valid = (df['wrist_right_conf'] >= CONF_MEDIUM).sum()

    wrist_side = 'left' if left_valid >= right_valid else 'right'

    print(f"[Analyze] Using {wrist_side} wrist "
          f"({max(left_valid, right_valid)} valid frames out of {len(df)})")

    wrist_x_raw = df[f'wrist_{wrist_side}_x_mm'].values.astype(float)
    wrist_y_raw = df[f'wrist_{wrist_side}_y_mm'].values.astype(float)
    wrist_conf = df[f'wrist_{wrist_side}_conf'].values.astype(int)
    elbow_y_raw = df[f'elbow_{wrist_side}_y_mm'].values.astype(float)
    elbow_conf = df[f'elbow_{wrist_side}_conf'].values.astype(int)

    valid_mask = wrist_conf >= CONF_MEDIUM
    if valid_mask.sum() < 20:
        print(f"[Analyze] Too few valid wrist frames ({valid_mask.sum()})")
        return None

    # Interpolate invalid frames
    wrist_x = wrist_x_raw.copy()
    wrist_y = wrist_y_raw.copy()
    elbow_y = elbow_y_raw.copy()

    for arr in [wrist_x, wrist_y, elbow_y]:
        invalid = ~valid_mask
        if invalid.any() and valid_mask.any():
            arr[invalid] = np.interp(
                np.where(invalid)[0],
                np.where(valid_mask)[0],
                arr[valid_mask]
            )

    # ── Savitzky-Golay smoothing ──────────────────────────────────
    wl = min(sg_window, len(wrist_x) if len(wrist_x) % 2 == 1 else len(wrist_x) - 1)
    wl = max(wl, 5)

    wrist_x_smooth = savgol_filter(wrist_x, wl, sg_order, mode='nearest')
    wrist_y_smooth = savgol_filter(wrist_y, wl, sg_order, mode='nearest')
    elbow_y_smooth = savgol_filter(elbow_y, wl, sg_order, mode='nearest')

    # ── Phase detection ───────────────────────────────────────────
    n = len(wrist_x_smooth)

    rolling_std = np.array([
        np.std(wrist_x_smooth[max(0, i - stability_window):i + 1])
        for i in range(n)
    ])

    stable_mask = rolling_std < stability_threshold_mm

    initial_stable_end = 0
    consecutive_stable = 0
    for i in range(n):
        if stable_mask[i]:
            consecutive_stable += 1
            if consecutive_stable >= stability_window:
                initial_stable_end = i
                break
        else:
            consecutive_stable = 0

    if initial_stable_end == 0:
        initial_stable_end = max(10, n // 10)
        print("[Analyze] Warning: No clear initial stable period detected. "
              f"Using first {initial_stable_end} frames as baseline.")

    stable_start = max(0, initial_stable_end - stability_window)
    baseline_x = np.mean(wrist_x_smooth[stable_start:initial_stable_end + 1])

    print(f"  Baseline period: frames {stable_start}–{initial_stable_end}")
    print(f"  Baseline wrist X: {baseline_x:.1f} mm")

    displacement = wrist_x_smooth - baseline_x

    max_positive = np.max(displacement)
    max_negative = np.abs(np.min(displacement))

    if max_positive >= max_negative:
        reach_displacement = displacement
        reach_direction = "positive X"
    else:
        reach_displacement = -displacement
        reach_direction = "negative X"

    print(f"  Reach direction: {reach_direction}")

    search_start = initial_stable_end + 1
    if search_start >= n:
        search_start = n // 4

    peak_idx = search_start + np.argmax(reach_displacement[search_start:])
    peak_displacement_mm = reach_displacement[peak_idx]
    reach_cm = peak_displacement_mm / 10.0

    reach_onset_idx = search_start
    for i in range(search_start, n):
        if reach_displacement[i] > reach_onset_mm:
            reach_onset_idx = i
            break

    return_idx = peak_idx
    return_threshold = peak_displacement_mm * 0.3
    for i in range(peak_idx, n):
        if reach_displacement[i] < return_threshold:
            return_idx = i
            break

    # ── Clinical assessment ───────────────────────────────────────
    if reach_cm > 25.4:
        assessment = "NORMAL"
        risk_level = "LOW FALL RISK"
    elif reach_cm > 15.24:
        assessment = "MODERATE LIMITATION"
        risk_level = "MODERATE FALL RISK"
    else:
        assessment = "SIGNIFICANT LIMITATION"
        risk_level = "HIGH FALL RISK"

    result = {
        'reach_distance_cm': round(reach_cm, 2),
        'reach_distance_mm': round(peak_displacement_mm, 1),
        'baseline_wrist_x_mm': round(baseline_x, 1),
        'peak_wrist_x_mm': round(float(wrist_x_smooth[peak_idx]), 1),
        'wrist_side': wrist_side,
        'reach_direction': reach_direction,
        'assessment': assessment,
        'risk_level': risk_level,
        'baseline_frames': f"{stable_start}–{initial_stable_end}",
        'reach_onset_time_s': round(float(timestamps[reach_onset_idx]), 3),
        'peak_time_s': round(float(timestamps[peak_idx]), 3),
        'return_time_s': round(float(timestamps[return_idx]), 3),
        'total_frames': len(df),
        'valid_frames': int(valid_mask.sum()),
    }

    print("\n" + "=" * 60)
    print("FUNCTIONAL REACH TEST RESULTS")
    print("=" * 60)
    print(f"  Reach distance:  {reach_cm:.2f} cm  ({peak_displacement_mm:.1f} mm)")
    print(f"  Wrist tracked:   {wrist_side}")
    print(f"  Peak at:         {timestamps[peak_idx]:.2f}s (frame {peak_idx})")
    print(f"  Reach onset:     {timestamps[reach_onset_idx]:.2f}s")
    print(f"  Return at:       {timestamps[return_idx]:.2f}s")
    print(f"\n  Assessment:      {assessment}")
    print(f"  Risk level:      {risk_level}")
    print("=" * 60)

    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n  Result saved: {result_path}")

    if show_plot or save_plot:
        _generate_plot(
            timestamps, wrist_x_raw, wrist_x_smooth, wrist_y_smooth,
            elbow_y_smooth, reach_displacement, valid_mask,
            baseline_x, stable_start, initial_stable_end,
            reach_onset_idx, peak_idx, return_idx,
            reach_cm, assessment,
            plot_path, show_plot, save_plot,
        )

    return result


def _generate_plot(
    timestamps, wrist_x_raw, wrist_x_smooth, wrist_y_smooth,
    elbow_y_smooth, reach_displacement, valid_mask,
    baseline_x, stable_start, stable_end,
    onset_idx, peak_idx, return_idx,
    reach_cm, assessment,
    plot_path, show_plot, save_plot,
):
    """Generate 3-panel analysis plot."""
    try:
        import matplotlib
        if save_plot and not show_plot:
            matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
        fig.suptitle(
            f"Functional Reach Test — {reach_cm:.1f} cm ({assessment})",
            fontsize=14, fontweight='bold'
        )

        # Panel 1: Wrist X position over time
        ax = axes[0]
        ax.plot(timestamps, wrist_x_raw, 'b', alpha=0.2, label='Raw X')
        ax.plot(timestamps, wrist_x_smooth, 'b', lw=2, label='Smoothed X')
        ax.axhline(baseline_x, color='gray', ls='--',
                   label=f'Baseline ({baseline_x:.0f}mm)')
        ax.axvspan(timestamps[stable_start], timestamps[stable_end],
                   alpha=0.15, color='green', label='Stable period')
        ax.axvline(timestamps[onset_idx], color='orange', ls='--', lw=1.5,
                   label='Reach onset')
        ax.axvline(timestamps[peak_idx], color='red', ls='--', lw=2,
                   label='Peak reach')
        ax.axvline(timestamps[return_idx], color='purple', ls='--', lw=1.5,
                   label='Return')
        ax.set_ylabel('Wrist X (mm)')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_title('Wrist X-Axis Position (forward/backward)')

        # Panel 2: Wrist Y + Elbow Y
        ax = axes[1]
        ax.plot(timestamps, wrist_y_smooth, 'r', lw=2, label='Wrist Y')
        ax.plot(timestamps, elbow_y_smooth, 'orange', lw=2, label='Elbow Y')
        ax.axvline(timestamps[onset_idx], color='orange', ls='--', lw=1.5)
        ax.axvline(timestamps[peak_idx], color='red', ls='--', lw=2)
        ax.set_ylabel('Joint Y (mm)')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_title('Wrist & Elbow Y-Axis (arm raise height)')
        ax.invert_yaxis()

        # Panel 3: Reach displacement
        ax = axes[2]
        ax.fill_between(timestamps, reach_displacement / 10.0,
                        alpha=0.3, color='blue')
        ax.plot(timestamps, reach_displacement / 10.0, 'b', lw=1.5)
        ax.axhline(reach_cm, color='blue', ls='-', lw=3,
                   label=f'Peak: {reach_cm:.1f} cm')
        ax.axhline(25.4, color='green', ls=':', lw=2, label='Normal (>25.4cm)')
        ax.axhline(15.24, color='orange', ls=':', lw=2, label='Moderate (15.2cm)')
        ax.axhline(0, color='gray', ls='-', lw=0.5)
        ax.axvline(timestamps[peak_idx], color='red', ls='--', lw=2)

        inv = ~valid_mask
        for i in range(len(inv)):
            if inv[i]:
                ax.axvspan(
                    timestamps[max(0, i - 1)],
                    timestamps[min(len(timestamps) - 1, i)],
                    alpha=0.05, color='red'
                )

        ax.set_ylabel('Reach Distance (cm)')
        ax.set_xlabel('Time (s)')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_title('Forward Reach Displacement')

        plt.tight_layout()

        if save_plot:
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            print(f"  Plot saved: {plot_path}")
        if show_plot:
            plt.show()
        plt.close()

    except ImportError:
        print("  [Plot skipped — matplotlib not installed]")


# ═══════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════

def full_pipeline(output_dir: str, **kwargs):
    """Run record → analyze sequentially."""
    print("\n" + "#" * 60)
    print("# FUNCTIONAL REACH TEST — FULL PIPELINE")
    print("#" * 60)

    print("\n>>> PHASE 1: RECORD")
    success = phase_record(output_dir=output_dir, **kwargs)
    if not success:
        return None

    print("\n>>> PHASE 2: ANALYZE")
    result = phase_analyze(
        input_dir=output_dir,
        show_plot=kwargs.get('show_plot', True),
    )
    return result


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Functional Reach Test — Frailty Assessment System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='phase', help='Test phase')

    p_rec = subparsers.add_parser('record', help='Record with body tracking')
    p_rec.add_argument('--output', '-o', type=str, required=True)

    p_ana = subparsers.add_parser('analyze', help='Analyze wrist data')
    p_ana.add_argument('--input', '-i', type=str, required=True)
    p_ana.add_argument('--sg-window', type=int, default=15)
    p_ana.add_argument('--sg-order', type=int, default=3)
    p_ana.add_argument('--stability-window', type=int, default=20)
    p_ana.add_argument('--stability-threshold', type=float, default=15.0)
    p_ana.add_argument('--reach-onset', type=float, default=30.0)
    p_ana.add_argument('--no-plot', action='store_true')

    p_full = subparsers.add_parser('full', help='Record + Analyze')
    p_full.add_argument('--output', '-o', type=str, required=True)

    args = parser.parse_args()

    if args.phase is None:
        parser.print_help()
        return

    if args.phase == 'record':
        phase_record(output_dir=args.output)

    elif args.phase == 'analyze':
        phase_analyze(
            input_dir=args.input,
            sg_window=args.sg_window,
            sg_order=args.sg_order,
            stability_window=args.stability_window,
            stability_threshold_mm=args.stability_threshold,
            reach_onset_mm=args.reach_onset,
            show_plot=not args.no_plot,
        )

    elif args.phase == 'full':
        full_pipeline(output_dir=args.output)


if __name__ == '__main__':
    main()
