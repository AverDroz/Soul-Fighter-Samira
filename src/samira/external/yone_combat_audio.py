"""Play locally imported Yone SFX from resolved room-scoped combat events."""
import math
from pathlib import Path

from samira_audio import MAX_EVENT_AGE, MAX_PACKET_AGE_MS, Mixer


GAINS = {
    "attack": .32,
    "attack2": .32,
    "q": .39,
    "q3": .43,
    "w": .40,
    "e": .38,
    "e_return": .40,
    "r": .48,
    "shield": .28,
}


class YoneCombatAudio:
    @staticmethod
    def load_samples(root):
        root = Path(root)
        return {kind: [{"file": kind + ".wav"}] for kind in GAINS
                if (root / (kind + ".wav")).is_file()}

    def __init__(self, root, backend=Mixer, *, mixer=None, samples=None):
        root = Path(root)
        self.samples = self.load_samples(root) if samples is None else samples
        self.backend = mixer
        self.owns_mixer = mixer is None
        if self.owns_mixer and self.samples:
            self.backend = backend(root, self.samples)
        self.scene = None
        self.serial = 0
        self.audible = False

    def close(self):
        if self.owns_mixer and self.backend is not None:
            self.backend.close()

    def update(self, state, visible, _now):
        if self.backend is None:
            return
        state = state or {}
        scene = (state.get("session"), state.get("room"))
        active = state.get("active") and state.get("hero") == "yone" and scene[0] is not None
        events = (state.get("yone") or {}).get("fx") or ()
        timestamp = state.get("time", 0)
        packet_age_ms = max(0., state.get("heartbeatTime", timestamp) - timestamp)
        raw_volume = state.get("sfxVolume", 1.)
        volume = 1.
        if isinstance(raw_volume, (int, float)) and math.isfinite(raw_volume):
            volume = min(1., max(0., raw_volume))
        hidden = any(state.get(flag) for flag in ("occluded", "paused", "transition", "stasis"))
        audible = bool(active and visible and not hidden and packet_age_ms <= MAX_PACKET_AGE_MS and volume > 0)
        was_audible = self.audible
        scene_changed = active and scene != self.scene
        if scene_changed:
            self.scene = scene
            self.serial = 0
        if scene_changed or (was_audible and not audible):
            self.backend.stop_all()
        self.audible = audible
        if not active:
            return
        if audible:
            self.backend.set_volume(volume)
        clock = state.get("clock", 0)
        visual_delay = max(0., state.get("packetClock", clock) - clock) / 30
        for event in events:
            serial = event.get("id")
            if not isinstance(serial, int) or serial <= self.serial:
                continue
            kind = event.get("kind")
            age = event.get("age")
            cue = (audible and was_audible and kind in self.samples and isinstance(age, (int, float))
                   and 0 <= age <= MAX_EVENT_AGE - packet_age_ms / 1000)
            # The room publishes effects in creation order. Let the delayed
            # renderer reach this event before advancing beyond its ID.
            if cue and age < visual_delay:
                break
            self.serial = serial
            if cue:
                self.backend.play(kind, "ultimate" if kind == "r" else "effect", GAINS[kind])
