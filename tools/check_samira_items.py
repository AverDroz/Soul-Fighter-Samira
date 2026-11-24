"""Exercise the native Samira item callbacks against the generated catalog."""
from pathlib import Path
import sys
import json
import hashlib
from PIL import Image
from xml.etree import ElementTree
from build_item_components import component_icons
from build_isaac_items import encode_png, render_legacy_icons

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

MOD = ROOT / 'src/samira-testroom/mod'
# Passive items resolve through the engine's collectible subdirectory.
native_items = ElementTree.parse(MOD / 'content/items.xml').getroot()
assert native_items.attrib['gfxroot'] == 'gfx/items/'
# The first 46 IDs and names are persistent save identifiers.
lock = json.loads((ROOT / 'docs/components-data.lock.json').read_text(encoding='utf8'))
icon_lock = json.loads((ROOT / 'docs/components-icons.lock.json').read_text(encoding='utf8'))
component_art, styled_atlases = component_icons()
assert len(native_items) == len(lock['entries']) == 73
assert [int(item.attrib['id']) for item in native_items] == list(range(1, 74))
assert styled_atlases == icon_lock['styled_atlases']
assert set(component_art) == {icon['riot_id'] for icon in icon_lock['icons']}
assert len({icon['output_sha256'] for icon in icon_lock['icons']}) == 27
for index, riot_id in enumerate(lock['original_ids']):
    assert native_items[index].attrib['gfx'] == f'samira_item_{riot_id}.png'
    assert native_items[index].attrib['name'] == 'Samira: ' + lock['entries'][str(riot_id)]['name_en']
for icon in icon_lock['icons']:
    riot_id = icon['riot_id']
    source = ROOT / 'assets/samira-items/components' / f'{riot_id}.png'
    target = MOD / 'resources/gfx/items/collectibles' / f'samira_item_{riot_id}.png'
    native_png, art_asset, art_cell = component_art[riot_id]
    assert (icon['art_asset'], icon['art_cell']) == (art_asset, art_cell)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == icon['source_sha256']
    assert target.read_bytes() == native_png
    assert hashlib.sha256(target.read_bytes()).hexdigest() == icon['output_sha256']
    with Image.open(target) as image:
        assert image.size == (32, 32) and image.mode == 'RGBA'
        bounds = image.getchannel('A').getbbox()
        assert bounds is not None and bounds[0] >= 2 and bounds[1] >= 2 and bounds[2] <= 30 and bounds[3] <= 30
for native_item in native_items:
    assert native_item.tag == 'passive'
    icon = MOD / 'resources' / native_items.attrib['gfxroot'] / 'collectibles' / native_item.attrib['gfx']
    assert icon.is_file(), f"Native item texture missing: {icon}"

lua = LuaRuntime()
catalog = lua.execute((MOD / 'samira_items_data.lua').read_text(encoding='utf8'))
rows = {row['riotId']: row for row in catalog.values()}
assert set(rows) == {int(key) for key in lock['entries']}
original_ids = set(lock['original_ids'])
legacy_icons = json.loads((ROOT / 'docs/items-icons.lock.json').read_bytes())
legacy_tiles, legacy_atlas, legacy_digest, overrides = render_legacy_icons(lock['original_ids'])
assert legacy_digest == legacy_icons['styled_atlas']['sha256']
assert (MOD / legacy_icons['spritesheet']['output']).read_bytes() == encode_png(legacy_atlas)
for icon, tile in zip(legacy_icons['icons'], legacy_tiles, strict=True):
    assert (MOD / icon['output']).read_bytes() == encode_png(tile)
    assert overrides.get(icon['riot_id'], {}).get('art_override') == icon.get('art_override')
for key, entry in lock['entries'].items():
    riot_id = int(key)
    row = rows[riot_id]
    assert bool(row['component']) == (riot_id not in original_ids or riot_id == 1001)
    recipe = entry['from']
    actual = list(row['components'].values()) if row['components'] is not None else []
    assert actual == recipe, (riot_id, actual, recipe)
    if recipe:
        assert all(part in rows for part in recipe)
        assert row['combinePrice'] == max(0, row['price'] - sum(rows[part]['price'] for part in recipe))
    else:
        assert row['combinePrice'] is None

