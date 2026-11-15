"""Check style ranks, transition and edge effects without launching the game."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
font_bytes = (ROOT / 'src/samira-testroom/mod/resources/font/samira_items_ru.fnt').read_bytes()
offset = 4
while offset < len(font_bytes):
    block, size = struct.unpack_from('<BI', font_bytes, offset)
    offset += 5
    if block == 4:
        glyphs = {chr(glyph[0]) for glyph in struct.iter_unpack('<IHHHHhhhBB', font_bytes[offset:offset + size])}
        assert set('-EDCBASR 0123456789') <= glyphs
        break
    offset += size
else:
    raise RuntimeError('BMFont has no glyph table')
lua.globals().style_source = (ROOT / 'src/samira-testroom/mod/samira_style_hud.lua').read_text(encoding='utf-8')
lua.execute(r'''
local hud = assert(load(style_source))()
local w, h, tick = 640, 270, 100
local lines, words = {}, {}
function Vector(x, y) return {X = x, Y = y} end
function KColor(r, g, b, a) return {r, g, b, a} end
function Font(path)
    assert(path == 'font/samira_items_ru.fnt')
    return {
        GetStringWidthUTF8 = function(_, word) return utf8.len(word) * 7 end,
        DrawStringScaledUTF8 = function(_, word, x, y, scale) words[#words + 1] = {word, x, y, scale} end,
    }, true
end
Isaac = {
    GetTime = function() return tick end,
    GetScreenWidth = function() return w end,
    GetScreenHeight = function() return h end,
    GetTextWidth = function(word) return #word * 7 end,
    RenderScaledText = function(word, x, y, scale) words[#words + 1] = {word, x, y, scale} end,
    DrawLine = function(a, b, ca, cb, thickness)
        assert(a.X >= 0 and a.Y >= 0 and b.X <= w and b.Y <= h)
        lines[#lines + 1] = {a, b, ca, cb, thickness}
    end,
}

local function draw(rank, ready, remaining, cooldown)
    lines, words = {}, {}
    hud.render({}, {rank = rank, ready = ready, remaining = remaining, cooldown = cooldown})
end

for rank, letter in ipairs({'-', 'E', 'D', 'C', 'B', 'A', 'S'}) do
    tick = tick + 250
    draw(rank - 1, false, 3.01, 9.01)
    assert(#lines == 8 and words[1][1] == letter and words[2][1] == 'R 10')
    if rank > 1 then assert(words[3][1] == '4') end
    for i = 1, 6 do
        assert((lines[i + 2][3][1] > 0.50) == (i <= rank - 1))
    end
end
assert(words[1][4] > 1.23)
tick = tick + 201
draw(6, false)
assert(words[1][4] == 1.23)
draw(6, true, 5)
assert(#lines == 20 and words[2][1] == 'R' and words[3][1] == '5')
local pulse = lines[1][3][4]
tick = tick + 200
draw(6, true, 5)
assert(pulse ~= lines[1][3][4])
for i = 1, 12 do
    assert(lines[i][5] <= 14 and lines[i][3][4] < 0.20)
end
for _, width in ipairs({480, 640}) do
    w = width
    draw(6, true)
    local panel, bounds = lines[13], hud.bounds()
    assert(panel[1].X == w / 2 + 50 and panel[1].X == bounds.x)
    assert(bounds.y == (w == 480 and 215 or 241))
    assert(bounds.x > 233 and bounds.y + bounds.height < h)
end

lines, words = {}, {}
hud.render({}, {rank = 6, ready = true}, true)
assert(#lines == 0 and #words == 0)
Font = function() return nil, false end
hud = assert(load(style_source))()
draw(4, false, 5)
assert(#lines == 8 and words[1][1] == 'B' and words[2][1] == '5')
lines, words = {}, {}
hud.render({}, nil)
assert(#lines == 0 and #words == 0)
''')
print('Samira style HUD ranks, meter, animation, clocks, pulse and pocket-item clearance passed.')
