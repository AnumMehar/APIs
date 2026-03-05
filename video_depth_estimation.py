#!/usr/bin/env python3
"""
Video Depth Estimation Pipeline
================================
Processes video frame-by-frame, detecting person and estimating calibrated depth.
Saves results to CSV.

Author: Kashif (NCAI/NCRA NUST)
Usage: python3 video_depth_estimation.py --video video.mp4 --output results.csv
"""

import argparse
import csv
import json
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Tuple, Dict, Optional

import cv2
import numpy as np

warnings.filterwarnings('ignore')

try:
    import torch
except ImportError:
    print("Error: PyTorch not installed.")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    print("Error: ultralytics not installed. Run: pip install ultralytics")
    sys.exit(1)

from PIL import Image


# ============================================================================
# PERSON DETECTOR (from person_detection_mask.py)
# ============================================================================

class PersonDetector:
    """Handles person detection and mask extraction using YOLOv8-seg."""
    
    def __init__(self, model_path: str = "yolov8n-seg.pt", confidence: float = 0.5):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.person_class_id = 0  # COCO class ID for 'person'
        
    def detect_people(self, image: np.ndarray) -> dict:
        """Detect all people in the image."""
        results = self.model(image, conf=self.confidence, classes=[self.person_class_id], verbose=False)
        
        detections = {
            'people': [],
            'image_shape': image.shape[:2]
        }
        
        if len(results) == 0 or results[0].masks is None:
            return detections
            
        result = results[0]
        masks = result.masks.data.cpu().numpy() if result.masks is not None else []
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else []
        confs = result.boxes.conf.cpu().numpy() if result.boxes is not None else []
        
        for i, (mask, box, conf) in enumerate(zip(masks, boxes, confs)):
            # Resize mask to original image size
            mask_resized = cv2.resize(
                mask.astype(np.float32), 
                (image.shape[1], image.shape[0]), 
                interpolation=cv2.INTER_LINEAR
            )
            binary_mask = (mask_resized > 0.5).astype(np.uint8)
            
            person_data = {
                'id': i,
                'bbox': box.tolist(),
                'confidence': float(conf),
                'mask': binary_mask,
                'area': int(np.sum(binary_mask)),
                'centroid': self._calculate_centroid(binary_mask)
            }
            detections['people'].append(person_data)
        
        # Sort by area (largest first)
        detections['people'].sort(key=lambda x: x['area'], reverse=True)
        for i, person in enumerate(detections['people']):
            person['id'] = i
            
        return detections
    
    def _calculate_centroid(self, mask: np.ndarray) -> tuple:
        moments = cv2.moments(mask)
        if moments['m00'] > 0:
            cx = int(moments['m10'] / moments['m00'])
            cy = int(moments['m01'] / moments['m00'])
            return (cx, cy)
        return (0, 0)


# Resolve project root (parent of tests/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

# Candidate checkpoint paths (first valid one wins)
_CKPT_CANDIDATES = [
    os.path.join(_PROJECT_ROOT, "models", "depth_pro.pt"),
    os.path.join(os.path.expanduser("~"), "Documents", "Kashif",
                 "ml-depth-pro-main", "checkpoints", "depth_pro.pt"),
]

def _find_depth_pro_ckpt() -> str:
    """Return the first valid (>1 MB) depth_pro.pt found, or the first candidate."""
    for p in _CKPT_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1_000_000:
            return p
    # Fall back to first candidate (will fail later with a clear message)
    return _CKPT_CANDIDATES[0]

_DEFAULT_DEPTH_PRO_CKPT = _find_depth_pro_ckpt()


