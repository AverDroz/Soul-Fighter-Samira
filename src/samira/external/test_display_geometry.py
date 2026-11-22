import unittest

from display_geometry import DisplayGate


def pose(seq, display_id, viewport, mode="borderless"):
    return {
        "session": "yone-a", "room": 1, "seq": seq, "screen": [640, 360],
        "display": {"id": display_id, "mode": mode, "viewport": viewport},
    }


class DisplayGeometryTest(unittest.TestCase):
    def test_client_resize_never_accepts_a_repeated_old_packet(self):
        gate = DisplayGate()
        window = (40, 70, 1280, 720)
        fullscreen = (0, 0, 3840, 2160)
        old = [0, 0, 1280, 720]
        self.assertIsNone(gate.choose(1, window, pose(10, 1, old, "windowed")))
        self.assertEqual(gate.choose(1, window, pose(11, 1, old, "windowed")), window)
        self.assertIsNone(gate.choose(1, fullscreen, pose(11, 1, old, "windowed")))
        self.assertIsNone(gate.choose(1, fullscreen, pose(11, 1, old, "windowed")))
        self.assertIsNone(gate.choose(1, fullscreen, pose(12, 1, old, "windowed")))
        new = [0, 0, 3840, 2160]
        self.assertIsNone(gate.choose(1, fullscreen, pose(13, 2, new)))
        self.assertEqual(gate.choose(1, fullscreen, pose(14, 2, new)), fullscreen)

    def test_letterbox_origin_is_added_to_the_actual_win32_client(self):
        gate = DisplayGate()
        client = (-2560, 120, 2560, 1200)
        rect = [320, 60, 1920, 1080]
        self.assertIsNone(gate.choose(7, client, pose(5, 2, rect)))
        self.assertEqual(gate.choose(7, client, pose(6, 2, rect)), (-2240, 180, 1920, 1080))
        self.assertIsNone(gate.choose(7, client, pose(7, 3, rect, "exclusive")))
        self.assertIsNone(gate.choose(7, client, pose(8, 3, rect, "exclusive")))

    def test_legacy_packets_still_render_and_malformed_viewports_stay_native(self):
        gate = DisplayGate()
        client = (10, 20, 1280, 720)
        legacy = {"session": "old", "room": 1, "seq": 0}
        self.assertEqual(gate.choose(3, client, legacy), client)
        self.assertIsNone(gate.choose(3, client, pose(1, 2, [0, -50, 1280, 720])))
        self.assertIsNone(gate.choose(3, client, pose(2, 2, [0, -50, 1280, 720])))


if __name__ == "__main__":
    unittest.main()
