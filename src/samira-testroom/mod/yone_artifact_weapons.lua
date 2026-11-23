local Weapons = {}

local bombFuse = 12
local bombDamageScale = .24
local bombRadiusLimit = .45
local fetusDamageScale = .24
local knifeDamageScale = .24
local knifeLifetime = 30
local knifeLaunchGrace = 2

local function fireBomb(player, facing, origin, reach, tintWeapon)
    if not player.FireBomb then return false end
    local speed = math.min(8, reach * .75 / bombFuse)
    local bomb = player:FireBomb(origin, facing * speed, player)
    if not bomb or not bomb:Exists() then return false end

    bomb.ExplosionDamage = player.Damage * bombDamageScale
    bomb.RadiusMultiplier = math.min(bomb.RadiusMultiplier, bombRadiusLimit)
    bomb:SetExplosionCountdown(bombFuse)
    bomb:GetData().YoneArtifactBomb = {origin = origin, reach = reach}
    if tintWeapon then tintWeapon(bomb, bombFuse) end
    return true
end

local function fireFetus(player, facing, origin, track)
    if not (player.FireTear and TearFlags and TearFlags.TEAR_FETUS and TearVariant and TearVariant.FETUS) then
        return false
    end
    local speed = 8 * math.max(.55, math.min(2.2, player.ShotSpeed))
    local tear = player:FireTear(origin, facing * speed, false, true, false, player, fetusDamageScale)
    if not tear or not tear:Exists() then return false end

    -- Preserve the flags supplied by Isaac, including any fetus synergy already applied.
    if tear.Variant ~= TearVariant.FETUS then tear:ChangeVariant(TearVariant.FETUS) end
    tear:AddTearFlags(TearFlags.TEAR_FETUS)
    if track then track(tear) end
    return true
end

local function removeKnife(throw)
    if throw.knife and throw.knife:Exists() then throw.knife:Remove() end
    if throw.anchor:Exists() then throw.anchor:Remove() end
    if throw.owner:Exists() then
        local data = throw.owner:GetData()
        if data.YoneArtifactKnifeCast == throw then data.YoneArtifactKnifeCast = nil end
    end
end

local function sameEntity(first, second)
    return first and second and GetPtrHash(first) == GetPtrHash(second)
end

local function fireKnife(player, weapon, facing, origin, reach, tintWeapon)
    if not (player.FireKnife and EffectVariant and EffectVariant.POOF01
        and ModCallbacks.MC_PRE_EFFECT_UPDATE
        and ModCallbacks.MC_POST_KNIFE_UPDATE and ModCallbacks.MC_PRE_KNIFE_COLLISION) then
        return false
    end

    local main = weapon.GetMainEntity and weapon:GetMainEntity()
    local data = player:GetData()
    if data.YoneArtifactKnifeCast then removeKnife(data.YoneArtifactKnifeCast) end
    -- A stationary parent keeps the return point at the strike origin during Q3's dash.
    local anchor = Isaac.Spawn(EntityType.ENTITY_EFFECT, EffectVariant.POOF01, 0, origin, Vector.Zero, player)
    if not anchor or not anchor:Exists() then return false end
    anchor.Visible = false
    anchor.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
    local angle = facing:GetAngleDegrees()
    local variant = KnifeVariant and KnifeVariant.MOMS_KNIFE or 0
    local knife = player:FireKnife(anchor, angle, true, 0, variant)
    if not knife or not knife:Exists() or sameEntity(knife, main) then
        anchor:Remove()
        return false
    end

    local throw = {
        knife = knife, anchor = anchor, owner = player, origin = origin, reach = reach,
        angle = angle, damage = player.Damage * knifeDamageScale, hits = {},
        launchDeadline = knife.FrameCount + knifeLaunchGrace, expires = knife.FrameCount + knifeLifetime,
    }
    data.YoneArtifactKnifeCast = throw
    anchor:GetData().YoneArtifactKnifeAnchor = throw
    knife:GetData().YoneArtifactKnife = throw
    knife.Position = origin
    knife.Rotation = angle
    knife.EntityCollisionClass = EntityCollisionClass.ENTCOLL_ENEMIES
    knife:Shoot(1, reach)
    throw.launched = knife:IsFlying()
    knife.MaxDistance = math.min(knife.MaxDistance, reach)
    if tintWeapon then tintWeapon(knife, knifeLifetime) end
    return true
