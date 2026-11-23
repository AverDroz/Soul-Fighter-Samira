"""Exercise Yone's native Dr. Fetus, C Section, and Mom's Knife adapters against Lua stubs."""

from pathlib import Path

from lupa.lua54 import LuaRuntime


MODULE = Path(__file__).resolve().parents[1] / 'src/samira-testroom/mod/yone_artifact_weapons.lua'


def main():
    lua = LuaRuntime()
    lua.globals().source = MODULE.read_text(encoding='utf-8')
    lua.execute(r"""
local weapons = assert(load(source))()
WeaponType = {WEAPON_TEARS = 1, WEAPON_KNIFE = 4, WEAPON_BOMBS = 5, WEAPON_FETUS = 14}
CollectibleType = {COLLECTIBLE_C_SECTION = 678}
TearFlags = {TEAR_FETUS = 1 << 50, TEAR_FETUS_BRIMSTONE = 1 << 51}
TearVariant = {BLUE = 0, FETUS = 50}
ModCallbacks = {
    MC_POST_BOMB_UPDATE = 1, MC_PRE_EFFECT_UPDATE = 2, MC_PRE_KNIFE_UPDATE = 3,
    MC_POST_KNIFE_UPDATE = 4, MC_PRE_KNIFE_COLLISION = 5, MC_POST_NEW_ROOM = 6,
}
KnifeVariant = {MOMS_KNIFE = 0}
EffectVariant = {POOF01 = 15}
EntityType = {ENTITY_EFFECT = 1000}
EntityCollisionClass = {ENTCOLL_NONE = 0, ENTCOLL_ENEMIES = 3}

local methods, vectorMeta = {}, {}
vectorMeta.__index = methods
local function vec(x, y) return setmetatable({X = x, Y = y}, vectorMeta) end
function vectorMeta.__add(a, b) return vec(a.X + b.X, a.Y + b.Y) end
function vectorMeta.__mul(a, scale) return vec(a.X * scale, a.Y * scale) end
function methods:Distance(other)
    return math.sqrt((self.X - other.X)^2 + (self.Y - other.Y)^2)
end
function methods:GetAngleDegrees() return math.deg(math.atan(self.Y, self.X)) end
Vector = {Zero = vec(0, 0)}

local origin, strike = vec(100, 75), {kind = 'q3', facing = vec(1, 0)}
local bomb, tear, tracked, knife, anchor, tinted, tintDuration
local function entity()
    return {
        data = {},
        GetData = function(self) return self.data end,
        Exists = function(self) return not self.removed end,
        Remove = function(self) self.removed = true end,
    }
end
local player = entity()
player.Damage, player.ShotSpeed, player.kind = 5, 1, WeaponType.WEAPON_TEARS
local mainKnife = entity()
mainKnife.IsFlying = function() return false end
GetPtrHash = function(e) return e end
EntityRef = function(e) return {Entity = e} end
Game = function() return {GetNumPlayers = function() return 1 end} end
Isaac = {
    GetPlayer = function(index) assert(index == 0) return player end,
    Spawn = function(kind, variant, subtype, position, velocity, owner)
        assert(kind == EntityType.ENTITY_EFFECT and variant == EffectVariant.POOF01 and subtype == 0)
        assert(position == origin and velocity == Vector.Zero and owner == player)
        anchor = entity()
        anchor.Position = position
        return anchor
    end,
}
function player:GetWeapon(slot)
    assert(slot == 1)
    if not self.kind then return end
    return {
        GetWeaponType = function() return self.kind end,
        GetMainEntity = function() return mainKnife end,
    }
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
function player:FireKnife(parent, angle, cantOverwrite, subtype, variant)
    assert(parent == anchor and parent.Position == origin and not parent.Visible)
    assert(angle == strike.facing:GetAngleDegrees() and cantOverwrite and subtype == 0)
    assert(variant == 0)
    if self.spawnFails then return end
    if self.returnsMainKnife then return mainKnife end
    knife = entity()
    knife.FrameCount = 0
    knife.IsFlying = function(self) return self.flying end
    knife.Shoot = function(self, charge, reach)
        assert(self.Position == origin and self.Rotation == angle and charge == 1 and reach == 80)
        self.MaxDistance = reach + 20
        self.flying = not player.delaysKnife
    end
    return knife
end
local callbacks = {}
weapons.init({AddCallback = function(_, id, callback, variant)
    assert(not callbacks[id])
    if id == ModCallbacks.MC_PRE_EFFECT_UPDATE then assert(variant == EffectVariant.POOF01) end
    callbacks[id] = callback
end})
local update = callbacks[ModCallbacks.MC_POST_BOMB_UPDATE]
local function fire(reach)
    return weapons.fire(player, strike, origin, reach, function(e) tracked = e end, function(e, duration)
        tinted, tintDuration = e, duration
    end)
end

assert(not fire(80) and not bomb and not tear, 'ordinary shot should use existing fallback')
player.kind = nil
assert(not fire(80), 'empty weapon slot should use existing fallback')
player.kind = WeaponType.WEAPON_BOMBS
assert(not fire(0) and not bomb, 'empty reach should not spawn a bomb')
assert(fire(80) and bomb and not tear)
assert(bomb.ExplosionDamage == 1.2 and bomb.RadiusMultiplier == .45 and bomb.fuse == 12)
assert(tinted == bomb and tintDuration == 12)
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

local knifeUpdate = callbacks[ModCallbacks.MC_POST_KNIFE_UPDATE]
local knifeCollision = callbacks[ModCallbacks.MC_PRE_KNIFE_COLLISION]
local anchorUpdate = callbacks[ModCallbacks.MC_PRE_EFFECT_UPDATE]
local enemy = {
    InitSeed = 13, hits = 0,
    IsActiveEnemy = function() return true end,
    IsVulnerableEnemy = function() return true end,
    TakeDamage = function(self, amount, flags, source, cooldown)
        assert(amount == 1.2 and flags == 0 and source.Entity == player and cooldown == 0)
        self.hits = self.hits + 1
    end,
}
local function collideWithEnemy()
    local result = knifeCollision(nil, knife, enemy)
    assert(result.SkipCollisionEffects == true and result.Collide == false,
        'the secondary throw must suppress the engine knife collision damage')
end
player.kind = WeaponType.WEAPON_KNIFE
assert(not fire(80) and not anchor:Exists(), 'failed native knife spawn should clean up the anchor')
player.spawnFails, player.returnsMainKnife = false, true
assert(not fire(80) and mainKnife:Exists() and not anchor:Exists(),
    'the held knife must not be modified as a secondary throw')
player.returnsMainKnife, tracked = false, nil
strike.facing = vec(-1, 1)
player.Position = vec(140, 75)
for _, kind in ipairs({'a', 'q', 'q3'}) do
    strike.kind = kind
    local previousKnife, previousAnchor = knife, anchor
    assert(fire(80) and not tracked and tinted == knife and tintDuration == 30)
    assert(knife:IsFlying() and knife.Rotation == 135 and knife.MaxDistance == 80)
    assert(knife.Position == origin and anchorUpdate(nil, anchor) == true)
    assert(anchor.EntityCollisionClass == EntityCollisionClass.ENTCOLL_NONE)
    assert(knife.EntityCollisionClass == EntityCollisionClass.ENTCOLL_ENEMIES)
    if previousKnife then assert(not previousKnife:Exists() and not previousAnchor:Exists()) end
end
knife.Rotation = 0
callbacks[ModCallbacks.MC_PRE_KNIFE_UPDATE](nil, knife)
assert(knife.Rotation == 135, 'the knife must keep the blade direction after the Q3 dash')
collideWithEnemy()
assert(enemy.hits == 1)
collideWithEnemy()
assert(enemy.hits == 1, 'one proc per target per throw')
knife.Position = vec(181, 75)
collideWithEnemy()
assert(enemy.hits == 1)
knifeUpdate(nil, knife)
assert(not knife:Exists() and not anchor:Exists())
assert(fire(80))
knife.flying = false
knifeUpdate(nil, knife)
assert(not knife:Exists() and not anchor:Exists(), 'a returned knife must expire')
assert(fire(80))
knife:Remove()
anchorUpdate(nil, anchor)
assert(not anchor:Exists() and not player:GetData().YoneArtifactKnifeCast)
assert(fire(80))
callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
assert(not knife:Exists() and not anchor:Exists() and not player:GetData().YoneArtifactKnifeCast)
assert(knifeCollision(nil, mainKnife, enemy) == nil and mainKnife:Exists(),
    'unrelated knife collisions must retain native behavior')
player.delaysKnife, KnifeVariant = true, nil
assert(fire(80) and not knife:IsFlying(), 'missing variant enum should use vanilla knife variant zero')
knife.FrameCount = 1
knifeUpdate(nil, knife)
assert(knife:Exists(), 'the knife may become airborne on an engine update')
knife.flying = true
knifeUpdate(nil, knife)
knife.flying = false
knifeUpdate(nil, knife)
assert(not knife:Exists() and not anchor:Exists(), 'the delayed launch must still expire on return')
assert(fire(80))
knife.FrameCount = 2
knifeUpdate(nil, knife)
assert(not knife:Exists() and not anchor:Exists(), 'an unsuccessful launch must clean up')
Isaac.GetPlayer = function() return nil end
callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
""")
    print('PASS Yone native bomb bounds, C Section carrier, and returning knife')


if __name__ == '__main__':
    main()
