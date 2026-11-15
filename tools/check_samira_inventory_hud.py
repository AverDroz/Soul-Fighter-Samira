"""Verify the six inventory slots and input edges under the native projection."""
from pathlib import Path
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
MOD = ROOT / 'src/samira-testroom/mod'
ASSET = MOD / 'resources/gfx/items/collectibles/samira_hud_icon.anm2'
frame = ElementTree.parse(ASSET).find('.//LayerAnimation/Frame')
assert (frame.get('Width'), frame.get('Height'), frame.get('XPivot'), frame.get('YPivot')) == ('32', '32', '16', '16')
lua.globals().sources = lua.table_from({name: (MOD / f'{name}.lua').read_text(encoding='utf-8')
                                      for name in ('samira_inventory_hud', 'samira_item_icons',
                                                   'samira_item_description', 'samira_items_data')})
lua.globals().texture_exists = lambda path: (MOD / 'resources' / path).is_file()
lua.execute(r'''
function include(name) return assert(load(sources[name], name))() end
local vec = {}
vec.__index = vec
Vector = setmetatable({}, {__call = function(_, x, y) return setmetatable({X = x, Y = y}, vec) end})
Vector.Zero = Vector(0, 0)
function vec.__sub(a, b) return Vector(a.X - b.X, a.Y - b.Y) end
function vec.__mul(a, b) return Vector(a.X * b, a.Y * b) end
function KColor(...) return {...} end
local hud = include('samira_inventory_hud')
local width, height, mouse, left, xKey, paused = 640, 270, Vector.Zero
local rectangles, icons, words, textureLoads = {}, {}, {}, 0
Options = {HUDOffset = 0}
Keyboard = {KEY_X = 88}
Input = {
    IsMouseBtnPressed = function(button) assert(button == 0); return left end,
    IsButtonPressed = function(key) assert(key == 88); return xKey end,
    GetMousePosition = function(inWorld) assert(not inWorld); return mouse end,
}
Isaac = {
    GetScreenWidth = function() return width end,
    GetScreenHeight = function() return height end,
    ScreenToWorld = function(v) return Vector(v.X * 0.7 + 10, v.Y * 0.8 + 20) end,
    WorldToScreenDistance = function(v) return Vector(v.X / 2, v.Y / 2) end,
    DrawLine = function(start, finish, color, _, thickness)
        rectangles[#rectangles + 1] = {start.X, start.Y - thickness / 2, finish.X, start.Y + thickness / 2, color}
    end,
}
function Sprite(path, loadGraphics)
    assert(path == 'gfx/items/collectibles/samira_hud_icon.anm2' and not loadGraphics)
    return {
        ReplaceSpritesheet = function(self, layer, texture, reload)
            assert(layer == 0 and reload and texture_exists(texture))
            self.texture = texture
            textureLoads = textureLoads + 1
        end,
        SetFrame = function(_, name, index) assert(name == 'Idle' and index == 0) end,
        Render = function(self, pos)
            assert(self.Scale.X == 0.55 and self.Scale.Y == 0.55)
            icons[#icons + 1] = {self.texture, pos.X, pos.Y}
        end,
    }, true
end
function Font(path)
    assert(path == 'font/samira_items_ru.fnt')
    return {
        GetStringWidthUTF8 = function(_, text) return utf8.len(text) * 7 end,
        DrawStringScaledUTF8 = function(_, text, x, y) words[#words + 1] = {text, x, y} end,
    }, true
end
local slots, selected, selections, drops = {}, 1, {}, {}
local inventory = {
    slots = function() return slots end,
    selected = function() return selected end,
    select = function(i) selected = i; selections[#selections + 1] = i end,
    drop = function(_, i) drops[#drops + 1] = i; slots[i] = nil end,
}
local trinket
local player = {GetTrinket = function(_, slot) return slot == 0 and trinket or 0 end}
local game = {IsPaused = function() return paused end}
hud.init(game, inventory)

local function hover(index, x)
    local b = hud.bounds(player)
    mouse = Vector((b.x + (index - 1) * 25 + (x or 10)) / 0.35, (b.y + 10) / 0.4)
end
hud.render(player)
assert(#rectangles == 12 and #icons == 0 and #words == 0)
assert(rectangles[1][5][1] == 1 and rectangles[3][5][1] < 1)
left = true
hover(4)
hud.input(player, true)
assert(#selections == 1 and selected == 4)
hover(2)
hud.input(player, true)
assert(#selections == 1 and selected == 4)
left = false
hud.input(player, true)
left = true
hover(4, 23)
hud.input(player, true)
assert(#selections == 1)
left = false
hud.input(player, true)
left, xKey = true, true
hover(2)
hud.input(player, false)
hud.input(player, true)
assert(#selections == 1 and #drops == 0)
left, xKey = false, false
hud.input(nil, false)
local icon = 'gfx/items/collectibles/samira_item_3072.png'
slots[4] = {collectibleId = 900, icon = icon, name = 'Кровопийца', descriptionRu = 'Шанс восстановить ½ красного сердца.',
    stats = {damage_flat = 3.2, lifesteal_chance_pct = 3.75}}
rectangles, icons, words = {}, {}, {}
hover(4)
hud.render(player)
assert(#icons == 1 and icons[1][1] == icon and #words >= 3)
assert(words[1][1] == 'Кровопийца' and words[#words][1] == 'X · выбросить выбранное')
local observed = {}
for _, word in ipairs(words) do observed[#observed + 1] = word[1] end
assert(table.concat(observed, ' '):find('Урон +3,2 · Шанс вампиризма автоатак +3,75%', 1, true))
for _, size in ipairs({480, 640}) do
    width = size
    for _, offset in ipairs({0, 1}) do
        Options.HUDOffset = offset
        hover(4)
        rectangles, icons, words = {}, {}, {}
        hud.render(player)
        assert(#rectangles >= 14 and #icons == 1)
        local b = hud.bounds(player)
        assert(b.x == 6 + offset * 16 and b.y + b.height == height - 4)
        for _, r in ipairs(rectangles) do
            assert(r[1] >= b.x and r[3] <= b.x + b.width)
            assert(r[2] >= 0 and r[4] <= height - 4)
        end
        trinket = 42
        assert(hud.bounds(player).x == 70 + offset * 16)
        trinket = nil
    end
end
assert(textureLoads == 1)
local stored = slots[4]
for _, item in ipairs(include('samira_items_data')) do
    slots[4] = item
    hover(4)
    rectangles, icons, words = {}, {}, {}
    hud.render(player)
    assert(rectangles[13][2] >= 0, item.name)
    assert(#words > 2 and table.concat(words[1], ' '):find(item.name:match('^[^ ]+'), 1, true), item.name)
end
slots[4] = stored
paused, xKey = true, true
hud.input(player, true)
paused = false
hud.input(player, true)
assert(#drops == 0)
xKey = false
hud.input(player, true)
xKey = true
hud.input(player, true)
hud.input(player, true)
assert(#drops == 1 and drops[1] == 4 and not slots[4])
''')
print('Samira inventory HUD sprites, click calibration, input latching and bottom-left trinket clearance passed.')
