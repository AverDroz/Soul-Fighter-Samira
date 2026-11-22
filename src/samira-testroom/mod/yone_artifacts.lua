-- Adapt tear-specific collectibles to Yone's direct blade impacts. The caller
-- shares one context across all targets and consumes it only after acceptance.
local Artifacts = {}

local function owns(player, name)
    local id = CollectibleType[name]
    return id and player:HasCollectible(id), id
end

local function eligible(hit)
    return hit and not hit.artifactHit
        and (hit.kind == 'attack' or hit.kind == 'q' or hit.kind == 'q3')
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

local function roll(player, name, chance)
    local hasItem, id = owns(player, name)
    return hasItem and player:GetCollectibleRNG(id):RandomFloat() < chance
end

function Artifacts.onHit(player, hit, enemy)
    if not eligible(hit) then return end
    hit.artifactHit = true
    local source = EntityRef(player)
    local dot = math.max(0, player.Damage or 0) * .3
    if roll(player, 'COLLECTIBLE_COMMON_COLD', .15) then enemy:AddPoison(source, 43, dot) end
    if roll(player, 'COLLECTIBLE_FIRE_MIND', .15) then enemy:AddBurn(source, 43, dot) end
    if roll(player, 'COLLECTIBLE_SPIDER_BITE', .15) then
        enemy:AddSlowing(source, 45, .7, Color(1, 1, 1, 1))
    end
    if not enemy:IsBoss() and roll(player, 'COLLECTIBLE_MOMS_CONTACTS', .10) then
        enemy:AddFreeze(source, 30)
    end
end

return Artifacts
