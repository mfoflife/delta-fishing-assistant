from pathlib import Path
import cv2
import numpy as np


def splash_score(bgr, value_min=80, saturation_max=100):
    if bgr is None or bgr.size == 0:
        raise ValueError("截图为空")
    hsv = cv2.cvtColor(bgr[:, :, :3], cv2.COLOR_BGR2HSV)
    mask = (hsv[:, :, 2] >= value_min) & (hsv[:, :, 1] <= saturation_max)
    return float(mask.mean()), mask.astype(np.uint8)*255


def digit_pixels(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    red = ((h < 12) | (h > 170)) & (s > 100) & (v > 90)
    # Low-count digits are red. Other digits are bright white; leading zeros are dim.
    return red if red.sum() >= 20 else ((v > 140) & (s < 100))


def normalize_digit(mask):
    yy, xx = np.where(mask)
    if len(xx) < 12 or mask.mean() > 0.85:
        return None
    crop = mask[yy.min():yy.max()+1, xx.min():xx.max()+1].astype(np.uint8)*255
    return cv2.resize(crop, (24, 40), interpolation=cv2.INTER_NEAREST)


def digit_mask(bgr):
    return normalize_digit(digit_pixels(bgr))


def digit_candidates(bgr):
    """Group stencil strokes by columns, separating nearby HUD labels and /infinity."""
    pixels = digit_pixels(bgr)
    columns = np.flatnonzero(pixels.any(axis=0))
    if not len(columns):
        return []
    # A glyph is made of disconnected strokes; connected components alone split a 5.
    groups = np.split(columns, np.flatnonzero(np.diff(columns) > max(2, round(bgr.shape[0]*.04))+1)+1)
    candidates = []
    for group in groups:
        crop = pixels[:, group[0]:group[-1]+1]
        rows = np.flatnonzero(crop.any(axis=1))
        height = rows[-1]-rows[0]+1
        width = len(range(group[0], group[-1]+1))
        if height < max(8, bgr.shape[0]*.2) or not .12 <= width/height <= 1.0:
            continue
        normalized = normalize_digit(crop)
        if normalized is not None:
            candidates.append(normalized)
    return candidates


class BaitReader:
    def __init__(self, folder=None):
        folder = Path(folder) if folder else Path(__file__).parent / "assets" / "digits"
        self.templates = {}
        for n in range(6):
            path = folder / f"{n}.png"
            if path.exists():
                image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
                mask = digit_mask(image)
                if mask is not None:
                    self.templates[n] = mask > 0

    def _match(self, mask):
        mask = mask > 0
        scores = sorted(((float((mask & t).sum()/max(1, (mask | t).sum())), n)
                         for n, t in self.templates.items()), reverse=True)
        best, digit = scores[0]
        margin = best - (scores[1][0] if len(scores) > 1 else 0)
        return (digit if best >= 0.65 and margin >= 0.08 else None), best

    def read(self, bgr):
        if bgr is None or bgr.size == 0 or not self.templates:
            return None, 0.0
        matches = [self._match(mask) for mask in digit_candidates(bgr)]
        valid = [(digit, score) for digit, score in matches if digit is not None]
        # A tight or slightly padded crop should contain one active digit. Multiple
        # plausible digits are ambiguous; do not guess which count the user intended.
        if len(valid) == 1:
            return valid[0]
        return None, max((score for _, score in matches), default=0.0)


class StableBait:
    """Never treat an uncertain frame or an old candidate as a fresh reading."""
    def __init__(self, duration=0.2):
        self.duration = duration
        self.candidate = None
        self.since = 0.0
        self.value = None
        self.updated_at = -1e9

    def update(self, value, now):
        if value is None:
            self.candidate = None
        elif value != self.candidate:
            self.candidate, self.since = value, now
        elif now - self.since >= self.duration:
            self.value, self.updated_at = value, now
        return self.value if now-self.updated_at < 0.75 else None
