local Encounters = {}
local mod, game, getPlayer, items
local roomId, saved, scanned, spawning
local updatingNpc, spawnOwners, recentSplits
local suppressInitialSpawn = false

local function entityTypes(names)
    local types = {}
    for _, name in ipairs(names) do
        local kind = EntityType['ENTITY_' .. name]
        if kind then types[kind] = true end
    end
    return types
end

local scripted = entityTypes({
    'GIDEON', 'MOM', 'MOMS_HEART', 'MAMA_GURDY', 'SATAN', 'MEGA_SATAN', 'MEGA_SATAN_2',
    'MOTHER', 'DOGMA', 'BEAST', 'DELIRIUM', 'HUSH', 'HUSH_SKINLESS', 'ISAAC', 'THE_LAMB',
    'ULTRA_GREED',
})
local hazards = entityTypes({
    'DUMMY', 'FIREPLACE', 'GENERIC_PROP', 'ENVIRONMENT', 'TRIGGER_OUTPUT',
    'STONEY', 'DEATHS_HEAD', 'FLESH_DEATHS_HEAD', 'DUSTY_DEATHS_HEAD', 'FROZEN_ENEMY',
})

local function scriptedPhase(npc)
    local kind, variant = npc.Type, npc.Variant
    if not scripted[kind] then return false end
    if variant == 0 then return true end
    if kind == EntityType.ENTITY_MOTHER then return variant == 10 end
    if kind == EntityType.ENTITY_DOGMA then return variant == 2 end
    if kind == EntityType.ENTITY_BEAST then
        return variant == 10 or variant == 20 or variant == 30 or variant == 40
    end
    if kind == EntityType.ENTITY_MOMS_HEART or kind == EntityType.ENTITY_ULTRA_GREED then return variant == 1 end
    if kind == EntityType.ENTITY_ISAAC then return variant == 1 or variant == 2 end
    return false
end

local function entityKey(npc)
    return tostring(npc.InitSeed)
end

local function entityRecord(npc, state)
    local native = EntitySaveStateManager and EntitySaveStateManager.TryGetEntityData(mod, npc)
    local record = native and native.samiraEncounter
    if record then
        state.entities[record.key] = record
        return record
    end
    return state.entities[entityKey(npc)]
end

local function recordEntity(npc, state, role)
    local record = {key = entityKey(npc), role = role}
    if EntitySaveStateManager then
        local native = EntitySaveStateManager.GetEntityData(mod, npc)
        native.samiraEncounter = record
    end
    state.entities[record.key] = record
    return record
end

local function phaseKey(npc)
    return npc.Type .. ':' .. npc.Variant .. ':' .. npc.SubType
end

function Encounters.reset()
    roomId, saved, scanned, spawning = nil, nil, false, false
    updatingNpc, spawnOwners, recentSplits = nil, {}, {}
end

local function roomState(room)
    local level = game:GetLevel()
    local key = table.concat({'encounters', level:GetDimension(),
        level:GetCurrentRoomDesc().SafeGridIndex, room:GetSpawnSeed()}, ':')
    if key ~= roomId then
        roomId, scanned = key, false
        saved = items.getRoomState(key)
        saved.entities = saved.entities or {}
    end
    return saved
end

local function npcOwner(npc)
    local parent = npc.ParentNPC or npc.Parent
    if parent and parent:ToNPC() then return parent, true end
    local spawner = npc.SpawnerEntity
    if spawner and spawner:ToNPC() then return spawner, false end
    return nil, false
end

local function eligible(npc)
    return npc and npc:Exists() and not npc:IsDead() and not hazards[npc.Type]
        and not npc:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

local function canShutDoors(npc)
    local predicate = npc.CanShutDoors
    if type(predicate) == 'function' then return predicate(npc) end
    return predicate == true
end

local function bossSummon(npc)
    if npc.Type ~= EntityType.ENTITY_BEAST then return false end
    local variant = npc.Variant
    return variant == 11 or variant == 21 or variant == 22 or variant == 42
end

local function applyBossHealth(npc, record, restored)
    local phase = phaseKey(npc)
    local previous = record.phases[phase]
    if previous then
        if restored and npc.MaxHitPoints == previous.base then npc.MaxHitPoints = previous.boosted end
        return
    end
    if record.family == EntityType.ENTITY_DELIRIUM and record.boostedMax then return end
    if not scriptedPhase(npc) then return end
    if npc.MaxHitPoints <= 0 or npc.HitPoints <= 0 then return end
    -- Some phases morph the same NPC and keep its already increased health.
    if npc.MaxHitPoints ~= record.boostedMax then
        local health = npc.HitPoints
        record.baseMax = npc.MaxHitPoints
        npc.MaxHitPoints = record.baseMax * 2
        npc.HitPoints = health * 2
        record.boostedMax = npc.MaxHitPoints
    end
    record.phases[phase] = {base = record.baseMax, boosted = record.boostedMax}
