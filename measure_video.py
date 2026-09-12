"""Record simple image measurements for offline fishing-video analysis."""
import argparse
import csv
import json
from pathlib import Path
import time

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("out")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    rows = []
    t0 = time.perf_counter()
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        # Coordinates refer only to the supplied 1728 x 1080 zoom recording.
        water = frame[300:650, 680:1040]
        hsv = cv2.cvtColor(water, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        white = (v >= 80) & (s <= 100)
        stem = frame[280:670, 790:935]
        sh = cv2.cvtColor(stem, cv2.COLOR_BGR2HSV)
        hh, ss, vv = cv2.split(sh)
        color = (((hh < 15) | (hh > 170)) | ((hh > 40) & (hh < 90))) & (ss > 90) & (vv > 45)
        ys = np.where(color.sum(axis=1) >= 2)[0]
        top = float(ys[0] + 280) if len(ys) else -1
        terrain_mean = float(cv2.cvtColor(frame[100:280, 500:1250], cv2.COLOR_BGR2GRAY).mean())
        upper = int(color[:180].sum())
        hud = frame[931:963, 1640:1664]
        # Keep tiny digit crops losslessly, for a later fixed-position template check.
        if i % 6 == 0:
            cv2.imencode(".png", hud)[1].tofile(str(out / f"hud_{i:05d}.png"))
        rows.append([i, round(i/fps, 6), round(terrain_mean, 3), int(white.sum()), int(color.sum()), upper, top])
        i += 1
    cap.release()
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time_s", "terrain_mean", "splash_pixels", "stem_color_pixels", "upper_stem_pixels", "stem_top_y"])
        writer.writerows(rows)
    print(json.dumps({"frames": i, "elapsed_s": time.perf_counter()-t0, "metrics": str((out / "metrics.csv").resolve())}))


if __name__ == "__main__":
    main()
