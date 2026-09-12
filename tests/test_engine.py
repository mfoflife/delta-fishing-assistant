import unittest
from fishing_assistant.config import Config
from fishing_assistant.engine import Engine, Observation, SplashGate


class GateTests(unittest.TestCase):
    def test_entry_splash_is_ignored_and_one_bite_only(self):
        gate = SplashGate(Config())
        gate.reset(0)
        hits = []
        for i in range(600):
            now = i/60
            score = 0.05 if 2.3 <= now <= 3.15 or 7 <= now <= 7.7 else 0.001
            if gate.update(now, score):
                hits.append(now)
        self.assertEqual(len(hits), 1)
        self.assertGreaterEqual(hits[0], 7)
        self.assertLess(hits[0], 7.1)

    def test_long_entry_requires_calm_before_arming(self):
        gate = SplashGate(Config())
        gate.reset(0)
        for i in range(360):
            self.assertFalse(gate.update(i/60, 0.05))
        self.assertFalse(gate.armed)

    def test_one_frame_flash_does_not_trigger(self):
        gate = SplashGate(Config(cast_blind=0, calm_time=0))
        gate.reset(0)
        gate.update(0, 0)
        self.assertFalse(gate.update(0.1, .05))
        self.assertFalse(gate.update(0.2, 0))


class EngineTests(unittest.TestCase):
    def setup_hook(self, bait, vision=False):
        cfg = Config(bait_vision=vision, initial_bait=bait, cast_blind=0, calm_time=0, zoom_mode="manual")
        engine = Engine(cfg)
        engine.start(0)
        self.assertEqual(engine.update(0, Observation(bait=bait)), ["cast"])
        engine.update(.1, Observation(bait=bait))
        engine.update(.2, Observation(.05, bait))
        self.assertEqual(engine.update(.25, Observation(.05, bait)), ["hook"])
        return engine

    def advance(self, engine, start, end, bait=None):
        actions = []
        tick = start
        while tick < end-1e-6:
            actions += [(tick, action) for action in engine.update(tick, Observation(bait=bait))]
            tick += .05
        return actions

    def test_ordinary_wait_starts_at_hook_not_cast(self):
        engine = self.setup_hook(5)
        actions = self.advance(engine, .3, 3.04)
        self.assertFalse(any(action == "cast" for _, action in actions))
        self.assertEqual(engine.update(3.06, Observation()), ["cast"])

    def test_last_bait_waits_full_reload_period(self):
        engine = self.setup_hook(1)
        actions = self.advance(engine, .3, 5.04)
        self.assertEqual(engine.state, "reload")
        self.assertFalse(any(action == "cast" for _, action in actions))
        self.assertEqual(engine.update(5.06, Observation()), ["cast"])
        self.assertEqual(engine.bait, 5)

    def test_zero_bait_never_casts_when_reload_timer_expires(self):
        engine = self.setup_hook(1, vision=True)
        self.advance(engine, .3, 6.0, bait=0)
        self.assertEqual(engine.state, "reload")
        self.assertEqual(engine.update(6.05, Observation(bait=5)), ["cast"])

    def test_focus_loss_prevents_due_cast(self):
        engine = self.setup_hook(5)
        self.advance(engine, .3, 3.0)
        self.assertEqual(engine.update(3.1, Observation(focused=False)), [])
        self.assertEqual(engine.state, "paused")

    def test_pause_prevents_all_actions(self):
        engine = self.setup_hook(5)
        engine.pause()
        self.assertEqual(engine.update(100, Observation(.1, 5)), [])

    def test_unknown_bait_at_start_does_not_click(self):
        engine = Engine(Config())
        engine.start(0)
        self.assertEqual(engine.update(.1, Observation()), [])
        self.assertEqual(engine.state, "prepare")

    def test_processing_stall_pauses_instead_of_using_old_frame(self):
        engine = self.setup_hook(5)
        self.assertEqual(engine.update(4, Observation()), [])
        self.assertEqual(engine.state, "paused")

    def test_bright_water_cannot_trigger_hook_and_explains_failure(self):
        engine = Engine(Config(bait_vision=False))
        engine.start(0, already_cast=True)
        actions = []
        for i in range(1, 250):
            actions += engine.update(i*.05, Observation(.92))
        self.assertEqual(actions, [])
        self.assertEqual(engine.state, "paused")
        self.assertIn("亮色持续超标", engine.reason)

    def test_water_clearing_before_deadline_can_still_arm(self):
        engine = Engine(Config(bait_vision=False))
        engine.start(0, already_cast=True)
        for i in range(1, 220):
            engine.update(i*.05, Observation(.92 if i < 180 else 0))
        self.assertTrue(engine.gate.armed)
        self.assertEqual(engine.state, "fishing")

    def test_non_finite_parameter_rejected(self):
        with self.assertRaises(ValueError):
            Config(reel_wait=float("nan")).validate()


if __name__ == "__main__":
    unittest.main()
