"""Check native Yone tear handoff, retained effects and its damage budget."""

from pathlib import Path
from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'src/samira-testroom/mod/yone_artifacts.lua'


def main():
    lua = LuaRuntime()
    lua.globals().source = MODULE.read_text(encoding='utf-8')
    lua.globals().weaponsSource = MODULE.with_name('yone_artifact_weapons.lua').read_text(encoding='utf-8')
    lua.execute(r"""
function include(name)
    assert(name == 'yone_artifact_weapons')
    return assert(load(weaponsSource))()
end
local a = assert(load(source))()
CollectibleType = {COLLECTIBLE_20_20=1, COLLECTIBLE_INNER_EYE=2, COLLECTIBLE_MUTANT_SPIDER=3,
    COLLECTIBLE_MOMS_KNIFE=4, COLLECTIBLE_EYE_SORE=5, COLLECTIBLE_CRICKETS_BODY=6,
    COLLECTIBLE_BLOOD_CLOT=7}
TrinketType = {TRINKET_RAINBOW_WORM=64}
TearVariant = {BLUE=0, BLOOD=1, TOOTH=2}
TearFlags = {TEAR_NORMAL=0, TEAR_WIGGLE=1, TEAR_PULSE=2, TEAR_SPIRAL=4, TEAR_SQUARE=8, TEAR_FLAT=16,
    TEAR_BIG_SPIRAL=32, TEAR_HOMING=64, TEAR_QUADSPLIT=128, TEAR_POISON=256, TEAR_SLOW=512,
    TEAR_UNRECOGNIZED=1<<55}
WeaponType = {WEAPON_TEARS=1, WEAPON_BRIMSTONE=2, WEAPON_LASER=3, WEAPON_TECH_X=9}
LaserOffset = {LASER_TECH1_OFFSET=0}
ModCallbacks = {MC_POST_TEAR_UPDATE=1, MC_POST_LASER_UPDATE=2, MC_POST_FIRE_SPLIT_TEAR=3}
local methods = {}
local meta = {__index=methods}
function Vector(x,y) return setmetatable({X=x,Y=y}, meta) end
function Color(...)
    local color = {components={...}}
    function color:SetColorize(...) self.colorize={...} end
    return color
end
function meta.__mul(v, n) return Vector(v.X*n,v.Y*n) end
function methods:Rotated(d)
    local c,s = math.cos(math.rad(d)), math.sin(math.rad(d))
    return Vector(self.X*c-self.Y*s, self.X*s+self.Y*c)
end
function methods:Distance(other) return math.sqrt((self.X-other.X)^2+(self.Y-other.Y)^2) end
local origin, facing = Vector(1, 1), Vector(1, 0)
local p = {Damage=4, TearRange=260, ShotSpeed=1, owned={}, InitSeed=0,
    flags=0, variant=0, fired={}, rainbow=0, shots=1, weapon=1}
local defaultLaserColor = Color(1, 0, 0, 1)
p.laserColor = defaultLaserColor
function p:GetLaserColor() return self.laserColor end
function p:SetLaserColor(color) self.laserColor = color end
function p:HasCollectible(id) return self.owned[id] == true end
function p:GetTrinketMultiplier(id) assert(id==64); return self.rainbow end
function p:GetMultiShotParams(kind)
    assert(kind == 1)
    return {
        GetNumTears=function() return self.shots end,
        GetSpreadAngle=function() return 10 end,
        IsCrossEyed=function() return false end,
        IsShootingBackwards=function() return self.backwards end,
        IsShootingSideways=function() return self.sideways end,
        GetNumRandomDirTears=function() return self.randomShots or 0 end,
    }
end
function p:GetCollectibleRNG(id)
    assert(id == CollectibleType.COLLECTIBLE_EYE_SORE)
    return {RandomInt=function(_,limit) assert(limit==360); return 140 end}
end
function p:GetWeapon(slot)
    assert(slot==1)
    return {GetWeaponType=function() return self.weapon end}
end
local function entity()
    local e = {data={}}
    function e:GetData() return self.data end
    function e:Exists() return not self.removed end
    function e:Remove() self.removed = true end
    function e:Die() self.died = true end
    function e:SetColor(color, frames, priority, fade, share)
        assert(frames > 0 and priority == 8 and not fade and not share)
        self.color = color
    end
    return e
end
function p:FireTear(pos, vel, canBeEye, ignoreTractor, canEndStreak, owner, multiplier)
    assert(canBeEye and not ignoreTractor and not canEndStreak and owner==self)
    local tore = entity()
    tore.Position, tore.Velocity, tore.TearFlags, tore.Variant = pos,vel,self.flags,self.variant
    tore.CollisionDamage = (self.shotDamage or self.Damage) * multiplier
    function tore:HasTearFlags(flag) return self.TearFlags & flag == flag end
    function tore:AddTearFlags(flag) self.TearFlags = self.TearFlags | flag end
    function tore:ClearTearFlags(flag) self.TearFlags = self.TearFlags & ~flag end
    self.fired[#self.fired+1] = tore
    return tore
end
function p:FireBrimstone(heading, owner, multiplier)
    assert(heading==facing and owner==self and multiplier==.18)
    if self.failBeam then error('beam callback failed') end
    local laser = entity()
    laser.Timeout = 19
    laser.spawnColor = self.laserColor
    function laser:SetMaxDistance(n) self.distance = n end
    self.fired[#self.fired+1] = laser
    return laser
end
function p:FireTechLaser(pos, offset, heading, left, oneHit, owner, multiplier)
    assert(pos == origin and offset == 0 and left and oneHit and multiplier == .28)
    return self:FireBrimstone(heading, owner, .18)
end
function p:FireTechXLaser(pos, vel, radius, owner, multiplier)
    assert(pos==origin and vel.X==10 and radius==17 and owner==self and multiplier==.20)
    return self:FireBrimstone(facing, owner, .18)
end

local callbacks={}
a.init({AddCallback=function(_, which, callback) callbacks[which]=callback end})
local function fire(kind, clock, reach, target, clip)
    p.fired={}
    local strike = {kind=kind, clip=clip, facing=facing}
    if target then a.acceptHit(strike, target) end
    a.fire(p, strike, origin, reach or 70, clock)
    return p.fired
end
local base = fire('attack', 0)
assert(#base==1 and base[1].removed and not base[1].color, 'ordinary blade left a colored extra tear')
p.shotDamage = p.Damage + .75
for _, kind in ipairs({'attack', 'q', 'q3'}) do
    local shot = fire(kind, 0)[1]
    assert(shot.removed and not shot.color, 'native damage drift retained an ordinary '..kind..' tear')
end
p.owned[CollectibleType.COLLECTIBLE_BLOOD_CLOT] = true
p.variant = TearVariant.BLOOD
assert(fire('q', 0)[1]:Exists(), 'native per-eye damage effect was discarded')
p.shotDamage, p.variant = nil, TearVariant.BLUE
p.owned[CollectibleType.COLLECTIBLE_BLOOD_CLOT] = nil
local target = entity()
target.Position = Vector(25, 1)
function target:ToNPC() return self end
function target:IsDead() return self.dead end
function target:ApplyTearflagEffects(at, flags, owner, damage)
    assert(at == self.Position and flags == (TearFlags.TEAR_POISON | TearFlags.TEAR_SLOW))
    assert(owner == p and math.abs(damage - p.Damage * .28) < .0001)
    self.procs = (self.procs or 0) + 1
end
p.flags = TearFlags.TEAR_HOMING | TearFlags.TEAR_POISON | TearFlags.TEAR_SLOW
for _, kind in ipairs({'attack', 'q', 'q3'}) do
    local carrier = fire(kind, 1, 124, target)[1]
    assert(carrier:Exists() and carrier.TearFlags == TearFlags.TEAR_HOMING,
        'transferred flags were duplicated or unrelated native flag was stripped')
end
assert(target.procs == 3)
assert(fire('q', 1)[1].TearFlags == p.flags and target.procs == 3, 'miss transferred its flags')
target.dead = true
assert(fire('attack', 1, 124, target)[1].TearFlags == p.flags and target.procs == 3, 'hit status was applied to a corpse')
p.owned[6]=true; p.flags=TearFlags.TEAR_QUADSPLIT
assert(fire('attack',0)[1].removed, 'Cricket alone created an extra straight tear')
p.flags=TearFlags.TEAR_QUADSPLIT | TearFlags.TEAR_HOMING
local mixed=fire('q',0)[1]
assert(mixed:Exists() and mixed.TearFlags==TearFlags.TEAR_HOMING, 'Cricket suppressed an unrelated tear effect')
p.owned[6]=false; p.flags=TearFlags.TEAR_QUADSPLIT
assert(fire('q',0)[1]:Exists(), 'non-Cricket quadsplit was removed')
p.flags=0
p.rainbow=2
for _, kind in ipairs({'attack','q','q3'}) do
    local early, late = fire(kind, 15)[1], fire(kind, 105)[1]
    assert(early:Exists() and late:Exists() and early.TearFlags ~= late.TearFlags, 'missing Rainbow Worm rotation')
    assert(early:GetData().YoneTearRange.reach==70)
end
p.flags=TearFlags.TEAR_BIG_SPIRAL | TearFlags.TEAR_HOMING
local native = fire('q', 120, 124)[1]
assert(native.TearFlags == p.flags, 'native worm motion or homing was overwritten')
p.rainbow=0
p.flags=TearFlags.TEAR_UNRECOGNIZED
local flagged = fire('q', 0, 124)[1]
assert(flagged:Exists() and flagged.TearFlags==p.flags, 'generic native effect was discarded')
flagged.Position = Vector(125,1)
callbacks[1](nil,flagged)
assert(not flagged.died, 'shot was clipped inside strike reach')
flagged.Position = Vector(126,1)
flagged.StickTarget = {}
callbacks[1](nil,flagged)
assert(not flagged.died, 'bounded projectile cancelled a stuck native effect')
flagged.StickTarget = nil
callbacks[1](nil,flagged)
assert(flagged.died, 'range cap did not end the extra shot')
local child = entity()
child.Position = Vector(126,1)
callbacks[3](nil,child,flagged)
assert(child.color == flagged.color, 'split tear did not inherit the blade tint')
callbacks[1](nil,child)
assert(child.removed and not child.died, 'projectile descendant ignored range or triggered a synthetic split')
p.flags, p.variant=0, TearVariant.TOOTH
assert(fire('q3',0)[1]:Exists(), 'tear variant effect was discarded')
p.shots, p.variant, p.backwards=4,TearVariant.BLUE,true
local volley, total = fire('attack',0), 0
assert(#volley==5 and volley[1].Velocity.Y<0 and volley[4].Velocity.Y>0 and volley[5].Velocity.X<0)
for _, tear in ipairs(volley) do
    assert(tear:Exists())
    total=total+tear.CollisionDamage
end
assert(math.abs(total / p.Damage - .20)<.00001, 'multi-shot blew past the aggregate damage budget')
p.shots=20
assert(#fire('q',0)==6, 'volley cap ignored')
p.sideways, p.randomShots = true, 1
volley = fire('q',0)
assert(#volley==6 and volley[3].Velocity.X<0 and volley[4].Velocity.Y<0 and volley[5].Velocity.Y>0
    and volley[6].Velocity.X<0, 'full volley dropped direction modifiers')
for _, kind in ipairs({WeaponType.WEAPON_BRIMSTONE, WeaponType.WEAPON_LASER}) do
    p.weapon = kind
    local laser = fire('q',0,124)
    assert(#laser == 1 and laser[1].distance == 124 and laser[1].Timeout == 6
        and laser[1].DisableFollowParent and laser[1].Position == origin)
end
p.weapon = WeaponType.WEAPON_BRIMSTONE
local steel = fire('attack',0,124,nil,'attack')[1]
local azakana = fire('attack',0,124,nil,'attack2')[1]
assert(steel.color == steel.spawnColor and steel.color.colorize[3] > steel.color.colorize[1])
assert(azakana.color == azakana.spawnColor and azakana.color.colorize[1] > azakana.color.colorize[3])
assert(steel.color ~= azakana.color and p.laserColor == defaultLaserColor, 'beam lost blade palette or leaked it globally')
for _, kind in ipairs({'q','q3'}) do
    local beam = fire(kind,0,124)[1]
    assert(beam.color.colorize[3] > beam.color.colorize[1], 'Q did not use the steel blade palette')
end
p.failBeam = true
assert(not pcall(fire,'attack',0,124,nil,'attack2') and p.laserColor == defaultLaserColor,
    'failing native beam left the player with a different global laser color')
p.failBeam = false
p.weapon=WeaponType.WEAPON_TECH_X
local ring = fire('q',0,124)[1]
assert(ring.color and ring.color.colorize[3] > ring.color.colorize[1])
ring.Position = Vector(126,1)
callbacks[2](nil,ring)
assert(ring.died)

local hit = {kind='q'}
assert(a.range(p)==1 and a.multiplier(p,hit)==1)
p.TearRange=9999; assert(a.range(p)==1.35)
p.TearRange=-100; assert(a.range(p)==.85)
p.TearRange=260; p.owned[4]=true; assert(a.range(p)>1 and a.range(p)<=1.35)
p.owned[1]=true; assert(math.abs(a.multiplier(p,hit)-1.4)<.0001)
p.owned[2]=true; p.owned[3]=true; assert(math.abs(a.multiplier(p,hit)-1.75)<.0001)
a.acceptHit(hit); assert(a.multiplier(p,hit)==1)
assert(a.multiplier(p,{kind='w'})==1)
""")
    print('PASS Yone native tear flags, Rainbow Worm, multishot budget, beams and reach')


if __name__ == '__main__':
    main()