end

local function clonePosition(npc, player, room)
    local offset = math.max(24, npc.Size * 2 + 8)
    local baseAngle = npc.InitSeed % 360
    for index = 0, 7 do
        local candidate = npc.Position + Vector(offset, 0):Rotated(baseAngle + index * 45)
        if room:IsPositionInRoom(candidate, npc.Size)
            and room:GetGridCollisionAtPos(candidate) == GridCollisionClass.COLLISION_NONE
            and candidate:Distance(player.Position) >= npc.Size + player.Size + 12 then
            return candidate
        end
    end
    return npc.Position
end

local function cloneNpc(npc, player, room, state)
    local seed = (npc.InitSeed ~ 0x39F6A1C5) & 0x7FFFFFFF
    while seed == 0 or seed == npc.InitSeed or state.entities[tostring(seed)] do
        seed = (seed + 1) & 0x7FFFFFFF
    end
    local position = clonePosition(npc, player, room)
    spawning = true
    local ok, entity = pcall(game.Spawn, game, npc.Type, npc.Variant, position, Vector.Zero, nil, npc.SubType, seed)
    spawning = false
    local clone = ok and entity and entity:ToNPC()
    if not clone then return false end
    spawnOwners[entityKey(clone)] = nil
    recordEntity(clone, state, 'clone')
    local champion = npc:GetChampionColorIdx()
    if champion >= 0 and clone:GetChampionColorIdx() ~= champion then
        clone:MakeChampion(seed, champion, false)
    end
    clone.MaxHitPoints = npc.MaxHitPoints
    clone.HitPoints = npc.HitPoints
    return true
end

local function splitChild(npc)
    local clock = game:GetFrameCount()
    for _, split in ipairs(recentSplits) do
        if clock - split.clock <= 2 and npc.Type == split.kind and npc.Variant == split.variant
            and npc.Position:Distance(split.position) <= 64 then
            return true
        end
    end
    return false
end

local function process(npc, player, room, state, maySpawn)
    if not eligible(npc) then return end
    local existing = entityRecord(npc, state)
    if existing then
        if existing.role == 'scripted' then applyBossHealth(npc, existing, not maySpawn) end
        return
    end
    if not maySpawn then
        recordEntity(npc, state, 'restored')
        return
    end
    local owner, attached = npcOwner(npc)
    local ownerRecord = owner and entityRecord(owner, state)
    local inferredOwner = spawnOwners[entityKey(npc)]
    spawnOwners[entityKey(npc)] = nil
    local ownerIsScripted
    if ownerRecord then
        ownerIsScripted = ownerRecord.role == 'scripted' or ownerRecord.role == 'part'
    elseif owner then
        ownerIsScripted = scripted[owner.Type] and not bossSummon(owner)
    else
        ownerIsScripted = inferredOwner == 'scripted' or not inferredOwner and scripted[npc.SpawnerType]
    end
    local specialSummon = bossSummon(npc)
    if scripted[npc.Type] and not specialSummon then
        -- Hands, props and attached actors share the encounter's health or AI.
        if not scriptedPhase(npc) or attached and phaseKey(owner) == phaseKey(npc) then
            recordEntity(npc, state, 'part')
            return
        end
        local root = recordEntity(npc, state, 'scripted')
        root.family, root.phases = npc.Type, {}
        applyBossHealth(npc, root)
        return
    end
    if attached and not specialSummon or splitChild(npc)
        or (owner or inferredOwner or (npc.SpawnerType or 0) > 0) and not ownerIsScripted then
        recordEntity(npc, state, 'child')
        return
    end
    if not npc:IsActiveEnemy(false) or not (canShutDoors(npc) or specialSummon and npc:IsVulnerableEnemy()) then return end
    local record = recordEntity(npc, state, 'original')
    if not cloneNpc(npc, player, room, state) then record.cloneFailed = true end
end

