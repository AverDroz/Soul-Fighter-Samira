"""Exercise the native Samira item callbacks against the generated catalog."""
from pathlib import Path
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

MOD = ROOT / 'src/samira-testroom/mod'
# Passive items resolve through the engine's collectible subdirectory.
native_items = ElementTree.parse(MOD / 'content/items.xml').getroot()
assert native_items.attrib['gfxroot'] == 'gfx/items/'
assert len(native_items) == 46
for native_item in native_items:
    assert native_item.tag == 'passive'
    icon = MOD / 'resources' / native_items.attrib['gfxroot'] / 'collectibles' / native_item.attrib['gfx']
    assert icon.is_file(), f"Native item texture missing: {icon}"

lua = LuaRuntime()
lua.globals().itemsSource = (MOD / 'samira_items.lua').read_text(encoding='utf8')
lua.globals().catalogSource = (MOD / 'samira_items_data.lua').read_text(encoding='utf8')
lua.globals().styleSource = (MOD / 'samira_style.lua').read_text(encoding='utf8')
lua.globals().yoneCombatSource = (MOD / 'yone_combat.lua').read_text(encoding='utf8')
lua.globals().yoneArtifactsSource = (MOD / 'yone_artifacts.lua').read_text(encoding='utf8')
lua.execute(r'''
local catalog = assert(load(catalogSource))()
local Style = assert(load(styleSource))()
function include(name)
    if name == 'samira_items_data' then return catalog end
    assert(name == 'yone_artifacts')
    return assert(load(yoneArtifactsSource))()
end
package.loaded.json = {encode = function(t) return t end, decode = function(t) return t end}
local callbacks, save, clock, index, floor, clear, list = {}, nil, 0, 1, 1, false, {}
local p, source, random, rolls, sounds = nil, nil, .01, 0, 0
local consoleLines = {}
local bolts = 0
local function nameKey(_, key) return key end
ModCallbacks, EntityType = setmetatable({}, {__index = nameKey}), setmetatable({}, {__index = nameKey})
CacheFlag = {CACHE_DAMAGE = 1, CACHE_FIREDELAY = 2, CACHE_SPEED = 4, CACHE_SIZE = 8}
EntityFlag = {FLAG_FRIENDLY = 1, FLAG_SLOW = 2}
ProjectileFlags = {CANT_HIT_PLAYER = 1}
EntityPartition = {ENEMY = 1, BULLET = 2}
GridCollisionClass = {COLLISION_NONE = 0}
TearFlags = {TEAR_SPECTRAL = 1}
TearVariant, EntityCollisionClass, EntityGridCollisionClass = {BLUE = 0}, {ENTCOLL_NONE = 0}, {GRIDCOLL_NONE = 0}
DamageFlag = {DAMAGE_POISON_BURN = 1, DAMAGE_IV_BAG = 2, DAMAGE_EXPLOSION = 4, DAMAGE_LASER = 8, DAMAGE_SPIKES = 16}
CollectibleType = {COLLECTIBLE_GLOWING_HOUR_GLASS = 1}
CallbackPriority = {LATE = 100}
Color = function(...) return {...} end
EntityRef = function(t) return {Entity = t} end
GetPtrHash = function(t) return t.InitSeed end
SFXManager = function() return {Play = function(_, id) assert(id == 12345); sounds = sounds + 1 end} end
RNG = function()
    return {SetSeed = function() end, Next = function() end, RandomFloat = function()
        rolls = rolls + 1
        return random
    end}
end
local vec = {}
vec.__index = vec
Vector = setmetatable({}, {__call = function(_, x, y) return setmetatable({X = x, Y = y}, vec) end})
Vector.Zero = Vector(0, 0)
function vec.__add(a,b) return Vector(a.X+b.X,a.Y+b.Y) end
function vec.__sub(a,b) return Vector(a.X-b.X,a.Y-b.Y) end
function vec.__mul(a,b) return Vector(a.X*b,a.Y*b) end
function vec:Dot(b) return self.X*b.X+self.Y*b.Y end
function vec:Length() return math.sqrt(self:Dot(self)) end
function vec:Distance(b) return (self-b):Length() end
function vec:Normalized() return self * (1 / self:Length()) end

local host = {}
function host:AddCallback(name, callback, filter) assert(not callbacks[name], name); callbacks[name] = callback end
function host:AddPriorityCallback(name, priority, callback) self:AddCallback(name, callback) end
function host:HasData() return save ~= nil end
function host:LoadData() return save end
function host:SaveData(data) save = data end
local function fire(name, ...)
    if callbacks[name] then return callbacks[name](host, ...) end
end

local itemIds = {}
for _, row in ipairs(catalog) do itemIds[row.collectibleName] = row.riotId end
Isaac = {
    GetItemIdByName = function(name) return assert(itemIds[name], name) end,
    GetSoundIdByName = function(name) assert(name == 'Samira Heartsteel Proc'); return 12345 end,
    GetPlayer = function() return p end,
    ConsoleOutput = function(line) consoleLines[#consoleLines + 1] = line end,
    GetRoomEntities = function() return list end,
    Spawn = function(kind, _, _, origin, velocity, owner)
        assert(kind == EntityType.ENTITY_TEAR and owner == p and velocity:Length() > 0)
        bolts = bolts + 1
        return {ToTear = function(self) return self end, SetColor = function() end}
    end,
    FindInRadius = function(origin, radius, partition)
        local result = {}
        for _, entity in ipairs(list) do
            local candidate = entity.Type == EntityType.ENTITY_PROJECTILE and EntityPartition.BULLET or EntityPartition.ENEMY
            if candidate == partition and entity.Position:Distance(origin) <= radius then result[#result + 1] = entity end
        end
        return result
    end
}
local game = {
    GetRoom = function() return {IsClear = function() return clear end} end,
    GetLevel = function()
        return {
            GetStage = function() return floor end,
            GetDungeonPlacementSeed = function() return floor * 10 end,
            GetDimension = function() return 0 end,
            GetCurrentRoomDesc = function() return {SafeGridIndex = index} end,
        }
    end,
    GetSeeds = function() return {GetStartSeed = function() return 59469 end} end,
    GetFrameCount = function() return clock end,
}
local Items = assert(load(itemsSource))()
local yoneRoutes = {reductions = 0}
local yone = {
    is = function(player) return player and player.yone == true end,
    exportCooldowns = function() return {q=17} end,
    reset = function(keep) assert(keep); yoneRoutes.reset = true end,
    restoreCooldowns = function(saved, frame) yoneRoutes.restored = {saved=saved, frame=frame} end,
    reduceCooldowns = function(fraction) assert(fraction == .15); yoneRoutes.reductions = yoneRoutes.reductions + 1 end,
}
Items.init(host, game, function() return p end, nil, yone)
local reductions = 0
local accepted = {}
Items.bindCombat({
    reduceCooldowns = function(fraction, _)
        assert(fraction == .15); reductions = reductions + 1
    end,
    acceptHit = function(context, frame)
        Style.hit(context, frame)
        accepted[#accepted + 1] = {context = context, frame = frame}
    end,
})

local function entity(seed, kind, x, y)
    local e = {InitSeed = seed, Type = kind, Position = Vector(x or 0, y or 0), HitPoints = 10000,
        MaxHitPoints = 10000, Size = 5, flags = 0, hits = {}, data = {}}
    function e:GetData() return self.data end
    function e:Exists() return not self.removed end
    function e:IsDead() return self.HitPoints <= 0 end
    function e:HasMortalDamage() return self.HitPoints <= (self.deferredDamage or 0) end
    function e:FlushDamage()
        if not self.deferredDamage then return end
        self.HitPoints = self.HitPoints - self.deferredDamage
        self.deferredDamage = nil
        if self:IsDead() then fire('MC_POST_NPC_DEATH', self) end
    end
    function e:IsVulnerableEnemy() return not self.protected end
    function e:IsActiveEnemy() return self.Type == EntityType.ENEMY end
    function e:IsBoss() return self.boss == true end
    function e:HasEntityFlags(flag) return self.flags & flag ~= 0 end
    function e:AddSlowing(_, frames, speed) self.slowed = {frames, speed} end
    function e:AddTearFlags(flag) self.tearFlags = (self.tearFlags or 0) | flag end
    function e:ToProjectile() return self end
    function e:HasProjectileFlags(_) return self.harmless == true end
    function e:Remove() self.removed = true end
    function e:TakeDamage(amount, flags, origin, countdown, extra)
        if self.protected or self:IsDead() then return false end
        local result = fire('MC_ENTITY_TAKE_DMG', self, amount, flags, origin, countdown, extra)
        if result == false or self.cancelled then return false end
        if type(result) == 'table' then amount = result.Damage end
        self.hits[#self.hits + 1] = amount
        if self == p then
            self.hp = math.max(0, self.hp - amount)
            self.damageCooldown = 60
        elseif self.bufferDamage then
            self.deferredDamage = (self.deferredDamage or 0) + amount
        elseif not self.instantReset then
            self.HitPoints = self.HitPoints - amount
        end
        fire('MC_POST_ENTITY_TAKE_DMG', self, amount, flags, origin, countdown, extra)
        if self:IsDead() then fire('MC_POST_NPC_DEATH', self) end
        return true
    end
    return e
end

local function step(frames)
    for _ = 1, (frames or 1) do
        clock = clock + 1
        for _, npc in ipairs(list) do npc:FlushDamage() end
        Items.update(p, clock)
    end
end
local function enter(num, newFloor)
    index, floor, list, clear = num, newFloor or floor, {}, false
    fire('MC_POST_NEW_ROOM')
    step()
end
local function start(owned, red, max)
    clock, index, floor, clear, list, save, reductions, rolls, sounds, bolts = 0, 1, 1, false, {}, nil, 0, 0, 0, 0
    accepted = {}
    Style.reset()
    p = entity(1, EntityType.ENTITY_PLAYER)
    p.owned, p.hp, p.max, p.coins, p.soul, p.bone = {}, red or 6, max or 6, 0, 0, 0
    for _, id in ipairs(owned) do p.owned[id] = (p.owned[id] or 0) + 1 end
    function p:GetCollectibleNum(id) return self.owned[id] or 0 end
    function p:GetEffectiveMaxHearts() return self.max + 2 * self.bone end
    function p:GetMaxHearts() return self.max end
    function p:GetHearts() return self.hp end
    function p:GetSoulHearts() return self.soul end
    function p:GetBoneHearts() return self.bone end
    function p:AddMaxHearts(amount) self.max = math.min(self.max + amount, 24) end
    function p:AddHearts(amount) self.hp = math.min(self.hp + amount, self:GetEffectiveMaxHearts()) end
    function p:AddCoins(amount) self.coins = self.coins + amount end
    function p:GetDamageCooldown() return self.damageCooldown end
    function p:SetMinDamageCooldown(ticks) self.damageCooldown = math.max(ticks, self.damageCooldown) end
    function p:AddCacheFlags(flags) self.cacheFlags = flags end
    function p:EvaluateItems()
        local flags = self.cacheFlags
        if flags & CacheFlag.CACHE_DAMAGE ~= 0 then self.Damage = 4 end
        if flags & CacheFlag.CACHE_SPEED ~= 0 then self.MoveSpeed = 1 end
        if flags & CacheFlag.CACHE_FIREDELAY ~= 0 then self.MaxFireDelay = 14 end
        if flags & CacheFlag.CACHE_SIZE ~= 0 then self.SpriteScale = Vector(1, 1) end
        for _, flag in pairs(CacheFlag) do
            if flags & flag ~= 0 then fire('MC_EVALUATE_CACHE', self, flag) end
        end
    end
    source = EntityRef(p)
    fire('MC_POST_GAME_STARTED', false)
    Items.activate(p)
    enter(1)
end
local function close(got, expected, context)
    assert(math.abs(got - expected) < 1e-6, ('%s: %s vs %s'):format(context or 'wrong value', got, expected))
end
local function hit(npc, kind, ctx, amount)
    ctx = ctx or Items.newAttack(p, kind or 'attack', clock)
    Items.withContext(ctx, function() npc:TakeDamage(amount or p.Damage, 0, source, 0) end)
    return npc.hits[#npc.hits]
end
local function tear(npc, ctx, amount)
    local shot = entity(200, EntityType.ENTITY_TEAR)
    shot.FallingSpeed, shot.FallingAcceleration = -2, 1
    Items.tagTear(p, shot, ctx or Items.newAttack(p, 'attack', clock))
    npc:TakeDamage(amount or p.Damage, 0, EntityRef(shot), 0)
    return shot
end
local function enemy(seed, x, y)
    local result = entity(seed, EntityType.ENEMY, x, y)
    list[#list + 1] = result
    return result
end

assert(#catalog == 46)
for _, row in ipairs(catalog) do
    start({row.riotId})
    local foe = enemy(4, 30, 0)
    local stats = row.stats
    local flat = (stats.damage_flat or 0)
    if row.riotId == 3053 then flat = flat + .35 end
    if row.riotId == 2501 then flat = flat + .4 end
    if row.riotId == 3170 then flat = flat + .13 end
    close(p.Damage, (4 + flat) * (1 + ((stats.lethality_damage_bonus_pct or 0)
        + (stats.armor_pen_damage_bonus_pct or 0)) / 100), row.nameEn)
    close(p.MaxFireDelay, 15 / (1 + (stats.attack_speed_pct or 0) / 100) - 1)
    close(p.MoveSpeed, (1 + (stats.move_speed_flat or 0)) * (1 + (stats.move_speed_pct or 0) / 100))
    local ctx = Items.newAttack(p, 'w', clock)
    Items.onCast(p, 'w', clock, ctx)
    hit(foe, 'w', ctx)
    hit(foe, 'attack')
    tear(foe)
    step(2)
end

start({3078, 3153})
local foe = enemy(3)
local damage = p.Damage
local cooldown = Items.cooldown(p, 'q', 60)
assert(cooldown == 46 and Items.attackInterval(p, p.MaxFireDelay + 1) == 10)
Items.onCast(p, 'q', clock)
foe.cancelled = true
hit(foe, 'attack')
foe.cancelled = false
close(hit(foe, 'attack'), damage * 1.25 + 3, 'Trinity survives cancelled hit')
close(hit(foe, 'attack'), damage * 1.25)
enter(2)
foe = enemy(3)
Items.onCast(p, 'e', clock)
close(hit(foe, 'attack'), damage * 1.25, 'Trinity cooldown crosses rooms')

start({3181, 6672})
foe = enemy(3)
for i = 1, 15 do
    local expected = p.Damage * (i % 3 == 0 and 1.5 or 1) + (i % 5 == 0 and 4 or 0)
    close(hit(foe, 'attack'), expected, 'Hullbreaker and Kraken')
end

start({3031, 2517, 6696}, 1, 8)
foe, damage = enemy(3), p.Damage
local ult = Items.newAttack(p, 'r', clock)
assert(rolls == 1)
for _ = 1, 10 do close(hit(foe, 'r', ult), damage * 1.8 * 1.2) end
assert(rolls == 2 and p.hp == 2, 'R must use one crit roll and one vamp roll')
enter(2)
hit(enemy(3), 'r')
assert(p.hp == 2, 'vamp cooldown crosses rooms')
step(240)
hit(enemy(4), 'r')
assert(p.hp == 3)
start({3033, 6609})
foe, damage = enemy(3), p.Damage
hit(foe, 'q')
step(15)
hit(foe, 'q')
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step(15)
assert(#foe.hits == 3)
close(foe.hits[3], damage * .15)
step(105)
assert(#foe.hits == 5, 'shared bleed did not tick precisely three times')

start({3072, 3072, 6672}, 2, 8)
local dummy = entity(3, EntityType.ENTITY_DUMMY, 50, 0)
dummy.instantReset = true
list = {dummy}
random = .05
tear(dummy)
assert(rolls == 1 and p.hp == 2, '5% is an exclusive upper roll threshold')
random = .0499
local nativeTear = entity(200, EntityType.ENTITY_TEAR)
Items.tagTear(p, nativeTear, Items.newAttack(p, 'attack', clock))
dummy:TakeDamage(p.Damage, 0, source, 0, EntityRef(nativeTear))
assert(rolls == 2 and p.hp == 3, 'tagged extra tear should heal once from an accepted dummy hit')
step(239)
tear(dummy)
assert(rolls == 2 and p.hp == 3)
step()
local direct = Items.newAttack(p, 'q', clock)
Items.withContext(direct, function() dummy:TakeDamage(p.Damage, 0, source, 0, EntityRef(nil)) end)
assert(rolls == 2 and p.hp == 3, 'an ability cannot use lifesteal')
tear(dummy)
assert(rolls == 3 and p.hp == 4)
fire('MC_EXECUTE_CMD', 'samiravamp')
assert(consoleLines[1]:find('AA 5.00%%') and consoleLines[2]:find('dummy 5') and consoleLines[2]:find('heals 2'))
assert(consoleLines[4]:find('active=false'))
foe = enemy(4)
close(hit(foe, 'attack'), p.Damage, 'dummy must not advance Kraken')

start({2517}, 2, 8)
dummy = entity(3, EntityType.ENTITY_DUMMY)
dummy.instantReset = true
local dummyUlt = Items.newAttack(p, 'r', clock)
random = 0
for _ = 1, 10 do hit(dummy, 'r', dummyUlt) end
assert(rolls == 1 and p.hp == 3, 'dummy R: exactly one omnivamp check')
step(240)
local foreignLaser = entity(222, EntityType.ENTITY_LASER)
local foreignCtx = Items.newAttack(p, 'w', clock)
Items.withContext(foreignCtx, function() dummy:TakeDamage(p.Damage, 0, source, 0, EntityRef(foreignLaser)) end)
assert(rolls == 1 and p.hp == 3, 'a native extra laser must not inherit a direct cast')
random = .01

start({2525, 3053, 6673}, 7, 8)
foe = enemy(3)
p:TakeDamage(6, 0, EntityRef(foe), 0)
assert(p.hp == 7 and p.damageCooldown == 72)
p:TakeDamage(6, 0, EntityRef(foe), 0)
p:TakeDamage(6, 0, EntityRef(foe), 0)
p.hp = 7
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step()
p:TakeDamage(6, 0, EntityRef(foe), 0)
assert(p.hp == 1, 'Lifeline used charges disappeared on continue')
enter(2, 2)
p.hp = 7
p:TakeDamage(6, DamageFlag.DAMAGE_IV_BAG, EntityRef(foe), 0)
assert(p.hp == 1, 'voluntary damage consumed or triggered Lifeline')
p.hp = 7
p:TakeDamage(6, DamageFlag.DAMAGE_SPIKES, nil, 0)
assert(p.hp == 1 and p.damageCooldown == 72, 'spikes should extend i-frames without triggering Lifeline')
p.hp = 7
p:TakeDamage(6, 0, EntityRef(foe), 0)
assert(p.hp == 7)

start({3814})
local function projectile(seed)
    local bullet = entity(seed, EntityType.ENTITY_PROJECTILE, 30, 0)
    list[#list + 1] = bullet
    return bullet
end
local bullet = projectile(5)
assert(p:TakeDamage(1, 0, EntityRef(bullet), 0) == false and bullet.removed)
clear = true
step(601)
assert(p:TakeDamage(1, 0, EntityRef(projectile(6)), 0))
clear = false
step(599)
foe = projectile(7)
assert(p:TakeDamage(1, 0, EntityRef(foe), 0))
step()
assert(p:TakeDamage(1, 0, EntityRef(projectile(8)), 0) == false)
enter(2)
assert(p:TakeDamage(1, 0, EntityRef(projectile(9)), 0) == false)

start({3084}, 6, 6)
local enemies = {}
for id = 1, 4 do enemies[id] = enemy(id + 5, 40, id) end
step(60)
local target = enemies[1]
close(hit(target, 'attack'), p.Damage * 1.5)
close(hit(target, 'attack'), p.Damage)
for id = 2, 4 do close(hit(enemies[id], 'attack'), p.Damage * 1.5) end
assert(p.hp == 7 and p.max == 7 and sounds == 4)
close(p.SpriteScale.X, 1.015)
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step(60)
close(hit(target, 'attack'), p.Damage, 'Heartsteel cooldown survives continue')

-- Both the first target and the item damage hooks are selected by the real
-- Yone combat module. The second target is listed first to catch ordering bugs.
local yoneCombat = assert(load(yoneCombatSource))()
local openRoom = {
    CheckLine = function() return true end, IsPositionInRoom = function() return true end,
    GetGridSize = function() return 0 end, GetGridIndex = function() return 0 end,
    GetGridCollision = function() return GridCollisionClass.COLLISION_NONE end,
}
start({}, 6, 6)
p.yone = true
assert(Items.heartsteelTargets() == nil, 'charge displayed without owning Heartsteel')
p.owned[3084] = 1
local fight = yoneCombat.new(Items)
local function strike(key, windup, clip)
    assert(yoneCombat.cast(fight, key, p, Vector(160, 0), clock, openRoom) == (clip or key))
    step(windup)
    yoneCombat.update(fight, openRoom, p, list, clock)
end
local function charge(entity)
    for _, targetStatus in ipairs(Items.heartsteelTargets()) do
        if targetStatus.position == entity.Position then return targetStatus.fraction end
    end
end
local second = enemy(302, 60, 0)
local first = enemy(301, 25, 0)
step(30)
close(charge(first), .5, 'nearby target displays a partially charged strike')
assert(sounds == 0)
step(30)
close(charge(first), 1, 'nearby target displays a full charge')
strike('attack', 4)
close(first.hits[1], p.Damage * 1.5, 'Yone basic attack procs Heartsteel')
assert(sounds == 1 and #second.hits == 0 and not charge(first))
strike('q', 6)
close(second.hits[1], p.Damage * 1.4, 'a charged second target cannot proc Heartsteel')
assert(sounds == 1 and charge(second) == 1)
first.Position = Vector(25, 90)
local third = enemy(303, 70, 0)
step(60)
strike('q', 6)
close(second.hits[2], p.Damage * 1.4 * 1.5, 'Yone Q procs Heartsteel on its first target')
close(third.hits[1], p.Damage * 1.4, 'Yone Q does not proc Heartsteel twice')
assert(sounds == 2)
second.Position = Vector(60, 90)
step(30)
fight.qStacks = 2
strike('q', 7, 'q3')
close(third.hits[2], p.Damage * 1.6 * 1.5, 'Yone Q3 procs Heartsteel')
assert(sounds == 3)
p.Position = Vector(0, 0)
local fourth = enemy(304, 25, 0)
step(60)
strike('w', 8)
close(fourth.hits[1], p.Damage * 1.15, 'Yone W cannot consume a charge')
assert(sounds == 3 and charge(fourth) == 1)
fourth.cancelled = true
strike('q', 6)
assert(sounds == 3 and p:GetMaxHearts() == 6 and charge(fourth) == 1, 'cancelled hit spent the Heartsteel charge')
fourth.cancelled = false
strike('attack', 4)
assert(sounds == 4 and p:GetMaxHearts() == 7 and p:GetHearts() == 7, 'four unique procs did not grant the half-heart')
fire('MC_PRE_GAME_EXIT', true)
assert(save.heartsteel == 1 and save.heartsteelPairs == 0)
fire('MC_POST_GAME_STARTED', true)
step(60)
close(hit(fourth, 'attack'), p.Damage, 'Yone Heartsteel cooldown survives continue')
step(300)
close(hit(fourth, 'attack'), p.Damage * 1.5, 'Yone Heartsteel can damage a target again after recharging')
fire('MC_PRE_GAME_EXIT', true)
assert(sounds == 5 and save.heartsteel == 1 and save.heartsteelPairs == 0, 'a repeat proc counted as a new target')

start({6697, 3083, 2520}, 6, 10)
foe = enemy(3)
foe.boss, foe.MaxHitPoints, foe.HitPoints = true, 200, 200
damage = p.Damage
close(hit(foe, 'w'), damage + 1.5 + 30)
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step()
close(hit(foe, 'w'), damage)
clear = true
step(10)
close(p.Damage, damage + .118)
enter(2)
clear = true
step()
assert(p.hp == 7)
enter(1)
clear = true
step()
close(p.Damage, damage + .236)

start({3085, 3046, 6695})
foe = enemy(3, 45, 0)
local neighbor, neighbor2, distant = enemy(4, 70, 0), enemy(5, 45, 30), enemy(6, 45, 100)
local shot = tear(foe)
assert(shot.tearFlags == TearFlags.TEAR_SPECTRAL)
bullet = projectile(7)
shot.Position = Vector(60, 0)
fire('MC_POST_TEAR_UPDATE', shot)
assert(bullet.removed, 'Serpent Fang missed a projectile along the swept path')
step()
close(neighbor.hits[1], foe.hits[1] * .25)
close(neighbor2.hits[1], foe.hits[1] * .25)
assert(#distant.hits == 0 and #neighbor.hits == 1, 'Runaan queued recursive bolts')
assert(bolts == 2)

start({6676})
foe = enemy(3, 40, 0)
foe.HitPoints, foe.MaxHitPoints = 12, 200
hit(foe, 'q', nil, 5)
assert(not foe:IsDead())
step()
assert(foe:IsDead())
clear = true
step()
assert(p.coins == 1)
enter(2)
foe = enemy(4)
foe.HitPoints, foe.MaxHitPoints = 12, 200
hit(foe, 'q', nil, 5)
foe.protected = true
step()
assert(not foe:IsDead(), 'execution bypassed an invulnerable phase')

start({6676})
random = .5
foe = enemy(3, 40, 0)
foe.HitPoints, foe.MaxHitPoints, foe.bufferDamage = 12, 200, true
hit(foe, 'q', nil, 5)
assert(foe.HitPoints == 12 and #foe.hits == 1)
Items.update(p, clock)
assert(#foe.hits == 1, 'Collector considered uncommitted same-frame HP')
step()
assert(foe.HitPoints == 7 and foe:HasMortalDamage() and not foe:IsDead() and #foe.hits == 2
    and p.coins == 0, 'Collector must attempt native damage without paying before death')
clear = true
step()
assert(foe:IsDead() and p.coins == 1, 'Collector must pay after the buffered native death and clear')

enter(2)
foe = enemy(4, 40, 0)
foe.HitPoints, foe.MaxHitPoints, foe.bufferDamage = 12, 200, true
hit(foe, 'q', nil, 2)
step()
assert(foe.HitPoints == 10 and #foe.hits == 1, 'Collector threshold is strictly below 5%')
hit(foe, 'q', nil, 12)
clear = true
step()
assert(foe:IsDead() and p.coins == 1, 'a normal lethal hit is not a Collector execution')

start({2523})
random = .5 -- Keep the explicit damage amounts independent of crit.
foe = enemy(3)
foe.HitPoints, foe.bufferDamage = 6, true
hit(foe, 'q', nil, 7)
assert(foe.HitPoints == 6 and Items.attackRange(p, 100) == 100)
step()
assert(foe:IsDead() and Items.attackRange(p, 100) == 120, 'confirmed direct buffered kill activates Hexoptics')
step(240)
assert(Items.attackRange(p, 100) == 100)
foe = enemy(4)
foe.HitPoints, foe.bufferDamage = 6, true
hit(foe, 'q', nil, 2)
foe:TakeDamage(7, DamageFlag.DAMAGE_POISON_BURN, source, 0)
step()
assert(foe:IsDead() and Items.attackRange(p, 100) == 100, 'secondary death must not grant Hexoptics range')
random = .01

start({})
clear = true
assert(not Items.claimCombatRoomReset(), 'a clear room does not grant a cooldown reset')
clear = false
assert(Items.claimCombatRoomReset(), 'entering combat grants one cooldown reset')
assert(not Items.claimCombatRoomReset(), 'the same fight cannot reset cooldowns twice')
enter(2)
assert(Items.claimCombatRoomReset(), 'a second combat room has its own reset')
enter(1)
assert(not Items.claimCombatRoomReset(), 'leaving and returning to combat preserves the reset claim')
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step()
assert(not Items.claimCombatRoomReset(), 'continuing a run preserves the reset claim')
enter(1, 2)
assert(Items.claimCombatRoomReset(), 'the same room index on another floor has a new reset')

Items.bindWeapons({
    context = function(player, sourceRef, extraRef)
        local entity = extraRef and extraRef.Entity or sourceRef and sourceRef.Entity
        if not entity or not entity.nativeContext or entity.nativeContext.player ~= player then return end
        return entity.nativeContext, entity.Type ~= EntityType.ENTITY_KNIFE, entity.Type
    end,
})

local function nativeOutput(kind, sourceKind, id)
    local ctx = Items.newAttack(p, kind, clock)
    ctx.nativeWeapon = true
    ctx.damageMultiplier = kind == 'q' and 1.5 or 1
    local entity = entity(id, sourceKind)
    entity.nativeContext = ctx
    return entity, ctx
end

start({2517}, 2, 8)
foe = enemy(3)
foe.instantReset = true  -- Simulate native buffered HP until a later update.
local nativeLaser, qContext = nativeOutput('q', EntityType.ENTITY_LASER, 901)
for _ = 1, 10 do
    assert(foe:TakeDamage(8, DamageFlag.DAMAGE_LASER, source, 0, EntityRef(nativeLaser)))
    close(foe.hits[#foe.hits], 12, 'native Q laser damage')
end
assert(#accepted == 10 and accepted[1].context == qContext and accepted[10].context == qContext)
assert(Style.status(clock).rank == 1, 'native Q laser contributes a single rank across ten accepted ticks')
assert(p.hp == 3 and rolls == 1 and foe.HitPoints == foe.MaxHitPoints,
    'buffered native damage still heals once and informs Style about the accepted Q')

start({3072}, 2, 8)
foe = enemy(3)
local nativeBomb = nativeOutput('q', EntityType.ENTITY_BOMB, 902)
foe:TakeDamage(8, DamageFlag.DAMAGE_EXPLOSION, EntityRef(nativeBomb), 0)
close(foe.hits[1], 12, 'native Q bomb damage')
assert(rolls == 0 and p.hp == 2, 'Q bomb may not use lifesteal')

local nativeAA, aaContext = nativeOutput('aa', EntityType.ENTITY_LASER, 903)
foe:TakeDamage(8, DamageFlag.DAMAGE_LASER, source, 0, EntityRef(nativeAA))
close(foe.hits[2], 8, 'native AA keeps base damage')
assert(rolls == 1 and p.hp == 3 and accepted[2].context == aaContext)
assert(Style.status(clock).rank == 2, 'accepted Q and AA contribute distinct style ranks')

local foreign = entity(904, EntityType.ENTITY_LASER)
Items.withContext(Items.newAttack(p, 'e', clock), function()
    foe:TakeDamage(8, DamageFlag.DAMAGE_LASER, source, 0, EntityRef(foreign))
end)
close(foe.hits[3], 8)
assert(#accepted == 2 and rolls == 1, 'foreign laser may not inherit a Samira cast')

local poison = nativeOutput('q', EntityType.ENTITY_TEAR, 905)
foe:TakeDamage(8, DamageFlag.DAMAGE_POISON_BURN, EntityRef(poison), 0)
close(foe.hits[4], 8)
assert(#accepted == 2 and rolls == 1, 'secondary poison may not inherit Q scaling or procs')

local fireplace = entity(906, EntityType.ENTITY_FIREPLACE)
fireplace:TakeDamage(8, DamageFlag.DAMAGE_EXPLOSION, EntityRef(nativeBomb), 0)
close(fireplace.hits[1], 12, 'native Q also scales object damage')
assert(#accepted == 2 and rolls == 1, 'object damage may not trigger Style')
assert(Style.status(clock).rank == 2, 'foreign, secondary and object damage must leave style unchanged')

-- These are the two independent save slots used by the native Hourglass.
-- Exercise callbacks in both orders relative to POST_NEW_ROOM, including
-- a backtracked room whose old first-combat reset claim must be forgotten.
start({})
local remaining = {q=0,w=0,e=0,r=0}
local restored, appliedAt
Items.bindCombat({
    reset=function(keep) assert(keep) end,
    exportCooldowns=function() return {q=remaining.q,w=remaining.w,e=remaining.e,r=remaining.r} end,
    restoreCooldowns=function(saved, f) restored,appliedAt=saved,f end,
})
assert(Items.claimCombatRoomReset())
clock=1002; fire('MC_POST_GLOWING_HOURGLASS_SAVE',0)
enter(2); assert(Items.claimCombatRoomReset())
remaining={q=21,w=525,e=0,r=0}
clock=1541; fire('MC_POST_GLOWING_HOURGLASS_SAVE',1)
fire('MC_PRE_GAME_EXIT',true)
fire('MC_POST_GAME_STARTED',true); step()
fire('MC_PRE_GLOWING_HOURGLASS_LOAD',0)
enter(1); fire('MC_POST_GLOWING_HOURGLASS_LOAD',0)
clock=1002; Items.applyCooldownCheckpoint(clock)
assert(appliedAt==1002 and restored.w==0 and restored.r==0 and not Items.claimCombatRoomReset())
enter(2); assert(Items.claimCombatRoomReset(), 'discarded visit consumed first-fight reset')
fire('MC_PRE_GLOWING_HOURGLASS_LOAD',1); fire('MC_POST_GLOWING_HOURGLASS_LOAD',1)
enter(2); clock=1541; Items.applyCooldownCheckpoint(clock)
assert(appliedAt==1541 and restored.w==525 and restored.q==21 and not Items.claimCombatRoomReset())
appliedAt=nil; Items.applyCooldownCheckpoint(1542); assert(appliedAt==nil, 'checkpoint applied twice')


-- Yone-specific profile applies only to Yone; Samira assertions above ran
-- against the same registered callbacks and must remain untouched.
start({2520, 3031, 6675, 3053, 6673, 2525}, 3, 12)
p.yone = true
step()
assert(Items.shopEligible(p, 3031) and not Items.shopEligible(p, 3078))
local shopCount = 0
for _, row in ipairs(catalog) do if Items.shopEligible(p, row.riotId) then shopCount = shopCount + 1 end end
assert(shopCount >= 16 and shopCount <= 24)
p.yone = false
for _, row in ipairs(catalog) do assert(Items.shopEligible(p, row.riotId)) end
p.yone = true
random = 0
local bossTarget = enemy(101); bossTarget.boss = true
local otherTarget = enemy(102)
local q = Items.newAttack(p, 'q3', clock)
assert(q.kind == 'q' and q.crit)
local damage = p.Damage
close(hit(bossTarget, nil, q), damage * 1.8 + 1.5 + 2 * damage, 'Yone boss cap')
close(hit(otherTarget, nil, q), damage, 'Yone crit once per cast')
local rollsBefore = rolls
local ult = Items.newAttack(p, 'r', clock)
assert(not ult.crit and rolls == rollsBefore, 'Yone R cannot roll critical')
hit(otherTarget, 'attack')
assert(yoneRoutes.reductions == 1, 'Navori must route to Yone')
assert(#accepted == 0, 'Yone must not route accepted hits to Samira style')
local attacker = enemy(103)
p:TakeDamage(1, 0, EntityRef(attacker), 0)
assert(p.hp == 5, 'Yone lifeline heals three half hearts')
p.hp = 3
p:TakeDamage(1, 0, EntityRef(attacker), 0)
assert(p.hp == 2, 'Yone lifeline family must share the floor trigger')
clock=100; fire('MC_POST_GLOWING_HOURGLASS_SAVE',0)
fire('MC_PRE_GLOWING_HOURGLASS_LOAD',0); fire('MC_POST_GLOWING_HOURGLASS_LOAD',0)
Items.applyCooldownCheckpoint(clock)
assert(yoneRoutes.reset and yoneRoutes.restored.saved.q == 17 and yoneRoutes.restored.frame == 100)
fire('MC_PRE_GAME_EXIT',true)
assert(save.combatCooldowns.q == 17, 'Yone cooldowns must be saved')
yoneRoutes.restored=nil
fire('MC_POST_GAME_STARTED',true)
Items.restoreCombatCooldowns()
assert(yoneRoutes.restored.saved.q == 17, 'Yone cooldowns must restore')

print('Passed 46 item stat checks, native weapon damage and Style, combat scenarios, and persistence.')
''')