class CalibratedDepthPro:
    """DepthPro with polynomial calibration for accurate metric depth."""
    
    # Calibration data from your measurements
    CALIB_RAW = np.array([0.882, 1.685, 2.479, 3.132, 3.775, 4.691, 5.008, 5.612, 6.326, 6.880])
    CALIB_ACTUAL = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    
    def __init__(self, device: str = None, poly_degree: int = 2,
                 checkpoint_path: str = None):
        self.device = self._get_device(device)
        self.model = None
        self.transform = None
        self.poly_degree = poly_degree
        self.checkpoint_path = checkpoint_path or _DEFAULT_DEPTH_PRO_CKPT
        
        # Fit polynomial calibration
        self.poly_coeffs = np.polyfit(self.CALIB_RAW, self.CALIB_ACTUAL, poly_degree)
        self.poly_func = np.poly1d(self.poly_coeffs)
        
    def _get_device(self, device: str = None) -> torch.device:
        if device:
            return torch.device(device)
        if torch.cuda.is_available():
            return torch.device('cuda')
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return torch.device('mps')
        else:
            return torch.device('cpu')
    
    def load_model(self) -> bool:
        """Load DepthPro model from local checkpoint."""
        try:
            import depth_pro
            from depth_pro.depth_pro import DepthProConfig
            
            # Verify checkpoint exists
            if not os.path.isfile(self.checkpoint_path):
                print(f"ERROR: DepthPro checkpoint not found at: {self.checkpoint_path}")
                print(f"  Please place depth_pro.pt in the models/ directory.")
                return False
            
            ckpt_size = os.path.getsize(self.checkpoint_path)
            if ckpt_size < 1_000_000:  # < 1 MB is suspicious
                print(f"WARNING: Checkpoint file is only {ckpt_size} bytes.")
                print(f"  A valid depth_pro.pt should be ~400 MB+.")
                print(f"  This may be a Git LFS pointer or incomplete download.")
            
            print(f"Loading DepthPro model from: {self.checkpoint_path}")
            
            # Create config pointing to our local checkpoint
            config = DepthProConfig(
                patch_encoder_preset="dinov2l16_384",
                image_encoder_preset="dinov2l16_384",
                checkpoint_uri=self.checkpoint_path,
                decoder_features=256,
                use_fov_head=True,
                fov_encoder_preset="dinov2l16_384",
            )
            
            self.model, self.transform = depth_pro.create_model_and_transforms(
                config=config,
                device=self.device,
                precision=torch.float16 if self.device.type == 'cuda' else torch.float32
            )
            self.model.eval()
            print(f"DepthPro loaded on {self.device}")
            return True
            
        except ImportError:
            print("ERROR: depth_pro package not found!")
            print("  Install with: pip install depth_pro")
            return False
        except Exception as e:
            print(f"ERROR loading DepthPro model: {e}")
            return False
    
    def estimate_depth(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """Estimate calibrated metric depth."""
        import depth_pro
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        image_tensor = self.transform(pil_image)
        
        with torch.no_grad():
            prediction = self.model.infer(image_tensor, f_px=None)
        
        raw_depth = prediction['depth'].cpu().numpy().squeeze()
        calibrated_depth = self.poly_func(raw_depth)
        
        focal_length = prediction.get('focallength_px', None)
        if focal_length is not None:
            focal_length = focal_length.cpu().numpy().item()
        
        return calibrated_depth, focal_length
    
    def get_person_depth(self, depth_map: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
        """Extract depth statistics for masked region."""
        binary_mask = (mask > 127).astype(bool) if mask.max() > 1 else mask.astype(bool)
        
        if depth_map.shape != mask.shape:
            depth_map = cv2.resize(depth_map, (mask.shape[1], mask.shape[0]), 
                                   interpolation=cv2.INTER_LINEAR)
        
        person_depths = depth_map[binary_mask]
        
        if len(person_depths) == 0:
            return {'metric_depth_m': -1, 'valid': False}
        
        valid_depths = person_depths[
            (person_depths > 0) & 
            (person_depths < 100) & 
            (~np.isnan(person_depths))
        ]
        
        if len(valid_depths) == 0:
            return {'metric_depth_m': -1, 'valid': False}
        
        return {
            'metric_depth_m': float(np.median(valid_depths)),
            'mean_depth_m': float(np.mean(valid_depths)),
            'min_depth_m': float(np.min(valid_depths)),
            'max_depth_m': float(np.max(valid_depths)),
            'std_depth_m': float(np.std(valid_depths)),
            'valid_pixel_count': int(len(valid_depths)),
            'valid': True
        }


class VideoDepthProcessor:
    """Process video frame-by-frame for person detection and depth estimation."""

    # Proximity tracking constants
    LOCK_TOLERANCE = 200      # Max centroid distance (pixels) to re-match
    AREA_RATIO_LOW = 0.3      # Reject if area < 30% of locked
    AREA_RATIO_HIGH = 3.0     # Reject if area > 300% of locked

    # Display size for interactive window
    DISPLAY_W = 1280
    DISPLAY_H = 720
    YOLO_EVERY_N = 3  # Run YOLO every N-th frame for speed

    def __init__(
        self,
        yolo_model: str = "yolov8n-seg.pt",
        yolo_conf: float = 0.5,
        device: str = None,
        person_selection: str = "largest",  # "largest", "first", or person index
        interactive: bool = False,  # click-to-select with live preview
        checkpoint_path: str = None  # path to depth_pro.pt
    ):
        self.person_detector = PersonDetector(model_path=yolo_model, confidence=yolo_conf)
        self.depth_estimator = CalibratedDepthPro(device=device, checkpoint_path=checkpoint_path)
        self.person_selection = person_selection
        self.interactive = interactive

        # Locked-person tracking state
        self._locked = False
        self._locked_centroid = None   # (cx, cy)
        self._locked_area = 0.0
        self._locked_bbox = None       # [x1, y1, x2, y2]

        # Mouse state for interactive mode
        self._mouse_click_pos = None   # (x, y) of last left-click
        self._right_clicked = False    # flag for right-click deselect
        
    def load_models(self) -> bool:
        """Load all models."""
        print("Loading YOLO model...")
        # YOLO loads on first use
        return self.depth_estimator.load_model()
    
    def select_person(self, detections: dict) -> Optional[dict]:
        """Select which person to track based on selection strategy."""
        if len(detections['people']) == 0:
            return None

        # If a person is locked, use proximity matching
        if self._locked and self._locked_centroid is not None:
            matched = self._match_by_proximity(detections['people'])
            if matched is not None:
                # Update lock state with matched person
                self._locked_centroid = matched['centroid']
                area = matched['area']
                self._locked_area = 0.9 * self._locked_area + 0.1 * area
                self._locked_bbox = matched['bbox']
                return matched
            # Person lost this frame — return None (no fallback to largest)
            return None

        if self.person_selection == "largest":
            return detections['people'][0]
        elif self.person_selection == "first":
            return detections['people'][0]
        elif isinstance(self.person_selection, int):
            idx = self.person_selection
            if idx < len(detections['people']):
                return detections['people'][idx]
            return detections['people'][0]
        else:
            return detections['people'][0]

    # ── Interactive click-to-select ────────────────────────────────

    def _interactive_select(self, video_path: str, scale_x: float, scale_y: float) -> bool:
        """
        Show first frame with detected persons. User clicks to lock one.
        Returns True if a person was selected, False if cancelled.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("Error: Could not open video for selection.")
            return False

        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("Error: Could not read first frame.")
            return False

        # Detect people on first frame
        detections = self.person_detector.detect_people(frame)
        people = detections['people']

        if len(people) == 0:
            print("No people detected in first frame — falling back to 'largest' mode.")
            return False

        if len(people) == 1:
            # Only one person, auto-select
            self._lock_person(people[0])
            print(f"[SELECT] Only 1 person detected — auto-locked.")
            return True

        # Build selection image
        display = cv2.resize(frame, (self.DISPLAY_W, self.DISPLAY_H))
        h, w = display.shape[:2]

        # Dim background
        overlay = display.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.25, display, 0.75, 0, display)

        # Banner
        cv2.rectangle(display, (0, 0), (w, 60), (40, 40, 40), -1)
        cv2.putText(display, "WALKING SPEED - Click on the person to track",
                    (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(display, f"Detected {len(people)} person(s) | Q=cancel",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (200, 200, 200), 1, cv2.LINE_AA)

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
                  (255, 255, 0), (255, 0, 255), (0, 255, 255)]

        bboxes = []  # store for click testing
        for i, p in enumerate(people):
            c = colors[i % len(colors)]
            x1, y1, x2, y2 = map(int, p['bbox'])
            # Scale bbox to display coords
            dx1, dy1 = int(x1 / scale_x), int(y1 / scale_y)
            dx2, dy2 = int(x2 / scale_x), int(y2 / scale_y)
            bboxes.append((dx1, dy1, dx2, dy2, i))
            cv2.rectangle(display, (dx1, dy1), (dx2, dy2), c, 3)

            label = f"Person {i + 1}"
            lw_s, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(display, (dx1, dy1 - 28), (dx1 + lw_s[0] + 10, dy1), c, -1)
            cv2.putText(display, label, (dx1 + 5, dy1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cx, cy = p['centroid']
            dcx, dcy = int(cx / scale_x), int(cy / scale_y)
            cv2.putText(display, "CLICK", (dcx - 30, dcy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)
            cv2.putText(display, "TO SELECT", (dcx - 50, dcy + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)

        # Mouse callback state
        selected_idx = [None]  # mutable container for callback

        def on_mouse(event, mx, my, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                for (bx1, by1, bx2, by2, idx) in bboxes:
                    if bx1 <= mx <= bx2 and by1 <= my <= by2:
                        selected_idx[0] = idx
                        break

        win_name = "Select Person for Walking Speed Test"
        cv2.namedWindow(win_name, cv2.WINDOW_AUTOSIZE)
        cv2.setWindowProperty(win_name, cv2.WND_PROP_TOPMOST, 1)
        cv2.setMouseCallback(win_name, on_mouse)
        cv2.imshow(win_name, display)

        print("[SELECT] Waiting for click on a person...")

        while True:
            key = cv2.waitKey(50) & 0xFF
            if key == ord('q') or key == ord('Q') or key == 27:
                cv2.destroyWindow(win_name)
                print("[SELECT] Cancelled by user.")
                return False
            if selected_idx[0] is not None:
                break

        cv2.destroyWindow(win_name)

        idx = selected_idx[0]
        self._lock_person(people[idx])
        print(f"[SELECT] Locked Person {idx + 1} "
              f"(centroid={self._locked_centroid}, area={self._locked_area:.0f})")
        return True

    def _draw_tracking_overlay(self, display: np.ndarray, people: list,
                                frame_result: dict, frame_idx: int,
                                timestamp: float, scale_x: float,
                                scale_y: float) -> np.ndarray:
        """Draw tracking UI: locked person highlighted, depth info, other persons dim."""
        h, w = display.shape[:2]

        # Draw all person bboxes
        for p in people:
            x1, y1, x2, y2 = map(int, p['bbox'])
            dx1, dy1 = int(x1 / scale_x), int(y1 / scale_y)
            dx2, dy2 = int(x2 / scale_x), int(y2 / scale_y)

            # Check if this is the locked person
            is_locked = False
            if self._locked_centroid is not None:
                dist = np.sqrt((p['centroid'][0] - self._locked_centroid[0]) ** 2 +
                               (p['centroid'][1] - self._locked_centroid[1]) ** 2)
                if dist < self.LOCK_TOLERANCE:
                    is_locked = True

            if is_locked:
                cv2.rectangle(display, (dx1, dy1), (dx2, dy2), (0, 255, 0), 3)
                cv2.putText(display, "LOCKED", (dx1, dy1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                # Depth label on locked person
                if frame_result['person_detected'] and frame_result['metric_depth_m'] > 0:
                    depth_label = f"{frame_result['metric_depth_m']:.2f}m"
                    cv2.putText(display, depth_label, (dx1, dy2 + 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.rectangle(display, (dx1, dy1), (dx2, dy2), (80, 80, 80), 1)

        # Top banner
        overlay = display.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, display, 0.35, 0, display)

        # Status text
        if frame_result['person_detected']:
            depth_str = f"{frame_result['metric_depth_m']:.2f}m" if frame_result['metric_depth_m'] > 0 else "estimating..."
            banner = f"TRACKING — Depth: {depth_str} | Frame {frame_idx}"
            cv2.putText(display, banner, (15, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2, cv2.LINE_AA)
        else:
            cv2.putText(display, "Person lost — searching...", (15, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 165, 255), 2, cv2.LINE_AA)

        # Bottom instructions
        cv2.putText(display, "RIGHT-CLICK: deselect | Q: quit & save",
                    (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (160, 160, 160), 1)

        return display

    def _lock_person(self, person: dict):
        """Lock onto a detected person."""
        self._locked = True
        self._locked_centroid = person['centroid']
        self._locked_area = float(person['area'])
        self._locked_bbox = person['bbox']

    # ── Proximity matching ────────────────────────────────────────

    def _match_by_proximity(self, people: list) -> Optional[dict]:
        """
        Find the person closest to our locked selection.
        Rejects candidates whose bbox area differs too much.
        """
        if self._locked_centroid is None:
            return None

        lcx, lcy = self._locked_centroid
        best, min_dist = None, float('inf')

        for p in people:
            cx, cy = p['centroid']
            dist = np.sqrt((cx - lcx) ** 2 + (cy - lcy) ** 2)

            if dist >= self.LOCK_TOLERANCE:
                continue

            if self._locked_area > 0:
                area_ratio = p['area'] / self._locked_area
                if area_ratio < self.AREA_RATIO_LOW or area_ratio > self.AREA_RATIO_HIGH:
                    continue

            if dist < min_dist:
                min_dist = dist
                best = p

        return best

    # ── Frame processing ──────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> dict:
        """
        Process a single frame.

        Returns:
            Dict with depth info and detection status
        """
        result = {
            'person_detected': False,
            'metric_depth_m': -1,
            'mean_depth_m': -1,
            'min_depth_m': -1,
            'max_depth_m': -1,
            'std_depth_m': -1,
            'bbox': None,
            'centroid': None,
            'confidence': -1,
            'num_people': 0,
            'focal_length_px': -1
        }

        # Detect people
        detections = self.person_detector.detect_people(frame)
        result['num_people'] = len(detections['people'])

        if len(detections['people']) == 0:
            return result

        # Select person (uses locked tracking if available)
        person = self.select_person(detections)
        if person is None:
            return result

        result['person_detected'] = True
        result['bbox'] = person['bbox']
        result['centroid'] = person['centroid']
        result['confidence'] = person['confidence']

        # Estimate depth
        depth_map, focal_length = self.depth_estimator.estimate_depth(frame)
        result['focal_length_px'] = focal_length if focal_length else -1

        # Get person depth
        depth_stats = self.depth_estimator.get_person_depth(depth_map, person['mask'])

        if depth_stats.get('valid', False):
            result['metric_depth_m'] = depth_stats['metric_depth_m']
            result['mean_depth_m'] = depth_stats['mean_depth_m']
            result['min_depth_m'] = depth_stats['min_depth_m']
            result['max_depth_m'] = depth_stats['max_depth_m']
            result['std_depth_m'] = depth_stats['std_depth_m']

        return result
    
    def process_video(
        self,
        video_path: str,
        output_csv: str,
        output_video: str = None,
        show_progress: bool = True,
        save_every_n: int = 1,  # Process every N frames (1 = all frames)
        max_frames: int = None  # Limit frames for testing
    ) -> str:
        """
        Process entire video and save results to CSV.

        If interactive mode is enabled, shows the first frame for person selection
        before processing begins.
        """
        # Open video to get properties
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video: {video_path}")
            sys.exit(1)

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Scale factors (original → display)
        scale_x = width / self.DISPLAY_W
        scale_y = height / self.DISPLAY_H
        
        # Close to let interactive select open it cleanly
        cap.release()

        # ── Interactive person selection ───────────────────────────
        if self.interactive and not self._locked:
            selected = self._interactive_select(video_path, scale_x, scale_y)
            if not selected:
                print("No person selected — falling back to 'largest' strategy.")

        # Reopen video for actual processing
        cap = cv2.VideoCapture(video_path)

        print(f"\nVideo: {video_path}")
        print(f"Resolution: {width}x{height}")
        print(f"FPS: {fps:.2f}")
        print(f"Total frames: {total_frames}")
        print(f"Duration: {total_frames/fps:.2f} seconds")

        if max_frames:
            total_frames = min(total_frames, max_frames)
            print(f"Processing first {total_frames} frames")

        # ── Optional: Live tracking window ─────────────────────────
        win_name = None
        if self.interactive:
            win_name = "Depth Estimation Tracking"
            try:
                cv2.namedWindow(win_name, cv2.WINDOW_AUTOSIZE)
                cv2.setWindowProperty(win_name, cv2.WND_PROP_TOPMOST, 1)
            except cv2.error:
                print("[WARN] cv2 GUI unavailable — running headless.")
                win_name = None

        # Setup output video writer
        video_writer = None
        if output_video:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        # CSV header
        csv_header = [
            'frame_number',
            'timestamp_sec',
            'person_detected',
            'metric_depth_m',
            'mean_depth_m',
            'min_depth_m',
            'max_depth_m',
            'std_depth_m',
            'confidence',
            'num_people',
            'centroid_x',
            'centroid_y',
            'bbox_x1',
            'bbox_y1',
            'bbox_x2',
            'bbox_y2',
            'focal_length_px'
        ]

        # Process frames
        results = []
        frame_idx = 0
        processed_count = 0
        start_time = time.time()
        last_people = []  # cache YOLO detections
        quit_requested = False

        print(f"\nProcessing video...")
        print("=" * 60)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if max_frames and frame_idx >= max_frames:
                break

            # Skip frames if save_every_n > 1
            if frame_idx % save_every_n != 0:
                frame_idx += 1
                continue

            timestamp = frame_idx / fps

            # ── Process depth only if a person is locked (or non-interactive) ──
            frame_result = {
                'person_detected': False,
                'metric_depth_m': -1,
                'mean_depth_m': -1,
                'min_depth_m': -1,
                'max_depth_m': -1,
                'std_depth_m': -1,
                'bbox': None,
                'centroid': None,
                'confidence': -1,
                'num_people': 0,
                'focal_length_px': -1
            }
            
            # Since person detection happens inside process_frame, we'll get num_people there
            if self._locked or not self.interactive:
                frame_result = self.process_frame(frame)

            # ── Build CSV row ─────────────────────────────────────
            if self._locked or not self.interactive:
                centroid = frame_result['centroid'] or (-1, -1)
                bbox = frame_result['bbox'] or [-1, -1, -1, -1]

                row = {
                    'frame_number': frame_idx,
                    'timestamp_sec': round(timestamp, 4),
                    'person_detected': 1 if frame_result['person_detected'] else 0,
                    'metric_depth_m': round(frame_result['metric_depth_m'], 4),
                    'mean_depth_m': round(frame_result['mean_depth_m'], 4),
                    'min_depth_m': round(frame_result['min_depth_m'], 4),
                    'max_depth_m': round(frame_result['max_depth_m'], 4),
                    'std_depth_m': round(frame_result['std_depth_m'], 4),
                    'confidence': round(frame_result['confidence'], 4),
                    'num_people': frame_result['num_people'],
                    'centroid_x': centroid[0],
                    'centroid_y': centroid[1],
                    'bbox_x1': round(bbox[0], 1),
                    'bbox_y1': round(bbox[1], 1),
                    'bbox_x2': round(bbox[2], 1),
                    'bbox_y2': round(bbox[3], 1),
                    'focal_length_px': round(frame_result['focal_length_px'], 2)
                }
                results.append(row)

            # Annotate frame for video output
            if video_writer:
                annotated = self._annotate_frame(frame, frame_result, frame_idx, timestamp)
                video_writer.write(annotated)

            processed_count += 1

            # ── Live tracking window ──────────────────────────────
            if win_name is not None:
                # We need `people` for the tracking overlay. Process frame doesn't return all bboxes.
                # But we can just pass an empty list for `people` since we only care about the locked person right now, 
                # or we can mock it with the locked bbox.
                people = [{'bbox': frame_result['bbox'], 'centroid': frame_result['centroid']}] if frame_result['person_detected'] else []
                display = cv2.resize(frame, (self.DISPLAY_W, self.DISPLAY_H))

                display = self._draw_tracking_overlay(
                    display, people, frame_result, frame_idx,
                    timestamp, scale_x, scale_y)

                # FPS counter
                elapsed_so_far = time.time() - start_time
                current_fps = processed_count / elapsed_so_far if elapsed_so_far > 0 else 0
                cv2.putText(display, f"FPS: {current_fps:.1f}",
                            (self.DISPLAY_W - 120, self.DISPLAY_H - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                cv2.imshow(win_name, display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == ord('Q') or key == 27:
                    print("\n[DEPTH] Quit requested by user.")
                    quit_requested = True
                    break

            # Progress (non-interactive or console)
            if show_progress and processed_count % 10 == 0 and not self.interactive:
                elapsed = time.time() - start_time
                fps_actual = processed_count / elapsed if elapsed > 0 else 0
                eta = (total_frames - frame_idx) / fps_actual if fps_actual > 0 else 0

                depth_str = f"{frame_result['metric_depth_m']:.2f}m" if frame_result['person_detected'] else "N/A"
                print(f"Frame {frame_idx:5d}/{total_frames} | "
                      f"Depth: {depth_str:8s} | "
                      f"Speed: {fps_actual:.1f} fps | "
                      f"ETA: {eta:.0f}s", end='\r')

            frame_idx += 1

        # Cleanup
        cap.release()
        if video_writer:
            video_writer.release()
        if win_name is not None:
            cv2.destroyAllWindows()

        # Write CSV
        os.makedirs(os.path.dirname(output_csv) if os.path.dirname(output_csv) else '.', exist_ok=True)

        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_header)
            writer.writeheader()
            writer.writerows(results)

        # Summary
        elapsed = time.time() - start_time
        valid_depths = [r['metric_depth_m'] for r in results if r['metric_depth_m'] > 0]

        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Frames processed: {processed_count}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
        if elapsed > 0:
            print(f"Average speed: {processed_count/elapsed:.1f} fps")
        print(f"Frames with depth data: {len(valid_depths)}/{len(results)}")

        if valid_depths:
            print(f"\nDepth statistics:")
            print(f"  Min:  {min(valid_depths):.3f} m")
            print(f"  Max:  {max(valid_depths):.3f} m")
            print(f"  Mean: {np.mean(valid_depths):.3f} m")
            print(f"  Std:  {np.std(valid_depths):.3f} m")

        print(f"\nCSV saved to: {output_csv}")
        if output_video:
            print(f"Video saved to: {output_video}")
        print("=" * 60)

        return output_csv
    
    def _annotate_frame(self, frame: np.ndarray, result: dict, frame_idx: int, timestamp: float) -> np.ndarray:
        """Add annotations to frame for visualization."""
        annotated = frame.copy()
        
        # Draw info box
        cv2.rectangle(annotated, (10, 10), (400, 120), (0, 0, 0), -1)
        cv2.rectangle(annotated, (10, 10), (400, 120), (255, 255, 255), 2)
        
        # Frame info
        cv2.putText(annotated, f"Frame: {frame_idx} | Time: {timestamp:.2f}s", 
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        if result['person_detected']:
            # Depth info
            depth_text = f"Depth: {result['metric_depth_m']:.2f} m"
            cv2.putText(annotated, depth_text, 
                        (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.putText(annotated, f"Confidence: {result['confidence']:.2f}", 
                        (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Draw bounding box
            if result['bbox']:
                x1, y1, x2, y2 = map(int, result['bbox'])
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Depth label on box
                label = f"{result['metric_depth_m']:.2f}m"
                cv2.putText(annotated, label, (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            # Draw centroid
            if result['centroid']:
                cx, cy = result['centroid']
                cv2.circle(annotated, (cx, cy), 8, (0, 0, 255), -1)
        else:
            cv2.putText(annotated, "No person detected", 
                        (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return annotated


def main():
    parser = argparse.ArgumentParser(
        description="Process video for person detection and depth estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 video_depth_estimation.py --video video.mp4
  python3 video_depth_estimation.py --video video.mp4 --output results/depth.csv
  python3 video_depth_estimation.py --video video.mp4 --output-video annotated.mp4
  python3 video_depth_estimation.py --video video.mp4 --every-n 5
  python3 video_depth_estimation.py --video video.mp4 --interactive  # Click to select person
        """
    )

    parser.add_argument('--video', '-v', type=str, required=True,
                        help='Path to input video file')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Path to output CSV (default: <video_name>_depth.csv)')
    parser.add_argument('--output-video', type=str, default=None,
                        help='Path to output annotated video (optional)')
    parser.add_argument('--yolo-model', type=str, default='yolov8n-seg.pt',
                        help='YOLO model to use (default: yolov8n-seg.pt)')
    parser.add_argument('--yolo-conf', type=float, default=0.5,
                        help='YOLO confidence threshold (default: 0.5)')
    parser.add_argument('--device', type=str, choices=['cuda', 'mps', 'cpu'], default=None,
                        help='Device to use (auto-detected if not specified)')
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='Path to depth_pro.pt checkpoint (default: models/depth_pro.pt)')
    parser.add_argument('--every-n', type=int, default=1,
                        help='Process every N frames (default: 1 = all frames)')
    parser.add_argument('--max-frames', type=int, default=None,
                        help='Maximum frames to process (for testing)')
    parser.add_argument('--person', type=str, default='largest',
                        help='Person selection: "largest", "first", or index (default: largest)')
    parser.add_argument('--interactive', '-i', action='store_true', default=False,
                        help='Show first frame and click to select person (default: off)')

    args = parser.parse_args()

    # Validate video exists
    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    # Set default output CSV
    if args.output is None:
        video_name = Path(args.video).stem
        args.output = f"{video_name}_depth.csv"

    # Parse person selection
    person_selection = args.person
    if args.person.isdigit():
        person_selection = int(args.person)

    # Interactive mode: if --interactive flag given, enable click-to-select
    interactive = args.interactive

    # Initialize processor
    processor = VideoDepthProcessor(
        yolo_model=args.yolo_model,
        yolo_conf=args.yolo_conf,
        device=args.device,
        person_selection=person_selection,
        interactive=interactive,
        checkpoint_path=args.checkpoint
    )

    # Load models
    if not processor.load_models():
        sys.exit(1)

    # Process video
    processor.process_video(
        video_path=args.video,
        output_csv=args.output,
        output_video=args.output_video,
        save_every_n=args.every_n,
        max_frames=args.max_frames
    )


if __name__ == "__main__":
    main()
