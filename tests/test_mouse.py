import os
import threading
import unittest
from unittest.mock import Mock

if os.name == "nt":
    from fishing_assistant.windows import Mouse


@unittest.skipUnless(os.name == "nt", "Windows input adapter")
class MouseTests(unittest.TestCase):
    def mouse(self):
        mouse = Mouse(0, 0, threading.Event())
        mouse._event = Mock()  # No real OS input is sent by any test.
        mouse.focused = Mock(return_value=True)
        return mouse

    def test_focus_loss_prevents_mouse_down(self):
        mouse = self.mouse()
        mouse.focused.return_value = False
        with self.assertRaises(RuntimeError):
            mouse.click("left")
        mouse._event.assert_not_called()

    def test_stop_cancels_mouse_down(self):
        mouse = self.mouse()
        mouse.stop_event.set()
        with self.assertRaises(RuntimeError):
            mouse.click("left")
        mouse._event.assert_not_called()

    def test_owned_buttons_released_on_cleanup(self):
        mouse = self.mouse()
        mouse.down("right")
        mouse.release()
        self.assertEqual([call.args[0] for call in mouse._event.call_args_list], [8, 16])
        self.assertFalse(mouse.held)

    def test_unowned_button_is_not_released(self):
        mouse = self.mouse()
        mouse.up("left")
        mouse._event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
