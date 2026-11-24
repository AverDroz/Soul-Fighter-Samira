-- Blade damage stays immediate. A short native volley carries the effects
-- which Isaac applies to tears, including luck rolls and third-party flags.
local Artifacts = {}
local Weapons = include('yone_artifact_weapons')
local rainbowMotion = {'TEAR_WIGGLE', 'TEAR_PULSE', 'TEAR_SPIRAL', 'TEAR_SQUARE', 'TEAR_FLAT'}
local impactFlags = {'TEAR_SLOW', 'TEAR_POISON', 'TEAR_FREEZE', 'TEAR_CHARM', 'TEAR_CONFUSION',
    'TEAR_PERMANENT_CONFUSION', 'TEAR_BURN', 'TEAR_FEAR', 'TEAR_GODS_FLESH', 'TEAR_MIDAS'}
local eyeDamageItems = {'COLLECTIBLE_BLOOD_CLOT', 'COLLECTIBLE_CHEMICAL_PEEL', 'COLLECTIBLE_STYE'}
local volleyBudget, volleyLimit = .28, 6
local steelHue, azakanaHue = {.42, .83, 1}, {1, .26, .48}

function Artifacts.bladeHue(clip)
    return clip == 'attack2' and azakanaHue or steelHue
end

local function bladeTint(clip)
    if not Color then return end
    local r, g, b = table.unpack(Artifacts.bladeHue(clip))
    local color = Color(1, 1, 1, 1, r * .09, g * .09, b * .09)
    -- Colorize replaces the base hue, including Brimstone's red texture.
    if color.SetColorize then color:SetColorize(r * 1.25, g * 1.25, b * 1.25, 1) end
    return color
end

local function tintArtifact(entity, color, frames)
    if not color or not entity.SetColor then return end
    entity:SetColor(color, frames or 90, 8, false, false)
    entity:GetData().YoneArtifactTint = color
end

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

function Artifacts.acceptHit(hit, target)
    if eligible(hit) then
        hit.artifactHit = true
        hit.artifactTarget = target
    end
end

