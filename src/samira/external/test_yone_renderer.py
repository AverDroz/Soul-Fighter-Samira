import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
                animations=[dict(name=name, samplers=[dict(input=times, output=values)],
                                 channels=[dict(sampler=0, target={'node': 0, 'path': 'translation'})])
                            for name in ('idle', 'e_body')])
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

    def region(self, x1, y1, x2, y2):
        return self.pixels()[::-1][y1:y2, x1:x2]

    def test_spirit_draws_independent_body_tether_and_enemy_mark(self):
        from run_testroom_renderer import YoneRenderer

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'yone.glb'
            write_rig(path)
            renderer = YoneRenderer(self.ctx, path)
        self.addCleanup(renderer.close)
        state = {'hero': 'yone', 'kind': 'idle', 'phase': .35, 'screen': [160, 160],
                 'position': [100, 115], 'face': [0, 1], 'clock': 120}
        renderer.draw(state, 0)
        normal = self.region(87, 93, 112, 114).copy()
        self.fbo.clear(0, 0, 0, 0)
        state['yone'] = {'spirit': {'anchor': [35, 115], 'face': [0, 1], 'remaining': .75,
                                   'marks': [{'position': [130, 72], 'amount': 4.5}]}}
        with patch.object(renderer.actor, 'draw', wraps=renderer.actor.draw) as draw_actor:
            drawn, capabilities = renderer.draw(state, 0)
        self.assertTrue(drawn)
        self.assertEqual(capabilities, {'yoneModel': True, 'mastery': True, 'yoneVfx': True})
        call = next(call for call in draw_actor.call_args_list if call.kwargs.get('clip') == 'e_body')
        self.assertEqual(call.args[2], (35, 115))
        self.assertTrue(call.kwargs.get('detached'))
        self.assertEqual(renderer.actor.rig_sample, ('idle', .35))
        self.assertGreater(np.count_nonzero(self.region(19, 91, 50, 105)[:, :, 3]), 20)
        self.assertGreater(np.count_nonzero(self.region(47, 106, 85, 119)[:, :, 3]), 10)
        self.assertGreater(np.count_nonzero(self.region(116, 37, 144, 57)[:, :, 3]), 25)
        spirit = self.region(87, 93, 112, 114)
        self.assertGreater(np.count_nonzero(normal != spirit), 100)
        self.assertGreater(float(spirit[:, :, 2].mean()), float(normal[:, :, 2].mean()) + 5)
        self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_contact_bursts_require_authoritative_targets(self):
        from run_testroom_renderer import YoneRenderer
        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        state = {'kind': 'idle', 'screen': [160, 160], 'position': [30, 120],
                 'face': [1, 0], 'clock': 120}
        for kind in ('r', 'e_return'):
            event = {'kind': kind, 'age': .04, 'origin': [30, 120], 'target': [100, 120]}
            state['yone'] = {'fx': [event]}
            self.fbo.clear(0, 0, 0, 0)
            renderer.draw(state, 0)
            without = self.region(119, 32, 150, 63).copy()
            event['contacts'] = [[135, 56], ['bad', 3]]
            self.fbo.clear(0, 0, 0, 0)
            renderer.draw(state, 0)
            with_contact = self.region(119, 32, 150, 63).copy()
            self.assertFalse(without.any(), kind)
            self.assertGreater(np.count_nonzero(with_contact[:, :, 3]), 5, kind)
            self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_q3_has_no_endpoint_hit_before_wind_front_arrives(self):
        from run_testroom_renderer import YoneRenderer
        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        event = {'kind': 'q3', 'age': 0, 'origin': [20, 110], 'target': [130, 110],
                 'contacts': [[130, 110]]}
        state = {'kind': 'idle', 'screen': [160, 160], 'position': [20, 110],
                 'face': [1, 0], 'clock': 120, 'yone': {'fx': [event]}}
        renderer.draw(state, 0)
        self.assertFalse(self.region(119, 86, 150, 120).any())
        self.fbo.clear(0, 0, 0, 0)
        event['age'] = .16
        renderer.draw(state, 0)
        self.assertTrue(self.region(119, 86, 150, 120).any())

    def test_skill_effects_change_shape_during_their_motion(self):
        from run_testroom_renderer import YoneRenderer
        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        state = {'kind': 'idle', 'screen': [160, 160], 'position': [40, 100],
                 'face': [1, 0], 'clock': 120}
        for kind in ('q3', 'w', 'r', 'e_return'):
            event = {'kind': kind, 'age': .04, 'origin': [40, 100], 'target': [110, 100]}
            state['yone'] = {'fx': [event]}
            self.fbo.clear(0, 0, 0, 0)
            renderer.draw(state, 0)
            early = self.pixels().copy()
            event['age'] = .14
            self.fbo.clear(0, 0, 0, 0)
            renderer.draw(state, 0)
            late = self.pixels().copy()
            self.assertTrue(early.any() and late.any(), kind)
            self.assertFalse(np.array_equal(early, late), kind)
            self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_expired_spirit_stays_visible_until_authoritative_recall(self):
        from run_testroom_renderer import YoneRenderer
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'yone.glb'
            write_rig(path)
            renderer = YoneRenderer(self.ctx, path)
        self.addCleanup(renderer.close)
        state = {'kind': 'r', 'phase': .8, 'screen': [160, 160], 'position': [100, 115],
                 'face': [1, 0], 'clock': 120,
                 'yone': {'spirit': {'anchor': [35, 115], 'face': [1, 0], 'remaining': 0}}}
        with patch.object(renderer.actor, 'draw', wraps=renderer.actor.draw) as draw:
            renderer.draw(state, 0)
        self.assertTrue(any(call.kwargs.get('clip') == 'e_body' for call in draw.call_args_list))
        self.assertGreater(np.count_nonzero(self.region(20, 88, 50, 117)[:, :, 3]), 20)
        self.assertGreater(np.count_nonzero(self.region(50, 105, 85, 117)[:, :, 3]), 10)
        self.fbo.clear(0, 0, 0, 0)
        state['yone'] = {'fx': []}
        with patch.object(renderer.actor, 'draw', wraps=renderer.actor.draw) as draw:
            renderer.draw(state, 0)
        self.assertFalse(any(call.kwargs.get('clip') == 'e_body' for call in draw.call_args_list))
        self.assertFalse(self.region(20, 88, 50, 117).any())

    def test_w_uses_projected_arc_and_old_packets_fall_back(self):
        from run_testroom_renderer import YoneRenderer
        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        state = {'kind': 'idle', 'screen': [160, 160], 'position': [40, 100],
                 'face': [1, 0], 'clock': 120}
        event = {'kind': 'w', 'age': .04, 'origin': [40, 100], 'target': [95, 100]}
        state['yone'] = {'fx': [event]}
        renderer.draw(state, 0)
        fallback = self.pixels().copy()
        self.assertGreater(np.count_nonzero(fallback[:, :, 3]), 40)
        self.fbo.clear(0, 0, 0, 0)
        event['arc'] = [[48, 60], [100, 70], [110, 100], [100, 130], [48, 140]]
        renderer.draw(state, 0)
        projected = self.pixels().copy()
        self.assertFalse(np.array_equal(fallback, projected))
        self.assertGreater(np.count_nonzero(self.region(43, 45, 57, 62)[:, :, 3]), 0)
        self.fbo.clear(0, 0, 0, 0)
        event['arc'] = [[0, 0], ['invalid', 2], [0, 0]]
        renderer.draw(state, 0)
        np.testing.assert_array_equal(fallback, self.pixels())
        self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_r_anticipation_precedes_impact_event(self):
        from run_testroom_renderer import YoneRenderer
        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        state = {'kind': 'r', 'phase': .3, 'screen': [160, 160], 'position': [80, 100],
                 'face': [1, 0], 'clock': 120, 'yone': {'fx': []}}
        self.assertTrue(renderer.draw(state, 0)[1]['yoneVfx'])
        self.assertGreater(np.count_nonzero(self.pixels()[:, :, 3]), 40)
        self.fbo.clear(0, 0, 0, 0)
        state['phase'] = .7
        self.assertNotIn('yoneVfx', renderer.draw(state, 0)[1])

    def test_visible_impacts_follow_packet_endpoints_and_fade(self):
        from run_testroom_renderer import YoneRenderer

        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        state = {'hero': 'yone', 'kind': 'idle', 'screen': [160, 160], 'position': [44, 96],
                 'face': [1, 0], 'clock': 120}
        footprints = {}
        for kind in ('q3', 'w', 'r', 'e_return', 'shield'):
            with self.subTest(kind=kind):
                event = {'id': 1, 'kind': kind, 'age': .04, 'origin': [35, 95], 'target': [105, 95]}
                state['yone'] = {'fx': [event]}
                self.fbo.clear(0, 0, 0, 0)
                drawn, capabilities = renderer.draw(state, 0)
                self.assertFalse(drawn)  # Effects alone never acquire the actor lease.
                self.assertTrue(capabilities['yoneVfx'])
                footprints[kind] = self.pixels().copy()
                alpha = self.pixels()[:, :, 3]
                self.assertGreater(np.count_nonzero(alpha), 40)
                if kind in ('w', 'r', 'e_return'):
                    self.assertGreater(np.count_nonzero(self.region(98, 68, 119, 110)[:, :, 3]), 10)
                event['age'] = 2
                self.fbo.clear(0, 0, 0, 0)
                _, capabilities = renderer.draw(state, 0)
                self.assertNotIn('yoneVfx', capabilities)
                self.assertFalse(self.pixels().any())
        self.assertFalse(np.array_equal(footprints['q3'], footprints['r']))
        self.assertEqual(self.ctx.error, 'GL_NO_ERROR')

    def test_floor_transition_keeps_effects_and_ack_out_of_the_next_scene(self):
        from run_testroom_renderer import YoneRenderer, acknowledge

        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / 'yone.glb'
            write_rig(path)
            renderer = YoneRenderer(self.ctx, path)
            self.addCleanup(renderer.close)
            state = {'hero': 'yone', 'kind': 'idle', 'phase': .35, 'screen': [160, 160],
                     'position': [100, 115], 'face': [1, 0], 'clock': 120,
                     'session': 'run', 'room': 1, 'time': 4000, 'seq': 7,
                     'mastery': {'at': .32, 'position': [80, 100]}, 'transition': True,
                     'yone': {'spirit': {'anchor': [35, 115], 'face': [1, 0], 'remaining': .75}}}
            drawn, capabilities = renderer.draw(state, 0)
            self.assertEqual((drawn, capabilities), (False, {}))
            self.assertFalse(self.pixels().any())
            acknowledge(folder, state, drawn, capabilities)
            ack = json.loads((folder / 'save1.dat').read_text(encoding='utf8'))
            self.assertEqual((ack['ready'], ack['time'], ack['room']), (False, 4000, 1))
            renderer.reset()
            next_state = dict(state, room=2, seq=8, time=5000, transition=False, yone={}, mastery=None)
            drawn, capabilities = renderer.draw(next_state, 0)
            self.assertTrue(drawn)
            self.assertEqual(capabilities, {'yoneModel': True, 'mastery': True})
            self.assertFalse(self.region(19, 91, 50, 119).any())
            acknowledge(folder, next_state, drawn, capabilities)
            ack = json.loads((folder / 'save1.dat').read_text(encoding='utf8'))
            self.assertEqual((ack['ready'], ack['time'], ack['room']), (True, 5000, 2))

    def test_failed_effect_pass_keeps_model_and_mastery_capabilities(self):
        from run_testroom_renderer import YoneRenderer

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'yone.glb'
            write_rig(path)
            renderer = YoneRenderer(self.ctx, path)
        self.addCleanup(renderer.close)
        state = {'hero': 'yone', 'kind': 'idle', 'phase': .35, 'screen': [160, 160],
                 'position': [100, 115], 'face': [0, 1], 'clock': 120, 'yone': {'shield': True}}
        with patch.object(renderer.vfx, 'finish', side_effect=RuntimeError('test rendering error')):
            self.assertEqual(renderer.draw(state, 0), (True, {'yoneModel': True, 'mastery': True}))
        self.assertIsNotNone(renderer.actor)
        self.assertIsNone(renderer.vfx)

    def test_effects_start_at_the_interpolated_impact_tick(self):
        from run_testroom_renderer import YoneRenderer

        renderer = YoneRenderer(self.ctx, Path('unavailable-yone.glb'))
        self.addCleanup(renderer.close)
        event = {'id': 19, 'kind': 'q3', 'age': 0, 'origin': [30, 95], 'target': [106, 95]}
        state = {'hero': 'yone', 'kind': 'idle', 'screen': [160, 160], 'position': [44, 96],
                 'face': [1, 0], 'clock': 119.5, 'packetClock': 120, 'yone': {'fx': [event]}}
        self.assertNotIn('yoneVfx', renderer.draw(state, 0)[1])
        self.assertFalse(self.pixels().any())
        state['clock'] = 120
        self.assertTrue(renderer.draw(state, 0)[1]['yoneVfx'])
        self.assertTrue(self.pixels().any())

    def test_samira_actor_is_pixel_identical_after_yone_materials_render(self):
        from run_testroom_renderer import YoneRenderer

        samira_model = Path(__file__).resolve().parents[1] / 'reference/source/model.glb'
        samira = GPURenderer(self.ctx, Model(samira_model))
        self.addCleanup(samira.close)
        def render_samira():
            samira.draw('Idle', .35, (80, 110), (160, 160), 0, 0)
        render_samira()
        expected = self.pixels().copy()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'yone.glb'
            write_rig(path)
            renderer = YoneRenderer(self.ctx, path)
        self.addCleanup(renderer.close)
        renderer.draw({'hero': 'yone', 'kind': 'idle', 'phase': .35, 'screen': [160, 160],
                       'position': [100, 115], 'face': [1, 0], 'clock': 120,
                       'yone': {'spirit': {'anchor': [35, 115], 'face': [1, 0], 'remaining': .75}}}, 0)
        self.fbo.clear(0, 0, 0, 0)
        samira.reset()
        render_samira()
        np.testing.assert_array_equal(expected, self.pixels())

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
    def test_run_uses_original_clip_duration(self):
        from run_testroom_renderer import yone_animation

        state = {"kind": "run", "phase": 19 / 24, "clock": 19}
        self.assertEqual(yone_animation(state, {"run": 38 / 30}), ("run", .5))

    def test_ordinary_q_runs_both_source_segments(self):
        from run_testroom_renderer import yone_animation

        clips = {"q": 7 / 30, "q_follow": 21 / 30}
        state = {"kind": "q", "phase": 3 / 16}
        self.assertEqual(yone_animation(state, clips), ("q", .5))
        self.assertEqual(yone_animation(dict(state, phase=6 / 16), clips), ("q_follow", 0))
        self.assertEqual(yone_animation(dict(state, phase=11 / 16), clips), ("q_follow", .5))

    def test_yone_diagonal_face_survives_camera_and_sprite_scale(self):
        import math
        from model import YONE_VIEW
        from run_testroom_renderer import actor_yaw

        state = {"kind": "q", "face": [1, 0], "viewFace": [-3, 4], "bodyScale": [1.25, .75]}
        yaw = actor_yaw(state, YONE_VIEW)
        projected = math.sin(yaw) * 1.25, math.cos(yaw) * YONE_VIEW[1] * .75
        self.assertLess(projected[0], 0)
        self.assertGreater(projected[1], 0)
        self.assertAlmostEqual(projected[0] / projected[1], -.75)

    def test_compound_clips_follow_lua_impact_and_landing(self):
        from run_testroom_renderer import yone_animation, yone_dash_position

        clips = {"q3_in": .4, "q3": .467, "q3_out": .067,
                 "e_return": .167, "e_return_out": 1.167}
        state = {"kind": "q3", "phase": 6 / 22, "yoneTiming": {"hit": 9, "length": 22}}
        self.assertEqual(yone_animation(state, clips)[0], "q3_in")
        self.assertEqual(yone_animation(dict(state, phase=9 / 22), clips), ("q3", 0))
        self.assertEqual(yone_animation(dict(state, phase=14 / 22), clips), ("q3_out", 0))
        self.assertEqual(yone_animation({"kind": "e_return", "phase": .65}, clips)[0], "e_return_out")
        dash = {"kind": "q3", "origin": [10, 50], "target": [140, 50], "landing": [70, 50]}
        self.assertEqual(yone_dash_position(state, dict(dash, age=0)), (10, 50))
        self.assertEqual(yone_dash_position(state, dict(dash, age=1 / 12)), (40, 50))
        self.assertIsNone(yone_dash_position(state, dict(dash, age=.24)))
        self.assertIsNone(yone_dash_position(dict(state, kind="r"), dict(dash, age=0)))

    def test_ultimate_in_and_out_cover_windup_and_recovery(self):
        from run_testroom_renderer import yone_animation

        durations = {'r': 1.67, 'r_out': .27}
        state = {'kind': 'r', 'clip': 'r', 'phase': 0}
        self.assertEqual(yone_animation(state, durations), ('r', 0))
        clip, phase = yone_animation(dict(state, phase=11.5/40), durations)
        self.assertEqual(clip, 'r')
        self.assertAlmostEqual(phase, .5)
        self.assertEqual(yone_animation(dict(state, phase=23/40), durations), ('r_out', 0))
        clip, phase = yone_animation(dict(state, phase=39/40), durations)
        self.assertEqual(clip, 'r_out')
        self.assertGreater(phase, .9)

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
    def __init__(self, _root, samples):
        self.samples = samples
        self.events = []

    def set_volume(self, _volume):
        pass

    def play(self, clip, group, _gain, *, loops=0):
        self.events.append(('play', clip, group, loops))

    def stop(self, group):
        assert group == 'voice'
        self.events.append(('stop',))

    def stop_all(self):
        self.events.append(('stop_all',))


class YoneAudioTests(unittest.TestCase):
    def test_resolved_combat_effect_survives_emote_interruption(self):
        from run_testroom_renderer import YoneAudio

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for clip in ('laugh', 'q3'):
                (root / f'{clip}.wav').touch()
            audio = YoneAudio(root, backend=RecordingMixer)
            self.assertIs(audio.combat.backend, audio.backend)
            self.assertEqual(set(audio.backend.samples), {'laugh', 'q3'})
            state = dict(active=True, hero='yone', session='run', room=1, kind='laugh',
                         actionId=100, actionFrame=0, time=1000, heartbeatTime=1000)
            audio.update(state, True, 1)
            strike = dict(state, kind='q3', actionId=None, yone={'fx': [{'kind': 'q3', 'id': 1, 'age': .04}]})
            audio.update(strike, True, 1.04)
            audio.update(strike, True, 1.05)
            self.assertEqual(audio.backend.events, [('stop_all',), ('play', 'laugh', 'voice', 0),
                                                    ('play', 'q3', 'effect', 0), ('stop',)])

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