local function prepare()
    if spawning then return end
    local player = getPlayer()
    if not player then return end
    local room = game:GetRoom()
    local state = roomState(room)
    if not scanned then
        local maySpawn = room:IsFirstVisit() and not state.entered and not suppressInitialSpawn
        state.entered, scanned, suppressInitialSpawn = true, true, false
        -- Snapshot before cloning so the resulting NPCs cannot enter the census.
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            process(entity:ToNPC(), player, room, state, maySpawn)
        end
    end
    return player, room, state
end

function Encounters.update()
    updatingNpc = nil
    local clock = game:GetFrameCount()
    for index = #recentSplits, 1, -1 do
        if clock - recentSplits[index].clock > 2 then table.remove(recentSplits, index) end
    end
    prepare()
end

local function onNPC(npc)
    local player, room, state = prepare()
    if player then process(npc, player, room, state, true) end
end

local function report()
    if not getPlayer() then
        Isaac.ConsoleOutput('Samira encounters inactive.\n')
        return
    end
    local room = game:GetRoom()
    local state = roomState(room)
    local copies, boosted, failed = 0, 0, 0
    for _, record in pairs(state.entities) do
        if record.role == 'clone' then copies = copies + 1 end
        if record.role == 'scripted' and record.boostedMax then boosted = boosted + 1 end
        if record.cloneFailed then failed = failed + 1 end
    end
    Isaac.ConsoleOutput(('Samira encounters: %d copies, %d boosted bosses, %d failed copies, %d living enemies, %d living bosses.\n')
        :format(copies, boosted, failed, room:GetAliveEnemiesCount(), room:GetAliveBossesCount()))
end

local function recordSplit(entity)
    if not saved or not getPlayer() then return end
    local record = entityRecord(entity, saved)
    if not record or record.role == 'restored' then return end
    local kind, variant = entity.Type, entity.Variant
    local childType, childVariant
    if kind == EntityType.ENTITY_FISTULA_BIG then
        childType, childVariant = EntityType.ENTITY_FISTULA_MEDIUM, 0
    elseif kind == EntityType.ENTITY_FISTULA_MEDIUM then
        childType, childVariant = EntityType.ENTITY_FISTULA_SMALL, 0
    elseif kind == EntityType.ENTITY_ENVY and variant < 30 then
        childType, childVariant = kind, variant + 10
    end
    if childType then
        recentSplits[#recentSplits + 1] = {
            kind = childType, variant = childVariant, position = entity.Position, clock = game:GetFrameCount(),
        }
    end
end

function Encounters.init(modRef, currentGame, getSamiraPlayer, itemModule)
    mod, game, getPlayer, items = modRef, currentGame, getSamiraPlayer, itemModule
    Encounters.reset()
    mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, Encounters.reset)
    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, continued)
        Encounters.reset()
        suppressInitialSpawn = continued
    end)
    mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, Encounters.reset)
    if ModCallbacks.MC_POST_GLOWING_HOURGLASS_LOAD then
        mod:AddCallback(ModCallbacks.MC_POST_GLOWING_HOURGLASS_LOAD, function()
            Encounters.reset()
            suppressInitialSpawn = true
        end)
    end
    mod:AddCallback(ModCallbacks.MC_PRE_NPC_UPDATE, function(_, npc)
        updatingNpc = nil
        onNPC(npc)
        if not spawning and saved and getPlayer() then
            local record = entityRecord(npc, saved)
            if record and record.role ~= 'restored' then
                updatingNpc = {kind = record.role == 'scripted' and 'scripted' or 'child', npc = npc}
            end
        end
    end)
    mod:AddCallback(ModCallbacks.MC_NPC_UPDATE, function(_, npc)
        if updatingNpc and GetPtrHash(updatingNpc.npc) == GetPtrHash(npc) then updatingNpc = nil end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_NPC_INIT, function(_, npc)
        if spawning then
            spawnOwners[entityKey(npc)] = 'child'
        elseif updatingNpc then
            spawnOwners[entityKey(npc)] = updatingNpc.kind
        end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_ENTITY_KILL, function(_, entity) recordSplit(entity) end)
    mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, entity)
        local npc = entity:ToNPC()
        if npc then onNPC(npc) end
    end)
    mod:AddCallback(ModCallbacks.MC_PRE_SPAWN_CLEAN_AWARD, function()
        if spawning then return true end
    end)
    mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command)
        if command == 'samiradoubles' then report() end
    end)
    if Console and Console.RegisterCommand then
        Console.RegisterCommand('samiradoubles', 'Show Samira encounter status', 'samiradoubles', false, AutocompleteType.NONE)
    end
end

return Encounters
