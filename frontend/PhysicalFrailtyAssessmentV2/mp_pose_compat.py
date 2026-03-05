"""
MediaPipe Pose Compatibility Wrapper
=====================================
Provides a unified `create_pose_detector()` function that works with both
the legacy `mp.solutions.pose.Pose` API and newer MediaPipe versions.

The returned object supports:
    .process(rgb_image)  → results with .pose_landmarks.landmark
    .close()             → cleanup
"""

import mediapipe as mp


def create_pose_detector(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
):
    """
    Create a MediaPipe Pose detector using the solutions API.

    Returns an object with .process(rgb_image) and .close() methods.
    """
    return mp.solutions.pose.Pose(
        static_image_mode=static_image_mode,
        model_complexity=model_complexity,
        enable_segmentation=enable_segmentation,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )
