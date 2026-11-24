"""Render the locally supplied Miss Fortune rig and its authored clips."""
import math

import numpy as np

from model import GPURenderer, Model, YONE_VIEW
from mf_muzzle import MuzzleFlashes
from mf_taunt_doll import TauntDoll


LOOPING = {'idle', 'base_idle', 'run', 'strut_run_loop', 'r', 'taunt_loop', 'joke_loop',
           'dance_loop', 'recall_loop', 'homeguard'}
EXPRESSIONS = ('joke', 'taunt', 'taunt_spam', 'dance', 'laugh', 'recall', 'recall_cinematic')
RECALL_FRAMES = 240
PIXEL_SCALE = .26
CRIT_RECOVERY_BLENDS = {('crit', 'crit_out'), ('crit_out', 'base_idle')}
SHOT_CLIPS = {'attack', 'attack2', 'crit', 'q'}


def animation(state, durations):
    frame = max(0., state.get('actionFrame', state.get('clock', 0)))
    expression = state.get('expression')
    if expression == 'joke' and 'joke_in' in durations:
        entry = max(1, round(30 * durations['joke_in']))
        if frame < entry:
            return 'joke_in', frame / (30 * durations['joke_in'])
        frame -= entry
    if expression in EXPRESSIONS and expression in durations:
        duration = max(1, round(30 * durations[expression]))
        loop = 'taunt_loop' if expression == 'taunt_spam' else expression + '_loop'
        if expression == 'recall' and 'recall_out' in durations:
            exit_frames = max(1, round(30 * durations['recall_out']))
            if frame >= RECALL_FRAMES - exit_frames:
                return 'recall_out', min(1., (frame - RECALL_FRAMES + exit_frames) / exit_frames)
        if frame >= duration and loop in LOOPING and loop in durations:
            period = 30 * durations[loop]
            return loop, ((frame - duration) / period) % 1
        return expression, min(1., frame / duration)

    clip = state.get('clip') or state['kind']
    if clip not in durations:
        clip = 'run' if state.get('mfMoving') and 'run' in durations else 'idle'
    action_length = state.get('actionLength')
    frame_count = max(1, action_length - 1) if action_length and clip not in LOOPING else 30 * durations[clip]
    if clip in LOOPING:
        return clip, (frame % frame_count) / frame_count
    return clip, min(1., frame / frame_count)


def barrage_recoil(state, model):
    timing = state.get('mfBarrage')
    if not isinstance(timing, dict):
        return None
    clip_info = model.rig_events.get('states', {}).get('r_preview', {})
    if clip_info.get('mode') != 'hold_terminal_pose':
        return None
    start, interval, clock = timing.get('start'), timing.get('interval'), state.get('clock')
    if not all(type(value) in (int, float) and math.isfinite(value) for value in (start, interval, clock)):
        return None
    if interval <= 0 or clock < start:
        return None

    # The supplied windup ends with both guns pointing forward. Only the gun
    # branches recoil per pulse, so the grounded actor and authored pose stay put.
    wave_age = (clock - start) % interval
    offsets = {}
    for socket, delay in (('R_weapon', 0.), ('L_weapon', .75)):
        index = model.node_names.get(socket)
        age = (wave_age - delay) % interval
        if index is not None and age < 3.:
            impulse = (1. - age / 3.) ** 2
            offsets[index] = np.array((0., 3.0 * impulse, -8.0 * impulse), dtype='f4')
    return offsets or None


class MissFortuneRenderer:
    def __init__(self, ctx, path, effect_assets=None):
        self.actor = None
        self.taunt_doll = None
        self.muzzles = None
        self.blend_seconds = .04
        if not path.is_file():
            return
        try:
            model = Model(path, hero='mf')
            model.pixel_scale = PIXEL_SCALE
            self.actor = GPURenderer(ctx, model)
            self.taunt_doll = TauntDoll(ctx, path)
            print('Miss Fortune model loaded', flush=True)
        except (OSError, ValueError, KeyError, RuntimeError, AssertionError) as error:
            print(f'Miss Fortune model unavailable: {error!r}', flush=True)
        if self.actor and effect_assets is not None:
            try:
                centres = ('right', 'left')
                sockets = {}
                for index, label in enumerate(centres, 1):
                    joint = model.node_names[f'BUFFBONE_CSTM_WEAPON_MUZZLE_{index}']
                    sockets[label] = (joint, np.array((0., 0., 0., 1.), dtype='f4'))
                    sockets[label + '_forward'] = (joint, np.array((0., 0., -16., 1.), dtype='f4'))
                self.muzzles = MuzzleFlashes(ctx, effect_assets)
                self.actor.node_sockets = sockets
                print('Miss Fortune GPU muzzle loaded', flush=True)
            except Exception as error:
                print(f'Miss Fortune GPU muzzle unavailable, using native effects: {error!r}', flush=True)

    def reset(self):
        self.blend_seconds = .04
        if self.actor:
            self.actor.reset()
        if self.taunt_doll:
            self.taunt_doll.reset()

    def draw(self, state, dt):
        if not self.actor:
            return False, {}
        try:
            clip, phase = animation(state, self.actor.model.durations)
            confirmed_shot = clip in SHOT_CLIPS and state.get('actionLength')
            if confirmed_shot or (clip == 'r' and state.get('mfBarrage')):
                # The weapon has already fired. Match the pose to the live muzzle.
                self.blend_seconds = .001
            elif self.actor.kind != clip:
                self.blend_seconds = .10 if (self.actor.kind, clip) in CRIT_RECOVERY_BLENDS else .04
            sx, sy = state.get('bodyScale', (1, 1))
            x, y = state.get('viewFace') or state['face']
            yaw = math.pi / 2 - math.atan2(y / (YONE_VIEW[1] * (sy or 1)), x / (sx or 1))
            w = state.get('mfW', 0)
            strength = max(0., min(1., w / .12)) if type(w) in (int, float) and math.isfinite(w) else 0.
            recoil = barrage_recoil(state, self.actor.model) if clip in ('r', 'r_in') else None
            points = self.actor.draw(
                clip, phase, tuple(state['position']), tuple(state['screen']), yaw, dt,
                clip=clip, hurt=state.get('hurt', False), body_scale=(sx, sy), anchor_root=True,
                snap_facing=clip not in ('idle', 'run'), blend_seconds=self.blend_seconds, warm_glow=strength,
                world_offsets=recoil,
            )
            if self.taunt_doll:
                self.taunt_doll.draw(state, self.actor, yaw, dt, clip, phase)
            cue = state.get('mfMuzzle')
            if self.muzzles and isinstance(cue, dict) and cue.get('kind') == clip:
                try:
                    self.muzzles.draw(state, points)
                except Exception as error:
                    print(f'Miss Fortune GPU muzzle disabled, using native effects: {error!r}', flush=True)
                    self.muzzles.close()
                    self.muzzles = None
                    self.actor.node_sockets.clear()
            capabilities = {'mfModel': True}
            if self.muzzles:
                capabilities['mfMuzzle'] = True
            return True, capabilities
        except Exception as error:
            print(f'Miss Fortune model disabled; native character restored: {error!r}', flush=True)
            self.close()
            return False, {}

    def close(self):
        if self.muzzles:
            self.muzzles.close()
            self.muzzles = None
        if self.taunt_doll:
            self.taunt_doll.close()
            self.taunt_doll = None
        if self.actor:
            self.actor.close()
            self.actor = None
