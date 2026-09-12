"""Windows memory/CPU benchmark using synthetic frames, real vision and GUI preview.

Does not capture the screen, register hotkeys, or send mouse input. The hidden
window retains its laid-out widget sizes so preview images are still generated.
Each scenario runs in a fresh process; game/driver/capture costs are excluded.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Counters(C.Structure):
    _fields_ = [("cb", W.DWORD), ("faults", W.DWORD)] + [
        (name, C.c_size_t) for name in ("peak_working", "working", "peak_paged", "paged",
                                      "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]


def memory():
    kernel = C.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = W.HANDLE
    psapi = C.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(Counters), W.DWORD]
    counters = Counters()
    counters.cb = C.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), C.byref(counters), counters.cb):
        raise C.WinError()
    return {"working_set_mib": counters.working/2**20, "private_commit_mib": counters.private/2**20}


def benchmark(scenario, seconds, warmup):
    import cv2
    import numpy as np
    from fishing_assistant.windows import set_dpi_awareness
    set_dpi_awareness()
    import fishing_assistant.gui as gui
    from fishing_assistant.config import Config
    from fishing_assistant.engine import SplashGate
    from fishing_assistant.vision import BaitReader, StableBait, splash_score

    class NoHotkeys:
        def __init__(self, callback):
            pass
        def close(self):
            pass

    gui.Hotkeys = NoHotkeys
    gui.App.refresh_windows = lambda self: None
    app = gui.App()
    app.title("资源测量（合成画面，无输入）")
    app.update()
    app.withdraw()
    app.update()
    cfg = Config()
    # Record actual dimensions instead of relying on the user's saved ROI/config.
    # Fixed comparison sizes: do not silently change the benchmark when presets change.
    water_size = (1651, 932) if scenario == "large_roi" else (534, 519)
    bait_size = (110, 71) if scenario == "large_roi" else (35, 48)
    frame = np.full((water_size[1], water_size[0], 4), [40, 45, 35, 255], np.uint8)
    source = cv2.imdecode(np.fromfile(ROOT/"fishing_assistant/assets/digits/5.png", np.uint8), 1)
    digit_image = cv2.resize(source, bait_size)
    reader, stable, gate = BaitReader(), StableBait(), SplashGate(cfg)
    beginning = time.perf_counter()
    gate.reset(beginning)
    samples, frames = [], 0
    measured_frames = 0
    cpu_start = wall_start = None
    last_bait = last_view = last_sample = 0
    deadline = beginning
    try:
        while time.perf_counter()-beginning < warmup+seconds:
            now = time.perf_counter()
            if now-beginning >= warmup and cpu_start is None:
                cpu_start, wall_start = time.process_time(), now
            if scenario != "idle":
                # Mirror BGRA->contiguous BGR allocation; no actual screen capture.
                frame[10:30, 10:30, :3] = 200 if frames % 120 < 5 else 40
                image = np.ascontiguousarray(frame.copy()[:, :, :3])
                score, mask = splash_score(image, cfg.value_min, cfg.saturation_max)
                if now-last_bait >= .1:
                    digit, confidence = reader.read(digit_image)
                    stable.update(digit, now)
                    last_bait = now
                gate.update(now, score)
                if now-last_view >= .12:
                    app.publish("frame", {"image": image, "mask": mask, "bait_image": digit_image,
                                         "score": score, "bait": stable.value, "confidence": confidence,
                                         "status": "资源测量", "casts": 0, "hooks": 0})
                    last_view = now
                frames += 1
                if wall_start is not None:
                    measured_frames += 1
            app.update()
            if wall_start is not None and now-last_sample >= .25:
                samples.append(memory())
                last_sample = now
            deadline += 1/30
            time.sleep(max(0, deadline-time.perf_counter()))
        elapsed = time.perf_counter()-wall_start
        cpu_time = time.process_time()-cpu_start
        metrics = {}
        for key in samples[0]:
            values = sorted(item[key] for item in samples)
            metrics[key] = {"min": round(values[0], 1), "median": round(statistics.median(values), 1),
                            "p95": round(values[min(len(values)-1, int(len(values)*.95))], 1), "max": round(values[-1], 1)}
        return {"scenario": scenario, "water_pixels": list(water_size), "bait_pixels": list(bait_size),
                "sample_seconds": round(elapsed, 2), "warmup_seconds": warmup, "samples": len(samples),
                "fps": round(measured_frames/elapsed, 2), "memory": metrics,
                "cpu_one_logical_core_percent": round(cpu_time/elapsed*100, 2),
                "cpu_total_machine_percent": round(cpu_time/elapsed/os.cpu_count()*100, 2)}
    finally:
        app.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["all", "idle", "small_roi", "large_roi"], default="all")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--output", type=Path, default=ROOT/"logs/resource_benchmark.json")
    args = parser.parse_args()
    if os.name != "nt" or args.seconds < 1 or args.warmup < 0:
        parser.error("Requires Windows, seconds >= 1 and warmup >= 0")
    if args.scenario != "all":
        print(json.dumps(benchmark(args.scenario, args.seconds, args.warmup)))
        return
    cases = []
    for scenario in ("idle", "small_roi", "large_roi"):
        child = subprocess.run([sys.executable, __file__, "--scenario", scenario, "--seconds", str(args.seconds),
                                "--warmup", str(args.warmup)], check=True, capture_output=True, text=True, encoding="utf-8")
        cases.append(json.loads(child.stdout))
    report = {"measured_at": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(),
              "windows": platform.platform(), "logical_processors": os.cpu_count(),
              "method": "Fresh process per scenario; synthetic BGRA frames, actual vision and Tk preview generation; hidden window; no screen capture, no video decoder, no hotkeys, no mouse input; excludes game.",
              "scenarios": cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
