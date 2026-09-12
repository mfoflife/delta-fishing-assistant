from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "local_config.json"


@dataclass
class Config:
    # All timing values are seconds measured from actual action dispatch.
    cast_blind: float = 3.5
    reel_wait: float = 2.8
    reload_wait: float = 4.8
    zoom_delay: float = 0.7
    calm_time: float = 0.2
    confirm_time: float = 0.025
    bite_timeout: float = 60.0
    ready_timeout: float = 12.0
    splash_ratio: float = 1000 / 126000
    calm_ratio: float = 500 / 126000
    value_min: int = 80
    saturation_max: int = 100
    fps: int = 30
    zoom_mode: str = "hold"
    bait_vision: bool = True
    initial_bait: int = 5
    # User-calibrated working preset on a 2560 x 1600 client; scale with the window.
    splash_roi: list = field(default_factory=lambda: [510/2560, 311/1600, 1651/2560, 932/1600])
    bait_roi: list = field(default_factory=lambda: [2356/2560, 1365/1600, 110/2560, 71/1600])

    def validate(self):
        for name in ("cast_blind", "reel_wait", "reload_wait", "zoom_delay", "calm_time", "confirm_time", "bite_timeout", "ready_timeout"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} 必须是有效的非负数")
        if not 0 <= self.calm_ratio < self.splash_ratio <= 1:
            raise ValueError("平静阈值必须小于触发阈值，且范围为 0～1")
        if self.bite_timeout <= self.cast_blind + self.calm_time or self.ready_timeout < 1:
            raise ValueError("等待超时太短")
        if not 5 <= self.fps <= 120 or not 1 <= self.initial_bait <= 5:
            raise ValueError("检测频率应为 5～120，初始鱼饵应为 1～5")
        if not 0 <= self.value_min <= 255 or not 0 <= self.saturation_max <= 255:
            raise ValueError("颜色阈值应为 0～255")
        if self.zoom_mode not in ("toggle", "hold", "manual"):
            raise ValueError("未知放大方式")
        for roi in (self.splash_roi, self.bait_roi):
            if len(roi) != 4 or not all(math.isfinite(x) for x in roi):
                raise ValueError("检测区域无效")
            x, y, w, h = roi
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > 1.000001 or y+h > 1.000001:
                raise ValueError("检测区域必须位于游戏窗口内")
        return self

    def save(self):
        self.validate()
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)

    @classmethod
    def load(cls):
        if not CONFIG_PATH.exists():
            return cls()
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__}).validate()


def pixel_roi(roi, width, height):
    x, y, w, h = roi
    left, top = round(x*width), round(y*height)
    right, bottom = min(width, round((x+w)*width)), min(height, round((y+h)*height))
    if right <= left or bottom <= top:
        raise ValueError("检测区域太小")
    return left, top, right-left, bottom-top
