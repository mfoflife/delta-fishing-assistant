import unittest
from pathlib import Path
import cv2
import numpy as np
from fishing_assistant.vision import BaitReader, StableBait, splash_score
from fishing_assistant.config import pixel_roi


class VisionTests(unittest.TestCase):
    def digit(self, number):
        path = Path(__file__).resolve().parents[1]/"fishing_assistant"/"assets"/"digits"/f"{number}.png"
        return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)

    def test_padded_digit_with_nearby_hud_noise(self):
        reader = BaitReader()
        for number in range(6):
            with self.subTest(number=number):
                digit = self.digit(number)
                canvas = np.zeros((70, 110, 3), np.uint8)
                canvas[15:47, 20:44] = digit
                cv2.putText(canvas, "NAT", (60, 24), cv2.FONT_HERSHEY_SIMPLEX, .3, (200, 200, 200), 1)
                cv2.line(canvas, (62, 36), (57, 46), (200, 200, 200), 1)
                cv2.ellipse(canvas, (77, 42), (10, 4), 0, 0, 360, (200, 200, 200), 1)
                self.assertEqual(reader.read(canvas)[0], number)
                resized = cv2.resize(canvas, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
                self.assertEqual(reader.read(resized)[0], number)

    def test_two_plausible_digits_are_ambiguous(self):
        canvas = np.zeros((40, 80, 3), np.uint8)
        canvas[4:36, 4:28] = self.digit(4)
        canvas[4:36, 45:69] = self.digit(5)
        self.assertIsNone(BaitReader().read(canvas)[0])

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
