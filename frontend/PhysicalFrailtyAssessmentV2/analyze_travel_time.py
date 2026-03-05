"""
Analyze video_depthazure.csv to calculate the total time taken
for the tracked person to travel from 8m to 3m depth.

Can be run standalone:
    python analyze_travel_time.py  video_depthazure.csv

Or imported:
    from analyze_travel_time import analyze_travel_time
    result = analyze_travel_time("video_depthazure.csv")
"""

import pandas as pd
import sys
import argparse
from pathlib import Path


def analyze_travel_time(csv_path="video_depthazure.csv"):
    """
    Analyze depth CSV and return travel-time results as a dict.

    Returns
    -------
    dict  with keys:
        travel_time_s, avg_speed_mps, distance_m,
        timestamp_8m, timestamp_3m, depth_8m, depth_3m,
        frame_8m, frame_3m, frames_elapsed,
        milestones  (list of dicts for 8→3 m)
    or None if analysis fails.
    """
    df = pd.read_csv(csv_path)

    # Filter out frames where person was not detected (metric_depth_m == -1)
    df_valid = df[df["metric_depth_m"] > 0].copy()

    print("=" * 60)
    print("  TRAVEL TIME ANALYSIS: 8m → 3m")
    print("=" * 60)
    print(f"\nCSV File: {csv_path}")
    print(f"Total frames: {len(df)}")
    print(f"Valid detection frames: {len(df_valid)}")
    print(f"Depth range: {df_valid['metric_depth_m'].max():.2f}m → "
          f"{df_valid['metric_depth_m'].min():.2f}m")
    print(f"Total video duration: {df_valid['timestamp_sec'].max():.2f}s")

    # --- Find the frame where depth first drops to/below 8m ---
    crossed_8m = df_valid[df_valid["metric_depth_m"] <= 8.0]
    if crossed_8m.empty:
        print("\n[ERROR] Person never reached 8m depth!")
        return None

    first_8m = crossed_8m.iloc[0]
    timestamp_8m = first_8m["timestamp_sec"]
    frame_8m = int(first_8m["frame_number"])
    depth_8m = first_8m["metric_depth_m"]

    # --- Find the frame where depth first drops to/below 3m ---
    crossed_3m = df_valid[df_valid["metric_depth_m"] <= 3.0]
    if crossed_3m.empty:
        print("\n[ERROR] Person never reached 3m depth!")
        return None

    first_3m = crossed_3m.iloc[0]
    timestamp_3m = first_3m["timestamp_sec"]
    frame_3m = int(first_3m["frame_number"])
    depth_3m = first_3m["metric_depth_m"]

    # --- Calculate travel time ---
    travel_time = timestamp_3m - timestamp_8m
    distance = depth_8m - depth_3m
    avg_speed = distance / travel_time if travel_time > 0 else 0.0

    print("\n" + "-" * 60)
    print("  RESULTS")
    print("-" * 60)

    print(f"\n  📍 8m crossing point:")
    print(f"     Frame: {frame_8m}")
    print(f"     Timestamp: {timestamp_8m:.4f}s")
    print(f"     Actual depth: {depth_8m:.4f}m")

    print(f"\n  📍 3m crossing point:")
    print(f"     Frame: {frame_3m}")
    print(f"     Timestamp: {timestamp_3m:.4f}s")
    print(f"     Actual depth: {depth_3m:.4f}m")

    print(f"\n  ⏱️  Total travel time (8m → 3m): {travel_time:.4f} seconds")
    print(f"  📐 Distance covered: {distance:.4f}m (as measured by depth)")
    print(f"  🚶 Average speed: {avg_speed:.4f} m/s")
    print(f"  🎞️  Frames elapsed: {frame_3m - frame_8m}")

    # --- Depth milestones ---
    milestones = []
    print("\n" + "-" * 60)
    print("  DEPTH MILESTONES")
    print("-" * 60)

    for milestone in [8, 7, 6, 5, 4, 3]:
        crossed = df_valid[df_valid["metric_depth_m"] <= float(milestone)]
        if not crossed.empty:
            row = crossed.iloc[0]
            time_from_8m = row["timestamp_sec"] - timestamp_8m
            milestones.append({
                "depth_m": milestone,
                "timestamp_sec": row["timestamp_sec"],
                "frame": int(row["frame_number"]),
                "time_from_8m": time_from_8m,
            })
            print(f"  {milestone}m reached at t={row['timestamp_sec']:.4f}s "
                  f"(frame {int(row['frame_number'])}) "
                  f"[+{time_from_8m:.4f}s from 8m]")

    print("\n" + "=" * 60)

    return {
        "travel_time_s": round(travel_time, 4),
        "avg_speed_mps": round(avg_speed, 4),
        "distance_m": round(distance, 4),
        "timestamp_8m": round(timestamp_8m, 4),
        "timestamp_3m": round(timestamp_3m, 4),
        "depth_8m": round(depth_8m, 4),
        "depth_3m": round(depth_3m, 4),
        "frame_8m": frame_8m,
        "frame_3m": frame_3m,
        "frames_elapsed": frame_3m - frame_8m,
        "milestones": milestones,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze travel time from depth CSV (8m to 3m)."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="video_depthazure.csv",
        help="Path to depth CSV file (default: video_depthazure.csv)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(2)
    analyze_travel_time(str(csv_path))
