"""Play Skin30 audio from acknowledged test-room snapshots."""
import json
import math
import os
from pathlib import Path


CASTS = frozenset(("q", "qmelee", "w", "e", "eq", "r"))
# The R voice event also contains media 1853863330, a nonverbal shout.
R_SPOKEN_MEDIA = frozenset((2131774679, 2138109273, 573580350))
R_VOICE_INTERVAL = 10
MAX_EVENT_AGE = .18
MAX_PACKET_AGE_MS = 200


class Mixer:
    """A private SDL mixer with dedicated speech and ultimate channels."""

    def __init__(self, root, samples):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from pygame import mixer

        self.mixer = mixer
        mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        try:
            mixer.set_num_channels(10)
            self.channels = [mixer.Channel(index) for index in range(10)]
            self.samples = {
                role: [mixer.Sound(str(root / sample["file"])) for sample in clips]
                for role, clips in samples.items()
            }
        except Exception:
            mixer.quit()
            raise
        self.indices = {}
        self.volumes = [0.] * len(self.channels)
        self.roles = [None] * len(self.channels)
        self.volume = 1.

    def set_volume(self, volume):
        if volume == self.volume:
            return
        self.volume = volume
        for channel, gain in zip(self.channels, self.volumes):
            channel.set_volume(volume * gain)

    def play(self, role, group, gain):
        if group == "voice":
            index = 0
        elif group == "ultimate":
            index = 1
        else:
            slots = range(2, len(self.channels))
            busy = [self.channels[i].get_busy() for i in slots]
            if sum(active and self.roles[i] == role for i, active in zip(slots, busy)) >= 2:
                return False
            index = next((i for i, active in zip(slots, busy) if not active), None)
            if index is None:
                return False
        variants = self.samples[role]
        number = self.indices.get(role, 0)
        channel = self.channels[index]
        # SDL_mixer resets channel volume on some playback paths.
        channel.play(variants[number % len(variants)])
        channel.set_volume(self.volume * gain)
        self.volumes[index] = gain
        self.roles[index] = role
        self.indices[role] = number + 1
        return True

    def busy(self, group):
        return self.channels[0 if group == "voice" else 1].get_busy()

    def stop(self, group):
        self.channels[0 if group == "voice" else 1].stop()

    def stop_all(self):
        self.mixer.stop()

    def close(self):
        self.mixer.quit()


class SamiraAudio:
    def __init__(self, root, backend=Mixer):
        root = Path(root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        samples = {role: manifest["samples"][role] for role in CASTS}
        samples["voice_r"] = [
            clip for clip in manifest["samples"]["voice_r"] if clip["wem_id"] in R_SPOKEN_MEDIA
        ]
        self.backend = backend(root, samples)
        self.scene = None
        self.audible = False
        self.serial = 0
        self.ultimate_casts = 0

    def close(self):
        self.backend.close()

    def _cast(self, skill):
        ultimate = skill == "r"
        self.backend.play(skill, "ultimate" if ultimate else "effect", .42)
        if ultimate:
            self.ultimate_casts += 1
            if self.ultimate_casts % R_VOICE_INTERVAL == 0 and not self.backend.busy("voice"):
                self.backend.play("voice_r", "voice", .44)

    def update(self, state, visible, _now):
        """Discard events while silent, including the first snapshot after resuming."""
        state = state or {}
        visual = state.get("visual") or {}
        events = visual.get("events") or []
        scene = (state.get("session"), state.get("room"))
        active = bool(state.get("active") and scene[0] is not None)
        fresh = state.get("heartbeatTime", 0) - state.get("time", 0) <= MAX_PACKET_AGE_MS
        raw_volume = state.get("sfxVolume", 1)
        volume = max(0., min(1., raw_volume)) if isinstance(raw_volume, (int, float)) and math.isfinite(raw_volume) else 1.
        audible = bool(active and visible and fresh and volume > 0)
        was_audible = self.audible

        if active and scene != self.scene:
            self.backend.stop_all()
            self.serial = 0
            if self.scene is None or scene[0] != self.scene[0]:
                self.ultimate_casts = 0
            self.scene = scene
        self.audible = audible
        if not audible:
            if was_audible:
                self.backend.stop_all()
            if events:
                self.serial = max(self.serial, max(event["id"] for event in events))
            return

        self.backend.set_volume(volume)
        skills = visual.get("skills") or (visual.get("skill") or {},)
        if not any(skill.get("kind") == "r" for skill in skills) and self.backend.busy("ultimate"):
            self.backend.stop("ultimate")
        for event in events:
            serial = event["id"]
            if serial <= self.serial:
                continue
            self.serial = serial
            source = event.get("source")
            if (was_audible and event.get("kind") == "cast" and source in CASTS
                    and 0 <= event.get("age", 1.) <= MAX_EVENT_AGE):
                self._cast(source)
