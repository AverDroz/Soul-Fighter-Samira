"""Check original audio data and its playback decisions without an audio device."""
from array import array
import hashlib
import json
from pathlib import Path
import unittest
import wave

from samira_audio import SamiraAudio


ROOT = Path(__file__).resolve().parents[3] / "assets/samira-soul-fighter/audio"


class CaptureMixer:
    def __init__(self, _, samples):
        self.samples = samples
        self.actions = []
        self.playing = set()

    def set_volume(self, volume):
        self.actions.append(("volume", volume))

    def play(self, name, group, gain):
        assert name in self.samples
        self.actions.append(("play", name, group))
        self.playing.add(group)
        return True

    def busy(self, group):
        return group in self.playing

    def stop(self, group):
        self.actions.append(("stop", group))
        self.playing.discard(group)

    def stop_all(self):
        self.actions.append(("stop_all",))
        self.playing.clear()

    def close(self):
        self.stop_all()


def snapshot(*events, room=1, active=True, age=0, volume=1, r=False):
    return {"active": active, "session": "samira", "room": room, "time": 300,
            "heartbeatTime": 300 + age, "sfxVolume": volume,
            "visual": {"events": events, "skills": [{"kind": "r"}] if r else []}}


def event(serial, kind, source=None, age=0):
    return {"id": serial, "kind": kind, "source": source, "age": age}


class TestAudio(unittest.TestCase):
    def setUp(self):
        self.audio = SamiraAudio(ROOT, backend=CaptureMixer)
        self.mixer = self.audio.backend
        self.audio.update(snapshot(), True, 0)

    def roles(self):
        return [action[1] for action in self.mixer.actions if action[0] == "play"]

    def test_audio_files(self):
        manifest = json.loads((ROOT / "manifest.json").read_bytes())
        self.assertEqual(manifest["voice"]["locale"], "ru_RU")
        self.assertEqual(len(manifest["samples"]), 26)
        for samples in manifest["samples"].values():
            for sample in samples:
                path = ROOT / sample["file"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sample["sha256"])
                with wave.open(str(path), "rb") as data:
                    self.assertEqual(data.getsampwidth(), 2)
                    self.assertIn(data.getnchannels(), (1, 2))
                    pcm = array("h", data.readframes(data.getnframes()))
                    self.assertTrue(any(pcm))

    def test_only_casts_play_and_each_event_is_deduplicated(self):
        casts = ("q", "qmelee", "w", "e", "eq", "r")
        for number, kind in enumerate(casts, 1):
            packet = snapshot(event(number, "cast", kind), r=kind == "r")
            self.audio.update(packet, True, number)
            self.audio.update(packet, True, number+.03)
        ignored = ("attack", "melee", "move", "target", "hit", "block", "r", "w", "eq")
        self.audio.update(snapshot(*(event(i, kind, "q") for i, kind in enumerate(ignored, 7))), True, 7)
        self.assertEqual(self.roles(), list(casts))
        self.assertEqual(set(self.mixer.samples), {*casts, "voice_r"})

    def test_scene_resume_mute_and_stale_packets(self):
        self.audio.update(snapshot(event(1, "cast", "q")), True, 1)
        self.audio.update(snapshot(event(2, "cast", "q")), False, 2)
        self.audio.update(snapshot(event(3, "cast", "q")), True, 3)
        self.audio.update(snapshot(event(4, "cast", "q"), volume=0), True, 4)
        self.audio.update(snapshot(event(5, "cast", "q")), True, 5)
        self.audio.update(snapshot(event(6, "cast", "q"), age=300), True, 6)
        self.audio.update(snapshot(event(7, "cast", "q")), True, 7)
        self.audio.update(snapshot(event(8, "cast", "q", age=.25)), True, 8)
        self.audio.update(snapshot(event(1, "cast", "w"), room=2), True, 9)
        self.audio.update(snapshot(active=False), False, 10)
        self.assertEqual(self.roles(), ["q", "w"])
        self.assertEqual(self.mixer.actions[-1], ("stop_all",))

    def test_one_spoken_line_per_ten_ultimate_casts(self):
        for i in range(1, 10):
            self.audio.update(snapshot(event(i*2-1, "cast", "q"), event(i*2, "cast", "r"), r=True), True, i)
        self.assertEqual(self.roles(), ["q", "r"] * 9)
        self.audio.update(snapshot(event(19, "cast", "r"), event(20, "r"), r=True, volume=.4), True, 10)
        self.audio.update(snapshot(event(19, "cast", "r"), event(20, "r"), volume=.4), True, 12)
        self.assertEqual(self.roles(), ["q", "r"] * 9 + ["r", "voice_r"])
        self.assertEqual({entry["wem_id"] for entry in self.mixer.samples["voice_r"]},
                         {2131774679, 2138109273, 573580350})
        self.assertIn(("volume", .4), self.mixer.actions)
        self.assertEqual(self.mixer.actions[-1], ("stop", "ultimate"))


if __name__ == "__main__":
    unittest.main()