local function shotAngles(player)
    if not player.GetMultiShotParams or not WeaponType then return {0} end
    local params = player:GetMultiShotParams(WeaponType.WEAPON_TEARS)
    if not params then return {0} end
    local backwards, sideways = params:IsShootingBackwards(), params:IsShootingSideways()
    local eyeSore = CollectibleType.COLLECTIBLE_EYE_SORE
    local reserved = (backwards and 1 or 0) + (sideways and 2 or 0)
    local randomShots = eyeSore and player.GetCollectibleRNG
        and math.min(params:GetNumRandomDirTears(), volleyLimit - reserved - 1) or 0
    local count = math.max(1, math.min(volleyLimit - reserved - randomShots, params:GetNumTears()))
    local step = math.max(5, math.min(18, params:GetSpreadAngle(WeaponType.WEAPON_TEARS)))
    local angles = {}
    for shot = 1, count do
        local angle = (shot - (count + 1) / 2) * step
        if params:IsCrossEyed() then angle = angle + (shot % 2 == 1 and -30 or 30) end
        angles[#angles + 1] = angle
    end
    if backwards then angles[#angles + 1] = 180 end
    if sideways then
        angles[#angles + 1], angles[#angles + 2] = -90, 90
    end
    if randomShots > 0 then
        local rng = player:GetCollectibleRNG(eyeSore)
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
    if tear.TearFlags ~= TearFlags.TEAR_NORMAL
        or tear.Variant ~= TearVariant.BLUE and tear.Variant ~= TearVariant.BLOOD then return true end
    -- Plain tears can differ from the blade's damage snapshot. Only an active
    -- per-eye damage effect can make that difference special by itself.
    if tear.CollisionDamage > player.Damage * damageScale + .01 then
        for _, name in ipairs(eyeDamageItems) do
            if owns(player, name) then return true end
        end
    end
    return false
end

local function applyImpactFlags(player, target, tear)
    if not target or not target:Exists() or target:IsDead() or not tear.ClearTearFlags then return end
    local npc = target:ToNPC()
    if not npc or not npc.ApplyTearflagEffects then return end
    local flags = TearFlags.TEAR_NORMAL
    for _, name in ipairs(impactFlags) do
        local flag = TearFlags[name]
        if flag and tear:HasTearFlags(flag) then flags = flags | flag end
    end
    if flags ~= TearFlags.TEAR_NORMAL then
        npc:ApplyTearflagEffects(target.Position, flags, player, tear.CollisionDamage)
        tear:ClearTearFlags(flags)
    end
end

local function withLaserColor(player, color, fire)
    if not (color and player.GetLaserColor and player.SetLaserColor) then return fire() end
    local previous = player:GetLaserColor()
    if not previous then return fire() end
    player:SetLaserColor(color)
    local ok, result = pcall(fire)
    player:SetLaserColor(previous)
    if not ok then error(result, 0) end
    return result
end

local function fireLaser(player, origin, facing, reach, color)
    if not player.GetWeapon or not WeaponType then return false end
    local weapon = player:GetWeapon(1)
    if not weapon then return false end
    local kind = weapon:GetWeaponType()
    local fire
    if kind == WeaponType.WEAPON_BRIMSTONE then
        fire = function() return player:FireBrimstone(facing, player, .18) end
    elseif kind == WeaponType.WEAPON_LASER then
        fire = function() return player:FireTechLaser(origin, LaserOffset.LASER_TECH1_OFFSET, facing, true, true, player, .28) end
    elseif kind == WeaponType.WEAPON_TECH_X then
        fire = function() return player:FireTechXLaser(origin, facing * 10, 17, player, .20) end
    end
    if not fire then return false end
    local laser = withLaserColor(player, color, fire)
    if not laser then return false end
    tintArtifact(laser, color)
    if kind == WeaponType.WEAPON_TECH_X then
        laser:GetData().YoneTearRange = {origin = origin, reach = reach}
    else
        laser.DisableFollowParent = true
        laser.Position = origin
        laser:SetMaxDistance(reach)
        laser.Timeout = math.min(laser.Timeout, 6)
    end
    return true
end

function Artifacts.fire(player, strike, origin, reach, clock)
    if not player.FireTear or not TearFlags or not TearVariant or reach <= 0 then return end
    local color = bladeTint(strike.clip or strike.kind)
    if fireLaser(player, origin, strike.facing, reach, color) then return end
    local function track(entity)
        entity:GetData().YoneTearRange = {origin = origin, reach = reach}
        tintArtifact(entity, color)
    end
    if Weapons.fire(player, strike, origin, reach, function(tear)
        applyImpactFlags(player, strike.artifactTarget, tear)
        track(tear)
    end, function(entity, frames) tintArtifact(entity, color, frames) end) then return end
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
            if index == 1 then applyImpactFlags(player, strike.artifactTarget, tear) end
            if rainbow then addRainbowMotion(player, tear, clock) end
            if rainbow or #angles > 1 or modifiedTear(player, tear, multiplier) then
                track(tear)
            else
                tear:Remove()
            end
        end
    end
end

local function boundProjectile(entity)
    local range = entity:GetData().YoneTearRange
    if range and entity.Position:Distance(range.origin) > range.reach then
        if range.derived then entity:Remove() else entity:Die() end
    end
end

function Artifacts.init(mod)
    Weapons.init(mod)
    if ModCallbacks.MC_POST_TEAR_UPDATE then
        mod:AddCallback(ModCallbacks.MC_POST_TEAR_UPDATE, function(_, tear)
            if not tear.StickTarget then boundProjectile(tear) end
        end)
    end
    if ModCallbacks.MC_POST_LASER_UPDATE then
        mod:AddCallback(ModCallbacks.MC_POST_LASER_UPDATE, function(_, laser) boundProjectile(laser) end)
    end
    if ModCallbacks.MC_POST_FIRE_SPLIT_TEAR then
        mod:AddCallback(ModCallbacks.MC_POST_FIRE_SPLIT_TEAR, function(_, tear, parent)
            if not parent then return end
            local data = parent:GetData()
            local range = data.YoneTearRange
            if range then
                tear:GetData().YoneTearRange = {origin = range.origin, reach = range.reach, derived = true}
            end
            tintArtifact(tear, data.YoneArtifactTint)
        end)
    end
end

return Artifacts
