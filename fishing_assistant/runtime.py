import json
import os
from datetime import datetime
import threading
import time
import cv2
import mss
import numpy as np

from .config import ROOT, pixel_roi
from .engine import Engine, Observation
from .vision import BaitReader, StableBait, splash_score
from .windows import Mouse, client_box, process_integrity


class Runner(threading.Thread):
    # Delay between releasing the first cast click and pressing the second.
    CAST_CLICK_GAP = 0.15

    def __init__(self, config, window, automatic, already_cast, publish, test_click=False):
        super().__init__(daemon=True)
        self.cfg, self.window = config, window
        self.automatic, self.already_cast, self.publish = automatic, already_cast, publish
        self.test_click = test_click
        if test_click and not automatic:
            raise ValueError("单次点击测试必须显式启用鼠标操作")
        self.stop_event = threading.Event()
        self.engine = Engine(config)

    def stop(self):
        self.stop_event.set()

    def execute_action(self, mouse, action):
        if action == "cast":
            mouse.click("left")
            if self.stop_event.wait(self.CAST_CLICK_GAP):
                raise RuntimeError("已暂停，取消抛竿的第二次点击")
            # Mouse.click rechecks both foreground and cancellation before pressing.
            mouse.click("left")
        elif action == "zoom":
            mouse.down("right") if self.cfg.zoom_mode == "hold" else mouse.click("right")
        elif action == "hook":
            mouse.up("right")
            mouse.click("left")
        else:
            raise ValueError(f"未知鼠标动作：{action}")

    def run(self):
        mouse = Mouse(self.window[0], self.window[2], self.stop_event)
        log_folder = ROOT / "logs"
        log_folder.mkdir(exist_ok=True)
        log_path = log_folder / f"session_{datetime.now():%Y%m%d_%H%M%S_%f}.jsonl"
        reader, stable = BaitReader(), StableBait()
        last_view, last_bait, last_sample = 0.0, 0.0, 0.0
        last_state = None
        digit, confidence, bait_crop = None, 0.0, None
        try:
            with log_path.open("w", encoding="utf-8") as log, mss.mss() as capture:
                def event(kind, **data):
                    record = {"time": datetime.now().isoformat(timespec="milliseconds"), "kind": kind, **data}
                    log.write(json.dumps(record, ensure_ascii=False)+"\n")
                    log.flush()
                    self.publish("log", record)
                event("start", automatic=self.automatic, already_cast=self.already_cast, test_click=self.test_click,
                      window={"hwnd": self.window[0], "title": self.window[1], "pid": self.window[2]},
                      settings=self.cfg.__dict__)
                own_access, game_access = process_integrity(os.getpid()), process_integrity(self.window[2])
                event("permissions", assistant=own_access, game=game_access)
                if (self.automatic and own_access["level"] is not None and game_access["level"] is not None
                        and own_access["level"] < game_access["level"]):
                    raise RuntimeError("助手权限低于游戏，无法发送点击；请关闭助手后右键 start.cmd，以管理员身份运行")
                if self.test_click:
                    if self.stop_event.is_set():
                        self.engine.pause("单次点击测试已取消")
                    elif not mouse.focused():
                        self.engine.pause("游戏失去前台焦点，未发送测试点击")
                        event("focus", **mouse.focus_details())
                    else:
                        mouse.click("left")
                        event("test_click", input_result="os_accepted_game_unverified")
                        self.engine.pause("单次左键已发送并停止；请确认游戏是否抛竿")
                    event("stop", reason=self.engine.reason)
                    return
                self.engine.start(time.monotonic(), already_cast=self.already_cast or not self.automatic)
                saved_bait_sample = False
                while not self.stop_event.is_set():
                    tick = time.monotonic()
                    if not mouse.focused():
                        self.engine.pause("游戏失去前台焦点")
                        event("focus", **mouse.focus_details())
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
                    if not saved_bait_sample and self.engine.state != "paused" and now-last_bait < .2:
                        snapshot = log_path.with_name(log_path.stem+"_bait.png")
                        cv2.imencode(".png", bait_crop)[1].tofile(str(snapshot))
                        event("bait_snapshot", path=str(snapshot))
                        saved_bait_sample = True
                    for action in actions:
                        if self.stop_event.is_set():
                            break
                        if self.automatic:
                            self.execute_action(mouse, action)
                        event(action, bait=bait, splash_ratio=round(score, 6), automatic=self.automatic,
                              click_count=(2 if action == "cast" else 1 if action == "hook" else None) if self.automatic else 0,
                              input_result="os_accepted_game_unverified" if self.automatic else "preview_only")
                        if action == "hook" and not self.automatic:
                            self.engine.pause("已识别一次咬钩；预览结束，没有点击鼠标")
                    if now-last_sample >= 1.0 or self.engine.state != last_state:
                        event("sample", state=self.engine.state, status=self.engine.status(now),
                              armed=self.engine.gate.armed, splash_ratio=round(score, 6),
                              bait=bait, raw_bait=digit, bait_confidence=round(confidence, 4),
                              client=box)
                        last_sample, last_state = now, self.engine.state
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
            # The capture/log context may have closed before an exception arrives.
            with log_path.open("a", encoding="utf-8") as error_log:
                error_log.write(json.dumps({"time": datetime.now().isoformat(timespec="milliseconds"),
                                           "kind": "error", "reason": str(exc)}, ensure_ascii=False)+"\n")
            self.publish("error", str(exc))
        finally:
            try:
                mouse.release()
            except Exception as exc:
                self.publish("error", str(exc))
            self.publish("finished", self.engine.reason or "已暂停")
