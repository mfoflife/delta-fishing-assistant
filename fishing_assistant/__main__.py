import argparse
import json
from .config import Config


def main():
    parser = argparse.ArgumentParser(description="本地水花识别与录像回放")
    parser.add_argument("--replay")
    parser.add_argument("--cast-times", help="录像内甩竿起点，秒，以逗号分隔")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.replay:
        if not args.cast_times:
            parser.error("录像回放必须提供 --cast-times")
        from .replay import replay_video
        result, output = replay_video(args.replay, Config.load(), [float(x) for x in args.cast_times.split(",")], args.output)
        print(json.dumps({"events": result["events"], "output": str(output)}, ensure_ascii=False, indent=2))
    else:
        from .windows import set_dpi_awareness
        set_dpi_awareness()
        from .gui import App
        App().mainloop()


if __name__ == "__main__":
    main()
