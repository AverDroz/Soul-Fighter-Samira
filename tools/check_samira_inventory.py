"""Exercise six-slot bookkeeping around genuine Isaac collectible callbacks."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

MOD = ROOT / 'src/samira-testroom/mod'
lua = LuaRuntime()
lua.globals().inventorySource = (MOD / 'samira_inventory.lua').read_text(encoding='utf8')
lua.globals().catalogSource = (MOD / 'samira_items_data.lua').read_text(encoding='utf8')
lua.execute(r'''
local catalog = assert(load(catalogSource))()
local names, capacities = {}, {}
for _, row in ipairs(catalog) do
    names[row.collectibleName] = row.riotId
    capacities[row.riotId] = (row.stats.health_red_hearts or 0) * 2
end
function include(name) assert(name == 'samira_items_data'); return catalog end
function GetPtrHash(entity) return entity end
Vector = {Zero = {X = 0, Y = 0}}
EntityType = {ENTITY_PICKUP = 5}
PickupVariant = {PICKUP_COLLECTIBLE = 100}
ModCallbacks = {MC_PRE_ADD_COLLECTIBLE = 1, MC_POST_ADD_COLLECTIBLE = 2, MC_POST_GAME_STARTED = 3}

local callbacks, spawned, failSpawn = {}, {}, false
local p = {Position = Vector.Zero}
local state = {}
local function activate()
    p.count, p.red, p.max, p.coins = {}, 6, 6, 99
    p.removeNativeHealth = false
    spawned, state, failSpawn = {}, {}, false
    callbacks[3]()
end
Isaac = {
    GetItemIdByName = function(name) return names[name] end,
    Spawn = function(kind, variant, id, position, velocity, owner)
        assert(kind == 5 and variant == 100 and owner == nil)
        if failSpawn then return nil end
        local pickup = {item = id, Price = 15, AutoUpdatePrice = true}
        function pickup:ToPickup() return self end
        function pickup:SetVarData(var) self.var = var end
        function pickup:Remove() self.removed = true end
        spawned[#spawned + 1] = pickup
        return pickup
    end,
}
function p:GetMaxHearts() return self.max end
function p:GetEffectiveMaxHearts() return self.max end
function p:GetHearts() return self.red end
function p:GetSoulHearts() return 0 end
function p:GetBoneHearts() return 0 end
function p:GetCollectibleNum(id) return self.count[id] or 0 end
function p:AddMaxHearts(add)
    self.max = math.max(0, math.min(24, self.max + add))
    self.red = math.min(self.max, self.red)
end
function p:AddHearts(add) self.red = math.max(0, math.min(self.max, self.red + add)) end
function p:RemoveCollectible(id)
    self.count[id] = self:GetCollectibleNum(id) - 1
    if self.removeNativeHealth then self:AddMaxHearts(-(capacities[id] or 0)) end
end

local room = {FindFreePickupSpawnPosition = function() return Vector.Zero end}
local Inventory = assert(load(inventorySource))()
Inventory.init({AddCallback = function(_, id, cb) callbacks[id] = cb end},
    {GetRoom = function() return room end}, function() return p end,
    {getInventoryState = function() return state end})

local function acquire(id, paid, pedestal, forceFresh)
    local price = paid or 0
    if p.coins < price then return false end
    p.coins = p.coins - price
    local firstTime = forceFresh == true or not pedestal or not pedestal.Touched
    local var = pedestal and pedestal.var or 0
    local arguments = callbacks[1](nil, id, 0, firstTime, 0, var, p)
    if arguments then firstTime = arguments[3] end
    p.count[id] = p:GetCollectibleNum(id) + 1
    if firstTime then
        p:AddMaxHearts(capacities[id] or 0)
        p:AddHearts(capacities[id] or 0)
    end
    callbacks[2](nil, id, 0, firstTime, 0, var, p)
    if pedestal then pedestal:Remove() end
    return true
end

activate()
assert(Inventory.selected() == 1)
assert(not Inventory.select(0) and not Inventory.select(7))
for _, id in ipairs({1001, 1001, 3006, 3008, 3009, 3031}) do assert(acquire(id)) end
for id = 1, 20 do
    if not capacities[id] then acquire(id) end
end
Inventory.update(p)
assert(p:GetCollectibleNum(1001) == 2 and p:GetCollectibleNum(1) == 1 and #spawned == 0)
assert(Inventory.select(2))
assert(not acquire(2520, 100))
assert(Inventory.slots(p)[2].riotId == 1001 and #spawned == 0 and p.coins == 99)
assert(acquire(2520, 20))
assert(Inventory.slots(p)[1].riotId == 1001 and Inventory.slots(p)[2].riotId == 2520)
assert(p:GetCollectibleNum(1001) == 1 and p:GetCollectibleNum(2520) == 1 and p.coins == 79)
local drop = spawned[1]
assert(drop.item == 1001 and drop.Price == 0 and drop.ShopItemId == -1 and drop.AutoUpdatePrice == false)
assert(drop.Touched and drop.Wait == 30 and drop.var ~= 0)
assert(Inventory.select(6) and Inventory.drop(p))
assert(Inventory.slots(p)[6] == nil and p:GetCollectibleNum(3031) == 0)
assert(#spawned == 2 and spawned[2].item == 3031)
assert(acquire(1001, 0, drop))
assert(Inventory.slots(p)[6].riotId == 1001 and p:GetCollectibleNum(1001) == 2)
local continued = {entries = {}, initialized = state.initialized, selected = state.selected,
    observedMax = state.observedMax}
for k, v in pairs(state.entries) do continued.entries[k] = {riotId = v.riotId, hearts = v.hearts} end
callbacks[3]()
state = continued
Inventory.update(p)
assert(Inventory.selected() == 6 and Inventory.slots(p)[2].riotId == 2520 and #spawned == 2)
p.count[2520] = 0
Inventory.update(p)
assert(Inventory.slots(p)[2] == nil and p:GetCollectibleNum(1) == 1 and #spawned == 2)

activate()
assert(acquire(2501))
assert(p.max == 10 and p.red == 10)
p.red = 4
for round = 1, 3 do
    assert(Inventory.drop(p, 1))
    assert(p.max == 6 and p.red == 4)
    assert(acquire(2501, 0, spawned[round], round == 2))
    assert(p.max == 10 and p.red == 4, 'dropped item refilled red health')
end
p.removeNativeHealth = true
assert(Inventory.drop(p, 1))
assert(p.max == 6 and p.red == 4, 'native removal already removed capacity')
assert(acquire(2501, 0, spawned[4]))
assert(p.max == 10 and p.red == 4)
p.count[2501] = 0
Inventory.update(p)
assert(p.max == 6 and Inventory.slots(p)[1] == nil)

activate()
p.max, p.red = 20, 19
for _, id in ipairs({2501, 1001, 3006, 3008, 3009, 3031}) do acquire(id) end
assert(p.max == 24 and p.red == 23)
assert(acquire(3084, 20))
assert(Inventory.slots(p)[1].riotId == 3084 and p.max == 24 and p.red == 24)
assert(Inventory.drop(p, 1) and p.max == 20)

activate()
assert(acquire(2501))
assert(Inventory.drop(p, 1))
local oldHealthPickup = spawned[1]
for _, id in ipairs({3078, 1001, 3006, 3008, 3009, 3031}) do acquire(id) end
assert(p.max == 12 and p.red == 12)
assert(acquire(2501, 0, oldHealthPickup, true))
assert(Inventory.slots(p)[1].riotId == 2501 and p.max == 10 and p.red == 6,
    'swapping a previously dropped health item should not refill outgoing containers')

activate()
for _, id in ipairs({1001, 1001, 3006, 3008, 3009, 3031}) do acquire(id) end
failSpawn = true
assert(acquire(2501, 20))
assert(Inventory.slots(p)[1].riotId == 1001 and p:GetCollectibleNum(2501) == 0
    and p.coins == 79 and p.max == 6 and p.red == 6)
Inventory.update(p)
assert(#spawned == 0)
failSpawn = false
Inventory.update(p)
assert(#spawned == 1 and spawned[1].item == 2501 and spawned[1].Price == 0)
assert(acquire(2501, 0, spawned[1]))
assert(Inventory.slots(p)[1].riotId == 2501 and p:GetCollectibleNum(1001) == 1 and p.coins == 79)

activate()
p.count[1001], p.count[2501], p.count[5] = 2, 1, 4
p.max, p.red = 10, 7
Inventory.update(p)
assert(Inventory.slots(p)[1].riotId == 1001 and Inventory.slots(p)[3].riotId == 2501)
assert(Inventory.drop(p, 3) and p.max == 6 and p.red == 6 and p:GetCollectibleNum(5) == 4)

print('Passed six-slot replacement, native purchases, duplicate and ordinary items, drop/re-pick, D4 and continue checks.')
''')
