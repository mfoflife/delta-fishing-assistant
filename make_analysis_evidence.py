"""Create a compact visual evidence panel from the original recording."""
from pathlib import Path
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis" / "zoom"
VIDEO = r"D:\GameVideos\deltaForceRecord\15623878227063700672\record\record20260912-233726.mp4"
cap = cv2.VideoCapture(VIDEO)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 23)
small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
board = Image.new("RGB", (1320, 568), "#15191f")
draw = ImageDraw.Draw(board)
samples = [(4.50, "甩竿入水水花", "甩竿后约 2.65 秒：需要屏蔽"),
           (8.00, "等待咬钩", "水面平静：可以进入检测状态"),
           (8.30, "咬钩水花", "局部亮色水花再次突然增加")]
for i, (t, title, subtitle) in enumerate(samples):
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t*60))
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError(f"Cannot decode frame at {t}")
    crop = frame[240:700, 640:1080]
    board.paste(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)), (i*440, 72))
    draw.text((i*440+15, 10), f"{t:.2f}s  {title}", font=font, fill="white")
    draw.text((i*440+15, 43), subtitle, font=small, fill="#aebbd0")
draw.text((15, 539), "原始录像局部裁剪，未调整亮度或颜色；甩竿起点为画面估计。", font=small, fill="#aebbd0")
board.save(OUT / "splash_evidence.png")
cap.release()
print(str((OUT / "splash_evidence.png").resolve()))
