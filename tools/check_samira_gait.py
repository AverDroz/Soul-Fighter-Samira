"""Measure foot contact on the source run clip and exercise the Lua gait clock."""

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in ("src/samira/external", "work/render-deps", "work/python-deps"):
    sys.path.insert(0, str(ROOT / path))

from lupa import LuaRuntime
import numpy as np
from model import Model


def measure_stride():
    model = Model(ROOT / "src/samira/reference/source/model.glb")
    rest = np.linalg.inv(model.ibm)
    poses = [model.sample("run_gun_base", frame / 30) for frame in range(31)]
    joints = np.array([model.matrices(pose) @ rest for pose in poses])
    slopes = []
    for name, first, last in (("R_Toe", 1, 8), ("L_Toe", 16, 23)):
        toe = list(model.joints).index(model.node_names[name])
        position = joints[first:last + 1, toe, :3, 3]
        assert np.ptp(position[:, 1]) < 3, f"{name} does not remain close to the floor"
        slope, _ = np.polyfit(np.arange(first, last + 1), position[:, 2], 1)
        slopes.append(float(slope))
    stride = -float(np.mean(slopes)) * 30
    root = model.node_names["Root"]
    root_translation = np.array([pose[0][root] for pose in poses])
    assert np.linalg.norm(root_translation[-1] - root_translation[0]) < .01
    assert np.ptp(root_translation[:, 2]) < stride * .02
    return stride, model.pixel_scale, slopes


def exercise_gait(stride):
    lua = LuaRuntime()
    lua.execute("""
        local V = {}
        V.__index = V
        Vector = setmetatable({}, {__call = function(_, x, y) return setmetatable({X=x, Y=y}, V) end})
        Vector.Zero = Vector(0, 0)
        function V.__sub(a,b) return Vector(a.X-b.X, a.Y-b.Y) end
        function V.__mul(a,b) return Vector(a.X*b, a.Y*b) end
        function V:Length() return math.sqrt(self.X*self.X + self.Y*self.Y) end
        function V:Normalized() local n = self:Length(); return Vector(self.X/n, self.Y/n) end
        camera = 0
        Isaac = {WorldToScreen = function(v) return Vector(v.X*.75 + camera, v.Y*.6 + camera) end}
    """)
    gait = lua.execute((ROOT / "src/samira-testroom/mod/samira_testroom_gait.lua").read_text(encoding="utf-8"))
    vector = lua.globals().Vector
    nearly = lambda value, expected: math.isclose(value, expected, rel_tol=.002, abs_tol=1e-7)

    start = 1 / 30
    gait.update(101, vector(100, 100), False)
    assert nearly(gait.phase, start) and not gait.moving
    gait.update(102, vector(104, 100), False)
    assert gait.moving and nearly(gait.phase, start + 3 / stride)
    assert nearly(gait.phaseRate, 90 / stride)
    gait.update(103, vector(112, 100), False)
    assert nearly(gait.phase, start + 9 / stride)
    assert nearly(gait.phaseRate, 180 / stride)
    gait.update(103, vector(160, 100), False)
    assert nearly(gait.phase, start + 9 / stride), "Same game tick advanced twice"
    gait.update(104, vector(112, 100), False)
    assert nearly(gait.phase, start) and not gait.moving and gait.phaseRate == 0

    lua.globals().camera = 125
    gait.update(105, vector(112, 104), False)
    assert nearly(gait.phase, start + 2.4 / .573576 / stride)
    assert nearly(gait.face.Y, 1)
    gait.update(106, vector(116, 108), False)
    projected = (gait.face.X, gait.face.Y * .573576)
    assert nearly(projected[1] / projected[0], 2.4 / 3), "Diagonal run faces off actual trajectory"

    gait.update(107, vector(150, 108), True)
    gait.update(108, vector(160, 108), False)
    assert nearly(gait.phase, start) and not gait.moving, "Dash crossed into walk phase"
    gait.update(109, vector(164, 108), False)
    assert nearly(gait.phase, start + 3 / stride)
    gait.update(110, vector(1000, 250), False)
    assert nearly(gait.phase, start) and not gait.moving, "Teleport advanced walk"
    gait.update(113, vector(1005, 250), False)
    assert nearly(gait.phase, start) and not gait.moving, "Resume caught up over paused ticks"
    gait.reset()
    gait.update(1, vector(25, 75), False)
    assert nearly(gait.phase, start) and not gait.moving, "Room reset retained old position"

    for tick in range(2, 25):
        gait.update(tick, vector(25 + 4 * (tick - 1), 75), False)
    assert nearly(gait.phase, (start + 69 / stride) % 1), "Distance did not wrap at one stride"


def main():
    stride, scale, slopes = measure_stride()
    assert abs(stride - 354) < .2
    exercise_gait(stride * scale)
    print(f"Original planted toe slopes {slopes}; stride {stride:.2f} client units / {stride * scale:.2f} logical pixels")
    print("Lua gait passed acceleration, stop, diagonal, camera pan, dash, teleport, pause, wrap and room reset checks")


if __name__ == "__main__":
    main()
