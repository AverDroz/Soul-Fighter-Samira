"""Check Skin30 blade contact and slash pixels against the Lua cast direction."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/render-deps"))
sys.path.insert(0, str(ROOT / "src/samira/external"))
import moderngl
import numpy as np
from model import GPURenderer, Model
from run_testroom_renderer import actor_phase, actor_yaw
from samira_vfx import SoulFighterVFX


def run():
    model = Model(ROOT / "src/samira/reference/source/model.glb")
    ctx = moderngl.create_standalone_context(require=330)
    size, origin = (256, 216), (128, 108)
    fbo = ctx.framebuffer([ctx.texture(size, 4)], ctx.depth_renderbuffer(size))
    fbo.use()
    renderer = GPURenderer(ctx, model)
    vfx = SoulFighterVFX(ctx, ROOT / "assets/samira-soul-fighter/vfx")
    # Measure distal vertices from the skinned sword submesh, independent of
    # the shader's nominal forward axis and the model's helpful tip socket.
    indices = next(idx for name, idx, _ in model.parts if name == "Sword")
    vertices = model.vertices[np.unique(indices)]
    positions = np.column_stack((vertices[:, :3], np.ones(len(vertices))))
    hilt = list(model.joints).index(model.node_names["Sword"])
    joint = np.linalg.inv(model.ibm[hilt])[:, 3]
    yy, xx = np.indices((size[1], size[0]))
    screen_axis = np.array((1., .72))
    windup, duration = 8 / 30, 13 / 30
    errors = []
    for mirror in (1, -1):
        for degrees in range(0, 360, 45):
            angle = math.radians(degrees)
            face = np.array((mirror * math.cos(angle), math.sin(angle))) * screen_axis
            face /= np.linalg.norm(face)
            cast = {"id": 3, "source": "qmelee", "kind": "cast", "age": 0, "direction": face, "position": origin}
            stale = {"id": 2, "kind": "qmelee", "age": .4, "radius": 42, "direction": -face, "position": origin}
            skill = {"kind": "qmelee", "windup": windup, "duration": duration, "age": 0}
            state = {"screen": size, "position": origin, "kind": "QMelee", "face": -face, "phase": 0,
                     "visual": {"skill": skill, "ground": screen_axis.tolist(), "events": [stale, cast]}}
            yaw = actor_yaw(state)
            for i in range(9):
                skill["age"] = cast["age"] = i / 30
                state["phase"] = skill["age"] / duration
                assert math.isclose(actor_yaw(state), yaw)
                fbo.clear()
                renderer.draw("QMelee", actor_phase(state), origin, size, yaw, 1 / 30, snap_facing=True)
            mats = model.matrices(renderer.pose, "QMelee", actor_phase(state))
            sword = np.einsum("nzij,nj,nz->ni", mats[vertices[:, 5:9].astype(int)], positions, vertices[:, 9:13])
            dist = np.linalg.norm(sword[:, :3] - (mats[hilt] @ joint)[:3], axis=1)
            x, _, z, _ = sword[dist >= np.percentile(dist, 98)].mean(axis=0)
            ground_tip = np.array((x * math.cos(yaw) + z * math.sin(yaw),
                                   .573576 * (-x * math.sin(yaw) + z * math.cos(yaw))))
            ground_tip /= np.linalg.norm(ground_tip)
            error = math.degrees(math.acos(np.clip(np.dot(ground_tip, face), -1, 1)))
            assert error < 4, (mirror, degrees, error)
            errors.append(error)
            state["visual"]["events"] = [cast, {"id": 4, "kind": "qmelee", "age": .09, "direction": face,
                                                "position": origin, "radius": 42}]
            previous = None
            for actor in (origin, (origin[0] + 18, origin[1] - 12)):
                state["position"] = actor
                fbo.clear()
                vfx.begin(state)
                vfx.draw_events(state, {})
                alpha = np.frombuffer(fbo.read(components=4), np.uint8).reshape(size[1], size[0], 4)[::-1, :, 3]
                forward = (xx + .5 - origin[0]) * face[0] + (yy + .5 - origin[1]) * face[1]
                assert alpha.sum() and alpha[forward < 0].sum() == 0
                assert previous is None or np.array_equal(previous, alpha)
                previous = alpha
            assert ctx.error == "GL_NO_ERROR"
    print(f"{len(errors)} normal/mirrored contact and VFX checks passed; largest blade error {max(errors):.2f} degrees")


if __name__ == "__main__":
    run()
