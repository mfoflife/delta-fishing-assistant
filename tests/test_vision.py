import unittest
import numpy as np
from fishing_assistant.vision import BaitReader, StableBait, splash_score
from fishing_assistant.config import pixel_roi


class VisionTests(unittest.TestCase):
    def test_bright_unsaturated_area_is_counted(self):
        image = np.zeros((100, 100, 3), np.uint8)
        image[:10] = 200
        score, _ = splash_score(image)
        self.assertAlmostEqual(score, .1)

    def test_dark_image_has_no_bait(self):
        value, _ = BaitReader().read(np.zeros((32, 24, 3), np.uint8))
        self.assertIsNone(value)

    def test_unknown_reading_does_not_become_stable(self):
        reader = StableBait()
        self.assertIsNone(reader.update(5, 0))
        self.assertIsNone(reader.update(None, .1))
        self.assertIsNone(reader.update(5, .3))
        self.assertEqual(reader.update(5, .6), 5)
        self.assertIsNone(reader.update(None, 1.5))

    def test_roi_scales_with_client_size(self):
        self.assertEqual(pixel_roi([.25, .25, .5, .5], 200, 100), (50, 25, 100, 50))


if __name__ == "__main__":
    unittest.main()
