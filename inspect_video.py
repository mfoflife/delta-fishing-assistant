"""Extract timestamped contact sheets from a local video; never sends game input."""
import argparse
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("out")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--step", type=float, default=1)
    parser.add_argument("--roi", type=int, nargs=4)
    parser.add_argument("--width", type=int, default=432)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--save-frames", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")
    fps = cap.get(cv2.CAP_PROP_FPS)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    meta = {"source": args.video, "fps": fps, "frames": count,
            "duration_seconds": count / fps, "width": int(cap.get(3)),
            "height": int(cap.get(4)), "roi": args.roi,
            "sample_start": args.start, "sample_step": args.step}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    end = min(args.end if args.end is not None else count / fps, count / fps)
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
    cells = []
    index = 0
    t = args.start
    def flush():
        nonlocal index
        if not cells:
            return
        w, h = cells[0].size
        board = Image.new("RGB", (w * args.cols, h * ((len(cells) + args.cols - 1) // args.cols)), "#181b20")
        for j, cell in enumerate(cells):
            board.paste(cell, ((j % args.cols) * w, (j // args.cols) * h))
        dest = out / f"sheet_{index:02d}.jpg"
        board.save(dest, quality=94)
        print(str(dest.resolve()))
        cells.clear()
        index += 1
    while t < end - 1e-6:
        frame_number = min(round(t * fps), count - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = cap.read()
        if not ok:
            break
        if args.roi:
            x, y, w, h = args.roi
            frame = frame[y:y+h, x:x+w]
        rgb = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if args.save_frames:
            rgb.save(out / f"frame_{frame_number:05d}_{frame_number/fps:.3f}s.png")
        h = round(rgb.height * args.width / rgb.width)
        rgb = rgb.resize((args.width, h), Image.Resampling.LANCZOS)
        cell = Image.new("RGB", (args.width, h + 30), "#181b20")
        cell.paste(rgb, (0, 30))
        ImageDraw.Draw(cell).text((8, 5), f"{frame_number/fps:07.3f}s  frame {frame_number}", font=font, fill="white")
        cells.append(cell)
        if len(cells) == args.cols * args.rows:
            flush()
        t += args.step
    flush()
    cap.release()
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
