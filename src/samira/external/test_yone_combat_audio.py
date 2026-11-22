"""Exercise combat audio without imported League files or an audio device."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from yone_combat_audio import YoneCombatAudio


class RecordingMixer:
    def __init__(self, _root, samples):
        self.samples = samples
        self.plays = []
        self.stops = 0
        self.volume = 1.

    def play(self, clip, group, gain):
        self.plays.append((clip, group, gain * self.volume))

    def set_volume(self, volume):
        self.volume = volume

    def stop_all(self):
        self.stops += 1

    def close(self):
        self.stop_all()


def snapshot(*effects, **changes):
    state = {"hero": "yone", "active": True, "session": "run", "room": 1,
             "time": 5000, "heartbeatTime": 5000, "sfxVolume": 1,
             "yone": {"fx": effects}}
    return dict(state, **changes)


def effect(serial, kind, age=0.):
    return {"id": serial, "kind": kind, "age": age,
            "origin": [20, 20], "target": [28, 20]}


class YoneCombatAudioTests(unittest.TestCase):
    roles = ("attack", "attack2", "q", "q3", "w", "e", "e_return", "r", "shield")

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for role in self.roles:
            (self.root / (role + ".wav")).touch()
        (self.root / "dance.wav").touch()
        self.audio = YoneCombatAudio(self.root, backend=RecordingMixer)
        self.mixer = self.audio.backend
        self.addCleanup(self.audio.close)
        self.audio.update(snapshot(), True, 0)

    def update(self, *events, visible=True, **packet):
        self.audio.update(snapshot(*events, **packet), visible, 0)

    def played(self):
        return [clip for clip, _, _ in self.mixer.plays]

    def test_only_new_combat_cues_play_and_respect_master_volume(self):
        self.assertEqual(set(self.mixer.samples), set(self.roles))
        for serial, clip in enumerate(self.roles, 1):
            new_effect = effect(serial, clip)
            self.update(new_effect, sfxVolume=.5)
            self.update(new_effect)
        self.update(effect(10, "unmapped"), effect(11, "dance"))
        self.assertEqual(self.played(), list(self.roles))
        self.assertEqual(self.mixer.plays[7][1], "ultimate")
        self.assertTrue(all(0 < gain <= .5 for _, _, gain in self.mixer.plays))

    def test_room_and_session_reset_ids_and_stop_the_previous_scene(self):
        self.update(effect(1, "q"))
        previous_stops = self.mixer.stops
        self.update(effect(1, "attack"), room=2)
        self.assertEqual(self.mixer.stops, previous_stops + 1)
        self.update(effect(1, "w"), room=2, session="next-run")
        self.assertEqual(self.mixer.stops, previous_stops + 2)
        self.assertEqual(self.played(), ["q", "attack", "w"])

    def test_cue_waits_for_the_interpolated_visual_clock(self):
        wind = effect(1, "q3")
        shield = effect(2, "shield")
        self.update(wind, shield, clock=12.5, packetClock=13)
        self.assertEqual(self.played(), [])
        self.update(wind, shield, clock=13, packetClock=13)
        self.assertEqual(self.played(), ["q3", "shield"])

    def test_muted_hidden_or_stale_cues_are_never_replayed(self):
        self.update(effect(1, "q"))
        self.update(effect(2, "q"), visible=False)
        self.update(effect(2, "q"), effect(3, "q"))
        self.update(effect(4, "q"), occluded=True)
        self.update(effect(4, "q"))
        self.update(effect(5, "q"), paused=True)
        self.update(effect(5, "q"))
        self.update(effect(6, "q"), transition=True)
        self.update(effect(6, "q"))
        self.update(effect(7, "q"), sfxVolume=0)
        self.update(effect(7, "q"))
        self.update(effect(8, "q"), heartbeatTime=5210)
        self.update(effect(8, "q"))
        self.update(effect(9, "q", age=.21))
        self.update(effect(10, "q", age=.16), heartbeatTime=5030)
        self.update(effect(11, "q", age=-.1))
        self.update(effect(12, "attack2"))
        self.assertEqual(self.played(), ["q", "attack2"])

    def test_mixer_is_optional_and_shared_mixer_stays_open(self):
        empty = self.root / "missing"
        audio = YoneCombatAudio(empty, backend=RecordingMixer)
        self.assertIsNone(audio.backend)
        audio.update(snapshot(effect(1, "q")), True, 0)
        audio.close()
        shared = YoneCombatAudio(self.root, mixer=self.mixer, samples=self.mixer.samples)
        self.assertIs(shared.backend, self.mixer)
        previous_stops = self.mixer.stops
        shared.close()
        self.assertEqual(self.mixer.stops, previous_stops)


if __name__ == "__main__":
    unittest.main()
