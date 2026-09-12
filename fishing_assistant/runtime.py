import json
from datetime import datetime
import threading
import time
import cv2
import mss
import numpy as np

from .config import ROOT, pixel_roi
from .engine import Engine, Observation
from .vision import BaitReader, StableBait, splash_score
from .windows import Mouse, client_box


class Runner(threading.Thread):
    def __init__(self, config, window, automatic, already_cast, publish):
        super().__init__(daemon=True)
        self.cfg, self.window = config, window
        self.automatic, self.already_cast, self.publish = automatic, already_cast, publish
        self.stop_event = threading.Event()
        self.engine = Engine(config)

    def stop(self):
        self.stop_event.set()

    def run(self):
        mouse = Mouse(self.window[0], self.window[2], self.stop_event)
        log_folder = ROOT / "logs"
        log_folder.mkdir(exist_ok=True)
        log_path = log_folder / f"session_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl"
        reader, stable = BaitReader(), StableBait()
        now = time.monotonic()
        self.engine.start(now, already_cast=self.already_cast or not self.automatic)
        last_view, last_bait = 0.0, 0.0
        digit, confidence, bait_crop = None, 0.0, None
        try:
            with log_path.open("w", encoding="utf-8") as log, mss.mss() as capture:
                def event(kind, **data):
                    record = {"time": datetime.now().isoformat(timespec="milliseconds"), "kind": kind, **data}
                    log.write(json.dumps(record, ensure_ascii=False)+"\n")
                    log.flush()
                    self.publish("log", record)
                event("start", automatic=self.automatic, settings=self.cfg.__dict__)
                while not self.stop_event.is_set():
                    tick = time.monotonic()
                    if not mouse.focused():
                        self.engine.pause("游戏失去前台焦点")
                        break
                    box = client_box(self.window[0])
                    def grab(roi):
                        x, y, w, h = pixel_roi(roi, box["width"], box["height"])
                        image = np.asarray(capture.grab({"left": box["left"]+x, "top": box["top"]+y, "width": w, "height": h}))
                        return np.ascontiguousarray(image[:, :, :3])
                    crop = grab(self.cfg.splash_roi)
                    score, mask = splash_score(crop, self.cfg.value_min, self.cfg.saturation_max)
                    if tick-last_bait >= 0.1:
                        bait_crop = grab(self.cfg.bait_roi)
                        digit, confidence = reader.read(bait_crop)
                        last_bait = tick
                        stable.update(digit, tick)
                    bait = stable.value if tick-stable.updated_at < 0.75 else None
                    # Re-read foreground immediately before deciding or dispatching input.
                    now = time.monotonic()
                    actions = self.engine.update(now, Observation(score, bait, mouse.focused()))
                    for action in actions:
                        if self.stop_event.is_set():
                            break
                        if self.automatic:
                            if action == "zoom":
                                mouse.down("right") if self.cfg.zoom_mode == "hold" else mouse.click("right")
                            else:
                                if action == "hook":
                                    mouse.up("right")
                                mouse.click("left")
                        event(action, bait=bait, splash_ratio=round(score, 6), automatic=self.automatic)
                        if action == "hook" and not self.automatic:
                            self.engine.pause("已识别一次咬钩；预览结束，没有点击鼠标")
                    if now-last_view >= 0.12:
                        self.publish("frame", {"image": crop, "mask": mask, "bait_image": bait_crop,
                                             "bait": bait, "confidence": confidence, "score": score,
                                             "status": self.engine.status(now), "casts": self.engine.casts,
                                             "hooks": self.engine.catches})
                        last_view = now
                    if self.engine.state == "paused":
                        break
                    self.stop_event.wait(max(0, 1/self.cfg.fps-(time.monotonic()-tick)))
                event("stop", reason=self.engine.reason or "手动暂停")
        except Exception as exc:
            self.engine.pause(str(exc))
            self.publish("error", str(exc))
        finally:
            try:
                mouse.release()
            except Exception as exc:
                self.publish("error", str(exc))
            self.publish("finished", self.engine.reason or "已暂停")