lua.globals().itemsSource = (MOD / 'samira_items.lua').read_text(encoding='utf8')
lua.globals().catalogSource = (MOD / 'samira_items_data.lua').read_text(encoding='utf8')
lua.globals().styleSource = (MOD / 'samira_style.lua').read_text(encoding='utf8')
lua.globals().yoneCombatSource = (MOD / 'yone_combat.lua').read_text(encoding='utf8')
lua.globals().yoneArtifactsSource = (MOD / 'yone_artifacts.lua').read_text(encoding='utf8')
lua.globals().yoneWeaponArtifactsSource = (MOD / 'yone_artifact_weapons.lua').read_text(encoding='utf8')
lua.globals().yoneProgressSource = (MOD / 'yone_progression.lua').read_text(encoding='utf8')
lua.globals().missFortuneRunesSource = (MOD / 'miss_fortune_runes.lua').read_text(encoding='utf8')
lua.globals().missFortuneCombatSource = (MOD / 'miss_fortune_combat.lua').read_text(encoding='utf8')
lua.globals().nativeWeaponsSource = (MOD / 'samira_weapons.lua').read_text(encoding='utf8')
lua.globals().navigationSource = (MOD / 'samira_navigation.lua').read_text(encoding='utf8')
lua.execute(r'''
local catalog = assert(load(catalogSource))()
local byRiot = {}
for _, row in ipairs(catalog) do assert(not byRiot[row.riotId]); byRiot[row.riotId] = row end
local Style = assert(load(styleSource))()
local Progress = assert(load(yoneProgressSource))()
function include(name)
    if name == 'samira_items_data' then return catalog end
    if name == 'yone_artifact_weapons' then return assert(load(yoneWeaponArtifactsSource))() end
    if name == 'yone_progression' then return Progress end
    if name == 'miss_fortune_runes' then return assert(load(missFortuneRunesSource))() end
    if name == 'samira_navigation' then return assert(load(navigationSource))() end
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
    reduceUltimateCooldown = function(fraction, tick)
        yoneRoutes.refunds = yoneRoutes.refunds or {}
        table.insert(yoneRoutes.refunds, {fraction=fraction, tick=tick})
    end,
}
local corsairRoutes = {accepted = {}, refunds = {}, reductions = 0}
local corsair = {
    is = function(player) return player and player.corsair == true end,
    damageMultiplier = function(ctx, target)
        return not ctx.corsairSecondary and target.corsairMarked and 1.25 or 1
    end,
    acceptHit = function(ctx, tick, target, amount)
        corsairRoutes.accepted[#corsairRoutes.accepted + 1] = {ctx = ctx, tick = tick, target = target, amount = amount}
    end,
    exportCooldowns = function() return {q = 23, r = 140} end,
    reset = function(keep) assert(keep); corsairRoutes.reset = true end,
    restoreCooldowns = function(saved, frame) corsairRoutes.restored = {saved = saved, frame = frame} end,
    reduceCooldowns = function(fraction)
        assert(fraction == .15)
        corsairRoutes.reductions = corsairRoutes.reductions + 1
    end,
    reduceUltimateCooldown = function(fraction) corsairRoutes.refunds[#corsairRoutes.refunds + 1] = fraction end,
}
Items.init(host, game, function() return p end, nil, yone, corsair)
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
        if self.deathBeforePost and self:IsDead() then fire('MC_POST_NPC_DEATH', self) end
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
    function result:ToNPC() return self end
    list[#list + 1] = result
    return result
end

assert(#catalog == 73)
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
local function strike(key, windup, clip, aim)
    assert(yoneCombat.cast(fight, key, p, aim or Vector(160, 0), clock, openRoom) == (clip or key))
    step(windup)
    yoneCombat.update(fight, openRoom, p, list, clock)
end
local function charge(entity)
    for _, targetStatus in ipairs(Items.heartsteelTargets()) do
        if targetStatus.position == entity.Position then return targetStatus.fraction end
    end
end
local second = enemy(302, 78, 0)
local first = enemy(301, 25, 0)
step(30)
close(charge(first), .5, 'nearby target displays a partially charged strike')
assert(sounds == 0)
step(30)
close(charge(first), 1, 'nearby target displays a full charge')
strike('attack', 4, nil, Vector(160, -80))
close(first.hits[1], p.Damage * 1.5, 'Yone basic attack procs Heartsteel')
assert(sounds == 1 and #second.hits == 0 and not charge(first))
strike('q', 6)
close(second.hits[1], p.Damage * 1.4, 'a charged second target cannot proc Heartsteel')
assert(sounds == 1 and charge(second) == 1)
first.Position = Vector(25, 90)
local third = enemy(303, 80, 0)
step(60)
strike('q', 6)
close(second.hits[2], p.Damage * 1.4 * 1.5, 'Yone Q procs Heartsteel on its first target')
close(third.hits[1], p.Damage * 1.4, 'Yone Q does not proc Heartsteel twice')
assert(sounds == 2)
second.Position = Vector(78, 90)
step(60)
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
start({3031}, 6, 6); p.yone=true; random=.49
assert(Items.combatStats(p) == .50, 'crit display did not use the doubled chance')
for _,kind in ipairs({'attack','q','q3'}) do
    assert(Items.newAttack(p,kind,clock).crit, 'Yone must double crit chance for '..kind)
end
random=.51
assert(not Items.newAttack(p,'attack',clock).crit, 'Yone crit chance exceeded the doubled rate')
p.yone=false; random=.49
assert(Items.combatStats(p) == .25, 'Samira stat query inherited Yone passive')
assert(not Items.newAttack(p,'attack',clock).crit, 'Samira inherited Yone passive')
start({3031,6675},6,6); p.yone=true; random=.99
local before=rolls
assert(Items.combatStats(p) == 1, 'crit display exceeded 100%')
assert(Items.newAttack(p,'q',clock).crit and rolls==before, 'Yone crit did not cap at 100%')
start({3031,3032},6,6); p.yone=true; random=0
local dummy=enemy(890)
for i=1,5 do hit(dummy,'attack') end
random=.51
assert(Items.combatStats(p) == .52, 'crit display ignored the live stacks from Yun Tal')
assert(Items.newAttack(p,'q',clock).crit, 'Yun Tal crit bonus was not doubled')
before=rolls
assert(not Items.newAttack(p,'r',clock).crit and rolls==before, 'Yun Tal enabled a Yone R crit roll')

start({6696},6,6); p.yone=true; yoneRoutes.refunds={}
local slain=enemy(891); slain.HitPoints=1
hit(slain,'q')
assert(#yoneRoutes.refunds==1 and yoneRoutes.refunds[1].fraction==.03, 'Axiom missed a normal kill')
fire('MC_POST_NPC_DEATH',slain)
assert(#yoneRoutes.refunds==1, 'Axiom counted the same death twice')
local slainBoss=enemy(892); slainBoss.boss=true; slainBoss.HitPoints=1
hit(slainBoss,'q')
assert(#yoneRoutes.refunds==2 and yoneRoutes.refunds[2].fraction==.10, 'Axiom missed boss kill refund')
local early=enemy(895); early.HitPoints=1; early.deathBeforePost=true
hit(early,'q')
assert(#yoneRoutes.refunds==3, 'Axiom missed death before accepted post-damage')
local deferred=enemy(896); deferred.HitPoints=1; deferred.bufferDamage=true
hit(deferred,'q'); assert(#yoneRoutes.refunds==3, 'Axiom refunded before deferred death')
step(); assert(#yoneRoutes.refunds==4, 'Axiom missed deferred death')
local untouched=enemy(893); untouched.HitPoints=0; fire('MC_POST_NPC_DEATH',untouched)
assert(#yoneRoutes.refunds==4, 'Axiom rewarded an unrelated kill')
local expired=enemy(894); hit(expired,'attack'); step(91); expired.HitPoints=0; fire('MC_POST_NPC_DEATH',expired)
assert(#yoneRoutes.refunds==4, 'Axiom rewarded a stale hit')

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

start({1043, 6675, 3085, 3094})
p.corsair = true
random = .9
assert(Items.combatStats(p) == .75, 'Corsair uses normal crit chance')
assert(Items.shopEligible(p, 3085) and Items.shopEligible(p, 3094))
local samiraKillHits = 0
Items.bindKills({acceptHit = function() samiraKillHits = samiraKillHits + 1 end})
local primary, bounce, blocked, boltTarget = enemy(920, 100), enemy(921, 30), enemy(922, 102), enemy(923, 120)
primary.corsairMarked, blocked.corsairMarked, blocked.cancelled = true, true, true
p.Position = Vector(120, 0)
step()
local native, corsairQ = nativeOutput('q', EntityType.ENTITY_TEAR, 925)
assert(not blocked:TakeDamage(8, 0, EntityRef(native), 0))
assert(not corsairQ.accepted and #corsairRoutes.accepted == 0)
assert(primary:TakeDamage(8, 0, EntityRef(native), 0))
close(primary.hits[1], 8 * 1.5 * 1.25 + .3 + 1.2, 'Corsair Q primary on-hit, passive and Firecannon')
local confirmation = corsairRoutes.accepted[1]
assert(confirmation.target == primary and confirmation.ctx == corsairQ and confirmation.tick == clock)
close(confirmation.amount, primary.hits[1], 'Corsair accepted amount')
corsairQ.corsairSecondary = true
bounce.corsairMarked = true
close(hit(bounce, nil, corsairQ, 8), 8 * 1.5 + .3, 'MF ricochet applies Recurve but cannot spend Firecannon again')
corsairQ.corsairSecondary = nil
step()
assert(bolts == 2 and #boltTarget.hits == 1 and #bounce.hits == 1, 'Hurricane originates from native primary only')
assert(corsairRoutes.reductions == 1 and #accepted == 0 and samiraKillHits == 0)
Items.bindKills(nil)

start({3031, 6696})
p.corsair = true
random = .9
local waveTarget, slainByWave = enemy(930), enemy(931)
local wave = Items.newAttack(p, 'r', clock)
assert(not wave.crit and not Items.newAttack(p, 'w', clock).crit)
close(hit(waveTarget, nil, wave, 8), 8 * 1.2, 'Corsair Axiom R damage')
random = 0
Items.rerollCrit(wave)
assert(wave.crit and wave.accepted)
close(hit(waveTarget, nil, wave, 8), 8 * 1.2 * (1.45 + .30 * .45), 'MF R crit plus scaled Infinity Edge')
slainByWave.HitPoints = 1
hit(slainByWave, nil, wave, 8)
fire('MC_POST_NPC_DEATH', slainByWave)
assert(#corsairRoutes.refunds == 1 and corsairRoutes.refunds[1] == .03, 'Corsair Axiom counts a death once')
clock = 100
fire('MC_POST_GLOWING_HOURGLASS_SAVE', 2)
fire('MC_POST_GLOWING_HOURGLASS_LOAD', 2)
Items.applyCooldownCheckpoint(clock)
assert(corsairRoutes.reset and corsairRoutes.restored.saved.r == 140 and corsairRoutes.restored.frame == 100)
fire('MC_PRE_GAME_EXIT', true)
assert(save.combatCooldowns.q == 23 and save.combatCooldowns.r == 140)
corsairRoutes.restored = nil
fire('MC_POST_GAME_STARTED', true)
Items.restoreCombatCooldowns()
assert(corsairRoutes.restored.saved.q == 23)

do
    start({})
    p.corsair = true
    local credited = 0
    corsair.recordTakedown = function(player, frame)
        assert(player == p and frame == clock)
        credited = credited + 1
    end
    for i=1,2 do
        local victim=enemy(935+i)
        victim.HitPoints, victim.deathBeforePost = 1, i == 1
        hit(victim,'aa',nil,4)
        fire('MC_POST_NPC_DEATH',victim)
        assert(credited==i,'each credited kill must be seen once in either native callback order')
    end
    local unrelated=enemy(938)
    unrelated:TakeDamage(20000,0,EntityRef(nil),0)
    assert(credited==2,'a death without an accepted Miss Fortune hit gives no credit')
    corsair.recordTakedown=nil
end

local Runes = include('miss_fortune_runes')
local seenRunes = {}
for seed = 0, 200 do
    local left, right = Runes.restore(), Runes.restore()
    assert(Runes.choose(left, 'random', seed) and Runes.choose(right, 'random', seed))
    assert(left.rune == right.rune)
    seenRunes[left.rune] = true
end
for _, choice in ipairs(Runes.choices) do assert(choice.id == 'random' or seenRunes[choice.id]) end

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('press_the_attack'))
assert(not Items.chooseMissFortuneRune('conqueror'))
local runeFoe, otherRuneFoe = enemy(940), enemy(941)
local runeShot, runeVolley = nativeOutput('q', EntityType.ENTITY_TEAR, 942)
runeFoe.cancelled = true
assert(not runeFoe:TakeDamage(8, 0, EntityRef(runeShot), 0))
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 0)
runeFoe.cancelled = false
assert(runeFoe:TakeDamage(8, 0, EntityRef(runeShot), 0))
assert(runeFoe:TakeDamage(8, 0, EntityRef(runeShot), 0))
runeVolley.corsairSecondary = true
hit(otherRuneFoe, nil, runeVolley, 8)
runeVolley.corsairSecondary = nil
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 1)
hit(otherRuneFoe, 'attack', nil, 8)
hit(runeFoe, 'attack', nil, 8)
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 1)
hit(runeFoe, 'attack', nil, 8)
hit(runeFoe, 'attack', nil, 8)
step()
close(runeFoe.hits[#runeFoe.hits], p.Damage * .5, 'Press the Attack bonus')
close(hit(otherRuneFoe, 'e', nil, 8), 8 * 1.08, 'Press the Attack buff')
step(150)
close(hit(otherRuneFoe, 'e', nil, 8), 8, 'Press the Attack buff expires')

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('arcane_comet'))
runeFoe, otherRuneFoe = enemy(943, 6), enemy(944, 46)
local distant = enemy(945, 90)
hit(runeFoe, 'attack', nil, 8)
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).ready)
hit(runeFoe, 'e', nil, 8)
assert(not Runes.runeStatus(Items.missFortuneRunes(), clock).ready)
step(11)
assert(#otherRuneFoe.hits == 0)
step()
close(runeFoe.hits[#runeFoe.hits], p.Damage * .45, 'Comet primary damage')
close(otherRuneFoe.hits[1], p.Damage * .45, 'Comet hits nearby enemies')
assert(#distant.hits == 0)
fire('MC_PRE_GAME_EXIT', true)
assert(save.missFortuneRunes.rune == 'arcane_comet' and save.missFortuneRunes.cometRemaining == 228)
clock = 100
fire('MC_POST_GAME_STARTED', true)
Items.startMissFortuneRunes()
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).remaining == 228)

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('lethal_tempo'))
runeFoe = enemy(946)
hit(runeFoe, 'e', nil, 8)
close(Items.missFortuneRuneAttackSpeed(clock), 1, 'Lethal Tempo excludes E')
hit(runeFoe, 'attack', nil, 8)
close(Items.missFortuneRuneAttackSpeed(clock), 1.04, 'Lethal Tempo stack')
enter(2)
close(Items.missFortuneRuneAttackSpeed(clock), 1, 'Lethal Tempo resets on room change')

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('conqueror'))
runeFoe = enemy(946)
local rainCast = Items.newAttack(p, 'e', clock)
close(hit(runeFoe, nil, rainCast, 8), 8, 'Conqueror bonus starts after first hit')
close(hit(runeFoe, nil, rainCast, 8), 8 * 1.02, 'Conqueror applies to direct ability damage')
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 1)

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('electrocute'))
runeFoe = enemy(946)
hit(runeFoe, 'attack', nil, 8)
hit(runeFoe, 'attack', nil, 8)
hit(runeFoe, 'q', nil, 8)
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).ready)
hit(runeFoe, 'e', nil, 8)
assert(not Runes.runeStatus(Items.missFortuneRunes(), clock).ready)
step()
close(runeFoe.hits[#runeFoe.hits], p.Damage * .45, 'Electrocute requires different attack kinds')

start({})
p.corsair = true
Items.startMissFortuneRunes()
assert(Items.chooseMissFortuneRune('first_strike'))
runeFoe = enemy(947)
runeFoe.cancelled = true
hit(runeFoe, 'attack', nil, 100)
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).ready and p.coins == 0)
runeFoe.cancelled = false
assert(p:TakeDamage(1, 0, EntityRef(runeFoe), 0))
assert(not Runes.runeStatus(Items.missFortuneRunes(), clock).ready)
close(hit(runeFoe, 'attack', nil, 100), 100, 'Receiving damage first consumes readiness')
step(450)
close(hit(runeFoe, 'attack', nil, 25), 27, 'First Strike boosts the opener')
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).active and p.coins == 1)
fire('MC_PRE_GAME_EXIT', true)
assert(save.missFortuneRunes.firstStrikeActive == 90 and save.missFortuneRunes.firstStrikeRemaining == 450)
clock = 100
fire('MC_POST_GAME_STARTED', true)
Items.startMissFortuneRunes()
step()
assert(Runes.runeStatus(Items.missFortuneRunes(), clock).active)
close(hit(runeFoe, 'e', nil, 100), 108, 'First Strike boosts subsequent damage')
assert(p.coins == 3)
assert(p:TakeDamage(1, 0, EntityRef(runeFoe), 0))
close(hit(runeFoe, 'attack', nil, 100), 108, 'Damage taken does not stop active First Strike')
assert(p.coins == 3)
step(90)
close(hit(runeFoe, 'q', nil, 100), 100, 'First Strike active window ends before cooldown')
step(450)
runeFoe.HitPoints = 1
hit(runeFoe, 'q', nil, 100)
assert(p.coins == 3 and Runes.runeStatus(Items.missFortuneRunes(), clock).active,
    'The opening hit still activates First Strike when its bonus is all overkill')

-- Components share timers with their upgrades, and their bonuses apply only
-- to accepted direct hits. Repeated hits in one action must not multiply on-hit.
start({1043})
foe = enemy(1001)
local multi = Items.newAttack(p, 'attack', clock)
close(hit(foe, nil, multi), p.Damage + .3, 'Recurve first attack')
close(hit(foe, nil, multi), p.Damage, 'Recurve one bonus per action')
close(hit(foe, 'q'), p.Damage, 'Recurve excludes abilities')

start({3057, 3078})
foe = enemy(1002)
Items.onCast(p, 'q', clock)
close(hit(foe, 'attack'), p.Damage + 3, 'shared Spellblade uses stronger upgrade')
Items.onCast(p, 'q', clock)
close(hit(foe, 'attack'), p.Damage, 'shared Spellblade cooldown')
start({3057})
foe = enemy(1003)
Items.onCast(p, 'q', clock)
close(hit(foe, 'attack'), p.Damage + 1, 'Sheen Spellblade')

start({3144, 3179})
foe = enemy(1004)
close(hit(foe, 'q'), p.Damage + 1.5, 'shared bonus uses stronger upgrade')
close(hit(foe, 'q'), p.Damage, 'shared bonus cooldown')

start({3123})
foe = enemy(1005)
hit(foe, 'q')
step(30)
close(foe.hits[2], p.Damage * .075, 'component bleed')
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
step(30)
close(foe.hits[3], p.Damage * .075, 'component bleed survives save')

start({3044})
foe = enemy(1006)
hit(foe, 'q')
step()
close(p.MoveSpeed, 1.04, 'Phage movement')
step(60)
close(p.MoveSpeed, 1, 'Phage movement expires')

for _, pair in ipairs({{1006, 4}, {3801, 3}, {3083, 2}}) do
    start({pair[1]}, 2, 6)
    for i = 1, pair[2] do
        if i > 1 then enter(i) end
        clear = true
        step()
        assert(p.hp == (i == pair[2] and 3 or 2), 'shared clean-room regeneration')
    end
end

-- Rune, XP and level ranks travel with the existing item save and rewind slots.
start({})
p.yone = true
Items.startYoneProgress(false)
local progress = Items.yoneProgress()
assert(progress.level == 1 and not progress.rune)
fire('MC_POST_GLOWING_HOURGLASS_SAVE', 0)
local _, chosen = Items.chooseYoneRune('random')
assert(chosen and progress.rune == chosen and not Items.chooseYoneRune('lethal_tempo'))
clear = true; step(2)
assert(progress.xp == 25, 'a regular clear was missed or counted more than once')
enter(2); clear = true; step()
assert(progress.xp == 50)
fire('MC_POST_GLOWING_HOURGLASS_SAVE', 1)
local originalGetRoom = game.GetRoom
RoomType = {ROOM_BOSS = 5}
game.GetRoom = function()
    local current = originalGetRoom()
    current.GetType = function() return index == 3 and RoomType.ROOM_BOSS or 1 end
    return current
end
enter(3); clear = true; step()
assert(progress.level == 2 and progress.xp == 65 and Progress.upgrade(progress, 'q'), 'boss room XP or rank was lost')
fire('MC_PRE_GAME_EXIT', true)
fire('MC_POST_GAME_STARTED', true)
Items.startYoneProgress(true)
progress = Items.yoneProgress()
assert(progress.level == 2 and progress.ranks.q == 2 and progress.rune == chosen, 'continue lost Yone progression')
step()
assert(progress.xp == 65, 'continue rewarded an already cleared room')
fire('MC_PRE_GLOWING_HOURGLASS_LOAD', 1)
index, clear = 2, true
fire('MC_POST_NEW_ROOM')
fire('MC_POST_GLOWING_HOURGLASS_LOAD', 1)
Items.applyCooldownCheckpoint(clock)
progress = Items.yoneProgress()
assert(progress.level == 1 and progress.xp == 50 and progress.ranks.q == 1 and progress.rune == chosen)
step()
assert(progress.xp == 50, 'Hourglass duplicated XP for a room already cleared at the snapshot')
enter(3); clear = true; step()
assert(progress.level == 2 and progress.xp == 65, 'Hourglass prevented legitimate XP after clearing again')
fire('MC_PRE_GLOWING_HOURGLASS_LOAD', 0)
index, clear = 1, false
fire('MC_POST_NEW_ROOM')
fire('MC_POST_GLOWING_HOURGLASS_LOAD', 0)
Items.applyCooldownCheckpoint(clock)
progress = Items.yoneProgress()
assert(progress.level == 1 and progress.xp == 0 and progress.rune == chosen, 'pre-choice slot reopened the picker')
game.GetRoom = originalGetRoom
start({})
p.yone = true
Items.startYoneProgress(true)
assert(Items.yoneProgress().rune == 'conqueror', 'legacy continue did not get a usable rune')

-- Run Dr. Fetus through the real native adapter, item damage callbacks and Miss Fortune combat.
do
    start({})
    p.corsair = true
    ButtonAction = setmetatable({}, {__index = nameKey})
    InputHook = {GET_ACTION_VALUE = 0}
    WeaponType = {WEAPON_BOMBS = 5}
    function vec.__div(a, n) return Vector(a.X / n, a.Y / n) end
    function vec:Rotated(degrees)
        local r = math.rad(degrees)
        return Vector(self.X * math.cos(r) - self.Y * math.sin(r), self.X * math.sin(r) + self.Y * math.cos(r))
    end
    local combat = assert(load(missFortuneCombatSource))()
    local weapons = assert(load(nativeWeaponsSource))()
    local state = combat.new(clock)
    corsair.damageMultiplier = function(ctx, target, tick, split)
        return combat.damageMultiplier(state, ctx, target, tick, split)
    end
    corsair.acceptHit = function(ctx, tick, target, amount, baseDamage, shot)
        combat.acceptHit(state, ctx, tick, target, amount, p, game:GetRoom(), Items, baseDamage, shot)
    end
    local weapon = {fired = 0}
    function p:GetWeapon(slot) assert(slot == 1); return weapon end
    function weapon:GetWeaponType() return WeaponType.WEAPON_BOMBS end
    function weapon:GetMaxCharge() return 0 end
    function weapon:GetCharge() return 0 end
    function weapon:GetNumFired() return self.fired end
    function weapon:GetMainEntity() return nil end
    local nativeCallbacks, volleys = {}, {}
    weapons.init({AddCallback = function(_, name, cb) nativeCallbacks[name] = cb end}, game, function() return p end,
        Items, function(kind, _, ctx) volleys[#volleys + 1] = {kind = kind, ctx = ctx} end)
    Items.bindWeapons(weapons)
    local aim = Vector(100, 100)
    local function beginDoubleUp()
        assert(combat.cast(state, 'q', p, aim, clock, game:GetRoom(), Items, weapons))
        for _=1,24 do
            step()
            weapons.update(p, clock, nil, true)
            nativeCallbacks.MC_PRE_PLAYER_UPDATE(nil, p)
            if weapons.input(p, InputHook.GET_ACTION_VALUE, ButtonAction.ACTION_SHOOTRIGHT) > 0 then return end
            nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        end
        error('Double Up did not reach the native release frame')
    end
    beginDoubleUp()
    local bomb = entity(250, EntityType.ENTITY_BOMB)
    bomb.SpawnerEntity, bomb.Velocity, bomb.SpriteScale = p, Vector(9, 0), Vector(1, 1)
    function bomb:SetColor(color) self.tint = color end
    nativeCallbacks.MC_POST_FIRE_BOMB(nil, bomb)
    weapon.fired = weapon.fired + 1
    nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
    nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
    close(bomb.Velocity.X, 9 / math.sqrt(2), 'Q bomb aims at the locked diagonal')
    close(bomb.Velocity.Y, bomb.Velocity.X, 'Q bomb preserves its native travel speed')
    assert(#volleys == 1 and volleys[1].kind == 'q' and bomb.tint)

    step(45)
    local primary, splash, bounce = enemy(251, 60, 60), enemy(252, 73, 73), enemy(253, 120, 120)
    local ordinary = entity(254, EntityType.ENTITY_BOMB)
    ordinary.SpawnerEntity = p
    local explosion, baseDamage = DamageFlag.DAMAGE_EXPLOSION, 11
    assert(primary:TakeDamage(baseDamage, explosion, EntityRef(ordinary), 0))
    close(primary.hits[1], baseDamage, 'ordinary player bomb receives no Q or Love Tap')
    assert(combat.loveTapTarget(state) == nil and #state.pendingBounce == 0)
    assert(primary:TakeDamage(baseDamage, explosion, EntityRef(bomb), 0))
    assert(splash:TakeDamage(baseDamage, explosion, EntityRef(bomb), 0))
    close(primary.hits[2], baseDamage * 1.5 * 1.35, 'Q explosion receives Love Tap on the first target')
    close(splash.hits[1], baseDamage * 1.5, 'Q explosion modifies splash damage once per target')
    assert(#state.pendingBounce == 1 and combat.loveTapTarget(state) == primary)
    local bombBeam = entity(255, EntityType.ENTITY_LASER)
    bombBeam.Parent, bombBeam.SpawnerEntity, bombBeam.SpriteScale = bomb, p, Vector(1, 1)
    function bombBeam:SetColor(color) self.tint = color end
    function bombBeam:ToLaser() return self end
    function bombBeam:IsCircleLaser() return false end
    nativeCallbacks.MC_POST_LASER_INIT(nil, bombBeam)
    bombBeam.Parent = nil
    assert(primary:TakeDamage(baseDamage, DamageFlag.DAMAGE_LASER, EntityRef(p), 0, EntityRef(bombBeam)))
    close(primary.hits[3], baseDamage * 1.5, 'a detached child beam still receives the bomb Q damage')
    assert(#state.pendingBounce == 1 and combat.loveTapTarget(state) == primary,
        'the derived laser shares the bomb hit limits and does not duplicate its ricochet')
    for _ = 1, 5 do
        step()
        combat.update(state, p, clock, game:GetRoom(), Items)
    end
    assert(#bounce.hits == 1 and #splash.hits == 1 and #state.pendingBounce == 0)
    close(bounce.hits[1], baseDamage * 1.5 * 1.35, 'one ricochet to the untouched enemy')
    assert(combat.loveTapTarget(state) == bounce and #volleys == 1)

    for _, moving in ipairs({true, false}) do
        list, state, volleys = {}, combat.new(clock), {}
        weapons.reset()
        beginDoubleUp()
        local turnedBomb = entity(278, EntityType.ENTITY_BOMB)
        turnedBomb.SpawnerEntity, turnedBomb.Velocity, turnedBomb.SpriteScale = p, Vector(9, 0), Vector(1, 1)
        function turnedBomb:SetColor(color) self.tint = color end
        nativeCallbacks.MC_POST_FIRE_BOMB(nil, turnedBomb)
        weapon.fired = weapon.fired + 1
        nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
        nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        turnedBomb.Velocity = moving and Vector(0, -9) or Vector(0, 0)
        local impact = enemy(279, 60, 60)
        local actualDirection = enemy(280, 60, 20)
        local originDirection = enemy(281, 120, 120)
        assert(impact:TakeDamage(baseDamage, DamageFlag.DAMAGE_EXPLOSION, EntityRef(turnedBomb), 0))
        for _ = 1, 5 do
            step()
            combat.update(state, p, clock, game:GetRoom(), Items)
        end
        assert(#actualDirection.hits == (moving and 1 or 0)
            and #originDirection.hits == (moving and 0 or 1),
            'Q bomb ricochet follows its velocity, falling back to the origin when stationary')
        assert(#volleys == 1 and #state.pendingBounce == 0)
    end

    local blocked = {CheckLine = function() return false end}
    -- The native damage callback reports the player as Source and the beam or
    -- knife hitbox as ExtraSource. The ricochet must carry the weapon's status.
    TearFlags.TEAR_NORMAL, TearFlags.TEAR_POISON = 0, 2
    WeaponType.WEAPON_TECH_X, WeaponType.WEAPON_KNIFE, WeaponType.WEAPON_LASER = 6, 7, 8
    WeaponType.WEAPON_BRIMSTONE = 9
    KnifeVariant = {MOMS_KNIFE=0}
    for _, case in ipairs({
        {kind=EntityType.ENTITY_LASER, weapon=WeaponType.WEAPON_TECH_X, label='Tech X'},
        {kind=EntityType.ENTITY_LASER, weapon=WeaponType.WEAPON_LASER, heading=-90, label='Technology'},
        {kind=EntityType.ENTITY_LASER, weapon=WeaponType.WEAPON_BRIMSTONE, heading=-90, label='Brimstone'},
        {kind=EntityType.ENTITY_KNIFE, weapon=WeaponType.WEAPON_KNIFE, label='knife'},
        {kind=EntityType.ENTITY_KNIFE, weapon=WeaponType.WEAPON_KNIFE, heading=-90, label='returning Mom’s Knife'},
        {kind=EntityType.ENTITY_KNIFE, weapon=WeaponType.WEAPON_KNIFE, heading=-90, child=true, label='returning Mom’s Knife hitbox'},
    }) do
        list, state, volleys = {}, combat.new(clock), {}
        weapons.reset()
        local carrier = entity(260, case.kind)
        carrier.SpawnerEntity, carrier.TearFlags = p, TearFlags.TEAR_POISON
        carrier.SpriteScale, carrier.Velocity, carrier.Rotation = Vector(1, 1), Vector(9, 0), 0
        function carrier:SetColor(color) self.tint = color end
        function carrier:GetColor() return {R=1, G=1, B=1, A=1, RO=0, GO=0, BO=0} end
        function carrier:ToKnife() return self end
        function carrier:ToLaser() return self end
        function carrier:IsCircleLaser() return case.kind == EntityType.ENTITY_LASER and not case.heading end
        local actualSource = carrier
        if case.kind == EntityType.ENTITY_KNIFE then
            if case.heading then
                carrier.Variant = KnifeVariant.MOMS_KNIFE
                function carrier:GetKnifeVelocity() return -5 end
            end
            if not case.heading or case.child then
                actualSource = entity(261, case.kind)
                actualSource.SpawnerEntity = p
                function actualSource:ToKnife() return self end
                function actualSource:GetHitboxParentKnife() return carrier end
            end
        end
        function weapon:GetWeaponType() return case.weapon end
        function weapon:GetMainEntity() return carrier end
        beginDoubleUp()
        if case.weapon == WeaponType.WEAPON_BRIMSTONE then
            nativeCallbacks.MC_POST_FIRE_BRIMSTONE(nil, carrier)
        elseif case.kind == EntityType.ENTITY_LASER then
            nativeCallbacks.MC_POST_FIRE_TECH_X_LASER(nil, carrier)
        end
        weapon.fired = weapon.fired + 1
        nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
        nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        if case.heading then carrier.AngleDegrees, carrier.Rotation = case.heading, case.heading+180 end
        function weapon:GetWeaponType() return WeaponType.WEAPON_BOMBS end
        function weapon:GetMainEntity() return nil end
        primary = enemy(262, 60, 60)
        bounce = case.heading and enemy(263, 60, 20) or enemy(263, 120, 120)
        local wrongDirection = case.child and enemy(264, 120, 120)
        function bounce:ToNPC() return self end
        function bounce:ApplyTearflagEffects(_, flags, owner, damage)
            assert(owner == p and damage == baseDamage)
            self.appliedFlags = flags
        end
        local attackFlag = case.kind == EntityType.ENTITY_LASER and DamageFlag.DAMAGE_LASER or 0
        assert(primary:TakeDamage(baseDamage, attackFlag, EntityRef(p), 0, EntityRef(actualSource)))
        assert(#volleys == 1 and #state.pendingBounce == 1 and not bounce.appliedFlags)
        if case.weapon == WeaponType.WEAPON_BRIMSTONE then
            assert(carrier.tint and carrier.TearFlags == TearFlags.TEAR_POISON)
            close(primary.hits[1], baseDamage * 1.5 * 1.35, 'Brimstone Q applies Love Tap on the first beam hit')
            step()
            assert(primary:TakeDamage(baseDamage, attackFlag, EntityRef(p), 0, EntityRef(actualSource)))
            close(primary.hits[2], baseDamage * 1.5, 'later Brimstone ticks retain Q damage')
            assert(#state.pendingBounce == 1, 'later Brimstone ticks cannot queue another ricochet')
        end
        for _ = 1, 5 do
            step()
            combat.update(state, p, clock, case.kind == EntityType.ENTITY_LASER and blocked or game:GetRoom(), Items)
        end
        assert(#bounce.hits == 1, case.label .. ' Q should ricochet once')
        assert(not wrongDirection or #wrongDirection.hits == 0, case.label .. ' Q follows the parent knife direction')
        assert(bounce.appliedFlags == TearFlags.TEAR_POISON, case.label .. ' Q ricochet lost poison')
    end

    WeaponType.WEAPON_TEARS = 1
    local function newNativeTear(seed, variant, flags, velocity)
        local projectile = entity(seed, EntityType.ENTITY_TEAR)
        projectile.SpawnerEntity = p
        projectile.Variant, projectile.TearFlags = variant, flags
        projectile.Velocity, projectile.Scale = velocity, 1
        function projectile:ToTear() return self end
        function projectile:SetColor(color) self.tint = color end
        return projectile
    end
    for _, spectral in ipairs({false, true}) do
        list, state, volleys = {}, combat.new(clock), {}
        weapons.reset()
        function weapon:GetWeaponType() return WeaponType.WEAPON_TEARS end
        beginDoubleUp()
        local flags = spectral and TearFlags.TEAR_SPECTRAL or TearFlags.TEAR_NORMAL
        local tear = newNativeTear(265, TearVariant.BLUE, flags, Vector(9, 0))
        nativeCallbacks.MC_POST_FIRE_TEAR(nil, tear)
        weapon.fired = weapon.fired + 1
        nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
        nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        function weapon:GetWeaponType() return spectral and WeaponType.WEAPON_KNIFE or WeaponType.WEAPON_TECH_X end
        primary, bounce = enemy(266, 60, 60), enemy(267, 120, 120)
        assert(primary:TakeDamage(baseDamage, 0, EntityRef(tear), 0))
        assert(#state.pendingBounce == 1)
        for _ = 1, 5 do
            step()
            combat.update(state, p, clock, blocked, Items)
        end
        assert(#bounce.hits == (spectral and 1 or 0), 'Q bounce must use tear spectral flags instead of the current weapon')
    end

    for _, case in ipairs({{health=27}, {health=27, unrelatedKill=true}, {health=12, buffer=true, critical=true}}) do
        list, state, volleys = {}, combat.new(clock), {}
        weapons.reset()
        function weapon:GetWeaponType() return WeaponType.WEAPON_TEARS end
        beginDoubleUp()
        local rebound = newNativeTear(268, TearVariant.BLUE, TearFlags.TEAR_POISON, Vector(9, 0))
        nativeCallbacks.MC_POST_FIRE_TEAR(nil, rebound)
        weapon.fired = weapon.fired + 1
        nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
        nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        rebound.Velocity = Vector(0, -9) -- The native tear has turned, e.g. with My Reflection.
        primary, bounce = enemy(269, 60, 60), enemy(276, 60, 20)
        local wrongDirection = enemy(277, 120, 120)
        primary.HitPoints, primary.bufferDamage = case.health, case.buffer
        assert(primary:TakeDamage(baseDamage, 0, EntityRef(rebound), 0))
        if case.unrelatedKill then primary.HitPoints = 0 end
        for _ = 1, 5 do
            step()
            combat.update(state, p, clock, game:GetRoom(), Items)
        end
        assert(#bounce.hits == 1 and #wrongDirection.hits == 0, 'a turned tear bounces in its actual impact direction')
        close(bounce.hits[1], baseDamage * 1.5 * 1.35 * (case.critical and 1.25 or 1),
            'only a primary Q kill guarantees a critical bounce')
    end

    -- Exercise C Section through the native tear path. REPENTOGON reports
    -- Cricket's Body with MC_POST_FIRE_SPLIT_TEAR(child, source, QUAD).
    weapons.reset()
    start({3036, 1043}) -- Lord Dominik's adds passive damage. Recurve Bow adds Q on-hit damage.
    random = .99
    p.corsair = true
    state, volleys = combat.new(clock), {}
    TearVariant.FETUS = 50
    SplitTearType = {QUAD = 1}
    TearFlags.TEAR_QUADSPLIT = 1 << 18
    TearFlags.TEAR_FETUS = 1 << 60 -- Stand-in for native BitSet128 bit 114.
    function weapon:GetWeaponType() return WeaponType.WEAPON_TEARS end
    function p:GetWeapon(slot) assert(slot == 1); return weapon end
    assert(combat.cast(state, 'w', p, nil, clock, game:GetRoom(), Items, weapons))
    local wReady = state.ready.w
    beginDoubleUp()
    local fetusFlags = TearFlags.TEAR_FETUS | TearFlags.TEAR_QUADSPLIT | TearFlags.TEAR_POISON
    local fetus = newNativeTear(270, TearVariant.FETUS, fetusFlags, Vector(9, 0))
    nativeCallbacks.MC_POST_FIRE_TEAR(nil, fetus)
    local cricket = newNativeTear(271, TearVariant.BLUE, TearFlags.TEAR_POISON, Vector(0, -4))
    -- The split callback supplies ancestry independently of the child's
    -- SpawnerEntity, which may resolve directly to the player later.
    nativeCallbacks.MC_POST_FIRE_SPLIT_TEAR(nil, cricket, fetus, SplitTearType.QUAD)
    nativeCallbacks.MC_POST_FIRE_TEAR(nil, cricket)
    weapon.fired = weapon.fired + 1
    nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
    nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
    assert(fetus.Variant == TearVariant.FETUS and fetus.TearFlags == fetusFlags and fetus.tint)
    close(fetus.Velocity.X, fetus.Velocity.Y, 'fetus follows the locked diagonal')
    assert(cricket.TearFlags == TearFlags.TEAR_POISON and cricket.Velocity.X == 0 and cricket.Velocity.Y == -4,
        "Cricket's Body keeps its native status flag and split direction")

    primary, bounce = enemy(272, 60, 60), enemy(273, 120, 120)
    local splitTarget = enemy(274, 80, 80)
    local splitDamage = 5
    assert(splitTarget:TakeDamage(splitDamage, 0, EntityRef(cricket), 0))
    assert(#state.pendingBounce == 0 and combat.loveTapTarget(state) == nil and state.ready.w == wReady,
        "Cricket's Body child must leave Double Up and Love Tap available to the fetus")
    close(splitTarget.hits[1], splitDamage * 1.5 * 1.15, "Cricket's Body retains Q and passive item damage")
    assert(primary:TakeDamage(baseDamage, 0, EntityRef(fetus), 0))
    close(primary.hits[1], baseDamage * 1.5 * 1.35 * 1.15 + .3,
        'the fetus retains the primary Double Up and purchased on-hit damage')
    assert(#state.pendingBounce == 1 and state.pendingBounce[1].point.X == primary.Position.X)
    assert(combat.loveTapTarget(state) == primary and state.ready.w == wReady - 60)

    for _ = 1, 5 do
        step()
        combat.update(state, p, clock, game:GetRoom(), Items)
    end
    assert(#bounce.hits == 1 and #splitTarget.hits == 1 and #state.pendingBounce == 0,
        "Double Up skips the nearer target already hit by Cricket's Body")
    assert(#volleys == 1 and volleys[1].kind == 'q')
    local lateTarget = enemy(275, 150, 150)
    assert(lateTarget:TakeDamage(splitDamage, 0, EntityRef(cricket), 0))
    close(lateTarget.hits[1], splitDamage * 1.5 * 1.15, 'late split keeps Q and passive item damage')
    assert(#state.pendingBounce == 0 and combat.loveTapTarget(state) == bounce,
        "late Cricket's Body hits widen neither Double Up nor Love Tap")

    -- Ordinary tears use the same split ancestry as C Section. Exercise both
    -- callback orders and confirm a child cannot spend the parent's effects.
    for _, kind in ipairs({'aa', 'q'}) do
        weapons.reset()
        start({3036, 1043})
        p.corsair, random = true, .99
        state, volleys = combat.new(clock), {}
        function p:GetWeapon(slot) assert(slot == 1); return weapon end
        Items.startMissFortuneRunes()
        assert(Items.chooseMissFortuneRune('conqueror'))
        if kind == 'q' then
            beginDoubleUp()
        else
            weapons.update(p, clock, Vector(1, 1), true)
            nativeCallbacks.MC_PRE_PLAYER_UPDATE(nil, p)
        end
        local flags = TearFlags.TEAR_QUADSPLIT | TearFlags.TEAR_POISON
        local parent = newNativeTear(282, TearVariant.BLUE, flags, Vector(9, 0))
        local child = newNativeTear(283, TearVariant.BLUE, TearFlags.TEAR_POISON, Vector(0, -4))
        nativeCallbacks.MC_POST_FIRE_TEAR(nil, parent)
        if kind == 'aa' then
            nativeCallbacks.MC_POST_FIRE_TEAR(nil, child)
            nativeCallbacks.MC_POST_FIRE_SPLIT_TEAR(nil, child, parent, SplitTearType.QUAD)
        else
            nativeCallbacks.MC_POST_FIRE_SPLIT_TEAR(nil, child, parent, SplitTearType.QUAD)
            nativeCallbacks.MC_POST_FIRE_TEAR(nil, child)
        end
        weapon.fired = weapon.fired + 1
        nativeCallbacks.MC_POST_TRIGGER_WEAPON_FIRED(nil, Vector(1, 0), 1, p, weapon)
        nativeCallbacks.MC_POST_PLAYER_UPDATE(nil, p)
        assert(parent.TearFlags == flags and child.TearFlags == TearFlags.TEAR_POISON
            and child.Velocity.X == 0 and child.Velocity.Y == -4,
            kind .. ' Cricket split preserves native flags and direction')
        local splitTarget = enemy(284, 80, 80)
        local primary = enemy(285, 60, 60)
        local bounce = enemy(286, 120, 120)
        assert(splitTarget:TakeDamage(5, 0, EntityRef(child), 0))
        close(splitTarget.hits[1], 5 * (kind == 'q' and 1.5 or 1) * 1.15,
            kind .. ' split keeps passive damage without Recurve on-hit')
        assert(combat.loveTapTarget(state) == nil and #state.pendingBounce == 0
            and Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 0,
            kind .. ' split must not consume Love Tap, rune, or ricochet')
        assert(primary:TakeDamage(baseDamage, 0, EntityRef(parent), 0))
        close(primary.hits[1], baseDamage * (kind == 'q' and 1.5 or 1) * 1.35 * 1.15 + .3,
            kind .. ' parent retains Recurve on-hit')
        assert(combat.loveTapTarget(state) == primary
            and Runes.runeStatus(Items.missFortuneRunes(), clock).stacks == 1
            and #state.pendingBounce == (kind == 'q' and 1 or 0),
            kind .. ' parent retains Love Tap, rune, and Q ricochet')
        for _ = 1, 5 do
            step()
            combat.update(state, p, clock, game:GetRoom(), Items)
        end
        assert(#bounce.hits == (kind == 'q' and 1 or 0) and #state.pendingBounce == 0
            and #volleys == 1 and volleys[1].kind == kind,
            kind .. ' produces only its expected ricochet')
    end
end

print('Passed item stat checks, component effects, native weapon damage and Style, combat scenarios, and persistence.')
''')
