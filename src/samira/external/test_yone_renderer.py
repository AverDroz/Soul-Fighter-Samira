import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

from bridge import PREFIX, Tail
from mastery_renderer import MasteryRenderer
from model import GPURenderer, Model

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))

def write_rig(path):
    """A generic skinned GLB with two primitives and no Samira bone names."""
    blob = bytearray()
    views, accessors = [], []

    def view(data):
        index = len(views)
        views.append(dict(buffer=0, byteOffset=len(blob), byteLength=len(data)))
        blob.extend(data)
        blob.extend(b'\0' * (-len(blob) % 4))
        return index

    def accessor(data, dtype, size, component):
        index = len(accessors)
        data = np.asarray(data, dtype=dtype)
        accessors.append(dict(bufferView=view(data.tobytes()), componentType=component,
                              count=len(data), type=size))
        return index

    indices = accessor([0, 1, 2], '<u2', 'SCALAR', 5123)
    texcoords = accessor([(0, 0), (0, 1), (1, 0)], '<f4', 'VEC2', 5126)
    joints = accessor([(0, 0, 0, 0)] * 3, '<u2', 'VEC4', 5123)
    weights = accessor([(1, 0, 0, 0)] * 3, '<f4', 'VEC4', 5126)
    bind = accessor([np.eye(4)] * 168, '<f4', 'MAT4', 5126)
    times = accessor([0, 1], '<f4', 'SCALAR', 5126)
    values = accessor([(0, 0, 0), (15, 0, 0)], '<f4', 'VEC3', 5126)
    primitives = []
    for x in (-70, 40):
        positions = accessor([(x, 10, 0), (x, 135, 0), (x + 40, 10, 0)], '<f4', 'VEC3', 5126)
        primitives.append(dict(attributes=dict(POSITION=positions, TEXCOORD_0=texcoords,
                                                JOINTS_0=joints, WEIGHTS_0=weights),
                               indices=indices, material=0))
    png = io.BytesIO()
    Image.new('RGBA', (1, 1), (220, 30, 30, 255)).save(png, format='PNG')
    image = view(png.getvalue())
    gltf = dict(asset={'version': '2.0'}, buffers=[{'byteLength': len(blob)}],
                bufferViews=views, accessors=accessors,
                nodes=[{'name': 'RigOrigin'}, *({'name': f'Bone{i}'} for i in range(167)), {'mesh': 0, 'skin': 0}],
                skins=[{'joints': list(range(168)), 'inverseBindMatrices': bind}], meshes=[{'primitives': primitives}],
                images=[{'bufferView': image, 'mimeType': 'image/png'}], textures=[{'source': 0}],
                materials=[{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
                animations=[dict(name='idle', samplers=[dict(input=times, output=values)],
                                 channels=[dict(sampler=0, target={'node': 0, 'path': 'translation'})])])
    payload = json.dumps(gltf).encode('utf-8')
    payload += b' ' * (-len(payload) % 4)
    path.write_bytes(struct.pack('<4sIIII', b'glTF', 2, 28 + len(payload) + len(blob), len(payload), 0x4e4f534a)
                     + payload + struct.pack('<II', len(blob), 0x004e4942) + blob)


class YoneRendererTests(unittest.TestCase):
    def setUp(self):
        self.ctx = moderngl.create_standalone_context(require=330)
        self.addCleanup(self.ctx.release)
        color = self.ctx.texture((160, 160), 4)
        depth = self.ctx.depth_renderbuffer(color.size)
        self.fbo = self.ctx.framebuffer([color], depth)
        for resource in (color, depth, self.fbo):
            self.addCleanup(resource.release)
        self.fbo.use()
        self.fbo.clear(0, 0, 0, 0)

    def pixels(self):
        return np.frombuffer(self.fbo.read(components=4), dtype='u1').reshape(160, 160, 4)

    def test_independent_yone_primitive_vertices_and_no_samira_sockets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'yone.glb'
            write_rig(path)
            model = Model(path, hero='yone')
        renderer = GPURenderer(self.ctx, model)
        self.addCleanup(renderer.close)
        sockets = renderer.draw('idle', .5, (80, 110), (160, 160), 0, 0)
        self.assertEqual(sockets, {})
        alpha = self.pixels()[:, :, 3]
        self.assertGreater(np.count_nonzero(alpha[:, :80] == 255), 15)
        self.assertGreater(np.count_nonzero(alpha[:, 80:] == 255), 15)
        self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_mastery_uses_normalized_progress_without_an_actor(self):
        mastery = MasteryRenderer(self.ctx)
        self.addCleanup(mastery.close)
        state = {'clock': 3000, 'mastery': {'at': .32, 'position': [80, 100]}, 'screen': [160, 160]}
        self.assertTrue(mastery.draw(state, normalized=True))
        self.assertGreater(np.count_nonzero(self.pixels()[:, :, 3]), 100)
        self.assertIs(mastery.draw(dict(state, paused=True), normalized=True), False)

    def test_missing_rig_leaves_native_actor_and_draws_mastery(self):
        from run_testroom_renderer import YoneRenderer, acknowledge

        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            renderer = YoneRenderer(self.ctx, folder / 'yone.glb')
            self.addCleanup(renderer.close)
            state = {'hero': 'yone', 'kind': 'idle', 'clock': 3000, 'screen': [160, 160]}
            visible, capabilities = renderer.draw(state, 0)
            self.assertFalse(visible)
            self.assertEqual(capabilities, {'mastery': True})
            acknowledge(folder, state, visible, capabilities)
            ack = json.loads((folder / 'save1.dat').read_text(encoding='utf8'))
            self.assertFalse(ack['visible'])
            self.assertEqual(ack['hero'], 'yone')
            self.assertEqual(ack['capabilities'], {'mastery': True})
            state['mastery'] = {'at': .32, 'position': [80, 100]}
            visible, capabilities = renderer.draw(state, 0)
            self.assertTrue(visible)
            self.assertEqual(capabilities, {'mastery': True})
            self.assertGreater(np.count_nonzero(self.pixels()[:, :, 3]), 100)


class YoneAnimationTests(unittest.TestCase):
    def test_dance_transitions_from_intro_and_continues_at_source_rate(self):
        from run_testroom_renderer import yone_animation

        state = {'kind': 'dance', 'clip': 'dance', 'phase': .11, 'actionFrame': 15}
        durations = {'dance_in': 1, 'dance': 2}
        self.assertEqual(yone_animation(state, durations), ('dance_in', .5))
        self.assertEqual(yone_animation(dict(state, actionFrame=30), durations), ('dance', 0))
        self.assertEqual(yone_animation(dict(state, actionFrame=165), durations), ('dance', .25))

    def test_taunt_continues_through_its_authored_loop_during_voice(self):
        from run_testroom_renderer import yone_animation

        state = {'kind': 'taunt', 'clip': 'taunt', 'phase': .11, 'actionFrame': 105}
        self.assertEqual(yone_animation(state, {'taunt': 2.5, 'taunt_loop': 4}), ('taunt_loop', .25))
        self.assertEqual(yone_animation(state, {'taunt': 2.5}), ('taunt', 1))


class RecordingMixer:
    def __init__(self, _root, _samples):
        self.events = []

    def set_volume(self, _volume):
        pass

    def play(self, clip, group, _gain, *, loops=0):
        self.events.append(('play', clip, group, loops))

    def stop_all(self):
        self.events.append(('stop',))


class YoneAudioTests(unittest.TestCase):
    def test_emote_audio_plays_once_and_stops_without_resuming(self):
        from run_testroom_renderer import YoneAudio

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'laugh.wav').touch()
            audio = YoneAudio(root, backend=RecordingMixer)
            state = dict(active=True, hero='yone', session='run', room=1, kind='laugh',
                         actionId=100, actionFrame=0, time=1000, heartbeatTime=1000, sfxVolume=.5)
            audio.update(state, True, 1)
            audio.update(dict(state, actionFrame=1), True, 1.033)
            audio.update(dict(state, actionFrame=2), False, 1.067)
            audio.update(dict(state, actionFrame=3), True, 1.1)
            audio.update(dict(state, actionId=110), True, 1.35)
            audio.update(dict(state, actionId=110, room=2, actionFrame=1), True, 1.383)
            audio.update(dict(state, actionId=120, room=2), True, 1.7)
            audio.update(dict(state, hero='samira'), True, 1.733)
            audio.update(dict(state, actionId=130, heartbeatTime=1201), True, 2)
            self.assertEqual(audio.backend.events, [('play', 'laugh', 'voice', 0), ('stop',)] * 3)

    def test_dance_audio_starts_one_loop_after_intro_and_stops_on_interrupt(self):
        from run_testroom_renderer import YoneAudio

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for clip in ('dance', 'dance_loop'):
                (root / f'{clip}.wav').touch()
            audio = YoneAudio(root, backend=RecordingMixer)
            state = dict(active=True, hero='yone', session='run', room=1, kind='dance',
                         actionId=100, actionFrame=0, time=1000, heartbeatTime=1000, sfxVolume=.5)
            audio.update(state, True, 1)
            audio.update(dict(state, actionFrame=92), True, 4.066)
            self.assertEqual(audio.backend.events, [('play', 'dance', 'voice', 0)])
            audio.update(dict(state, actionFrame=93), True, 4.1)
            audio.update(dict(state, actionFrame=99), True, 4.3)
            audio.update(dict(state, actionFrame=102), False, 4.4)
            audio.update(dict(state, actionFrame=105), True, 4.5)
            self.assertEqual(audio.backend.events, [('play', 'dance', 'voice', 0),
                                                  ('play', 'dance_loop', 'voice', -1), ('stop',)])


class YoneBridgeTests(unittest.TestCase):
    def test_yone_overlay_expires_with_the_native_fallback_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'log.txt'
            tail = Tail(log)
            packet = dict(version=1, active=True, hero='yone', presentation=2, session='run',
                          room=1, screen=[160, 160], position=[70, 80], face=[1, 0],
                          kind='idle', phase=.6, clock=2, seq=1, time=100)
            log.write_text(PREFIX + json.dumps(packet) + '\n', encoding='utf-8')
            tail.poll(1)
            self.assertIsNotNone(tail.sample(1.49))
            self.assertIsNone(tail.sample(1.51))

    def test_switching_heroes_does_not_lerp_old_actor_position(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'log.txt'
            tail = Tail(log)
            packet = dict(version=1, active=True, session='run', room=1, screen=[160, 160],
                          face=[1, 0], kind='Idle', phase=.6, clock=2, seq=1, time=100, position=[70, 80])
            with log.open('a', encoding='utf-8') as output:
                output.write(PREFIX + json.dumps(packet) + '\n')
                output.flush()
                tail.poll(1)
                packet.update(hero='yone', kind='idle', position=[90, 80], seq=2, time=133, clock=3)
                output.write(PREFIX + json.dumps(packet) + '\n')
                output.flush()
                tail.poll(1.033)
            self.assertEqual(tail.sample(1.033)['position'], [90, 80])


if __name__ == '__main__':
    unittest.main()
