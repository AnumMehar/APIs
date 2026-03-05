# Physical Frailty Assessment — New Laptop Setup Guide

> Complete setup instructions for deploying the **Gui_Standalone** project on a fresh Windows machine.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Software Installation](#3-software-installation)
4. [Project Setup](#4-project-setup)
5. [Folder Structure](#5-folder-structure)
6. [Test Overview](#6-test-overview)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

| Requirement         | Version / Notes                                                  |
| ------------------- | ---------------------------------------------------------------- |
| **OS**              | Windows 10 / 11 (64-bit)                                        |
| **Python**          | 3.8 – 3.11 (3.10 recommended). **Do NOT use 3.12+** (mediapipe compatibility) |
| **pip**             | Latest (`python -m pip install --upgrade pip`)                   |
| **Git** (optional)  | For cloning the repo                                             |
| **NVIDIA GPU**      | Recommended (CUDA 11.7+ for PyTorch GPU acceleration)            |

---

## 2. Hardware Requirements

| Device                       | Required For                                           |
| ---------------------------- | ------------------------------------------------------ |
| **Azure Kinect DK**          | Functional Reach, Seated Forward Bend, TUG, Standing On One Leg |
| **Any RGB camera** (webcam)  | Walking Speed (video recording only)                   |
| **Kinect v2** (Xbox One)     | Grip Strength test only (digit detection)              |

> **Note**: The Walking Speed test uses a regular webcam for recording and the DepthPro AI model for depth estimation (no depth camera needed).

---

## 3. Software Installation

### Step 1: Install Python 3.10

Download from [python.org](https://www.python.org/downloads/release/python-31011/).

During installation:
- ✅ Check **"Add Python to PATH"**
- ✅ Check **"Install pip"**

Verify:
```powershell
python --version   # Should show Python 3.10.x
pip --version
```

### Step 2: Install Azure Kinect SDK

> Required for: FRT, SFB, TUG, Standing On One Leg tests.

1. Download **Azure Kinect SDK v1.4.1** from [Microsoft](https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/develop/docs/usage.md)
2. Run the `.msi` installer
3. Add the SDK `bin` folder to your system `PATH`:
   ```
   C:\Program Files\Azure Kinect SDK v1.4.1\sdk\windows-desktop\amd64\release\bin
   ```
4. Verify installation: plug in the Azure Kinect and open **Azure Kinect Viewer** from Start Menu

### Step 3: Install Azure Kinect Body Tracking SDK (Optional)

> Required only if body tracking features are used.

1. Download from [Microsoft](https://learn.microsoft.com/en-us/azure/kinect-dk/body-sdk-download)
2. Run the `.msi` installer
3. The ONNX runtime and cuDNN files are included

### Step 4: Install NVIDIA CUDA Toolkit (Recommended)

> Needed for GPU-accelerated PyTorch / YOLO inference.

1. Download CUDA 11.7 or 11.8 from [NVIDIA](https://developer.nvidia.com/cuda-toolkit-archive)
2. Install with default options
3. Verify:
   ```powershell
   nvidia-smi
   nvcc --version
   ```

### Step 5: Install Kinect v2 SDK (Optional — Grip Strength only)

> Only needed if running the Grip Strength (digit detection) test.

1. Download **Kinect for Windows SDK 2.0** from [Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=44561)
2. Install the SDK
3. Then install the Python package:
   ```powershell
   pip install pykinect2
   ```

---

## 4. Project Setup

### Step 1: Copy the Project Folder

Copy the entire `Gui_Standalone` folder to the new laptop. The folder should contain all `.py` files, `models/`, `tests/`, and image assets.

```powershell
# Example: copy from USB drive
xcopy "E:\Gui_Standalone" "C:\Users\<YourName>\Desktop\Gui_Standalone" /E /I
```

### Step 2: Create a Virtual Environment (Recommended)

```powershell
cd "C:\Users\<YourName>\Desktop\Gui_Standalone"

# Create venv
python -m venv venv

# Activate venv
.\venv\Scripts\activate
```

### Step 3: Install PyTorch with CUDA

Install the correct PyTorch version for your CUDA:

```powershell
# For CUDA 11.8 (recommended)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# For CPU only (no GPU)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Step 4: Install All Other Dependencies

```powershell
pip install -r requirements.txt
```

### Step 5: Install Optional Packages

```powershell
# Depth Pro — for Walking Speed depth estimation
pip install depth_pro

# pykinect2 — for Grip Strength test
pip install pykinect2
```

### Step 6: Verify Model Files

Ensure the following model files exist in the `models/` folder:

| File                      | Size (approx) | Used By                          |
| ------------------------- | -------------- | -------------------------------- |
| `yolov8n.pt`              | ~6 MB          | Person detection (all tests)     |
| `yolov8n-seg.pt`          | ~7 MB          | Person segmentation + depth      |
| `best7.pt`                | ~5 MB          | Digit detection (Grip Strength)  |
| `depth_pro.pt`            | ~1.8 GB        | Depth estimation (Walking Speed) |
| `pose_landmarker_lite.task` | ~6 MB        | MediaPipe pose (SFB, SOOL)       |

> **Important**: `depth_pro.pt` is ~1.8 GB and should NOT be a Git LFS pointer. Verify the file size.

Also ensure these YOLO models exist in `tests/`:

| File                 | Size (approx) | Used By                     |
| -------------------- | -------------- | --------------------------- |
| `yolov8n.pt`         | ~6 MB          | Test scripts                |
| `yolov8n-seg.pt`     | ~7 MB          | Test scripts                |
| `yolo11n-seg.pt`     | ~6 MB          | Test scripts                |

### Step 7: Run the Application

```powershell
python test_main.py
```

The main menu should open in fullscreen with 6 test cards.

---

## 5. Folder Structure

```
Gui_Standalone/
├── test_main.py                       # Main entry point
├── requirements.txt                   # Python dependencies
├── setup.md                           # This file
├── README.md                          # Quick-start guide
│
├── # ─── GUI Window Files ───
├── walking_speed_test_window.py       # Walking Speed GUI
├── functional_reach_window.py         # Functional Reach GUI
├── seated_forward_bend_window.py      # Seated Forward Bend GUI
├── time_up_and_go_test_window.py      # Timed Up & Go GUI
├── standing_one_leg_window.py         # Standing On One Leg GUI
├── KinectNumberWindow.py              # Grip Strength GUI
│
├── # ─── Supporting Scripts ───
├── analyze_travel_time.py             # Walking speed analysis (8m→3m)
├── seated_forward_bend_test.py        # SFB test logic
├── mp_pose_compat.py                  # MediaPipe compatibility layer
│
├── # ─── Instruction / Demo Windows ───
├── instruction_walking_speed.py
├── instruction_functional_reach.py
├── instruction_seated_forward_bend.py
├── instruction_time_up_and_go.py
├── instruction_standing_one_leg.py
├── instruction_grip_strength.py
│
├── # ─── Test Scripts (launched via QProcess) ───
├── tests/
│   ├── walking_speed_test.py
│   ├── video_depth_estimation.py
│   ├── functional_reach_test.py
│   ├── tug_test.py
│   ├── standing_one_leg_test.py
│   ├── yolov8n.pt
│   ├── yolov8n-seg.pt
│   └── yolo11n-seg.pt
│
├── # ─── AI Model Weights ───
├── models/
│   ├── yolov8n.pt
│   ├── yolov8n-seg.pt
│   ├── best7.pt                       # Digit detection model
│   ├── depth_pro.pt                   # DepthPro (~1.8 GB)
│   └── pose_landmarker_lite.task      # MediaPipe pose
│
├── # ─── Image Assets ───
├── ncai.png                           # NCAI logo
├── tokyo.png                          # Tokyo logo
├── speed.png                          # Walking Speed icon
├── reach.png                          # Functional Reach icon
├── seated.png                         # Seated Forward Bend icon
├── ability.png                        # TUG icon
├── standing.png                       # Standing On One Leg icon
├── grip.png                           # Grip Strength icon
│
└── yolov8n.pt                         # Root-level YOLO model copy
```

---

## 6. Test Overview

| #  | Test                   | Camera               | Variables Saved      | Description                                |
| -- | ---------------------- | --------------------- | -------------------- | ------------------------------------------ |
| 1  | **Walking Speed**      | Webcam (front, 8m)    | `time1`, `time2`     | Measures time to walk from 8m to 3m depth  |
| 2  | **Functional Reach**   | Azure Kinect (side)   | `distance1`, `distance2` | Measures forward reach distance        |
| 3  | **Seated Forward Bend**| Azure Kinect (side)   | `distance1`, `distance2` | Measures seated flexibility            |
| 4  | **Standing On One Leg**| Azure Kinect (front)  | `time1`, `time2`     | Measures single-leg balance time           |
| 5  | **Timed Up & Go**      | Azure Kinect (front)  | `time1`, `time2`     | Measures sit-stand-walk-turn-sit time      |
| 6  | **Grip Strength**      | Kinect v2             | digit value          | Reads grip dynamometer display             |

Each test (1–5) has **Record 1** and **Record 2** buttons for saving two trial values.

---

## 7. Troubleshooting

### Python / pip Issues

| Problem                           | Solution                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| `python` not recognized           | Reinstall Python with **"Add to PATH"** checked                   |
| `ModuleNotFoundError: PyQt5`      | Run `pip install -r requirements.txt`                             |
| `ModuleNotFoundError: torch`      | Install PyTorch separately (see Step 3 above)                     |
| `ModuleNotFoundError: depth_pro`  | Run `pip install depth_pro` (optional, Walking Speed only)        |
| `ModuleNotFoundError: pykinect2`  | Run `pip install pykinect2` (optional, Grip Strength only)        |
| mediapipe install fails           | Use Python 3.10 (not 3.12+)                                       |

### Camera / SDK Issues

| Problem                           | Solution                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| Azure Kinect not detected         | Install Azure Kinect SDK, check USB 3.0 cable                    |
| `pyk4a` import error              | Install Azure Kinect SDK first, then `pip install pyk4a`          |
| Kinect v2 not detected            | Install Kinect for Windows SDK 2.0, check USB 3.0                |
| Camera index wrong                | Code defaults to index 0 or 1; edit `cv2.VideoCapture(0)` as needed |

### Model Issues

| Problem                           | Solution                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| YOLO model not found              | Ensure `.pt` files are in `models/` and `tests/` folders         |
| `depth_pro.pt` too small          | File may be a Git LFS pointer; re-download the actual model       |
| CUDA out of memory                | Use `--device cpu` or reduce batch size                           |
| Slow inference                    | Install CUDA + cuDNN for GPU acceleration                        |

### Application Issues

| Problem                           | Solution                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| Black screen on launch            | Check `QT_QPA_PLATFORM_PLUGIN_PATH` env variable conflicts       |
| Qt plugin error                   | `test_main.py` clears this automatically; ensure PyQt5 is installed |
| Window doesn't show               | Try running without fullscreen: edit `self.showFullScreen()` → `self.show()` |
