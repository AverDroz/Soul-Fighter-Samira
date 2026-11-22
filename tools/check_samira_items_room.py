"""Verify shop substitution, console showcases and the bundled glyph coverage."""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

MOD = ROOT / 'src/samira-testroom/mod'
FONT = MOD / 'resources/font/samira_items_ru.fnt'
font_data = FONT.read_bytes()
assert font_data[:4] == b'BMF\x03'
offset = 4
blocks = {}
while offset < len(font_data):
    kind, length = struct.unpack_from('<BI', font_data, offset)
    start = offset + 5
    blocks[kind] = font_data[start:start + length]
    offset = start + length
assert offset == len(font_data)
assert FONT.with_name(blocks[3].rstrip(b'\0').decode('ascii')).is_file()
glyphs = {values[0] for values in struct.iter_unpack('<IHHHHhhhBB', blocks[4])}
source = {name: (MOD / f'{name}.lua').read_text(encoding='utf-8')
          for name in ('samira_items_room', 'samira_items_data', 'samira_item_icons', 'samira_item_description')}
for char in set(''.join(source.values())):
    if not char.isspace():
        assert ord(char) in glyphs, repr(char)

lua = LuaRuntime()
lua.globals().sources = lua.table_from(source)
lua.globals().texture_exists = lambda path: (MOD / 'resources' / path).is_file()
lua.execute(r'''
function include(name) return assert(load(sources[name], name))() end
ModCallbacks = {MC_POST_UPDATE = 1, MC_POST_NEW_ROOM = 2, MC_EXECUTE_CMD = 3, MC_POST_GAME_STARTED = 4}
EntityType = {ENTITY_PICKUP = 5, ENTITY_PLAYER = 1, ENTITY_EFFECT = 1000}
PickupVariant = {PICKUP_COLLECTIBLE = 100, PICKUP_HEART = 10, PICKUP_COIN = 20, PICKUP_KEY = 30,
    PICKUP_BOMB = 40, PICKUP_LIL_BATTERY = 90, PICKUP_PILL = 70, PICKUP_TAROTCARD = 300,
    PICKUP_GRAB_BAG = 69, PICKUP_TRINKET = 350}
RoomType, GridCollisionClass = {ROOM_SHOP = 2}, {COLLISION_NONE = 0}
LevelCurse = {CURSE_OF_BLIND = 1}
Keyboard, AutocompleteType = {KEY_F4 = 1}, {NONE = 0}
Console = {RegisterCommand = function() end}

local vec = {}
vec.__index = vec
function vec.__add(a, b) return Vector(a.X + b.X, a.Y + b.Y) end
function vec:Distance(b) return ((self.X - b.X)^2 + (self.Y - b.Y)^2)^0.5 end
Vector = setmetatable({}, {__call = function(_, x, y) return setmetatable({X = x, Y = y}, vec) end})
Vector.Zero = Vector(0, 0)
local rngBounds = {}
function RNG()
    return {
        SetSeed = function(self, seed) self.seed = seed end,
        RandomInt = function(self, count)
            rngBounds[#rngBounds + 1] = count
            self.seed = (self.seed * 48271) % 2147483647
            return self.seed % count
        end,
    }
end

local catalog, lookup, byId = include('samira_items_data'), {}, {}
local description = include('samira_item_description')
local unwrapped = {GetStringWidthUTF8 = function() return 0 end}
for i, item in ipairs(catalog) do
    lookup[item.collectibleName] = i + 1000
    byId[i + 1000] = item
    local stats, passive = description.lines(unwrapped, item, 1)
    local segments = 0
    local text = table.concat(stats, ' ')
    for _ in string.gmatch(text, ' · ') do segments = segments + 1 end
    local fields = 0
    for _ in pairs(item.stats) do fields = fields + 1 end
    assert(segments + 1 == fields, item.name .. ' is missing a stat')
    assert(table.concat(passive, ' '):find(item.descriptionRu, 1, true))
    if item.riotId == 3031 then
        assert(text:find('Множитель крита +0,3×', 1, true))
    elseif item.riotId == 3032 then
        assert(text:find('Шанс крита 0%', 1, true))
    elseif item.riotId == 3083 then
        assert(text:find('Красные сердца +2,5', 1, true))
    end
end
local shops, roomType, visit, clear, curse, greed, active = {}, 2, true, true, 0, false, true
local entities, drawn, printed, renderedItems = {}, {}, {}, {}
local roomIndex, seed, spawnedCount, spawnFailureAt = 1, 70, 0
local cramped, keyDown, mirror = false, false, false
local screenWidth, reservedStyle = 480, nil
local room = {
    GetType = function() return roomType end,
    IsFirstVisit = function() return visit end,
    IsClear = function() return clear end,
    GetSpawnSeed = function() return seed end,
    GetCenterPos = function() return Vector(320, 200) end,
    GetGridSize = function() return 91 end,
    GetGridPosition = function(_, index) return Vector(80 + index % 13 * 40, 80 + index // 13 * 40) end,
    IsPositionInRoom = function(_, p) return p.X > 80 and p.X < 560 and p.Y > 80 and p.Y < 320 end,
    GetGridCollision = function(_, index) return cramped and 1 or 0 end,
    GetGridEntity = function(_, index) if index == 15 then return {} end end,
    GetDoor = function(_, slot) if slot == 0 then return {Position = Vector(80, 200)} end end,
    IsMirrorWorld = function() return mirror end,
}
local level = {
    GetCurrentRoomDesc = function() return {ListIndex = roomIndex} end,
    GetCurses = function() return curse end,
}
local game = {
    GetRoom = function() return room end,
    GetLevel = function() return level end,
    IsGreedMode = function() return greed end,
}
local player = {Position = Vector(320, 200)}
local nextSeed = 100
local function entity(typ, variant, id, pos, price)
    nextSeed = nextSeed + 1
    local e = {Type = typ, Variant = variant, SubType = id, Position = pos, Price = price, Index = nextSeed,
               InitSeed = nextSeed, Visible = true, data = {}}
    function e:ToPickup() if self.Type == 5 then return self end end
    function e:IsShopItem() return self.Price ~= 0 end
    function e:IsBlind() return self.blind end
    function e:MakeShopItem(slot) self.ShopItemId = slot end
    function e:GetData() return self.data end
    function e:Remove() self.removed = true end
    entities[#entities + 1] = e
    return e
end
local function roomEntities()
    local existing = {}
    for _, e in ipairs(entities) do if not e.removed then existing[#existing + 1] = e end end
    return existing
end
Isaac = {
    GetItemIdByName = function(name) return lookup[name] or -1 end,
    GetRoomEntities = roomEntities,
    FindByType = function(typ, variant)
        local found = {}
        for _, e in ipairs(roomEntities()) do
            if e.Type == typ and e.Variant == variant then found[#found + 1] = e end
        end
        return found
    end,
    Spawn = function(typ, variant, id, pos)
        spawnedCount = spawnedCount + 1
        return entity(typ, variant, spawnedCount == spawnFailureAt and 1 or id, pos, 0)
    end,
    ConsoleOutput = function(message) printed[#printed + 1] = message end,
    DebugString = function() end,
    GetScreenWidth = function() return screenWidth end,
    GetScreenHeight = function() return 270 end,
    WorldToScreen = function(position) return Vector(position.X / 2, position.Y / 2) end,
    DrawLine = function(a, b, _, _, thickness)
        if not reservedStyle then return end
        local top, bottom = a.Y - thickness / 2, a.Y + thickness / 2
        assert(a.X >= 0 and b.X <= screenWidth and top >= 0 and bottom <= 270)
        assert(b.X < reservedStyle.x or bottom < reservedStyle.y)
    end,
}
function Sprite(path, loadGraphics)
    assert(path == 'gfx/items/collectibles/samira_hud_icon.anm2' and not loadGraphics)
    return {
        ReplaceSpritesheet = function(self, layer, texture, reload)
            assert(layer == 0 and texture_exists(texture) and reload)
            self.texture = texture
        end,
        SetFrame = function(_, name, index) assert(name == 'Idle' and index == 0) end,
        Render = function(self)
            assert(self.Scale.X == 0.5 and self.Scale.Y == 0.5)
            renderedItems[self.texture] = true
        end,
    }, true
end
function KColor(...) return {...} end
function Font(path)
    assert(path == 'font/samira_items_ru.fnt')
    return {
        GetStringWidthUTF8 = function(_, value) return utf8.len(value) * 7 end,
        DrawStringScaledUTF8 = function(_, value, x, y)
            assert(x >= 0 and x <= screenWidth and y >= 0 and y <= 270)
            drawn[#drawn + 1] = value
        end,
    }, true
end
Input = {IsButtonPressed = function() return keyDown end}
local callbacks = {}
local mod = {AddCallback = function(_, callback, fn) callbacks[callback] = fn end}
local runtime = {getRoomState = function(key) shops[key] = shops[key] or {}; return shops[key] end}
local shop = include('samira_items_room')
shop.init(mod, game, function() if active then return player end end, runtime)
local function update() callbacks[1](mod) end
local function enter(index)
    roomIndex = index
    callbacks[2](mod)
end
local function run(command, args) callbacks[3](mod, command, args) end
local function fakeVanilla()
    local normal = entity(5, 100, 33, Vector(200, 200), 15)
    local heart = entity(5, 10, 1, Vector(240, 200), 5)
    normal.ShopItemId, heart.ShopItemId = 0, 1
    return normal, heart
end
local normal, heart = fakeVanilla()
local freeReward = entity(5, 100, 56, Vector(400, 200), 0)
local questPedestal = entity(5, 100, 900, Vector(200, 120), 15)
questPedestal.ShopItemId = 8
local device = entity(6, 8, 0, Vector(440, 120), 0)
active = false
update()
assert(not normal.removed and spawnedCount == 0)
active, clear = true, false
update()
assert(not normal.removed and spawnedCount == 0)
clear, greed = true, true
update()
assert(not normal.removed and spawnedCount == 0)
greed = false
update()
assert(not normal.removed and not heart.removed and not freeReward.removed and not questPedestal.removed and not device.removed)
assert(normal.Price == 15 and heart.Price == 5 and normal.ShopItemId == 0 and heart.ShopItemId == 1)
assert(table.concat(rngBounds, ',') == '46,45,44,43')
local firstShop, ids, slots = {}, {}, {[0] = true, [1] = true, [8] = true}
for _, e in ipairs(roomEntities()) do
    if byId[e.SubType] then
        firstShop[#firstShop + 1] = e
        local item = byId[e.SubType]
        assert(e.Price == item.price and not e.AutoUpdatePrice and not ids[e.SubType] and not slots[e.ShopItemId])
        assert(e.Position:Distance(Vector(80, 200)) >= 78)
        for _, existing in ipairs({normal, heart, freeReward, questPedestal, device}) do
            assert(e.Position:Distance(existing.Position) >= 32)
        end
        assert(e.Position:Distance(Vector(160, 120)) > 0)
        for _, other in ipairs(firstShop) do assert(other == e or e.Position:Distance(other.Position) >= 40) end
        ids[e.SubType], slots[e.ShopItemId] = true, true
    end
end
assert(#firstShop == 4)

EID = {}
shop.render(player)
local firstPage = table.concat(drawn, '|')
assert(firstPage:find('F4 · 1/2', 1, true))
drawn, keyDown, mirror = {}, true, true
shop.render(player)
assert(table.concat(drawn, '|'):find('F4 · 2/2', 1, true))
assert(firstShop[2].data.EID_Hide)
drawn, curse = {}, 1
shop.render(player)
assert(#drawn == 0 and not firstShop[2].data.EID_Hide)
curse, keyDown = 0, false
shop.render(player)
local function pagePress()
    drawn, keyDown = {}, true
    shop.render(player)
    local contents = table.concat(drawn, '|')
    keyDown = false
    shop.render(player)
    return contents
end
assert(pagePress():find('F4 · 2/2 · скрыть', 1, true))
assert(pagePress() == 'F4 · описания')
assert(pagePress():find('F4 · 1/2', 1, true))

firstShop[1]:Remove()
firstShop[2].Price = 99
visit = false
enter(1)
update()
assert(spawnedCount == 4 and firstShop[2].Price == byId[firstShop[2].SubType].price)
callbacks[4](mod, true)
update()
assert(spawnedCount == 4 and not normal.removed and not heart.removed)

enter(2)
entities, visit, cramped = {}, true, true
local crampedOffer = fakeVanilla()
update()
assert(not crampedOffer.removed and spawnedCount == 4)

enter(3)
entities, cramped = {}, false
local rollbackOffer = fakeVanilla()
spawnFailureAt = spawnedCount + 3
update()
assert(not rollbackOffer.removed and #roomEntities() == 2)
spawnFailureAt = nil

enter(5)
entities, seed = {}, seed + 1
local secondShop = fakeVanilla()
update()
local different = 0
for _, e in ipairs(roomEntities()) do
    if byId[e.SubType] and not ids[e.SubType] then different = different + 1 end
end
assert(#roomEntities() == 6 and different > 0 and not secondShop.removed)

enter(6)
entities = {}
local legacy = entity(5, 100, firstShop[2].SubType, Vector(200, 200), 99)
legacy.ShopItemId = 2
shops['shop:6'] = {stocked = {[tostring(legacy.InitSeed)] = legacy.SubType}}
update()
assert(#roomEntities() == 1 and legacy.Price == byId[legacy.SubType].price and not legacy.removed)

-- Profile filtering affects newly generated bonus offers, not native stock,
-- and persisted bonus offers survive later predicate changes.
enter(7)
entities, roomType, visit = {}, 2, true
local vanillaYone, heartYone = fakeVanilla()
local allowed = {}
for i = 1, 4 do allowed[catalog[i].riotId] = true end
runtime.shopEligible = function(_, riotId) return allowed[riotId] == true end
update()
local curated = {}
for _, e in ipairs(roomEntities()) do
    if byId[e.SubType] then
        assert(allowed[byId[e.SubType].riotId]); curated[#curated + 1] = e
    end
end
assert(#curated == 4 and not vanillaYone.removed and not heartYone.removed)
runtime.shopEligible = function() return false end
curated[1].Price = 99
visit = false
enter(7); update()
assert(curated[1].Price == byId[curated[1].SubType].price and not curated[1].removed)
runtime.shopEligible = nil

enter(4)
entities, roomType = {}, 1
local unrelated = entity(5, 100, 90, Vector(280, 160), 0)
local foe = entity(50, 0, 0, Vector(360, 240), 0)
local showcased = {}
for page = 1, 4 do
    run('samiraitems', tostring(page))
    local count = 0
    for _, e in ipairs(roomEntities()) do
        if byId[e.SubType] then
            assert(e.Price == 0 and e.ShopItemId == -1 and not showcased[e.SubType])
            showcased[e.SubType] = true
            count = count + 1
        end
    end
    assert(count == math.min(12, #catalog - (page - 1) * 12))
    assert(not unrelated.removed and not foe.removed)
    shop.render(player)
    for _ = 2, math.ceil(count / 3) do
        assert(pagePress():find('F4 · ', 1, true))
    end
    enter(4)
end
run('samiraitem', '3031')
local single
for _, e in ipairs(roomEntities()) do if byId[e.SubType] then single = e end end
assert(#roomEntities() == 3 and byId[single.SubType].riotId == 3031)
run('samirashop', '')
assert(#roomEntities() == 6 and single.removed)
assert(not unrelated.removed and not foe.removed)
assert(printed[#printed]:find('4 Samira offers', 1, true))
run('yoneitem', '3084')
for _, e in ipairs(roomEntities()) do if byId[e.SubType] then single = e end end
assert(#roomEntities() == 3 and byId[single.SubType].riotId == 3084)
run('yoneitems', '1')
assert(#roomEntities() == 14 and single.removed)
run('yoneshop', '')
assert(#roomEntities() == 6)

local backpack = {x = 86, width = 147, y = 244, height = 22}
for _, width in ipairs({480, 640}) do
    screenWidth, renderedItems = width, {}
    reservedStyle = {x = width - 79, y = 172, width = 51, height = 34}
    for page = 1, 4 do
        run('samiraitems', tostring(page))
        enter(4)
        keyDown = false
        shop.render(player, backpack, reservedStyle)
        local pagedOut = false
        for _ = 1, 12 do
            drawn, keyDown = {}, true
            shop.render(player, backpack, reservedStyle)
            if #drawn == 1 and drawn[1] == 'F4 · описания' then pagedOut = true break end
            keyDown = false
            shop.render(player, backpack, reservedStyle)
        end
        assert(pagedOut, 'F4 never reached the end of a debug group')
    end
    for _, item in ipairs(catalog) do
        assert(renderedItems[item.icon], item.name .. ' was hidden by responsive pagination')
    end
end
''')
print('Samira shops, console showcases, layout, rendered pages and Cyrillic glyphs passed.')
