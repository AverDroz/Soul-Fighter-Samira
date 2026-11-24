"""Draw the locally supplied Skin69 taunt doll at its authored socket."""

import math

import numpy as np

from model import GPURenderer, Model


class TauntDoll:
    def __init__(self, ctx, path):
        self.actor = None
        prop = path.parent / 'taunt-doll' / 'doll.glb'
        if not prop.is_file():
            return
        try:
            model = Model(prop, hero='mf')
            event = model.rig_events['authored_event']
            self.joint = event['joint']
            self.start_frame = event['frame']
            self.clips = {}
            for action in ('spam', 'loop'):
                effect = model.rig_events['effects'][action]
                pitch, yaw, roll = effect['rotation_degrees']
                if pitch or roll:
                    raise ValueError('Unsupported taunt doll emitter rotation')
                angle = math.radians(yaw)
                c, s = math.cos(angle), math.sin(angle)
                matrix = np.array(((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1)), dtype='f4')
                matrix[:, :3] *= np.array(effect['scale'], dtype='f4')
                clip = effect['clip']
                self.clips[action] = (clip, 30 * model.durations[clip], matrix)
            self.actor = GPURenderer(ctx, model)
        except Exception as error:
            print(f'Miss Fortune taunt doll unavailable: {error!r}', flush=True)

    def draw(self, state, main_actor, yaw, dt, clip, phase):
        if self.actor is None or clip not in ('taunt', 'taunt_loop', 'taunt_spam'):
            return
        sustained = clip == 'taunt_loop' and state.get('expression') == 'taunt_spam'
        if clip != 'taunt_spam' and not sustained and 'taunt_spam' in main_actor.model.durations:
            return
        try:
            if sustained:
                # The authored body and doll loops have the same duration.
                name, _, emitter = self.clips['loop']
                progress = phase
            else:
                age = state.get('actionFrame', state.get('clock', 0)) - self.start_frame
                if age < 0:
                    return
                name, duration, emitter = self.clips['spam']
                if age < duration:
                    progress = age / duration
                else:
                    age -= duration
                    name, duration, emitter = self.clips['loop']
                    progress = (age / duration) % 1
            main_model = main_actor.model
            self.actor.model.pixel_scale = main_model.pixel_scale
            self.actor.view = main_actor.view
            anchor = main_model.world_matrices(main_actor.pose, clip, phase)[main_model.node_names[self.joint]]
            self.actor.draw(
                name, progress, tuple(state['position']), tuple(state['screen']), yaw, dt,
                body_scale=tuple(state.get('bodyScale', (1, 1))), detached=True,
                model_transform=anchor @ emitter,
            )
        except Exception as error:
            print(f'Miss Fortune taunt doll disabled: {error!r}', flush=True)
            self.close()

    def reset(self):
        if self.actor is not None:
            self.actor.reset()

    def close(self):
        if self.actor is not None:
            self.actor.close()
            self.actor = None
