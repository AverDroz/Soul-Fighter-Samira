"""Exercise the shared display policy and window-to-render calibration."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/python-deps"))
from lupa.lua54 import LuaRuntime


def main():
    lua = LuaRuntime()
    source = ROOT / "src/samira-testroom/mod/samira_display.lua"
    lua.globals().displaySource = source.read_text(encoding="utf-8")
    lua.execute(r"""
local settings = {Fullscreen = true, UseBorderlessFullscreen = false}
local changes = {}
Options = setmetatable({}, {
    __index = settings,
    __newindex = function(_, key, value)
        settings[key] = value
        changes[#changes + 1] = key .. '=' .. tostring(value)
    end,
})
function Vector(x,y) return {X=x,Y=y} end
local left, top, scale, camera = 320, 60, 3, 12.4
Isaac = {
    GetScreenWidth=function() return 640 end,
    GetScreenHeight=function() return 360 end,
    ScreenToWorld=function(pixel)
        return Vector((pixel.X-left)/scale-camera,(pixel.Y-top)/scale-camera)
    end,
    WorldToScreen=function(world)
        return Vector(math.floor(world.X+camera+.5),math.floor(world.Y+camera+.5))
    end,
}
local display = assert(load(displaySource))()
display.acquire('samira')
display.acquire('yone')
assert(Options.Fullscreen and Options.UseBorderlessFullscreen)
assert(table.concat(changes, ',') == 'Fullscreen=false,UseBorderlessFullscreen=true,Fullscreen=true')
display.release('samira')
assert(#changes == 3 and Options.UseBorderlessFullscreen)
local _, _, old = display.sample()
assert(old.mode == 'borderless' and math.abs(old.viewport[1]-left) <= 1)
assert(math.abs(old.viewport[2]-top) <= 1 and math.abs(old.viewport[3]-1920) <= 1)
assert(math.abs(old.viewport[4]-1080) <= 1)
camera=12.9
local _, _, stable = display.sample()
assert(stable.id == old.id)
left,top,scale=0,0,2
local _, _, resized = display.sample()
assert(resized.id ~= old.id and math.abs(resized.viewport[3]-1280) <= 1)
display.release('yone')
assert(Options.Fullscreen and not Options.UseBorderlessFullscreen)
assert(#changes == 6)
""")
    print("PASS scoped borderless policy, letterbox geometry and display epochs")


if __name__ == "__main__":
    main()
