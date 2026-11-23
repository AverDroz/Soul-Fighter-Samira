"""Exercise Yone's bounded Dr. Fetus and C Section adapters against Lua stubs."""

from pathlib import Path

from lupa.lua54 import LuaRuntime


MODULE = Path(__file__).resolve().parents[1] / 'src/samira-testroom/mod/yone_artifact_weapons.lua'


def main():
    lua = LuaRuntime()
    lua.globals().source = MODULE.read_text(encoding='utf-8')
    lua.execute(r"""
local weapons = assert(load(source))()
WeaponType = {WEAPON_TEARS = 1, WEAPON_BOMBS = 5, WEAPON_FETUS = 14}
CollectibleType = {COLLECTIBLE_C_SECTION = 678}
TearFlags = {TEAR_FETUS = 1 << 50, TEAR_FETUS_BRIMSTONE = 1 << 51}
TearVariant = {BLUE = 0, FETUS = 50}
ModCallbacks = {MC_POST_BOMB_UPDATE = 1}

local methods, vectorMeta = {}, {}
vectorMeta.__index = methods
local function vec(x, y) return setmetatable({X = x, Y = y}, vectorMeta) end
function vectorMeta.__add(a, b) return vec(a.X + b.X, a.Y + b.Y) end
function vectorMeta.__mul(a, scale) return vec(a.X * scale, a.Y * scale) end
function methods:Distance(other)
    return math.sqrt((self.X - other.X)^2 + (self.Y - other.Y)^2)
end
Vector = {Zero = vec(0, 0)}

local origin, strike = vec(100, 75), {kind = 'q3', facing = vec(1, 0)}
local player = {Damage = 5, ShotSpeed = 1, kind = WeaponType.WEAPON_TEARS}
local bomb, tear, tracked
local function entity()
    return {
        data = {},
        GetData = function(self) return self.data end,
        Exists = function(self) return not self.removed end,
        Remove = function(self) self.removed = true end,
    }
end
function player:GetWeapon(slot)
    assert(slot == 1)
    if not self.kind then return end
    return {GetWeaponType = function() return self.kind end}
end
function player:HasCollectible(id)
    assert(id == CollectibleType.COLLECTIBLE_C_SECTION)
    return self.cSection
end
function player:FireBomb(pos, velocity, owner)
    assert(pos == origin and owner == self and velocity.X == 5 and velocity.Y == 0)
    if self.spawnFails then return end
    bomb = entity()
    bomb.Position, bomb.Velocity = pos, velocity
    bomb.ExplosionDamage, bomb.RadiusMultiplier = 100, 1.5
    bomb.SetExplosionCountdown = function(self, frames) self.fuse = frames end
    return bomb
end
function player:FireTear(pos, velocity, canBeEye, noTractorBeam, canEndStreak, owner, scale)
    assert(pos == origin and owner == self and velocity.X == 8 and scale == .24)
    assert(not canBeEye and noTractorBeam and not canEndStreak)
    if self.spawnFails then return end
    tear = entity()
    tear.Variant, tear.TearFlags = TearVariant.BLUE, TearFlags.TEAR_FETUS_BRIMSTONE
    tear.ChangeVariant = function(self, variant) self.Variant = variant end
    tear.AddTearFlags = function(self, flags) self.TearFlags = self.TearFlags | flags end
    return tear
end
local update
weapons.init({AddCallback = function(_, id, callback)
    assert(id == ModCallbacks.MC_POST_BOMB_UPDATE)
    update = callback
end})
local function fire(reach)
    return weapons.fire(player, strike, origin, reach, function(e) tracked = e end)
end

assert(not fire(80) and not bomb and not tear, 'ordinary shot should use existing fallback')
player.kind = nil
assert(not fire(80), 'empty weapon slot should use existing fallback')
player.kind = WeaponType.WEAPON_BOMBS
assert(not fire(0) and not bomb, 'empty reach should not spawn a bomb')
assert(fire(80) and bomb and not tear)
assert(bomb.ExplosionDamage == 1.2 and bomb.RadiusMultiplier == .45 and bomb.fuse == 12)
assert(not tracked, 'bomb must use its own update instead of tear tracking')
bomb.Position = vec(179, 75)
update(nil, bomb)
assert(bomb.Velocity == Vector.Zero and bomb:Exists(), 'bomb must stop just inside reach')
bomb.Position = vec(181, 75)
update(nil, bomb)
assert(not bomb:Exists(), 'out-of-range bomb must expire without a manual explosion')
local nativeBomb = entity()
update(nil, nativeBomb)
assert(nativeBomb:Exists(), 'unrelated bombs must remain untouched')
player.kind = WeaponType.WEAPON_FETUS
assert(fire(80) and tracked == tear and tear.Variant == TearVariant.FETUS)
assert(tear.TearFlags == TearFlags.TEAR_FETUS | TearFlags.TEAR_FETUS_BRIMSTONE)
player.kind, player.cSection = WeaponType.WEAPON_TEARS, true
assert(fire(80) and tracked == tear and tear.Variant == TearVariant.FETUS,
    'C Section using the standard tears slot was not recognized')
local fetusVariant = TearVariant.FETUS
TearVariant.FETUS = nil
assert(not fire(80), 'missing fetus support should use existing fallback')
TearVariant.FETUS = fetusVariant
player.spawnFails = true
assert(not fire(80), 'cancelled tear spawn should use existing fallback')
player.kind = WeaponType.WEAPON_BOMBS
assert(not fire(80), 'cancelled bomb spawn should use existing fallback')
""")
    print('PASS Yone native bomb bounds and C Section carrier')


if __name__ == '__main__':
    main()