end

function Weapons.fire(player, strike, origin, reach, track, tintWeapon)
    if reach <= 0 or not player.GetWeapon or not WeaponType then return false end
    local weapon = player:GetWeapon(1)
    if not weapon then return false end
    local kind = weapon:GetWeaponType()
    if kind == WeaponType.WEAPON_BOMBS then
        return fireBomb(player, strike.facing, origin, reach, tintWeapon)
    end
    if kind == WeaponType.WEAPON_KNIFE then
        return fireKnife(player, weapon, strike.facing, origin, reach, tintWeapon)
    end
    -- Some builds declare WEAPON_FETUS but still fire C Section from the tears slot.
    local cSection = CollectibleType and CollectibleType.COLLECTIBLE_C_SECTION
    if kind == WeaponType.WEAPON_FETUS
        or kind == WeaponType.WEAPON_TEARS and cSection and player:HasCollectible(cSection) then
        return fireFetus(player, strike.facing, origin, track)
    end
    return false
end

function Weapons.init(mod)
    local function callback(id, handler, variant)
        if id then mod:AddCallback(id, handler, variant) end
    end
    callback(ModCallbacks.MC_POST_BOMB_UPDATE, function(_, bomb)
        local bounds = bomb:GetData().YoneArtifactBomb
        if not bounds then return end
        if bomb.Position:Distance(bounds.origin) > bounds.reach then
            bomb:Remove()
        elseif (bomb.Position + bomb.Velocity):Distance(bounds.origin) > bounds.reach then
            bomb.Velocity = Vector.Zero
        end
    end)
    callback(ModCallbacks.MC_PRE_EFFECT_UPDATE, function(_, anchor)
        local throw = anchor:GetData().YoneArtifactKnifeAnchor
        if not throw then return end
        if not throw.knife:Exists() then removeKnife(throw) end
        return true
    end, EffectVariant and EffectVariant.POOF01)
    callback(ModCallbacks.MC_PRE_KNIFE_UPDATE, function(_, knife)
        local throw = knife:GetData().YoneArtifactKnife
        if not throw then return end
        if not throw.owner:Exists() or not throw.anchor:Exists() then
            removeKnife(throw)
            return true
        end
        knife.Rotation = throw.angle
    end)
    callback(ModCallbacks.MC_POST_KNIFE_UPDATE, function(_, knife)
        local throw = knife:GetData().YoneArtifactKnife
        if not throw then return end
        local flying = knife:IsFlying()
        local stopped = not flying and (throw.launched or knife.FrameCount >= throw.launchDeadline)
        if stopped or not throw.owner:Exists() or not throw.anchor:Exists()
            or knife.FrameCount >= throw.expires or knife.Position:Distance(throw.origin) > throw.reach then
            removeKnife(throw)
        elseif flying then
            throw.launched = true
        end
    end)
    callback(ModCallbacks.MC_PRE_KNIFE_COLLISION, function(_, knife, enemy)
        local throw = knife:GetData().YoneArtifactKnife
        if not throw then return end
        -- Use knife geometry with one bounded hit per enemy and explicit player attribution.
        if throw.owner:Exists() and knife:IsFlying() and knife.Position:Distance(throw.origin) <= throw.reach
            and enemy:IsActiveEnemy(false) and enemy:IsVulnerableEnemy() then
            local id = GetPtrHash(enemy)
            if throw.hits[id] ~= enemy.InitSeed then
                throw.hits[id] = enemy.InitSeed
                enemy:TakeDamage(throw.damage, 0, EntityRef(throw.owner), 0)
            end
        end
        return {Collide = false, SkipCollisionEffects = true}
    end)
    callback(ModCallbacks.MC_POST_NEW_ROOM, function()
        local game = Game()
        for i = 0, game:GetNumPlayers() - 1 do
            local player = Isaac.GetPlayer(i)
            local throw = player and player:Exists() and player:GetData().YoneArtifactKnifeCast
            if throw then removeKnife(throw) end
        end
    end)
end

return Weapons
