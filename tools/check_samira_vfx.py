"""Exercise Soul Fighter VFX in a hidden OpenGL context, with the original rig."""

import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/render-deps"))
sys.path.insert(0, str(ROOT / "src/samira/external"))

import glfw
import moderngl
import numpy as np
from PIL import Image, ImageDraw

from model import GPURenderer, Model
from run_testroom_renderer import actor_yaw
from samira_vfx import SoulFighterVFX
from system_pointer import SystemPointer, fallback_position


SCREEN = (320, 245)
ORIGIN = (135, 120)
FACE = (1, 0)
CASES = [
    ("RMB move", "Walk", "move", .19, 0, 0),
    ("RMB attack", "Attack", "attack", .09, .35, 0),
    ("RMB melee", "MeleeAttack", "melee", .08, .36, 38),
    ("Q ranged", "Q", "q", .11, .37, 0),
    ("Q melee", "QMelee", "qmelee", .09, .43, 104),
    ("W", "W", "w", .09, .8, 65),
    ("E", "E", "e", .09, .233, 0),
    ("R", "R", "r", .09, 2, 120),
    ("W block and hit", "W", "block", .06, .8, 0),
]


def alpha_count(image):
    return int(np.count_nonzero(np.asarray(image)[:, :, 3]))


def load_frame(fbo):
    return Image.frombytes("RGBA", SCREEN, fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def check_hud():
    def draw(width, style=None, cooldown=0, clock=0):
        rectangles, labels, glow = [], [], []
        canvas = SimpleNamespace(
            textures={f"icon-{key}" for key in "qwer"},
            rect=lambda *args: rectangles.append(args),
            text=lambda label, *args, **kwargs: labels.append(label),
            polygon=lambda points, colors: glow.append((points, colors)),
            flush=lambda: None,
        )
        snapshot = SimpleNamespace(
            visual={"cooldowns": {"q": 0, "w": 0, "e": 0, "r": cooldown}, "style": style},
            canvas=canvas,
            screen=(width, 270),
            clock=clock,
        )
        SoulFighterVFX.hud(snapshot)
        r_icon = next(rect for rect in rectangles if rect[-1] == "icon-r")
        badge = next((rect for rect in rectangles if rect[2:4] == (39, 28)), None)
        return rectangles[0], r_icon[4][-1], badge, labels, glow

    panel, opacity, badge, labels, glow = draw(480, {"rank": 5, "ready": False})
    assert panel[1] == 220 and panel[1] + panel[3] < 244
    assert badge[:4] == (290, 215, 39, 28) and badge[0] > 233
    assert opacity == .36 and labels == ["Q", "W", "E", "R", "A"] and not glow
    panel, opacity, badge, labels, glow = draw(640, {"rank": 6, "ready": True})
    assert panel[1] == 246 and opacity == .9 and labels[-2:] == ["R", "S"]
    assert badge[:4] == (370, 241, 39, 28)
    assert len(glow) == 96 and glow != draw(640, {"rank": 6, "ready": True}, clock=.31)[-1]
    for points, colors in glow:
        assert all(0 <= x <= 640 and 0 <= y <= 270 for x, y in points)
        assert any(all(distance(x, y) <= 16 for x, y in points)
                   for distance in (lambda x, y: x, lambda x, y: 640 - x,
                                    lambda x, y: y, lambda x, y: 270 - y))
        assert all(0 <= color[3] <= .25 and color[0] > color[1] > color[2] for color in colors)
    _, opacity, _, labels, glow = draw(556, {"rank": 6, "ready": False}, cooldown=1.2)
    assert opacity == .36 and labels[-3:] == ["2", "R", "S"] and not glow
    _, opacity, _, labels, glow = draw(556, {"rank": 2, "ready": False}, cooldown=1.2)
    assert opacity == .36 and labels[-3:] == ["2", "R", "D"]
    _, opacity, badge, labels, glow = draw(555)
    assert badge is None and opacity == .9 and labels[-1] == "R", "Older packets have no style data"
    for rank, letter in enumerate("-EDCBAS"):
        _, _, badge, labels, glow = draw(640, {"rank": rank, "remaining": 4})
        assert badge and (labels[-2:] == [letter, "4"] if rank else labels[-1] == "-")


def check_ready_glow_pixels(ctx, canvas):
    size = (640, 270)
    fbo = ctx.simple_framebuffer(size, components=4)
    try:
        fbo.use()
        ctx.viewport = (0, 0, *size)
        fbo.clear()
        snapshot = SimpleNamespace(visual={"style": {"rank": 6, "ready": True}},
                                   canvas=canvas, screen=size, clock=.31)
        canvas.begin(size)
        SoulFighterVFX.hud(snapshot)
        image = Image.frombytes("RGBA", size, fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        alpha = image.getchannel("A")
        assert alpha.crop((16, 16, 624, 254)).getbbox() is None
        assert 48 <= alpha.getextrema()[1] <= 64
        for box in ((0, 0, 640, 3), (0, 267, 640, 270), (0, 0, 3, 270), (637, 0, 640, 270)):
            assert alpha.crop(box).getbbox()
        fbo.clear(0.125, 0.085, 0.075, 1)
        snapshot.visual["cooldowns"] = {"q": 0, "w": 0, "e": 0, "r": 0}
        canvas.begin(size)
        SoulFighterVFX.hud(snapshot)
        preview = Image.frombytes("RGBA", size, fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        output = ROOT / "work/preview"
        output.mkdir(parents=True, exist_ok=True)
        preview.save(output / "samira-ready-glow-640x270.png")
    finally:
        fbo.release()


def main():
    check_hud()
    assert glfw.init(), "GLFW initialization failed"
    glfw.window_hint(glfw.VISIBLE, False)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    window = glfw.create_window(*SCREEN, "Samira VFX check", None, None)
    assert window, "Cannot create hidden context"
    try:
        glfw.make_context_current(window)
        ctx = moderngl.create_context(require=330)
        fbo = ctx.framebuffer([ctx.texture(SCREEN, 4)], ctx.depth_renderbuffer(SCREEN))
        model = Model(ROOT / "src/samira/reference/source/model.glb")
        renderer = GPURenderer(ctx, model)
        effects = SoulFighterVFX(ctx, ROOT / "assets/samira-soul-fighter/vfx")
        assert set("-EDCBASRQW0123456789") <= effects.canvas.glyphs.keys()
        check_ready_glow_pixels(ctx, effects.canvas)
        assert effects.can_projectiles, "Missing original textures or systems for native tears"
        report = {"gpu": ctx.info["GL_RENDERER"], "cases": []}
        sheet = Image.new("RGB", (SCREEN[0] * 3, (SCREEN[1] + 24) * 3), (23, 21, 30))
        for i, (label, action, kind, age, duration, radius) in enumerate(CASES):
            effects.reset()
            fbo.use()
            ctx.viewport = (0, 0, *SCREEN)
            ctx.clear(0, 0, 0, 0)
            state = {
                "screen": SCREEN, "position": ORIGIN, "face": FACE, "ground": (1, .98),
                "visual": {
                    "events": [{
                        "id": i, "kind": kind, "position": (92, 120) if kind == "e" else ORIGIN,
                        "target": (193, 118), "direction": FACE, "age": age, "radius": radius,
                    }],
                    "skill": {"kind": kind, "age": age + (.2 if kind == "r" else 0), "duration": duration},
                    "cooldowns": {"q": 0, "w": 0, "e": 3.5, "r": 0},
                },
            }
            visual = state["visual"]
            if kind == "move":
                visual["moveGoal"] = (210, 140)
            if kind in ("attack", "melee"):
                assert "target" in effects.canvas.textures
                visual["target"] = (228, 119)
            if kind in ("attack", "q"):
                visual["projectiles"] = [{"id": i, "kind": kind, "position": (210, 103), "velocity": (14, 0)}]
            if kind in ("q", "qmelee", "melee", "e", "r", "block"):
                visual["events"].append({
                    "id": i + 100, "kind": "hit", "source": "w" if kind == "block" else kind,
                    "position": (210 if kind in ("q", "r") else 168, 121), "direction": FACE, "age": .065,
                })
            effects.begin(state)
            effects.ground(state)
            ground = load_frame(fbo)
            if kind == "move":
                assert not ground.getbbox(), "Click destination drew a second pointer"
            if kind in ("attack", "melee"):
                assert ground.crop((216, 111, 241, 128)).getbbox(), "Missing target marker"
            if kind in ("w", "r"):
                left, _, right, _ = ground.getbbox()
                assert left < ORIGIN[0] - radius * .7 and right > ORIGIN[0] + radius * .7
            renderer.kind = renderer.pose = renderer.previous = renderer.yaw = None
            sockets = renderer.draw(action, .32, ORIGIN, SCREEN, math.pi / 2, .1, anchor_root=kind == 'e')
            body_only = load_frame(fbo)
            effects.foreground(state, sockets)
            frame = load_frame(fbo)
            assert not np.array_equal(np.asarray(frame), np.asarray(body_only)), f"No foreground effects or HUD for {label}"
            assert ctx.error == "GL_NO_ERROR", label
            if kind not in ("move",):
                assert effects.client.stats["draws"] > 0, f"No source particle draw for {label}"
            stats = dict(effects.client.stats)
            if kind in ("attack", "q"):
                fbo.clear()
                effects.clock += 2
                effects.draw_projectiles()
                projectile_only = load_frame(fbo)
                assert projectile_only.getpixel((210, 103))[3] > 24, (
                    f"Missing long-lived projectile at the native tear coordinate for {label}"
                )
                assert ctx.error == "GL_NO_ERROR", label
            report["cases"].append({"action": label, **stats, "alpha_pixels": alpha_count(frame)})
            # GL readback is premultiplied. Composite once, matching the desktop overlay.
            rgba = np.asarray(frame, dtype=np.float32)
            rgb = np.clip(rgba[:, :, :3] + np.array((23, 21, 30)) * (1 - rgba[:, :, 3:] / 255), 0, 255)
            x = i % 3 * SCREEN[0]
            y = i // 3 * (SCREEN[1] + 24)
            sheet.paste(Image.fromarray(rgb.astype("uint8")), (x, y + 24))
            ImageDraw.Draw(sheet).text((x + 10, y + 6), label, fill=(239, 225, 247))
        # Independent skill lifetimes allow the second W cut during R,
        # including when E takes priority for the actor animation.
        w = {"kind": "w", "age": .2, "duration": .8, "radius": 100}
        e = {"kind": "e", "age": .08, "duration": 7 / 30}
        r = {"kind": "r", "age": 0, "duration": 2, "radius": 120}
        sweep = {"id": 301, "kind": "w", "age": .2, "position": ORIGIN,
                 "direction": FACE, "radius": 100}
        dash = {"id": 302, "kind": "e", "age": .08, "position": (85, 120),
                "target": (195, 120), "direction": FACE}
        eq = {"id": 303, "kind": "eq", "age": .08, "position": (80, 165),
              "target": (205, 95), "direction": (.87, -.49), "radius": 30}
        second = {**sweep, "id": 304, "age": .09, "position": (140, 125)}
        active_w = {**w, "age": .69}
        active_r = {**r, "age": .35}
        overlapping_rings = {"R_Range_Indicator_Self", "W_Zone", "W_CircleCut"}
        combos = [
            ("W then E", [e, w], [sweep, dash], {"W_Zone", "W_CircleCut", "E_DashTrail"}, set()),
            ("Second W cut during R", [active_r, active_w], [second], overlapping_rings, set()),
            ("Second W cut during E and R", [e, active_r, active_w], [dash, second],
             overlapping_rings | {"E_R_Dash_Trail"}, {"E_DashTrail"}),
            ("Expired W during R", [r], [sweep], {"R_Range_Indicator_Self"}, {"W_Zone", "W_CircleCut"}),
            ("E during R", [e, r], [dash], {"R_Range_Indicator_Self", "E_R_Dash_Trail"}, {"E_DashTrail"}),
            ("E and Q detonation", [], [eq], {"Q_EBufferCast"}, set()),
        ]
        report["combos"] = []
        for label, skills, events, expected, excluded in combos:
            effects.reset()
            fbo.clear()
            state = {
                "screen": SCREEN, "position": ORIGIN, "face": FACE,
                "visual": {"skills": skills, "events": events, "ground": (1, .72)},
            }
            effects.begin(state)
            effects.ground(state)
            effects.foreground(state, {})
            frame = load_frame(fbo)
            systems = {key[0] for key in effects.client.cache}
            assert expected <= systems and not (excluded & systems), (label, systems)
            assert frame.getbbox() and ctx.error == "GL_NO_ERROR", label
            if second in events:
                assert ("W_CircleCut", second["id"]) in effects.client.cache, label
                fbo.clear()
                state["visual"]["events"] = [event for event in events if event is not second]
                effects.begin(state)
                effects.ground(state)
                effects.foreground(state, {})
                assert not np.array_equal(np.asarray(frame), np.asarray(load_frame(fbo))), label
            if label == "E and Q detonation":
                # Check two separated sections of the actual diagonal dash,
                # so an effect drawn only at the endpoint cannot pass.
                assert frame.crop((93, 142, 122, 168)).getbbox(), "No EQ scrape near the dash origin"
                assert frame.crop((179, 89, 210, 116)).getbbox(), "No EQ scrape near the dash destination"
            report["combos"].append({"action": label, "systems": sorted(systems)})
        report["muzzle_aim_directions"] = {}
        for kind in ("attack", "q"):
            checks = []
            for degrees in range(0, 360, 45):
                angle = math.radians(degrees)
                face = (math.cos(angle), math.sin(angle))
                state = {
                    "screen": SCREEN, "position": ORIGIN, "face": face,
                    "visual": {"events": [{
                        "id": degrees, "kind": kind, "position": ORIGIN,
                        "direction": face, "age": .06,
                    }]},
                }
                fbo.clear()
                effects.begin(state)
                effects.foreground(state, {"pistol": ORIGIN, "revolver": ORIGIN})
                muzzle = load_frame(fbo)
                count = alpha_count(muzzle.crop((120, 105, 151, 136)))
                assert count > 0 and ctx.error == "GL_NO_ERROR", (kind, degrees)
                checks.append({"degrees": degrees, "alpha_pixels_near_socket": count})
            report["muzzle_aim_directions"][kind] = checks
        # Check the cast art against the gameplay cone after undoing projection.
        # X-reflected headings also cover the form of mirror-room telemetry.
        yy, xx = np.indices((SCREEN[1], SCREEN[0]))
        xx, yy = xx + .5 - ORIGIN[0], yy + .5 - ORIGIN[1]
        ground = (1, .72)
        distances = np.hypot(xx / ground[0], yy / ground[1])
        report["melee_q_aim"] = []
        for degrees in range(0, 360, 45):
            angle = math.radians(degrees)
            face = math.cos(angle), math.sin(angle)
            ground_face = np.array(face) / ground
            ground_face /= np.linalg.norm(ground_face)
            ground_forward = xx / ground[0] * ground_face[0] + yy / ground[1] * ground_face[1]
            forward = xx * face[0] + yy * face[1]
            forward_distances = []
            for radius in (36, 72):
                state = {
                    "screen": SCREEN, "position": ORIGIN, "kind": "QMelee",
                    "face": (-face[0], -face[1]),  # Stale actor pose heading.
                    "visual": {"ground": ground, "events": [{
                        "id": degrees, "kind": "qmelee", "position": ORIGIN,
                        "direction": face, "age": .09, "radius": radius,
                        "target": (260, 140),
                    }]},
                }
                fbo.clear()
                effects.begin(state)
                effects.foreground(state, {})
                pixels = np.asarray(load_frame(fbo))[:, :, :3].max(axis=2).astype(float)
                assert pixels.sum() > 0 and ctx.error == "GL_NO_ERROR", degrees
                share_in_front = float(pixels[forward > 0].sum() / pixels.sum())
                assert share_in_front > .90, (degrees, radius, share_in_front)
                forward_distances.append(float((pixels * forward).sum() / pixels.sum()))
            ratio = forward_distances[1] / forward_distances[0]
            assert 1.9 < ratio < 2.1, (degrees, ratio)
            yaw = actor_yaw(state)
            projected_face = np.array((math.sin(yaw), .573576 * math.cos(yaw)))
            projected_face /= np.linalg.norm(projected_face)
            assert np.allclose(projected_face, face), (degrees, projected_face, face)
            renderer.yaw = yaw + math.pi
            renderer.draw("QMelee", .12, ORIGIN, SCREEN, yaw, 1 / 60, snap_facing=True)
            assert math.isclose(renderer.yaw, yaw) and ctx.error == "GL_NO_ERROR"
            outside = (distances > radius + .01) | (ground_forward < .55 * distances - .01)
            for age in (1 / 60, 1 / 30, 2 / 30, .1, .2, .4):
                state["visual"]["events"][0]["age"] = age
                fbo.clear()
                effects.begin(state)
                effects.foreground(state, {})
                alpha = np.asarray(load_frame(fbo))[:, :, 3]
                assert np.any(alpha), (degrees, age)
                assert not np.any(alpha[outside]), (degrees, age)
            report["melee_q_aim"].append({"degrees": degrees, "front_share": share_in_front,
                                          "linear_scale": ratio})

        # Only the actor moves. The event's cast position and target stay fixed.
        event = state["visual"]["events"][0]
        event["age"] = .1
        def q_frame():
            fbo.clear()
            effects.begin(state)
            effects.foreground(state, {})
            return np.asarray(load_frame(fbo)).astype(float)

        original = q_frame()
        dx, dy = 21, -12
        state["position"] = (ORIGIN[0] + dx, ORIGIN[1] + dy)
        moved = q_frame()
        expected = np.roll(original, (dy, dx), axis=(0, 1))
        assert np.abs(moved - expected).sum() < .01 * moved.sum()
        state["kind"] = "Idle"
        state["position"] = (ORIGIN[0] - 36, ORIGIN[1])
        assert np.array_equal(q_frame(), moved)
        effects.reset()
        assert np.array_equal(q_frame(), original)
        # The R startup packet has no burst event yet. The displayed radius
        # is still proportional to the live skill's combat geometry.
        radii = {}
        for radius in (60, 120):
            fbo.clear()
            state = {
                "screen": SCREEN, "position": ORIGIN, "face": FACE,
                "visual": {"skill": {"kind": "r", "age": 0, "duration": 2, "radius": radius}},
            }
            effects.begin(state)
            effects.ground(state)
            bounds = load_frame(fbo).getbbox()
            assert bounds and bounds[2] - ORIGIN[0] > .75 * radius
            radii[radius] = bounds[2] - bounds[0]
        assert radii[120] > radii[60] * 1.7
        report["opening_r_widths"] = radii

        # Offset, scaled-monitor and fullscreen coordinates are in physical
        # pixels, independent of the game's internal logical viewport size.
        assert fallback_position((-1920, 100, 1600, 900), (-1800, 500), 0) == (120, 400)
        assert fallback_position((0, 0, 1920, 1080), (300, 200), 0) == (300, 200)
        assert fallback_position((100, 200, 1600, 900), (111, 210), 1) is None
        assert fallback_position((100, 200, 1600, 900), (111, 210), 2) is None
        assert fallback_position((100, 200, 1600, 900), (111, 210), 0, True) is None
        assert fallback_position((100, 200, 1600, 900), (1700, 210), 0) is None
        pointer = SystemPointer(ctx)
        cursor_bounds = {}
        for dpi in (96, 144, 192):
            fbo.clear()
            pointer.paint((110, 80), SCREEN, dpi)
            canvas = load_frame(fbo)
            bounds = canvas.getbbox()
            assert bounds[:2] == (110, 80) and ctx.error == "GL_NO_ERROR"
            rgb = np.asarray(canvas)[80:bounds[3], 110:bounds[2], :3]
            assert rgb.max() >= 230
            cursor_bounds[dpi] = bounds[3] - bounds[1]
        assert list(cursor_bounds.values()) == sorted(set(cursor_bounds.values()))
        report["physical_pointer_heights"] = cursor_bounds
        report["unsupported_emitters"] = sorted(effects.client.unsupported)
        output = ROOT / "work/vfx-preview"
        output.mkdir(parents=True, exist_ok=True)
        sheet.save(output / "soul-fighter-vfx.png")
        (output / "render-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()

