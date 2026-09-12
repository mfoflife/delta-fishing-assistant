import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

if os.name == "nt":
    from fishing_assistant.config import Config
    from fishing_assistant.runtime import Runner
    from fishing_assistant.windows import Mouse


@unittest.skipUnless(os.name == "nt", "Windows runtime")
class RuntimeTests(unittest.TestCase):
    def action_runner(self):
        runner = Runner(Config(), (123, "测试窗口", 456), True, False, Mock())
        runner.stop_event.wait = Mock(return_value=False)
        mouse = Mouse(123, 456, runner.stop_event)
        mouse._event = Mock()  # Exercise press/release logic without sending OS input.
        mouse.focused = Mock(return_value=True)
        return runner, mouse

    def test_cast_sends_two_complete_clicks_with_gap(self):
        runner, mouse = self.action_runner()
        runner.execute_action(mouse, "cast")
        self.assertEqual([call.args[0] for call in mouse._event.call_args_list], [2, 4, 2, 4])
        self.assertEqual([call.args[0] for call in runner.stop_event.wait.call_args_list], [.04, .15, .04])
        self.assertFalse(mouse.held)

    def test_pause_between_cast_clicks_cancels_second_press(self):
        runner, mouse = self.action_runner()
        def wait(seconds):
            if seconds == runner.CAST_CLICK_GAP:
                runner.stop()
            return runner.stop_event.is_set()
        runner.stop_event.wait.side_effect = wait
        with self.assertRaises(RuntimeError):
            runner.execute_action(mouse, "cast")
        self.assertEqual([call.args[0] for call in mouse._event.call_args_list], [2, 4])
        self.assertFalse(mouse.held)

    def test_focus_loss_between_cast_clicks_cancels_second_press(self):
        runner, mouse = self.action_runner()
        mouse.focused.side_effect = [True, False]
        with self.assertRaises(RuntimeError):
            runner.execute_action(mouse, "cast")
        self.assertEqual([call.args[0] for call in mouse._event.call_args_list], [2, 4])
        self.assertFalse(mouse.held)

    def test_hook_releases_zoom_and_clicks_left_only_once(self):
        runner, mouse = self.action_runner()
        runner.execute_action(mouse, "zoom")
        self.assertEqual(mouse.held, {"right"})
        runner.execute_action(mouse, "hook")
        self.assertEqual([call.args[0] for call in mouse._event.call_args_list], [8, 16, 2, 4])
        self.assertFalse(mouse.held)

    def run_single_click(self, focused=True, stopped=False):
        cache = Path(__file__).resolve().parents[1] / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as folder:
            with (patch("fishing_assistant.runtime.ROOT", Path(folder)),
                  patch("fishing_assistant.runtime.Mouse") as mouse_class,
                  patch("fishing_assistant.runtime.mss.mss") as capture_class,
                  patch("fishing_assistant.runtime.BaitReader") as reader_class,
                  patch("fishing_assistant.runtime.process_integrity", return_value={"level": 12288, "label": "管理员"})):
                mouse = mouse_class.return_value
                mouse.focused.return_value = focused
                mouse.focus_details.return_value = {}
                runner = Runner(Config(), (123, "测试窗口", 456), True, False, Mock(), test_click=True)
                if stopped:
                    runner.stop()
                runner.run()
                reader_class.return_value.read.assert_not_called()
                capture_class.return_value.__enter__.return_value.grab.assert_not_called()
                mouse.release.assert_called_once()
                self.assertEqual(runner.engine.state, "paused")
                return mouse.click.call_args_list, runner.engine.reason

    def test_single_click_sends_exactly_once_without_ocr_or_zoom(self):
        calls, reason = self.run_single_click()
        self.assertEqual([call.args for call in calls], [("left",)])
        self.assertIn("请确认游戏", reason)

    def test_single_click_focus_loss_sends_nothing(self):
        calls, reason = self.run_single_click(focused=False)
        self.assertEqual(calls, [])
        self.assertIn("前台焦点", reason)

    def test_single_click_cancel_sends_nothing(self):
        calls, reason = self.run_single_click(stopped=True)
        self.assertEqual(calls, [])
        self.assertIn("已取消", reason)

    def test_lower_permission_stops_before_capture_or_click_and_logs_reason(self):
        cache = Path(__file__).resolve().parents[1] / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as folder:
            published = []
            with (patch("fishing_assistant.runtime.ROOT", Path(folder)),
                  patch("fishing_assistant.runtime.Mouse") as mouse_class,
                  patch("fishing_assistant.runtime.mss.mss") as capture_class,
                  patch("fishing_assistant.runtime.process_integrity", side_effect=[
                      {"level": 8192, "label": "普通"}, {"level": 12288, "label": "管理员"}])):
                runner = Runner(Config(), (123, "测试窗口", 456), True, False,
                                lambda kind, data: published.append((kind, data)))
                runner.run()
                mouse_class.return_value.click.assert_not_called()
                capture_class.return_value.__enter__.return_value.grab.assert_not_called()
                self.assertEqual(runner.engine.state, "paused")
                self.assertIn("权限低于游戏", runner.engine.reason)
                self.assertTrue(any(kind == "error" for kind, _ in published))
            log = next((Path(folder)/"logs").glob("*.jsonl"))
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([item["kind"] for item in events], ["start", "permissions", "error"])


if __name__ == "__main__":
    unittest.main()
