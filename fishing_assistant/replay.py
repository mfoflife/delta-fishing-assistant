"""Run the same splash gate on a video, without importing Windows input APIs."""
import json
from pathlib import Path
import cv2
from .config import ROOT, pixel_roi
from .engine import SplashGate
from .vision import splash_score

SAMPLE_CASTS = [1.85, 11.20, 24.65, 35.20, 46.20, 58.70]


def replay_video(path, config, cast_times, output=None, progress=None, stop_event=None):
    config.validate()
    if not cast_times or cast_times != sorted(set(cast_times)) or min(cast_times) < 0:
        raise ValueError("请输入递增且不重复的甩竿起点（秒）")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("无法打开录像")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or max(cast_times) >= total/fps:
        cap.release()
        raise ValueError("录像帧率或甩竿时间无效")
    gate = SplashGate(config)
    cast_index, frame_index = -1, 0
    events = []
    cancelled = False
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                cancelled = True
                break
            ok, frame = cap.read()
            if not ok:
                break
            now = frame_index/fps
            while cast_index+1 < len(cast_times) and now >= cast_times[cast_index+1]:
                cast_index += 1
                gate.reset(cast_times[cast_index])
            x, y, w, h = pixel_roi(config.splash_roi, frame.shape[1], frame.shape[0])
            crop = frame[y:y+h, x:x+w]
            score, mask = splash_score(crop, config.value_min, config.saturation_max)
            if cast_index >= 0 and gate.update(now, score):
                events.append({"cast": cast_index+1, "time_s": round(now, 4), "splash_ratio": round(score, 6)})
            if progress and frame_index % 30 == 0:
                progress({"image": crop, "mask": mask, "score": score,
                          "status": f"录像 {now:.1f} / {total/fps:.1f}s", "hooks": len(events), "casts": max(0, cast_index+1)})
            frame_index += 1
    finally:
        cap.release()
    if not cancelled and frame_index < total-2:
        raise RuntimeError(f"录像提前解码结束：{frame_index}/{total} 帧")
    result = {"video": str(path), "fps": fps, "frames_read": frame_index, "cancelled": cancelled,
              "cast_times_manual": cast_times, "settings": config.__dict__, "events": events,
              "note": "人工提供甩竿起点的离线回放；不是实服成功率或独立测试集准确率。"}
    output = Path(output) if output else ROOT / "logs" / "replay_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, output
