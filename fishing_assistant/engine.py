"""Clock-driven controller. Produces intents only; no mouse or screen access."""
from dataclasses import dataclass
from .config import Config


@dataclass
class Observation:
    splash: float = 0.0
    bait: int | None = None
    focused: bool = True


class SplashGate:
    def __init__(self, config):
        self.cfg = config
        self.reset(0)

    def reset(self, cast_at):
        self.cast_at = cast_at
        self.armed = False
        self.calm_since = self.high_since = None
        self.high_frames = 0
        self.fired = False

    def update(self, now, score):
        if self.fired or now-self.cast_at < self.cfg.cast_blind:
            return False
        if not self.armed:
            if score < self.cfg.calm_ratio:
                if self.calm_since is None:
                    self.calm_since = now
                self.armed = now-self.calm_since >= self.cfg.calm_time
            else:
                self.calm_since = None
            return False
        if score > self.cfg.splash_ratio:
            if self.high_since is None:
                self.high_since = now
            self.high_frames += 1
            if self.high_frames >= 2 and now-self.high_since >= self.cfg.confirm_time:
                self.fired = True
                return True
        else:
            self.high_since = None
            self.high_frames = 0
        return False


class Engine:
    LABELS = {"idle": "已暂停", "prepare": "确认鱼饵", "fishing": "等待咬钩",
              "reel": "收竿等待", "reload": "收竿与换饵", "paused": "已暂停"}

    def __init__(self, config: Config):
        self.cfg = config.validate()
        self.gate = SplashGate(config)
        self.state = "idle"
        self.reason = ""
        self.catches = self.casts = 0
        self.bait = config.initial_bait
        self.entered = self.deadline = 0.0
        self.zoomed = False
        self.last_now = None

    def start(self, now, already_cast=False):
        self.reason = ""
        self.last_now = now
        self.entered = now
        if already_cast:
            self.state = "fishing"
            # Still require a fresh quiet period after resuming on an existing cast.
            self.gate.reset(now-self.cfg.cast_blind)
            self.zoomed = True
            self.deadline = now + self.cfg.bite_timeout
        else:
            self.state = "prepare"
            self.deadline = now + self.cfg.ready_timeout

    def pause(self, reason="手动暂停"):
        self.state = "paused"
        self.reason = reason

    def _cast(self, now, bait):
        self.bait = bait
        self.casts += 1
        self.state = "fishing"
        self.entered = now
        self.deadline = now + self.cfg.bite_timeout
        self.gate.reset(now)
        self.zoomed = False
        return ["cast"]

    def update(self, now, obs: Observation):
        if self.state in ("paused", "idle"):
            return []
        if not obs.focused:
            self.pause("游戏失去前台焦点")
            return []
        if self.last_now is not None and now-self.last_now > 1.0:
            self.pause("画面处理停顿超过 1 秒，请重新开始")
            return []
        self.last_now = now
        if self.state == "prepare":
            if not self.cfg.bait_vision:
                return self._cast(now, self.bait)
            if obs.bait is not None and obs.bait > 0:
                return self._cast(now, obs.bait)
            if now > self.deadline:
                self.pause("无法确认鱼饵，请校准右下角数字区域")
            return []
        if self.state == "fishing":
            if obs.bait is not None and obs.bait > 0:
                self.bait = obs.bait
            if now > self.deadline:
                self.pause("等待咬钩超时，请检查是否抛竿成功")
                return []
            if not self.zoomed and now-self.entered >= self.cfg.zoom_delay:
                self.zoomed = True
                if self.cfg.zoom_mode != "manual":
                    return ["zoom"]
            if self.gate.update(now, obs.splash):
                self.catches += 1
                self.bait = max(0, self.bait-1)
                # If OCR has been unavailable, the internal count remains conservative.
                reload_needed = self.bait == 0
                self.state = "reload" if reload_needed else "reel"
                self.entered = now
                self.deadline = now + (self.cfg.reload_wait if reload_needed else self.cfg.reel_wait)
                return ["hook"]
            return []
        if self.state in ("reel", "reload"):
            if obs.bait == 0 and self.state != "reload":
                self.state = "reload"
                self.deadline = self.entered + self.cfg.reload_wait
            if now < self.deadline:
                return []
            if self.cfg.bait_vision:
                # A value of 0 never permits a cast. Reader provides only fresh stable data.
                if obs.bait is not None and obs.bait > 0:
                    return self._cast(now, obs.bait)
                if now > self.deadline + self.cfg.ready_timeout:
                    self.pause("换饵/收竿后没有确认到可用鱼饵")
            else:
                return self._cast(now, 5 if self.state == "reload" else self.bait)
        return []

    def status(self, now):
        if self.state == "fishing" and not self.gate.armed:
            remain = max(0, self.cfg.cast_blind-(now-self.gate.cast_at))
            return f"入水屏蔽 {remain:.1f}s" if remain else "等待水面平静"
        if self.state in ("reel", "reload"):
            return f"{self.LABELS[self.state]} · {max(0, self.deadline-now):.1f}s"
        return self.reason or self.LABELS[self.state]
