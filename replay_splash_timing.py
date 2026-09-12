"""Compare splash-only timing gates against six visually annotated casts.

Cast starts are manual estimates from rod animation (about +/-0.05 s), not
recorded mouse timestamps. Thresholds are calibrated on this clip, not held-out
validation. No live screen capture or input control is performed.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis" / "zoom"
CASTS = [1.85, 11.20, 24.65, 35.20, 46.20, 58.70]
BITE_WINDOWS = [(8.1, 8.6), (22.25, 22.6), (32.75, 33.15),
                (43.8, 44.2), (54.0, 54.4), (67.0, 67.4)]
with (OUT / "measurements" / "metrics.csv").open(encoding="utf-8") as f:
    rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]


def replay(delay, wait_for_calm=False):
    results = []
    for i, start in enumerate(CASTS):
        end = CASTS[i+1] if i+1 < len(CASTS) else 69.05
        armed = not wait_for_calm
        calm_frames = consecutive = 0
        found = None
        for row in rows:
            t = row["time_s"]
            if not start + delay <= t < end:
                continue
            if not armed:
                calm_frames = calm_frames + 1 if row["splash_pixels"] < 500 else 0
                if calm_frames >= 12:
                    armed = True
                continue
            consecutive = consecutive + 1 if row["splash_pixels"] > 1000 else 0
            if consecutive >= 2:
                found = t
                break
        results.append({"cast": i+1, "cast_start_estimate_s": start,
                        "trigger_s": found,
                        "matches_visually_labeled_bite": found is not None and BITE_WINDOWS[i][0] <= found <= BITE_WINDOWS[i][1]})
    return {"delay_s": delay, "wait_for_calm_0_2s": wait_for_calm,
            "matched_bites": sum(x["matches_visually_labeled_bite"] for x in results),
            "false_triggers": sum(x["trigger_s"] is not None and not x["matches_visually_labeled_bite"] for x in results),
            "results": results}


report = {
    "scope": "Offline replay of this clip; six manual cast starts; same-clip threshold calibration; not a live automation or independent accuracy test.",
    "splash_roi_xywh": [680, 300, 360, 350],
    "white_pixel_rule": "OpenCV HSV V >= 80 and S <= 100",
    "trigger": "white pixel count > 1000 for 2 consecutive 60-fps frames",
    "comparisons": [replay(x) for x in [2, 3, 3.5, 4]] + [replay(3, True)],
}
(OUT / "timing_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
