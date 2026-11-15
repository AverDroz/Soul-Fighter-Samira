local Kills = {}
local game, getPlayer, onKill
local hits, deaths, resolved, pendingSins, resolvedSins
local pendingBoss, resolvedBoss
local creditTicks = 90
local phaseGraceTicks = 2

local function entityKey(entity)
    return tostring(GetPtrHash(entity)) .. ':' .. tostring(entity.InitSeed)
end

local function eligible(npc)
    return npc and npc.Type ~= EntityType.ENTITY_DUMMY and npc.Type ~= EntityType.ENTITY_FIREPLACE
        and not npc:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

local function isSin(kind)
    return kind == EntityType.ENTITY_ENVY or kind == EntityType.ENTITY_SLOTH
        or kind == EntityType.ENTITY_LUST or kind == EntityType.ENTITY_WRATH
        or kind == EntityType.ENTITY_GLUTTONY or kind == EntityType.ENTITY_GREED
        or kind == EntityType.ENTITY_PRIDE
end

local function bossPart(npc)
    if npc:IsBoss() then return true end
    local parent = npc.Parent
    return parent and parent:Exists() and parent:ToNPC() ~= nil and parent:IsBoss()
end

function Kills.reset()
    hits, deaths, resolved = {}, {}, {}
    pendingSins, resolvedSins = {}, {}
    pendingBoss, resolvedBoss = nil, false
end

function Kills.acceptHit(entity, context, clock)
    local owner = getPlayer()
    if not owner or not context.player or entityKey(owner) ~= entityKey(context.player) then return end
    local npc = entity:ToNPC()
    if not eligible(npc) then return end
    local key = entityKey(npc)
    if not resolved[key] then hits[key] = clock end
end

local function recordDeath(npc)
    if not getPlayer() or not eligible(npc) then return end
    local key = entityKey(npc)
    if resolved[key] or deaths[key] then return end
    local sin = isSin(npc.Type) and npc.Type or nil
    local clock, boss = game:GetFrameCount(), bossPart(npc)
    deaths[key] = {clock = clock, boss = boss, sin = sin}
    if sin and pendingSins[sin] then pendingSins[sin] = clock end
    if pendingBoss and (boss or sin) then pendingBoss = clock end
end

local function hasLivingSin(kind)
    for _, npc in ipairs(Isaac.FindByType(kind, -1, -1, false, false)) do
        if eligible(npc) and npc:Exists() and not npc:IsDead() then return true end
    end
    return false
end

function Kills.update(clock)
    if not getPlayer() then return end
    local room = game:GetRoom()
    local bossRoom = room:GetType() == RoomType.ROOM_BOSS
    for key, death in pairs(deaths) do
        -- Let the accepted-damage callback stamp a lethal hit on the same tick.
        if clock > death.clock then
            local lastHit = hits[key]
            deaths[key], hits[key], resolved[key] = nil, nil, true
            if lastHit and lastHit <= death.clock and death.clock - lastHit <= creditTicks then
                if death.sin and not bossRoom then
                    if not resolvedSins[death.sin] then pendingSins[death.sin] = death.clock end
                elseif death.boss or death.sin then
                    if not resolvedBoss then pendingBoss = death.clock end
                else
                    onKill(false, clock)
                end
            end
        end
    end

    for key, lastHit in pairs(hits) do
        if clock - lastHit > creditTicks then hits[key] = nil end
    end

    -- Room completion spans multipart and phase-changing bosses.
    if pendingBoss and clock - pendingBoss >= phaseGraceTicks and room:IsClear() then
        pendingBoss, resolvedBoss = nil, true
        onKill(true, clock)
    end
    for kind, since in pairs(pendingSins) do
        -- Envy spawns smaller NPCs in the same family as its pieces die.
        if clock - since >= phaseGraceTicks and not hasLivingSin(kind) then
            pendingSins[kind], resolvedSins[kind] = nil, true
            onKill(true, clock)
        end
    end
end

function Kills.init(mod, currentGame, activePlayer, callback)
    game, getPlayer, onKill = currentGame, activePlayer, callback
    Kills.reset()
    mod:AddCallback(ModCallbacks.MC_POST_NPC_DEATH, function(_, npc) recordDeath(npc) end)
end

return Kills
