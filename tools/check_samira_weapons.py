"""Exercise the native weapon adapter against Isaac-style input and fire callbacks."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
lua.globals().weaponSource = (ROOT / 'src/samira-testroom/mod/samira_weapons.lua').read_text(encoding='utf8')
lua.execute(r'''
local function names()
    return setmetatable({}, {__index = function(_, name) return name end})
end
ButtonAction, InputHook, EntityType, ModCallbacks = names(), names(), names(), names()
FamiliarVariant = {INCUBUS = 23, TWISTED_BABY = 238}
WeaponType = {WEAPON_LUDOVICO_TECHNIQUE = 'ludo', WEAPON_ROCKETS = 'rockets', WEAPON_BRIMSTONE = 'brimstone',
    WEAPON_LASER = 'laser', WEAPON_TECH_X = 'techx', WEAPON_BONE = 'bone', WEAPON_SPIRIT_SWORD = 'sword'}
EffectVariant = {TARGET = 30, ROCKET = 31, SMALL_ROCKET = 118}
local vec = {}
vec.__index = vec
function Vector(x, y) return setmetatable({X=x,Y=y}, vec) end
function vec:Length() return math.sqrt(self.X * self.X + self.Y * self.Y) end
function vec:Normalized() return self * (1 / self:Length()) end
function vec:GetAngleDegrees() return math.deg(math.atan(self.Y, self.X)) end
function vec:Rotated(degrees)
    local radians = math.rad(degrees)
    return Vector(self.X * math.cos(radians) - self.Y * math.sin(radians),
        self.X * math.sin(radians) + self.Y * math.cos(radians))
end
function vec.__add(a, b) return Vector(a.X + b.X, a.Y + b.Y) end
function vec.__mul(a, b) return Vector(a.X * b, a.Y * b) end
function vec.__sub(a, b) return Vector(a.X - b.X, a.Y - b.Y) end
function Color(...) return {...} end
function GetPtrHash(entity) return entity end
local ticks, attacks, consoleLines, announced, p = 0, 0, {}, {}, {Type = EntityType.ENTITY_PLAYER, MaxFireDelay = 4}
local callbacks = {}
local weapon = {id = 'tears', charge = 0, max = 0, fired = 0}
function p:GetWeapon(slot) assert(slot == 1); return weapon end
function weapon:GetCharge() return self.charge end
function weapon:GetMaxCharge() return self.max end
function weapon:SetCharge(charge) self.charge = charge end
function weapon:GetNumFired() return self.fired end
function weapon:GetMainEntity() return self.entity end
function weapon:GetWeaponType() return self.id end
function weapon:GetDirection() return self.direction or Vector(1, 0) end
function weapon:GetOwner() return p end
function weapon:IsAxisAligned() return self.id == 'brimstone' end
local function object(kind, owner)
    local entity = {Type = EntityType['ENTITY_' .. kind], SpawnerEntity = owner, Scale = 1,
        SpriteScale = Vector(1, 1), data = {}}
    function entity:GetData() return self.data end
    function entity:Exists() return true end
    function entity:ToTear() return self end
    function entity:ToLaser() return self end
    function entity:ToKnife() return self end
    function entity:ToFamiliar() return self end
    function entity:IsFlying() return self.flying == true end
    function entity:IsCircleLaser() return self.ring == true end
    function entity:GetColor() return self.tint or 'native' end
    function entity:SetColor(color, ...) self.tint = color end
    return entity
end
local function event(name, ...)
    return callbacks[name](nil, ...)
end
Isaac = {ConsoleOutput = function(message) consoleLines[#consoleLines + 1] = message end}
local Weapons = assert(load(weaponSource))()
Weapons.init({AddCallback = function(_, name, cb) assert(not callbacks[name]); callbacks[name] = cb end},
    {GetFrameCount = function() return ticks end}, function() return p end, {
        newAttack = function(player, kind, clock)
            attacks = attacks + 1
            return {player = player, kind = kind, clock = clock, id = attacks}
        end,
        tagTear = function(player, entity, context)
            assert(player == p)
            entity.data.SamiraItemContext = context
        end,
    }, function(kind, heading, ctx)
        announced[#announced + 1] = {kind = kind, heading = heading, ctx = ctx}
    end)
local function reset(id, max)
    Weapons.reset()
    ticks, attacks, announced, consoleLines = 0, 0, {}, {}
    weapon.id, weapon.max, weapon.charge, weapon.fired, weapon.entity = id, max, 0, 0, nil
end
local aim = Vector(3, -4)
local function begin(aa, enabled, point)
    Weapons.update(p, ticks, aa, enabled ~= false, point)
    ticks = ticks + 1
    event('MC_PRE_PLAYER_UPDATE', p)
end
local function input(mode, direction)
    return Weapons.input(p, InputHook[mode], ButtonAction['ACTION_SHOOT' .. direction])
end
local function trigger(owner, nativeHeading)
    weapon.fired = weapon.fired + 1
    event('MC_POST_TRIGGER_WEAPON_FIRED', nativeHeading or aim:Normalized(), 1, owner or p, weapon)
end
local function endFrame() event('MC_POST_PLAYER_UPDATE', p) end
local function ref(entity) return {Entity = entity} end

reset('tears', 0)
begin(aim)
assert(math.abs(input('GET_ACTION_VALUE', 'RIGHT') - .6) < 1e-8 and input('GET_ACTION_VALUE', 'UP') == .8)
assert(input('GET_ACTION_VALUE', 'LEFT') == 0 and input('IS_ACTION_TRIGGERED', 'RIGHT'))
assert(attacks == 0 and #announced == 0, 'input alone is not an attack')
local first, second = object('TEAR', p), object('TEAR', p)
event('MC_POST_FIRE_TEAR', first)
trigger()
event('MC_POST_FIRE_TEAR', second)
endFrame()
assert(attacks == 1 and #announced == 1 and announced[1].kind == 'aa')
assert(Weapons.context(p, ref(first)) == Weapons.context(p, ref(second)))
assert(first.Scale == 1 and not first.tint)
local fam = object('FAMILIAR', p)
fam.Player, fam.Variant = p, FamiliarVariant.INCUBUS
local child = object('TEAR', fam)
event('MC_POST_FAMILIAR_FIRE_PROJECTILE', child)
assert(Weapons.context(p, ref(child)) == announced[1].ctx)

begin(aim)
assert(input('IS_ACTION_PRESSED', 'RIGHT') and not input('IS_ACTION_TRIGGERED', 'RIGHT'))
endFrame()

assert(Weapons.requestQ(p, aim, ticks) and not Weapons.requestQ(p, Vector(0, 1), ticks))
begin(Vector(-1, 0))
assert(math.abs(input('GET_ACTION_VALUE', 'RIGHT') - .6) < 1e-8, 'Q should preserve its aim')
local enhanced = object('TEAR', p)
event('MC_POST_FIRE_TEAR', enhanced)
trigger()
endFrame()
local ctx = Weapons.context(p, ref(enhanced))
assert(ctx.kind == 'q' and ctx.damageMultiplier == 1.5 and enhanced.Scale == 1.18 and enhanced.tint)
assert(#announced == 2)
local split = object('TEAR', enhanced)
event('MC_POST_FIRE_SPLIT_TEAR', split, enhanced)
assert(Weapons.context(p, ref(split)) == ctx and split.Scale == 1.18)
event('MC_POST_NEW_ROOM')
assert(not Weapons.context(p, ref(enhanced)))

reset('brimstone', 3)
assert(Weapons.requestQ(p, aim, ticks))
for i=1,3 do
    begin(nil)
    assert(input('IS_ACTION_PRESSED', 'RIGHT'))
    weapon.charge = i
    endFrame()
    assert(attacks == 0)
end
begin(nil)
assert(input('GET_ACTION_VALUE', 'RIGHT') == 0 and not input('IS_ACTION_PRESSED', 'RIGHT'))
local laser = object('LASER', p)
weapon.entity = laser
event('MC_POST_FIRE_BRIMSTONE', laser)
weapon.charge = 0
trigger()
endFrame()
local brim, ranged, entityType = Weapons.context(p, ref(p), ref(laser))
assert(brim.kind == 'q' and ranged and entityType == EntityType.ENTITY_LASER and #announced == 1)
for _ = 1,10 do assert(Weapons.context(p, ref(p), ref(laser)) == brim) end

for repeatIndex=1,2 do
    for i=1,3 do
        begin(aim)
        assert(input('IS_ACTION_PRESSED', 'RIGHT'))
        weapon.charge = i
        endFrame()
    end
    begin(aim)
    assert(input('GET_ACTION_VALUE', 'RIGHT') == 0)
    weapon.entity = object('LASER', p)
    event('MC_POST_FIRE_BRIMSTONE', weapon.entity)
    weapon.charge = 0
    trigger()
    endFrame()
    assert(announced[repeatIndex + 1].kind == 'aa')
end
assert(attacks == 3)
begin(aim)
weapon.charge = 2
endFrame()
assert(Weapons.requestQ(p, aim, ticks))
begin(nil, false)
assert(weapon.charge == 0 and input('GET_ACTION_VALUE', 'RIGHT') == 0)
event('MC_EXECUTE_CMD', 'samiraweapon')
assert(consoleLines[1]:find('pending Q false'))

reset('knife', 2)
assert(Weapons.requestQ(p, aim, ticks))
begin(nil)
weapon.charge = 2
endFrame()
begin(nil)
local knife = object('KNIFE', p)
knife.flying = true
weapon.entity = knife
trigger()
endFrame()
ctx, ranged = Weapons.context(p, ref(p), ref(knife))
assert(ctx.kind == 'q' and not ranged and knife.tint and knife.SpriteScale.X == 1.12)
ticks = ticks + 3
knife.flying = false
event('MC_POST_KNIFE_UPDATE', knife)
assert(not Weapons.context(p, ref(knife)) and knife.SpriteScale.X == 1)

reset('fetus', 0)
assert(Weapons.requestQ(p, aim, ticks))
begin(nil)
local bomb = object('BOMB', p)
event('MC_POST_FIRE_BOMB', bomb)
trigger()
endFrame()
assert(Weapons.context(p, ref(bomb)).damageMultiplier == 1.5 and bomb.tint)
local ordinaryBomb = object('BOMB', p)
assert(not Weapons.context(p, ref(ordinaryBomb)))

reset('rockets', 0)
assert(Weapons.requestQ(p, aim, ticks))
begin(nil)
local marker = object('EFFECT', p)
marker.Variant = EffectVariant.TARGET
event('MC_POST_EFFECT_INIT', marker)
assert(not Weapons.context(p, ref(marker)), 'the marker alone must not count as firing')
trigger()
endFrame()
local rocketCtx = Weapons.context(p, ref(marker))
assert(rocketCtx.kind == 'q')
ticks = ticks + 25
local rocket = object('EFFECT', p)
rocket.Variant, rocket.Parent = EffectVariant.ROCKET, marker
event('MC_POST_EFFECT_INIT', rocket)
local explosion = object('BOMB', rocket)
assert(Weapons.context(p, ref(rocket)) == rocketCtx and Weapons.context(p, ref(explosion)) == rocketCtx)
local unrelatedRocket = object('EFFECT', p)
unrelatedRocket.Variant = EffectVariant.ROCKET
event('MC_POST_EFFECT_INIT', unrelatedRocket)
assert(not Weapons.context(p, ref(unrelatedRocket)), 'shared player spawner must not link unrelated rockets')

reset('ludo', 0)
assert(not Weapons.requestQ(p, aim, ticks), 'no orb means no charge or Q cooldown')
local orb = object('TEAR', p)
weapon.entity = orb
local baseline = Weapons.context(p, ref(orb))
assert(baseline.kind == 'aa' and baseline.damageMultiplier == 1)
assert(Weapons.context(p, ref(orb)) == baseline)
assert(Weapons.requestQ(p, aim, ticks))
begin(nil)
endFrame()
local pulse = Weapons.context(p, ref(orb))
assert(pulse.persistentPulse and pulse.kind == 'q' and pulse.damageMultiplier == 1.5 and orb.Scale == 1.18)
assert(not Weapons.requestQ(p, aim, ticks), 'a pending pulse cannot be stacked')
assert(Weapons.context(p, ref(orb)) == pulse, 'unaccepted hit attempts do not spend the pulse')
pulse.accepted = true
assert(Weapons.context(p, ref(orb)) == baseline and orb.Scale == 1 and orb.tint == 'native')
ticks = ticks + 5
local nextPulse = Weapons.context(p, ref(orb))
assert(nextPulse.kind == 'aa' and nextPulse ~= baseline and Weapons.context(p, ref(orb)) == nextPulse)

orb.Position = Vector(30, 20)
begin(Vector(-1, 0), true, Vector(30, 40))
assert(input('GET_ACTION_VALUE', 'RIGHT') == 0 and input('GET_ACTION_VALUE', 'DOWN') == 1)
endFrame()
orb.Position = Vector(30, 37)
begin(Vector(-1, 0), true, Vector(30, 40))
assert(input('GET_ACTION_VALUE', 'LEFT') == 0 and input('GET_ACTION_VALUE', 'DOWN') == 0)
endFrame()

reset('rockets', 4)
marker = object('EFFECT', p)
marker.Variant, marker.Position = EffectVariant.TARGET, Vector(30, 20)
weapon.entity = marker
assert(Weapons.requestQ(p, Vector(-1, 0), ticks, Vector(30, 40)))
weapon.charge = 4
begin(Vector(1, 0), true, Vector(90, 20))
assert(input('GET_ACTION_VALUE', 'RIGHT') == 0 and input('GET_ACTION_VALUE', 'DOWN') == 1,
    'Epic Fetus must keep steering toward the locked Q point, even with full charge')
endFrame()
marker.Position = Vector(30, 37)
begin(Vector(1, 0), true, Vector(90, 20))
assert(input('GET_ACTION_VALUE', 'RIGHT') == 0 and input('GET_ACTION_VALUE', 'DOWN') == 0)
trigger()
endFrame()
assert(#announced == 1 and announced[1].kind == 'q' and Weapons.context(p, ref(marker)) == announced[1].ctx)

reset('tears', 0)
p.TearRange = 375
assert(Weapons.attackRange(p, 165) == 300 and not Weapons.passesGrid(p))
TearFlags, p.TearFlags = {TEAR_SPECTRAL = 8, TEAR_LUDOVICO = 16}, 8
assert(Weapons.passesGrid(p))
p.TearFlags = 0
for _, kind in ipairs({'brimstone', 'laser', 'rockets'}) do
    weapon.id = kind
    assert(Weapons.attackRange(p, 165) == 800 and Weapons.passesGrid(p))
end
weapon.id = 'sword'
assert(Weapons.attackRange(p, 165) == 48 and not Weapons.passesGrid(p))

local function near(actual, expected)
    assert(math.abs(actual - expected) < 1e-6, ('got %.6f, expected %.6f'):format(actual, expected))
end

-- The fake engine rounds to right, then creates two tears at fixed spread
-- angles. Verify trajectories, not just the values we handed to input hooks.
reset('tears', 0)
local diagonal = Vector(1, 1)
function p:GetTearMovementInheritance() return Vector(1, -1) end
begin(diagonal)
local lead, follow = object('TEAR', p), object('TEAR', p)
lead.Velocity = Vector(10, 0):Rotated(-12) + Vector(1, -1)
lead.ContinueVelocity = Vector(10, 0):Rotated(-12)
follow.Velocity = Vector(10, 0):Rotated(12) + Vector(1, -1)
event('MC_POST_FIRE_TEAR', lead)
trigger(nil, Vector(1, 0))
event('MC_POST_FIRE_TEAR', follow)
endFrame()
near((lead.Velocity - Vector(1, -1)):GetAngleDegrees(), 33)
near((follow.Velocity - Vector(1, -1)):GetAngleDegrees(), 57)
near((lead.Velocity - Vector(1, -1)):Length(), 10)
near(lead.ContinueVelocity:GetAngleDegrees(), 33)
near(announced[1].heading:GetAngleDegrees(), 45)
local lateral = object('TEAR', lead)
lateral.Velocity = Vector(0, -4)
event('MC_POST_FIRE_SPLIT_TEAR', lateral, lead)
near(lateral.Velocity:GetAngleDegrees(), -90)

-- Exercise cardinal (zero rotation) and diagonal (rotated) native volleys.
-- Flight time is set by the native spawn's own vertical parameters.
for _,angle in ipairs({0,45,90,135,180,225,270,315}) do
    local aimed = Vector(1,0):Rotated(angle)
    local native = Vector(1,0):Rotated(math.floor((angle+45)/90)*90)
    local ranges = {}
    for _,kind in ipairs({'aa','q'}) do
        reset('tears',0)
        if kind=='q' then assert(Weapons.requestQ(p,aimed,ticks)) end
        begin(aimed)
        local tear = object('TEAR',p)
        tear.Velocity = native*9 + p:GetTearMovementInheritance(native)
        tear.ContinueVelocity = native*9
        tear.Height, tear.FallingSpeed, tear.FallingAcceleration = -22,-1,.25
        weapon.entity = tear -- The fire callback and weapon main entity report the same tear.
        event('MC_POST_FIRE_TEAR',tear)
        trigger(nil,native)
        endFrame()
        local intrinsic = tear.Velocity - p:GetTearMovementInheritance(aimed)
        near((intrinsic - aimed*(kind=='q' and 12 or 9)):Length(),0)
        near((tear.ContinueVelocity - intrinsic):Length(),0)
        local height,fallSpeed,ticksInAir = tear.Height,tear.FallingSpeed,0
        while height < 0 do
            height = height + fallSpeed
            fallSpeed = fallSpeed + tear.FallingAcceleration
            ticksInAir = ticksInAir + 1
        end
        ranges[kind] = tear.Velocity:Length()*ticksInAir
    end
    assert(ranges.q > ranges.aa, 'ranged Q fell short of an AA at angle '..angle)
end

reset('laser', 0)
assert(Weapons.requestQ(p, Vector(-1, 1), ticks))
begin(Vector(1, 0))
local beam = object('LASER', p)
beam.AngleDegrees, beam.StartAngleDegrees, beam.LastAngleDegrees = 190, 188, 190
event('MC_POST_FIRE_TECH_LASER', beam)
trigger(nil, Vector(-1, 0))
endFrame()
near(beam.AngleDegrees, 145)
near(beam.StartAngleDegrees, 143)
assert(Weapons.context(p, ref(p), ref(beam)).kind == 'q')

reset('knife', 0)
begin(Vector(-1, 1))
knife = object('KNIFE', p)
knife.Rotation = 90
weapon.entity = knife
trigger(nil, Vector(0, 1))
endFrame()
near(knife.Rotation, 135)

reset('fetus', 0)
assert(Weapons.requestQ(p, Vector(-1,-1), ticks))
begin(Vector(-1, -1))
local chargedBomb = object('BOMB', p)
chargedBomb.Velocity = Vector(-8, 0)
event('MC_POST_FIRE_BOMB', chargedBomb)
trigger(nil, Vector(-1, 0))
endFrame()
near(chargedBomb.Velocity:GetAngleDegrees(), -135)
near(chargedBomb.Velocity:Length(), 8)

reset('techx', 0)
assert(Weapons.requestQ(p, diagonal, ticks))
begin(diagonal)
local ring = object('LASER', p)
ring.ring, ring.Velocity = true, Vector(8, 0)
event('MC_POST_FIRE_TECH_X_LASER', ring)
trigger(nil, Vector(1, 0))
endFrame()
near(ring.Velocity:GetAngleDegrees(), 45)
near(ring.Velocity:Length(), 8)

print('Passed native charge, grouped volleys, cardinal-to-cursor rotation, rockets and Ludovico.')
''')
