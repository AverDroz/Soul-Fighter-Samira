-- Blade damage stays immediate. A short native volley carries the effects
-- which Isaac applies to tears, including luck rolls and third-party flags.
local Artifacts = {}
local rainbowMotion = {'TEAR_WIGGLE', 'TEAR_PULSE', 'TEAR_SPIRAL', 'TEAR_SQUARE', 'TEAR_FLAT'}
local volleyBudget, volleyLimit = .28, 6

local function owns(player, name)
    local id = CollectibleType[name]
    return id and player:HasCollectible(id), id
end

local function eligible(hit)
    return hit and not hit.artifactHit
        and (hit.kind == 'attack' or hit.kind == 'q' or hit.kind == 'q3')
end

function Artifacts.cricket(player, hit)
    return eligible(hit) and owns(player, 'COLLECTIBLE_CRICKETS_BODY')
end

function Artifacts.range(player)
    local nativeRange = tonumber(player.TearRange) or 260
    local bonus = owns(player, 'COLLECTIBLE_MOMS_KNIFE') and .10 or 0
    return math.max(.85, math.min(1.35, 1 + (nativeRange - 260) / 1000 + bonus))
end

function Artifacts.multiplier(player, hit)
    if not eligible(hit) then return 1 end
    local extra = 0
    if owns(player, 'COLLECTIBLE_20_20') then extra = extra + 1 end
    if owns(player, 'COLLECTIBLE_INNER_EYE') then extra = extra + 2 end
    if owns(player, 'COLLECTIBLE_MUTANT_SPIDER') then extra = extra + 3 end
    -- The first extra blade is worth 40%, with diminishing returns thereafter.
    local bonus = extra > 0 and .4 + .175 * (extra - 1) or 0
    return 1 + math.min(.75, bonus)
end

function Artifacts.acceptHit(hit)
    if eligible(hit) then hit.artifactHit = true end
end

local function shotAngles(player)
    if not player.GetMultiShotParams or not WeaponType then return {0} end
    local params = player:GetMultiShotParams(WeaponType.WEAPON_TEARS)
    if not params then return {0} end
    local count = math.max(1, math.min(volleyLimit, params:GetNumTears()))
    local step = math.max(5, math.min(18, params:GetSpreadAngle(WeaponType.WEAPON_TEARS)))
    local angles = {}
    for shot = 1, count do
        local angle = (shot - (count + 1) / 2) * step
        if params:IsCrossEyed() then angle = angle + (shot % 2 == 1 and -30 or 30) end
        angles[#angles + 1] = angle
    end
    if params:IsShootingBackwards() then angles[#angles + 1] = 180 end
    if params:IsShootingSideways() then
        angles[#angles + 1], angles[#angles + 2] = -90, 90
    end
    local randomShots = math.min(params:GetNumRandomDirTears(), volleyLimit - #angles)
    if randomShots > 0 then
        local rng = player:GetCollectibleRNG(CollectibleType.COLLECTIBLE_EYE_SORE)
        for _ = 1, randomShots do angles[#angles + 1] = rng:RandomInt(360) end
    end
    return angles
end

local function hasRainbow(player)
    return TrinketType and TrinketType.TRINKET_RAINBOW_WORM and player.GetTrinketMultiplier
        and player:GetTrinketMultiplier(TrinketType.TRINKET_RAINBOW_WORM) > 0
end

local function addRainbowMotion(player, tear, clock)
    for _, name in ipairs(rainbowMotion) do
        if tear:HasTearFlags(TearFlags[name]) then return end
    end
    if tear:HasTearFlags(TearFlags.TEAR_BIG_SPIRAL) then return end
    local index = (math.floor(clock / 90) + player.InitSeed) % #rainbowMotion + 1
    tear:AddTearFlags(TearFlags[rainbowMotion[index]])
end

local function modifiedTear(player, tear, damageScale)
    return tear.TearFlags ~= TearFlags.TEAR_NORMAL
        or tear.Variant ~= TearVariant.BLUE and tear.Variant ~= TearVariant.BLOOD
        or math.abs(tear.CollisionDamage - player.Damage * damageScale) > .01
end

local function fireLaser(player, origin, facing, reach)
    if not player.GetWeapon or not WeaponType then return false end
    local weapon = player:GetWeapon(1)
    local kind = weapon and weapon:GetWeaponType()
    local laser
    if kind == WeaponType.WEAPON_BRIMSTONE then
        laser = player:FireBrimstone(facing, player, .18)
    elseif kind == WeaponType.WEAPON_LASER then
        laser = player:FireTechLaser(origin, LaserOffset.LASER_TECH1_OFFSET, facing, true, true, player, .28)
    elseif kind == WeaponType.WEAPON_TECH_X then
        laser = player:FireTechXLaser(origin, facing * 10, 17, player, .20)
        if laser then laser:GetData().YoneTearRange = {origin = origin, reach = reach} end
        return laser ~= nil
    end
    if not laser then return false end
    laser.DisableFollowParent = true
    laser.Position = origin
    laser:SetMaxDistance(reach)
    laser.Timeout = math.min(laser.Timeout, 6)
    return true
end

function Artifacts.fire(player, strike, origin, reach, clock)
    if not player.FireTear or not TearFlags or not TearVariant or reach <= 0 then return end
    if fireLaser(player, origin, strike.facing, reach) then return end
    local rainbow = hasRainbow(player)
    local angles = shotAngles(player)
    local count = math.min(volleyLimit, #angles)
    local multiplier = (count > 1 and .20 or volleyBudget) / count
    local speed = 9 * math.max(.55, math.min(2.2, player.ShotSpeed))
    for index = 1, count do
        local velocity = strike.facing:Rotated(angles[index]) * speed
        local tear = player:FireTear(origin, velocity, true, false, false, player, multiplier)
        if tear and tear:Exists() then
            -- Cricket's Body is represented by the blade impact, not a second
            -- straight tear. Preserve every unrelated native tear effect.
            if owns(player, 'COLLECTIBLE_CRICKETS_BODY') and TearFlags.TEAR_QUADSPLIT
                and tear.ClearTearFlags then
                tear:ClearTearFlags(TearFlags.TEAR_QUADSPLIT)
            end
            if rainbow then addRainbowMotion(player, tear, clock) end
            if rainbow or #angles > 1 or modifiedTear(player, tear, multiplier) then
                tear:GetData().YoneTearRange = {origin = origin, reach = reach}
            else
                tear:Remove()
            end
        end
    end
end

local function boundProjectile(entity)
    local range = entity:GetData().YoneTearRange
    if range and entity.Position:Distance(range.origin) > range.reach then entity:Die() end
end

function Artifacts.init(mod)
    if ModCallbacks.MC_POST_TEAR_UPDATE then
        mod:AddCallback(ModCallbacks.MC_POST_TEAR_UPDATE, function(_, tear)
            if not tear.StickTarget then boundProjectile(tear) end
        end)
    end
    if ModCallbacks.MC_POST_LASER_UPDATE then
        mod:AddCallback(ModCallbacks.MC_POST_LASER_UPDATE, function(_, laser) boundProjectile(laser) end)
    end
end

return Artifacts
