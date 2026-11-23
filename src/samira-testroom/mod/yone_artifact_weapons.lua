local Weapons = {}

local bombFuse = 12
local bombDamageScale = .24
local bombRadiusLimit = .45
local fetusDamageScale = .24

local function fireBomb(player, facing, origin, reach)
    if not player.FireBomb then return false end
    local speed = math.min(8, reach * .75 / bombFuse)
    local bomb = player:FireBomb(origin, facing * speed, player)
    if not bomb or not bomb:Exists() then return false end

    bomb.ExplosionDamage = player.Damage * bombDamageScale
    bomb.RadiusMultiplier = math.min(bomb.RadiusMultiplier, bombRadiusLimit)
    bomb:SetExplosionCountdown(bombFuse)
    bomb:GetData().YoneArtifactBomb = {origin = origin, reach = reach}
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

function Weapons.fire(player, strike, origin, reach, track)
    if reach <= 0 or not player.GetWeapon or not WeaponType then return false end
    local weapon = player:GetWeapon(1)
    if not weapon then return false end
    local kind = weapon:GetWeaponType()
    if kind == WeaponType.WEAPON_BOMBS then
        return fireBomb(player, strike.facing, origin, reach)
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
    if not ModCallbacks.MC_POST_BOMB_UPDATE then return end
    mod:AddCallback(ModCallbacks.MC_POST_BOMB_UPDATE, function(_, bomb)
        local bounds = bomb:GetData().YoneArtifactBomb
        if not bounds then return end
        if bomb.Position:Distance(bounds.origin) > bounds.reach then
            bomb:Remove()
        elseif (bomb.Position + bomb.Velocity):Distance(bounds.origin) > bounds.reach then
            bomb.Velocity = Vector.Zero
        end
    end)
end

return Weapons
