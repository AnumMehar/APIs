#!/usr/bin/env python3
"""
Walking Speed Test — Frailty Assessment System
===============================================
Three-phase pipeline for measuring walking speed using Azure Kinect DK RGB,
YOLO person tracking, and depth processing.

Phase 1 — RECORD:
    Capture RGB video from Azure Kinect at full 30fps via pyk4a.
    YOLO detects persons, operator clicks to lock one.
    Saves raw video at original camera resolution.

Phase 2 — PROCESS:
    (User-provided script) Load saved video, estimate depth, save CSV.

Phase 3 — ANALYZE:
    Load CSV. Apply Savitzky-Golay smoothing. Auto-detect walk boundaries
    (8m → 3m approach). Calculate walking speed. Clinical frailty assessment.

Usage:
    # Phase 1: Record
    python walking_speed_test.py record --output walking_test_001

    # Phase 2: Process saved video for depth
    python walking_speed_test.py process --input walking_test_001

    # Phase 3: Analyze depth CSV for speed
    python walking_speed_test.py analyze --input walking_test_001

    # All three phases in sequence
    python walking_speed_test.py full --output walking_test_001

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
import sys
import time
import warnings
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

import cv2
import numpy as np
warnings.filterwarnings('ignore')

from ultralytics import YOLO

# ── Core modules (for process phase only) ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent))


# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════

DISPLAY_W = 1280
DISPLAY_H = 720
YOLO_EVERY_N = 3
LOCK_TOLERANCE = 200


@dataclass
class PersonBBox:
    """Detected person bounding box (in display coords)."""
    id: int
    x1: int; y1: int; x2: int; y2: int
    confidence: float
    center_x: int; center_y: int


# ============================================================================
# PHASE 1: RECORD  (pyk4a + YOLO — full speed)
# ============================================================================

def phase_record(
    output_dir: str,
    camera_fps: int = 30,
    yolo_model: str = "yolov8n.pt",
    yolo_conf: float = 0.3,
    **kwargs,
):
    """
    Record RGB video from Azure Kinect at full camera FPS.

    Uses pyk4a for direct Kinect access and YOLO for person locking.
    Video is saved at the original camera resolution (720p) for quality.

    Saves:
        <output_dir>/video.mp4          — Raw RGB video at full speed
        <output_dir>/tracking.json      — Per-frame locked person centroid

    Controls:
        Left-click  → Lock person
        Right-click → Deselect
        SPACE       → Start recording
        ENTER / Q   → Stop and save
    """
    from pyk4a import PyK4A, Config, ColorResolution, DepthMode, FPS as K4AFPS

    os.makedirs(output_dir, exist_ok=True)
    video_path = os.path.join(output_dir, "video.mp4")
    meta_path = os.path.join(output_dir, "tracking.json")

    # ── Initialize Azure Kinect ───────────────────────────────────
    print("[INIT] Starting Azure Kinect...")
    try:
        config = Config(
            color_resolution=ColorResolution.RES_720P,
            depth_mode=DepthMode.OFF,          # No depth needed for record
            camera_fps=K4AFPS.FPS_30,
            synchronized_images_only=False,
        )
        k4a = PyK4A(config)
        k4a.start()
        print("  ✓ Azure Kinect started (720p, 30fps)")
    except Exception as e:
        print(f"[ERROR] Failed to start Azure Kinect: {e}")
        return False

    # ── Initialize YOLO ───────────────────────────────────────────
    print(f"[INIT] Loading YOLO ({yolo_model})...")
    yolo = YOLO(yolo_model)
    print("  ✓ YOLO loaded")

    # ── State ─────────────────────────────────────────────────────
    selected_person: Optional[PersonBBox] = None
    selection_mode = True
    mouse_click_pos: Optional[Tuple[int, int]] = None
    detected_persons: List[PersonBBox] = []
    recording = False
    frame_count = 0
    start_time = time.time()
    video_writer = None
    tracking_data: List[dict] = []

    scale_x = 1.0
    scale_y = 1.0

    # ── Mouse callback ────────────────────────────────────────────
    def mouse_cb(event, x, y, flags, param):
        nonlocal mouse_click_pos, selected_person, selection_mode
        if event == cv2.EVENT_LBUTTONDOWN:
            mouse_click_pos = (x, y)
            print(f"  [CLICK] ({x}, {y})")
        elif event == cv2.EVENT_RBUTTONDOWN:
            selected_person = None
            selection_mode = True
            print("[WS] Person deselected")

    window = "Walking Speed Test — RECORD"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, DISPLAY_W, DISPLAY_H)
    cv2.setMouseCallback(window, mouse_cb)

    print("\n" + "=" * 60)
    print("WALKING SPEED TEST — RECORDING")
    print("=" * 60)
    print("Camera: FACING the person (front view)")
    print("")
    print("  1. Click on the person to LOCK")
    print("  2. Press SPACE to start recording")
    print("  3. Person walks from ~8m toward camera to ~3m")
    print("  4. Press ENTER to stop and save")
    print("")
    print("  RIGHT-CLICK  = deselect person")
    print("  Q            = quit")
    print("=" * 60 + "\n")

    fps_start = time.time()
    fps_count = 0
    current_fps = 0
    capture_errors = 0
    yolo_frame_counter = 0

    # ── Helper functions ──────────────────────────────────────────
    def detect_persons(img: np.ndarray) -> List[PersonBBox]:
        results = yolo(img, classes=[0], conf=yolo_conf, verbose=False)
        persons = []
        for r in results:
            for i, box in enumerate(r.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                persons.append(PersonBBox(
                    id=i, x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=conf,
                    center_x=(x1 + x2) // 2,
                    center_y=(y1 + y2) // 2,
                ))
        return persons

    def find_by_proximity(persons: List[PersonBBox]) -> Optional[PersonBBox]:
        if selected_person is None:
            return None
        best, min_d = None, float('inf')
        for p in persons:
            d = np.sqrt((p.center_x - selected_person.center_x) ** 2 +
                        (p.center_y - selected_person.center_y) ** 2)
            if d < min_d and d < LOCK_TOLERANCE:
                min_d = d
                best = p
        return best

    def draw_selection(img, persons):
        h, w = img.shape[:2]
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)

        cv2.rectangle(img, (0, 0), (w, 60), (40, 40, 40), -1)
        cv2.putText(img, "WALKING SPEED - Click on the person to lock",
                    (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, f"Detected {len(persons)} person(s) | Q=quit",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (200, 200, 200), 1, cv2.LINE_AA)

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
                  (255, 255, 0), (255, 0, 255), (0, 255, 255)]
        for i, p in enumerate(persons):
            c = colors[i % len(colors)]
            cv2.rectangle(img, (p.x1, p.y1), (p.x2, p.y2), c, 3)
            label = f"Person {i + 1}"
            tw, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(img, (p.x1, p.y1 - 28),
                          (p.x1 + tw + 10, p.y1), c, -1)
            cv2.putText(img, label, (p.x1 + 5, p.y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(img, "CLICK", (p.center_x - 30, p.center_y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)
            cv2.putText(img, "TO SELECT", (p.center_x - 50, p.center_y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)

        if not persons:
            cv2.putText(img, "No persons detected - enter the frame",
                        (w // 2 - 200, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)
        return img

    def draw_tracking_hud(img):
        h, w = img.shape[:2]
        if selected_person:
            p = selected_person
            cv2.rectangle(img, (p.x1, p.y1), (p.x2, p.y2), (0, 255, 0), 3)
            cv2.putText(img, "LOCKED", (p.x1, p.y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, img, 0.35, 0, img)

        if recording:
            status = f"● REC  Frame {frame_count}"
            sc = (0, 0, 255)
            if frame_count % 30 < 15:
                cv2.circle(img, (25, 30), 10, (0, 0, 255), -1)
        else:
            status = "SELECTED — Press SPACE to start recording"
            sc = (0, 255, 0)

        cv2.putText(img, status, (45, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, sc, 2, cv2.LINE_AA)

        if not recording:
            cv2.putText(img, "SPACE: start | RIGHT-CLICK: deselect | Q: quit",
                        (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        (160, 160, 160), 1)
        else:
            cv2.putText(img, "ENTER: stop & save | RIGHT-CLICK: deselect | Q: quit",
                        (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        (160, 160, 160), 1)
        return img

    # ── Main loop ─────────────────────────────────────────────────
    try:
        while True:
            try:
                capture = k4a.get_capture()
            except Exception:
                capture_errors += 1
                if capture_errors > 20:
                    print("[ERROR] Too many capture errors, stopping.")
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

            color_bgr = capture.color[:, :, :3]
            orig_h, orig_w = color_bgr.shape[:2]
            scale_x = orig_w / DISPLAY_W
            scale_y = orig_h / DISPLAY_H

            display = cv2.resize(color_bgr, (DISPLAY_W, DISPLAY_H))
            timestamp = now - start_time

            # YOLO every N frames
            yolo_frame_counter += 1
            if yolo_frame_counter % YOLO_EVERY_N == 1 or not detected_persons:
                detected_persons = detect_persons(display)

            if selection_mode:
                display = draw_selection(display, detected_persons)

                if mouse_click_pos:
                    cx, cy = mouse_click_pos
                    mouse_click_pos = None
                    print(f"  [CLICK CHECK] ({cx},{cy}) vs {len(detected_persons)} persons")
                    for p in detected_persons:
                        print(f"    Person {p.id}: bbox=({p.x1},{p.y1})-({p.x2},{p.y2})", end="")
                        if p.x1 <= cx <= p.x2 and p.y1 <= cy <= p.y2:
                            selected_person = p
                            selection_mode = False
                            print(" → HIT!")
                            print(f"[WS] ✓ Locked Person {p.id + 1}")
                            break
                        else:
                            print(" → miss")
            else:
                matched = find_by_proximity(detected_persons)
                if matched:
                    selected_person = matched

                display = draw_tracking_hud(display)

                # Record
                if recording:
                    if video_writer is None:
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        video_writer = cv2.VideoWriter(
                            video_path, fourcc, 30,
                            (orig_w, orig_h),
                        )

                    video_writer.write(color_bgr)

                    # Save tracking centroid
                    td = {
                        'frame': frame_count,
                        'timestamp': round(timestamp, 4),
                    }
                    if selected_person:
                        td['centroid_x'] = int(selected_person.center_x * scale_x)
                        td['centroid_y'] = int(selected_person.center_y * scale_y)
                        td['bbox'] = [
                            int(selected_person.x1 * scale_x),
                            int(selected_person.y1 * scale_y),
                            int(selected_person.x2 * scale_x),
                            int(selected_person.y2 * scale_y),
                        ]
                    tracking_data.append(td)
                    frame_count += 1

            # FPS
            cv2.putText(display, f"FPS: {current_fps}",
                        (DISPLAY_W - 100, DISPLAY_H - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(' ') and not recording and not selection_mode:
                if selected_person is not None:
                    recording = True
                    print("[WS] Recording started!")
                else:
                    print("[WS] Select a person first!")
            elif key == 13:  # ENTER
                break
            elif key == ord('q') or key == ord('Q'):
                break

    except KeyboardInterrupt:
        print("\n[WS] Interrupted")
    finally:
        # ── Save & cleanup ────────────────────────────────────────
        print("\n[WS] Saving...")

        if video_writer:
            video_writer.release()
            print(f"  Video: {video_path}")

        if tracking_data:
            with open(meta_path, 'w') as f:
                json.dump(tracking_data, f, indent=1)
            print(f"  Tracking: {meta_path} ({len(tracking_data)} frames)")

        k4a.stop()
        cv2.destroyAllWindows()

        duration = time.time() - start_time
        print(f"\n[WS] Session: {duration:.1f}s, {frame_count} frames recorded")
        if frame_count > 0 and duration > 0:
            print(f"  Effective FPS: {frame_count / duration:.1f}")

    return True


# ============================================================================
# PHASE 2: PROCESS
# ============================================================================

def phase_process(
    input_dir: str,
    yolo_model: str = "yolo11n-seg.pt",
    yolo_conf: float = 0.3,
    device: str = None,
    process_every_n: int = 1,
    max_frames: int = None,
):
    """
    Process saved video: re-detect person, estimate depth, save CSV.
    
    Reads:
        <input_dir>/video.mp4
        <input_dir>/tracking.json
    
    Saves:
        <input_dir>/depth_data.csv
        <input_dir>/annotated_video.mp4  (optional visualization)
    """
    # Lazy import core modules (only needed for process phase)
    from core.camera import VideoFileReader
    from core.tracker import PersonTracker, TrackingMetadata, match_person_by_iou
    from core.depth import CalibratedDepthEstimator
    video_path = os.path.join(input_dir, "video.mp4")
    meta_path = os.path.join(input_dir, "tracking.json")
    csv_path = os.path.join(input_dir, "depth_data.csv")
    ann_video_path = os.path.join(input_dir, "annotated_video.mp4")
    
    if not os.path.exists(video_path):
        print(f"[Process] Video not found: {video_path}")
        return False
    
    # Load tracking metadata
    metadata = None
    if os.path.exists(meta_path):
        metadata = TrackingMetadata.load(meta_path)
    else:
        print("[Process] No tracking metadata — will use largest person")
    
    # Open video
    reader = VideoFileReader(video_path)
    if not reader.open():
        return False
    
    # Initialize tracker for re-detection
    tracker = PersonTracker(
        model_path=yolo_model,
        confidence=yolo_conf,
        max_lost_frames=120,
    )
    
    # Initialize depth estimator
    depth_est = CalibratedDepthEstimator(device=device)
    if not depth_est.load_model():
        print("[Process] DepthPro failed to load! Cannot process.")
        return False
    
    # Video writer for annotated output
    ann_writer = cv2.VideoWriter(
        ann_video_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        reader.fps,
        (reader.width, reader.height),
    )
    
    # CSV setup
    csv_header = [
        'frame_number', 'timestamp_sec', 'person_detected',
        'median_depth_m', 'mean_depth_m', 'min_depth_m', 'max_depth_m',
        'std_depth_m', 'confidence', 'centroid_x', 'centroid_y',
        'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2',
    ]
    csv_rows = []
    
    processed = 0
    start_time = time.time()
    
    print(f"\n[Process] Processing {reader.total_frames} frames...")
    print("=" * 60)
    
    while not reader.is_finished:
        frame_data = reader.read()
        if frame_data.color is None:
            break
        
        if max_frames and frame_data.frame_number >= max_frames:
            break
        
        if frame_data.frame_number % process_every_n != 0:
            continue
        
        frame = frame_data.color
        
        # Re-run YOLO tracking
        result = tracker.process_frame(frame)
        
        # Match to saved person if metadata available
        target_person = None
        if metadata is not None:
            saved_bbox = metadata.get_bbox_at_frame(frame_data.frame_number)
            if saved_bbox is not None and result.persons:
                target_person = match_person_by_iou(result.persons, saved_bbox)
        
        # Fallback: use locked person or largest person
        if target_person is None:
            if result.locked_person:
                target_person = result.locked_person
            elif result.persons:
                # Use largest person by area
                target_person = max(result.persons, key=lambda p: p.area)
        
        # Build CSV row
        row = {
            'frame_number': frame_data.frame_number,
            'timestamp_sec': round(frame_data.timestamp, 4),
            'person_detected': 0,
            'median_depth_m': -1, 'mean_depth_m': -1,
            'min_depth_m': -1, 'max_depth_m': -1, 'std_depth_m': -1,
            'confidence': -1,
            'centroid_x': -1, 'centroid_y': -1,
            'bbox_x1': -1, 'bbox_y1': -1, 'bbox_x2': -1, 'bbox_y2': -1,
        }
        
        if target_person is not None:
            row['person_detected'] = 1
            row['confidence'] = round(target_person.confidence, 4)
            row['centroid_x'], row['centroid_y'] = target_person.centroid
            x1, y1, x2, y2 = target_person.bbox
            row['bbox_x1'], row['bbox_y1'] = x1, y1
            row['bbox_x2'], row['bbox_y2'] = x2, y2
            
            # Build mask and estimate depth
            h, w = frame.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            if target_person.mask_polygon is not None:
                contour = target_person.mask_polygon.reshape(-1, 1, 2)
                cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)
                # Erode mask to avoid boundary artifacts
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
                eroded = cv2.erode(mask, kernel)
                if eroded.sum() > 0:
                    mask = eroded
            
            # Run DepthPro
            depth_map, focal = depth_est.estimate(frame)
            depth_stats = depth_est.get_person_depth(depth_map, mask)
            
            if depth_stats.get('valid', False):
                row['median_depth_m'] = round(depth_stats['median_depth_m'], 4)
                row['mean_depth_m'] = round(depth_stats['mean_depth_m'], 4)
                row['min_depth_m'] = round(depth_stats['min_depth_m'], 4)
                row['max_depth_m'] = round(depth_stats['max_depth_m'], 4)
                row['std_depth_m'] = round(depth_stats['std_depth_m'], 4)
            
            # Annotate frame
            ann_frame = frame.copy()
            cv2.rectangle(ann_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            depth_label = f"{row['median_depth_m']:.2f}m"
            cv2.putText(ann_frame, depth_label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            # Info bar
            cv2.rectangle(ann_frame, (5, 5), (420, 70), (0, 0, 0), -1)
            cv2.putText(ann_frame,
                        f"Frame: {frame_data.frame_number} | "
                        f"Time: {frame_data.timestamp:.2f}s | "
                        f"Depth: {depth_label}",
                        (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            
            ann_writer.write(ann_frame)
        else:
            ann_writer.write(frame)
        
        csv_rows.append(row)
        processed += 1
        
        # Progress
        if processed % 5 == 0:
            elapsed = time.time() - start_time
            fps_actual = processed / elapsed if elapsed > 0 else 0
            depth_str = (f"{row['median_depth_m']:.2f}m"
                         if row['person_detected'] else "N/A")
            eta = (reader.total_frames - frame_data.frame_number) / max(fps_actual, 0.1)
            print(f"  Frame {frame_data.frame_number:5d}/{reader.total_frames} | "
                  f"Depth: {depth_str:8s} | "
                  f"Speed: {fps_actual:.1f} fps | "
                  f"ETA: {eta:.0f}s", end='\r')
    
    # Save CSV
    with open(csv_path, 'w', newline='') as f:
        writer_csv = csv.DictWriter(f, fieldnames=csv_header)
        writer_csv.writeheader()
        writer_csv.writerows(csv_rows)
    
    ann_writer.release()
    reader.close()
    
    # Summary
    elapsed = time.time() - start_time
    valid_depths = [r['median_depth_m'] for r in csv_rows if r['median_depth_m'] > 0]
    
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"  Frames processed: {processed}")
    print(f"  Time: {elapsed:.1f}s ({processed / elapsed:.1f} fps)")
    print(f"  Frames with valid depth: {len(valid_depths)}/{processed}")
    if valid_depths:
        print(f"  Depth range: {min(valid_depths):.2f}m — {max(valid_depths):.2f}m")
    print(f"\n  CSV:   {csv_path}")
    print(f"  Video: {ann_video_path}")
    
    return True


# ============================================================================
# PHASE 3: ANALYZE
# ============================================================================

def phase_analyze(
    input_dir: str,
    sg_window: int = 11,
    sg_order: int = 3,
    speed_threshold: float = 0.2,
    min_walk_duration: float = 1.0,
    edge_trim: float = 0.10,
    show_plot: bool = True,
    save_plot: bool = True,
):
    """
    Analyze depth CSV to compute walking speed.
    
    Reads:
        <input_dir>/depth_data.csv
    
    Saves:
        <input_dir>/walking_speed_result.json
        <input_dir>/walking_speed_plot.png
    
    Returns:
        Dict with speed, distance, duration, clinical assessment
    """
    from scipy.signal import savgol_filter
    
    csv_path = os.path.join(input_dir, "depth_data.csv")
    result_path = os.path.join(input_dir, "walking_speed_result.json")
    plot_path = os.path.join(input_dir, "walking_speed_plot.png")
    
    if not os.path.exists(csv_path):
        print(f"[Analyze] CSV not found: {csv_path}")
        return None
    
    # Load data
    import pandas as pd
    df = pd.read_csv(csv_path)
    
    # Filter valid frames
    valid = df[df['median_depth_m'] > 0].copy()
    if len(valid) < 10:
        print(f"[Analyze] Not enough valid depth frames ({len(valid)})")
        return None
    
    timestamps = valid['timestamp_sec'].values
    depths = valid['median_depth_m'].values
    
    print(f"\n[Analyze] Loaded {len(valid)} valid depth frames")
    print(f"  Time range:  {timestamps[0]:.2f}s — {timestamps[-1]:.2f}s")
    print(f"  Depth range: {depths.min():.2f}m — {depths.max():.2f}m")
    
    # ── Savitzky-Golay smoothing ──────────────────────────────────
    wl = min(sg_window, len(depths) if len(depths) % 2 == 1 else len(depths) - 1)
    if wl < 5:
        wl = 5  # Minimum window
    
    depth_smooth = savgol_filter(depths, wl, sg_order, mode='nearest')
    
    dt = np.median(np.diff(timestamps))
    velocity = savgol_filter(depths, wl, sg_order, deriv=1, delta=dt, mode='nearest')
    
    # ── Walk boundary detection ───────────────────────────────────
    # Person approaches → depth decreases → velocity is negative
    approach_speed = -velocity  # Positive when approaching
    is_walking = approach_speed > speed_threshold
    
    # Find contiguous walking segments
    segments = []
    in_seg, seg_start = False, 0
    for i in range(len(is_walking)):
        if is_walking[i] and not in_seg:
            seg_start, in_seg = i, True
        elif not is_walking[i] and in_seg:
            if timestamps[i - 1] - timestamps[seg_start] >= min_walk_duration:
                segments.append((seg_start, i - 1))
            in_seg = False
    if in_seg and timestamps[-1] - timestamps[seg_start] >= min_walk_duration:
        segments.append((seg_start, len(is_walking) - 1))
    
    if not segments:
        print("[Analyze] WARNING: No walking segment detected!")
        print("  Try lowering --speed-threshold or check depth data quality")
        # Use full data as fallback
        si, ei = 0, len(depths) - 1
    else:
        # Select longest segment
        si, ei = max(segments, key=lambda x: x[1] - x[0])
        # Trim edges (exclude acceleration/deceleration)
        trim_n = int((ei - si) * edge_trim)
        si, ei = si + trim_n, ei - trim_n
    
    # ── Calculate walking speed ───────────────────────────────────
    distance = abs(depth_smooth[si] - depth_smooth[ei])
    duration = timestamps[ei] - timestamps[si]
    speed = distance / duration if duration > 0 else 0
    
    # Clinical assessment
    if speed >= 1.0:
        assessment = "NORMAL"
        risk_level = "LOW"
    elif speed >= 0.8:
        assessment = "BELOW NORMAL"
        risk_level = "MODERATE"
    elif speed >= 0.6:
        assessment = "FRAILTY RISK"
        risk_level = "HIGH"
    else:
        assessment = "SEVERE FRAILTY RISK"
        risk_level = "VERY HIGH"
    
    result = {
        'walking_speed_ms': round(speed, 3),
        'distance_m': round(distance, 3),
        'duration_s': round(duration, 3),
        'start_depth_m': round(float(depth_smooth[si]), 3),
        'end_depth_m': round(float(depth_smooth[ei]), 3),
        'assessment': assessment,
        'risk_level': risk_level,
        'walk_start_time': round(float(timestamps[si]), 3),
        'walk_end_time': round(float(timestamps[ei]), 3),
        'total_frames_analyzed': len(valid),
        'sg_window': wl,
        'sg_order': sg_order,
    }
    
    # Print results
    print("\n" + "=" * 60)
    print("WALKING SPEED TEST RESULTS")
    print("=" * 60)
    print(f"  Distance covered:  {distance:.2f} m")
    print(f"  Duration:          {duration:.2f} s")
    print(f"  Walking speed:     {speed:.3f} m/s")
    print(f"  Depth range:       {depth_smooth[si]:.2f}m → {depth_smooth[ei]:.2f}m")
    print(f"  Time range:        {timestamps[si]:.2f}s → {timestamps[ei]:.2f}s")
    print(f"\n  Assessment:        {assessment}")
    print(f"  Risk level:        {risk_level}")
    print("=" * 60)
    
    # Save result JSON
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n  Result saved: {result_path}")
    
    # ── Plot ──────────────────────────────────────────────────────
    if show_plot or save_plot:
        try:
            import matplotlib
            if save_plot and not show_plot:
                matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
            fig.suptitle("Walking Speed Test Analysis", fontsize=14, fontweight='bold')
            
            # Panel 1: Depth vs time
            ax = axes[0]
            ax.plot(timestamps, depths, 'b', alpha=0.3, label='Raw depth')
            ax.plot(timestamps, depth_smooth, 'b', lw=2, label='Smoothed')
            ax.axvline(timestamps[si], color='green', ls='--', lw=2, label='Walk start')
            ax.axvline(timestamps[ei], color='red', ls='--', lw=2, label='Walk end')
            ax.axhspan(depth_smooth[ei], depth_smooth[si], alpha=0.1, color='blue')
            ax.set_ylabel('Depth (m)')
            ax.legend(loc='upper right')
            ax.set_title('Person Distance from Camera')
            
            # Panel 2: Approach speed vs time
            ax = axes[1]
            ax.plot(timestamps, approach_speed, 'purple', lw=1.5)
            ax.axhline(speed_threshold, color='orange', ls=':', label=f'Threshold ({speed_threshold} m/s)')
            ax.fill_between(timestamps, approach_speed, 0,
                            where=is_walking, alpha=0.2, color='green', label='Walking')
            ax.axvline(timestamps[si], color='green', ls='--', lw=2)
            ax.axvline(timestamps[ei], color='red', ls='--', lw=2)
            ax.set_ylabel('Approach Speed (m/s)')
            ax.legend(loc='upper right')
            ax.set_title('Instantaneous Speed')
            
            # Panel 3: Speed profile with clinical thresholds
            ax = axes[2]
            walk_ts = timestamps[si:ei + 1]
            walk_speed = approach_speed[si:ei + 1]
            ax.fill_between(walk_ts, walk_speed, alpha=0.3, color='blue')
            ax.plot(walk_ts, walk_speed, 'b', lw=1.5)
            ax.axhline(speed, color='blue', ls='-', lw=3, label=f'Average: {speed:.3f} m/s')
            ax.axhline(1.0, color='green', ls=':', lw=2, label='Normal (≥1.0)')
            ax.axhline(0.8, color='orange', ls=':', lw=2, label='Caution (0.8)')
            ax.axhline(0.6, color='red', ls=':', lw=2, label='Frailty (<0.6)')
            ax.set_ylabel('Speed (m/s)')
            ax.set_xlabel('Time (s)')
            ax.legend(loc='upper right')
            ax.set_title(f'Walking Speed Profile — {assessment} ({speed:.3f} m/s)')
            
            plt.tight_layout()
            
            if save_plot:
                plt.savefig(plot_path, dpi=150, bbox_inches='tight')
                print(f"  Plot saved: {plot_path}")
            if show_plot:
                plt.show()
            plt.close()
            
        except ImportError:
            print("  [Plot skipped — matplotlib not installed]")
    
    return result


# ============================================================================
# FULL PIPELINE
# ============================================================================

def full_pipeline(output_dir: str, **kwargs):
    """Run all three phases sequentially."""
    print("\n" + "#" * 60)
    print("# WALKING SPEED TEST — FULL PIPELINE")
    print("#" * 60)

    # Phase 1
    print("\n>>> PHASE 1: RECORD")
    success = phase_record(output_dir=output_dir)
    if not success:
        return

    # Phase 2
    print("\n>>> PHASE 2: PROCESS")
    success = phase_process(input_dir=output_dir)
    if not success:
        return

    # Phase 3
    print("\n>>> PHASE 3: ANALYZE")
    result = phase_analyze(
        input_dir=output_dir,
        show_plot=kwargs.get('show_plot', True),
    )

    return result


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Walking Speed Test — Frailty Assessment System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='phase', help='Test phase')
    
    # ── Record ────────────────────────────────────────────────────
    p_rec = subparsers.add_parser('record', help='Record video from Azure Kinect')
    p_rec.add_argument('--output', '-o', type=str, required=True,
                       help='Output directory name')

    # ── Process ───────────────────────────────────────────────────
    p_proc = subparsers.add_parser('process', help='Process video for depth')
    p_proc.add_argument('--input', '-i', type=str, required=True,
                        help='Input directory (from record phase)')
    p_proc.add_argument('--yolo-model', type=str, default='yolo11n-seg.pt')
    p_proc.add_argument('--yolo-conf', type=float, default=0.3)
    p_proc.add_argument('--device', type=str, default=None,
                        choices=['cuda', 'mps', 'cpu'])
    p_proc.add_argument('--every-n', type=int, default=1,
                        help='Process every N frames')
    p_proc.add_argument('--max-frames', type=int, default=None)

    # ── Analyze ───────────────────────────────────────────────────
    p_ana = subparsers.add_parser('analyze', help='Analyze depth data for speed')
    p_ana.add_argument('--input', '-i', type=str, required=True,
                       help='Input directory (with depth_data.csv)')
    p_ana.add_argument('--sg-window', type=int, default=11,
                       help='Savitzky-Golay window (odd, default 11)')
    p_ana.add_argument('--sg-order', type=int, default=3)
    p_ana.add_argument('--speed-threshold', type=float, default=0.2,
                       help='Min approach speed to count as walking (m/s)')
    p_ana.add_argument('--no-plot', action='store_true')

    # ── Full ──────────────────────────────────────────────────────
    p_full = subparsers.add_parser('full', help='Run all 3 phases')
    p_full.add_argument('--output', '-o', type=str, required=True)

    args = parser.parse_args()

    if args.phase is None:
        parser.print_help()
        return

    if args.phase == 'record':
        phase_record(output_dir=args.output)
    
    elif args.phase == 'process':
        phase_process(
            input_dir=args.input,
            yolo_model=args.yolo_model,
            yolo_conf=args.yolo_conf,
            device=args.device,
            process_every_n=args.every_n,
            max_frames=args.max_frames,
        )
    
    elif args.phase == 'analyze':
        phase_analyze(
            input_dir=args.input,
            sg_window=args.sg_window,
            sg_order=args.sg_order,
            speed_threshold=args.speed_threshold,
            show_plot=not args.no_plot,
        )
    
    elif args.phase == 'full':
        full_pipeline(output_dir=args.output)


if __name__ == '__main__':
    main()
