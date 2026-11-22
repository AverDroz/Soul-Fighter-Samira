local Items = {}
local catalog = include('samira_items_data')
local json = require('json')

local mod, game, getPlayer, combat, weapons, kills, attachSettings, yone
local defeat
local ids, rng
local vampProbe
local run, room, clock, directContext, previousRoom, rewindRoom
local cooldownCheckpoints, loadingCheckpoint, pendingCheckpoint = {}, nil, nil
local resetPrefix = 'abilityReset:'
local queues = {}
local statFlags
local activeStats = false
local steelRange, steelChargeFrames, steelCooldownFrames = 80, 60, 300

local function isYone(p)
    return p and yone and yone.is and yone.is(p) or false
end

local function itemCombat(p)
    if isYone(p) then return yone end
    return combat
end

-- Only offer items whose effects have a useful melee/Yone interpretation.
-- This affects newly generated bonus stock, not native or persisted stock.
local yoneShop = {}
for _, id in ipairs({1001, 3006, 3009, 3031, 3032, 3036, 3053, 3071,
    3072, 3084, 3153, 3158, 3161, 3171, 3172, 3814, 6610, 6672,
    6675, 6676, 6692, 6696, 6697}) do yoneShop[id] = true end

function Items.shopEligible(p, riotId)
    return not isYone(p) or yoneShop[riotId] == true
end
local cooldownKeys = {
    vamp = true, spellblade = true, ruinedKing = true, umbral = true, yunTalCooldown = true,
    navori = true, voltaic = true, bastion = true, eclipse = true,
}
local roomCarry = {'effects', 'barrageShots', 'spellblade', 'shojin', 'eclipseKind', 'energized',
    'energizedDistance', 'stormHits'}
local executionBossTypes = {}
for _, name in ipairs({
    'MONSTRO', 'MONSTRO2', 'CHUB', 'GURDY', 'GURDY_JR', 'DUKE', 'PEEP', 'BLOAT',
    'WIDOW', 'DINGLE', 'DANGLE', 'MEGA_MAW', 'MEGA_FATTY', 'GATE', 'CAGE', 'MAMA_GURDY',
    'PIN', 'GEMINI', 'LOKI', 'LOKII', 'FISTULA_BIG', 'FISTULA_MEDIUM', 'FISTULA_SMALL',
    'FAMINE', 'PESTILENCE', 'WAR', 'DEATH', 'CONQUEST', 'HEADLESS_HORSEMAN', 'HORSEMAN_HEAD',
    'BIG_HORN', 'LITTLE_HORN', 'RAG_MAN', 'RAG_MEGA', 'URIEL', 'GABRIEL', 'MOM', 'MOMS_HEART',
    'ISAAC', 'MEGA_SATAN_2', 'HUSH', 'DELIRIUM', 'BEAST', 'SINGE', 'BUMBINO',
    'MIN_MIN', 'CLOG', 'SCOURGE', 'COLOSTOMIA', 'CADAVRA', 'TURDLET',
}) do
    local entityType = EntityType['ENTITY_' .. name]
    if entityType then executionBossTypes[entityType] = true end
end

local function clone(value)
    if type(value) ~= 'table' then return value end
    local result = {}
    for key, member in pairs(value) do result[key] = clone(member) end
    return result
end

local function entityKey(entity)
    return GetPtrHash and GetPtrHash(entity) or entity.InitSeed
end

local function same(a, b)
    return a and b and entityKey(a) == entityKey(b)
end

local function boss(entity)
    return entity:IsBoss() or entity.Type == EntityType.ENTITY_ENVY
        or entity.Type == EntityType.ENTITY_SLOTH or entity.Type == EntityType.ENTITY_LUST
        or entity.Type == EntityType.ENTITY_WRATH or entity.Type == EntityType.ENTITY_GLUTTONY
        or entity.Type == EntityType.ENTITY_GREED or entity.Type == EntityType.ENTITY_PRIDE
end

local function hushOpening(entity)
    return entity.Type == EntityType.ENTITY_ISAAC and LevelStage and game:GetLevel():GetStage() == LevelStage.STAGE4_3
end

local function bossKey(entity)
    if entity.Type == EntityType.ENTITY_MEGA_SATAN_2 then return 'mega_satan' end
    if entity.Type == EntityType.ENTITY_MEGA_SATAN then return 'mega_satan' end
    if entity.Type == EntityType.ENTITY_HUSH or entity.Type == EntityType.ENTITY_HUSH_SKINLESS
        or hushOpening(entity) then return 'hush' end
    if entity.Type == EntityType.ENTITY_MOTHER then return 'mother' end
    local parent = entity.Parent
    if parent and parent:Exists() and parent.Type == entity.Type then entity = parent end
    return tostring(entity.InitSeed)
end

local function validEnemy(entity)
    return entity and entity:Exists() and not entity:IsDead() and entity.HitPoints > 0
        and entity.Type ~= EntityType.ENTITY_FIREPLACE and entity:IsActiveEnemy(false)
        and entity:IsVulnerableEnemy() and not entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

local function trainingDummy(entity)
    return entity.Type == EntityType.ENTITY_DUMMY and entity:Exists() and not entity:IsDead()
        and entity.HitPoints > 0
end

local function executionAllowed(entity)
    -- Some phase entities have a fresh health bar. Require an identified
    -- damageable boss form before attempting the native low-health hit.
    return not boss(entity) or executionBossTypes[entity.Type] == true and not hushOpening(entity)
end

local function mortalDamage(entity)
    return entity:IsDead() or entity.HitPoints <= 0 or entity:HasMortalDamage()
end

local function hostileProjectile(entity)
    if not entity or entity.Type ~= EntityType.ENTITY_PROJECTILE or not entity:Exists()
        or entity:IsDead() or entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then return false end
    local projectile = entity:ToProjectile()
    local spawner = entity.SpawnerEntity
    return not projectile:HasProjectileFlags(ProjectileFlags.CANT_HIT_PLAYER)
        and (not spawner or spawner.Type ~= EntityType.ENTITY_PLAYER
            and not spawner:HasEntityFlags(EntityFlag.FLAG_FRIENDLY))
end

local function enemyDamage(flags, source)
    if not source or not source.Entity then return false end
    local banned = (DamageFlag.DAMAGE_FAKE or 0) | (DamageFlag.DAMAGE_CURSED_DOOR or 0)
        | (DamageFlag.DAMAGE_IV_BAG or 0) | (DamageFlag.DAMAGE_DEVIL or 0)
        | (DamageFlag.DAMAGE_CHEST or 0) | (DamageFlag.DAMAGE_SPIKES or 0)
    if flags & banned ~= 0 then return false end
    local entity = source.Entity
    for _ = 1, 4 do
        if entity.Type == EntityType.ENTITY_PLAYER or entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then
            return false
        end
        if hostileProjectile(entity) or entity:IsActiveEnemy(false) then return true end
        entity = entity.SpawnerEntity or entity.Parent
        if not entity then return false end
    end
    return false
end

local function inventory(p)
    local owned, stats, counts = {}, {}, {}
    for _, row in ipairs(catalog) do
        local id = ids[row.riotId]
        local count = id and p:GetCollectibleNum(id, true) or 0
        if count > 0 then
            owned[row.riotId] = true
            counts[#counts + 1] = tostring(row.riotId) .. ':' .. tostring(count)
            for key, value in pairs(row.stats) do
                stats[key] = (stats[key] or 0) + value * count
            end
        end
    end
    return owned, stats, table.concat(counts, ',')
end

local function roomKey()
    local level = game:GetLevel()
    return tostring(level:GetDimension()) .. ':' .. tostring(level:GetCurrentRoomDesc().SafeGridIndex)
end

local function floorKey()
    local level = game:GetLevel()
    return tostring(level:GetStage()) .. ':' .. tostring(level:GetDungeonPlacementSeed())
end

local function ensureFloor()
    local key = floorKey()
    if run.floorKey ~= key then
        run.floorKey = key
        run.floor = {lifeline = {}, rooms = {}, cleared = {}}
    end
    return run.floor
end

local function freshRun()
    return {
        version = 1, seed = game:GetSeeds():GetStartSeed(), rolls = 0, hubris = 0,
        heartsteel = 0, heartsteelPairs = 0, warmogGranted = 0, warmogClear = 0,
        yunTalHits = 0, gluttonous = 0, krakenHits = 0, hullHits = 0,
        floor = {lifeline = {}, rooms = {}, cleared = {}}, timers = {}, backpack = {}, combatCooldowns = {},
    }
end

local function resetRoom()
    local floor = ensureFloor()
    room = {
        key = roomKey(), edge = true, edgeTicks = 0, enemies = {}, effects = {}, pending = {},
        actionSequence = 0, spellblade = false, combatSeen = not game:GetRoom():IsClear(),
        bossesDefeated = {}, bastionBosses = {}, skyBosses = {},
    }
    room.combatSeen = room.combatSeen and not floor.cleared[room.key]
    if run.current and run.current.key == room.key then
        room.damaged, room.executed, room.skyHeal, room.yunTal = run.current.damaged,
            run.current.executed, run.current.skyHeal, run.current.yunTal
        room.edge, room.edgeTicks = run.current.edge ~= false, run.current.edgeTicks or 0
        room.savedEnemies = run.current.enemies
        room.restoredAt = clock
        room.bossesDefeated = run.current.bossesDefeated or {}
        room.bastionBosses = run.current.bastionBosses or {}
        room.skyBosses = run.current.skyBosses or {}
        room.combatSeen = run.current.combatSeen or room.combatSeen
        for _, key in ipairs(roomCarry) do
            if run.current[key] ~= nil then room[key] = clone(run.current[key]) end
        end
        for key, remaining in pairs(room.effects) do room.effects[key] = clock + remaining end
        room.bloodShield = run.current.bloodShield
    end
    queues = {}
end

local function save(shouldSave)
    if not run or not shouldSave then return end
    if room then
        local enemies = clone(room.savedEnemies or {})
        for _, enemy in pairs(room.enemies) do
            if enemy.entity:Exists() then
                enemies[tostring(enemy.entity.InitSeed)] = {
                    steelCounted = enemy.steelCounted,
                    steelReady = math.max(0, (enemy.steelReady or 0) - clock),
                    steelNear = enemy.steelNear,
                    bleedEnd = enemy.bleedEnd and math.max(0, enemy.bleedEnd - clock),
                    bleedNext = enemy.bleedNext and math.max(0, enemy.bleedNext - clock),
                    bleedPower = enemy.bleedPower,
                    cleave = enemy.cleave, cleaveEnd = enemy.cleaveEnd and math.max(0, enemy.cleaveEnd - clock),
                    ruinedKing = enemy.ruinedKing,
                }
            end
        end
        run.current = {
            key = room.key, damaged = room.damaged, executed = room.executed, skyHeal = room.skyHeal,
            yunTal = room.yunTal, edge = room.edge, edgeTicks = room.edgeTicks, enemies = enemies,
            bossesDefeated = room.bossesDefeated, combatSeen = room.combatSeen, bloodShield = room.bloodShield,
            bastionBosses = room.bastionBosses, skyBosses = room.skyBosses,
        }
        for _, key in ipairs(roomCarry) do run.current[key] = clone(room[key]) end
        for key, time in pairs(run.current.effects) do run.current.effects[key] = math.max(0, time - clock) end
    end
    local saved = clone(run)
    saved.cooldownCheckpoints = cooldownCheckpoints
    local driver = itemCombat(getPlayer())
    if driver and driver.exportCooldowns then saved.combatCooldowns = driver.exportCooldowns(clock) end
    for key, time in pairs(saved.timers) do saved.timers[key] = math.max(0, time - clock) end
    if attachSettings then attachSettings(saved) end
    mod:SaveData(json.encode(saved))
end

local function resetRng()
    rng = RNG()
    rng:SetSeed(math.max(1, run.seed & 0xffffffff), 35)
    for _ = 1, run.rolls do rng:Next() end
end

local function roll()
    run.rolls = run.rolls + 1
    return rng:RandomFloat()
end

local function newRun(continued)
    local initial = freshRun()
    cooldownCheckpoints, loadingCheckpoint, pendingCheckpoint = {}, nil, nil
    if continued and mod:HasData() then
        local ok, saved = pcall(json.decode, mod:LoadData())
        if ok and type(saved) == 'table' and saved.version == initial.version
            and saved.seed == initial.seed then
            for key in pairs(initial) do
                if saved[key] ~= nil then initial[key] = saved[key] end
            end
            initial.floorKey, initial.current, initial.enabled = saved.floorKey, saved.current, saved.enabled
            if type(saved.cooldownCheckpoints) == 'table' then cooldownCheckpoints = saved.cooldownCheckpoints end
        end
    end
    run, room, previousRoom, rewindRoom, clock = initial, nil, nil, nil, game:GetFrameCount()
    for key, ticks in pairs(run.timers) do run.timers[key] = clock + ticks end
    directContext, activeStats = nil, false
    vampProbe = {hits = 0, dummyHits = 0, dummyUnmatched = 0, rolls = 0, heals = 0, shields = 0}
    resetRng()
end

local function ready(key)
    local timers = cooldownKeys[key] and run.timers or room.effects
    return clock >= (timers[key] or 0)
end

local function start(key, ticks)
    local timers = cooldownKeys[key] and run.timers or room.effects
    timers[key] = clock + ticks
end

local function live(key)
    return not ready(key)
end

local function state(p)
    if not run then newRun(false) end
    if not room then resetRoom() end
    if not room.owned then room.owned, room.stats = inventory(p) end
    return room.owned, room.stats
end

function Items.getRoomState(key)
    if not run then newRun(false) end
    local floor = ensureFloor()
    if not floor.rooms[key] then floor.rooms[key] = {} end
    return floor.rooms[key]
end

function Items.getInventoryState()
    if not run then newRun(false) end
    return run.backpack
end

function Items.claimCombatRoomReset()
    if game:GetRoom():IsClear() then return false end
    local saved = Items.getRoomState(resetPrefix .. roomKey())
    if saved.used then return false end
    saved.used = true
    return true
end

local function saveCooldownCheckpoint(_, slot)
    local p = getPlayer()
    local driver = itemCombat(p)
    if not run or not p or not driver or not driver.exportCooldowns then return end
    local claims = {}
    for key, record in pairs(run.floor.rooms) do
        if key:sub(1, #resetPrefix) == resetPrefix and record.used then claims[key] = true end
    end
    cooldownCheckpoints['slot' .. slot] = {remaining = driver.exportCooldowns(game:GetFrameCount()),
        floorKey = run.floorKey, claims = claims}
end

-- Slot snapshots are independent of the ordinary run save and of one
-- another. Restore only after the engine settles on the destination room.
function Items.applyCooldownCheckpoint(frame)
    local snap = pendingCheckpoint
    pendingCheckpoint = nil
    if type(snap) ~= 'table' or type(snap.remaining) ~= 'table' then return end
    local driver = itemCombat(getPlayer())
    if not driver or not driver.reset or not driver.restoreCooldowns then return end
    driver.reset(true)
    driver.restoreCooldowns(snap.remaining, frame)
    if snap.floorKey == floorKey() and type(snap.claims) == 'table' then
        local rooms = ensureFloor().rooms
        for key in pairs(rooms) do
            if key:sub(1, #resetPrefix) == resetPrefix then rooms[key] = nil end
        end
        for key, used in pairs(snap.claims) do
            if used == true and type(key) == 'string' and key:sub(1, #resetPrefix) == resetPrefix then
                rooms[key] = {used = true}
            end
        end
    end
end

function Items.bindCombat(module)
    combat = module
end

function Items.bindWeapons(module) weapons = module end
function Items.bindKills(module) kills = module end

function Items.restoreCombatCooldowns()
    local driver = itemCombat(getPlayer())
    if run and driver and driver.restoreCooldowns then driver.restoreCooldowns(run.combatCooldowns, game:GetFrameCount()) end
end

function Items.cooldown(p, key, baseFrames)
    local owned, stats = state(p)
    local haste = stats.ability_haste or 0
    if owned[2517] then haste = haste + math.min(15, math.floor((stats.damage_flat or 0) / .4 + .00001)) end
    if key == 'r' then
        if owned[2512] then haste = haste + 30 end
        if owned[3073] then haste = haste + 30 end
    elseif owned[3161] then
        haste = haste + 25
    end
    return math.max(1, math.ceil(baseFrames * 100 / (100 + haste)))
end

function Items.attackInterval(p, baseFrames)
    local owned, stats = state(p)
    local speed = stats.attack_speed_pct or 0
    local native = 100 + speed
    if owned[2512] and ((room.barrageShots or 0) > 0 or room.barrageLastAt == clock)
        and live('barrage') then speed = speed + 25 end
    if owned[3073] and live('hexplate') then speed = speed + 25 end
    if owned[3032] and live('yunTal') then speed = speed + 30 end
    return math.max(1, math.ceil(baseFrames * native / (100 + speed)))
end

function Items.attackRange(p, baseRange)
    local owned = state(p)
    local range = baseRange
    if owned[2523] and live('hexoptics') then range = range + 20 end
    if owned[3094] and (room.energized == 3094 or room.energized == 3095) then range = range * 1.35 end
    return range
end

function Items.spectral(p)
    local owned = state(p)
    return owned[3046] == true
end

function Items.newAttack(p, nativeKind, tick)
    local owned, stats = state(p)
    clock = tick
    room.actionSequence = room.actionSequence + 1
    local kind = ({attack = 'aa', melee = 'aa', qmelee = 'q', q3 = 'q'})[nativeKind] or nativeKind
    local chance = (stats.crit_chance_pct or 0) / 100
    if owned[3032] then chance = chance + math.min(25, math.floor(run.yunTalHits / 5)) / 100 end
    if isYone(p) then
        chance = (kind == 'aa' or kind == 'q') and math.min(1, chance * 2) or 0
    end
    local barrage = kind == 'aa' and owned[2512] and live('barrage') and (room.barrageShots or 0) > 0
    if barrage then
        room.barrageShots = room.barrageShots - 1
        room.barrageLastAt = clock
    end
    return {
        id = room.actionSequence, room = room, player = p, kind = kind, clock = tick,
        origin = p.Position, hit = {},
        crit = barrage or chance >= 1 or chance > 0 and roll() < chance,
    }
end

function Items.onCast(p, key, tick)
    local owned = state(p)
    clock = tick
    if (owned[3078] or owned[3057]) and ready('spellblade') then
        room.spellblade = true
        start('spellbladeExpires', 120)
    end
    if key ~= 'r' then return end
    if owned[2512] then
        room.barrageShots = 3
        start('barrage', 180)
    end
    if owned[3073] then start('hexplate', 240) end
end

function Items.withContext(ctx, action)
    local previous = directContext
    directContext = ctx
    local result = table.pack(pcall(action))
    directContext = previous
    if not result[1] then error(result[2], 0) end
    return table.unpack(result, 2, result.n)
end

function Items.tagTear(p, tear, ctx)
    if not tear or not ctx then return end
    local owned = state(p)
    local data = tear:GetData()
    data.SamiraItemContext, data.SamiraItemPreviousPosition = ctx, tear.Position
    if ctx.kind == 'aa' and owned[3046] then tear:AddTearFlags(TearFlags.TEAR_SPECTRAL) end
    if owned[3094] and (room.energized == 3094 or room.energized == 3095)
        and not data.SamiraItemRangeExtended and tear.FallingSpeed and tear.FallingAcceleration then
        tear.FallingSpeed = tear.FallingSpeed / 1.35
        tear.FallingAcceleration = tear.FallingAcceleration / (1.35 * 1.35)
        data.SamiraItemRangeExtended = true
    end
end

local function contextFrom(p, source, extraSource)
    if weapons then
        local ctx, ranged = weapons.context(p, source, extraSource)
        if ctx and ctx.room == room then return ctx, ranged end
    end
    local entity = extraSource and extraSource.Entity or source and source.Entity
    if not entity then return end
    local ctx, ranged
    if entity.Type == EntityType.ENTITY_TEAR then
        ctx, ranged = entity:GetData().SamiraItemContext, true
    elseif same(entity, p) and not (extraSource and extraSource.Entity) then
        ctx = directContext
    end
    if ctx and not (weapons and ctx.nativeWeapon) and ctx.room == room and same(ctx.player, p) then return ctx, ranged end
end

local function enemyState(entity)
    local key = entityKey(entity)
    local result = room.enemies[key]
    if not result then
        result = {entity = entity, maxHP = entity.MaxHitPoints, cleave = 0}
        local seed = tostring(entity.InitSeed)
        local saved = room.savedEnemies and room.savedEnemies[seed]
        if saved then
            room.savedEnemies[seed] = nil
            result.steelCounted = saved.steelCounted
            local restored = room.restoredAt
            result.steelReady = restored + (saved.steelReady or 0)
            result.steelNear, result.cleave, result.ruinedKing = saved.steelNear, saved.cleave or 0, saved.ruinedKing
            if saved.bleedEnd and saved.bleedEnd > 0 then
                result.bleedEnd, result.bleedNext = restored + saved.bleedEnd, restored + saved.bleedNext
                result.bleedPower = saved.bleedPower or .15
            end
            if saved.cleaveEnd then result.cleaveEnd = restored + saved.cleaveEnd end
        end
        room.enemies[key] = result
    end
    return result
end

local function buffSpeed(owned, stats, native)
    local flat, percent = stats.move_speed_flat or 0, stats.move_speed_pct or 0
    if activeStats and room then
        if owned[3071] and live('cleaverSpeed') then flat = flat + .06
        elseif owned[3044] and live('cleaverSpeed') then flat = flat + .04 end
        if owned[3073] and live('hexplate') then percent = percent + 10 end
        if owned[3171] and live('crimson') then percent = percent + 8 end
        if owned[3095] and live('stormrazor') then percent = percent + 20 end
    end
    return (native + flat) * (1 + percent / 100)
end

local function cache(p, flag)
    local owned, stats = inventory(p)
    if flag == CacheFlag.CACHE_DAMAGE then
        local flat = (stats.damage_flat or 0) + (run and same(p, Isaac.GetPlayer(0)) and run.hubris * .1 or 0)
        local percent = (stats.lethality_damage_bonus_pct or 0) + (stats.armor_pen_damage_bonus_pct or 0)
        if owned[3053] then flat = flat + .35 end
        if owned[2501] then
            local extraHealth = (stats.health_red_hearts or 0) + (run and (run.heartsteel + run.warmogGranted) / 2 or 0)
            flat = flat + math.min(1, .2 * extraHealth)
        end
        if owned[3170] then
            local speed = (stats.move_speed_flat or 0) + (stats.move_speed_pct or 0) / 100
            flat = flat + .13 * math.min(5, math.floor(speed / .1 + .00001))
        end
        if activeStats and room and owned[6699] and live('voltaicLethality') then percent = percent + 2 end
        p.Damage = (p.Damage + flat) * (1 + percent / 100)
    elseif flag == CacheFlag.CACHE_SPEED then
        p.MoveSpeed = buffSpeed(owned, stats, p.MoveSpeed)
    elseif flag == CacheFlag.CACHE_FIREDELAY then
        local speed = stats.attack_speed_pct or 0
        if weapons and activeStats and room then
            if owned[2512] and (room.barrageShots or 0) > 0 and live('barrage') then speed = speed + 25 end
            if owned[3073] and live('hexplate') then speed = speed + 25 end
            if owned[3032] and live('yunTal') then speed = speed + 30 end
        end
        p.MaxFireDelay = (p.MaxFireDelay + 1) / (1 + speed / 100) - 1
    elseif flag == CacheFlag.CACHE_SIZE and run and run.heartsteel > 0 and same(p, Isaac.GetPlayer(0)) then
        p.SpriteScale = p.SpriteScale * (1 + .03 * run.heartsteel / 2)
    end
end

local function reevaluate(p, flags)
    p:AddCacheFlags(flags)
    p:EvaluateItems()
end

local function heal(p, amount)
    local capacity = p:GetEffectiveMaxHearts()
    local before = p:GetHearts()
    if before >= capacity then return false end
    p:AddHearts(amount)
    return p:GetHearts() > before
end

local function gainHeart(p, count)
    local old = p:GetMaxHearts()
    local cap = p.GetHeartLimit and p:GetHeartLimit() or 24
    if old + p:GetSoulHearts() + 2 * p:GetBoneHearts() >= cap then return 0 end
    p:AddMaxHearts(count, false)
    local added = math.max(0, p:GetMaxHearts() - old)
    if added > 0 then p:AddHearts(added) end
    return added
end

local function warmog(p, owned, stats)
    local total = stats.health_red_hearts or 0
    local id = ids[3083]
    local desired = owned[3083] and math.min(4, math.floor((total - 2.5 * p:GetCollectibleNum(id, true)) / 4)) or 0
    local delta = desired - run.warmogGranted
    if delta > 0 then
        run.warmogGranted = run.warmogGranted + gainHeart(p, delta)
    elseif delta < 0 then
        p:AddMaxHearts(delta, false)
        run.warmogGranted = desired
    end
end

local function slow(npc, p)
    npc:AddSlowing(EntityRef(p), 30, .7, Color(1, 1, 1, 1))
end

local function markEnergized(owned, item)
    if room.energized then return end
    local load = item or (owned[3095] and 3095 or owned[3094] and 3094)
    if load then room.energized = load end
end

local function prepareDamage(p, entity, amount, ctx, ranged)
    local owned, stats = state(p)
    local enemy = enemyState(entity)
    local isAA, firstTarget, first = ctx.kind == 'aa', not ctx.hit[entityKey(entity)], not ctx.accepted
    local plan = {ctx = ctx, first = first, firstTarget = firstTarget, ranged = ranged,
        mortalBefore = owned[2523] and mortalDamage(entity)}
    local modified = amount * (ctx.damageMultiplier or 1)
    if owned[2501] then
        local capacity = p:GetEffectiveMaxHearts()
        if capacity > 0 then modified = modified * (1 + .1 * (1 - math.min(1, p:GetHearts() / capacity))) end
    end
    if owned[3036] then
        modified = modified * (1 + .15 * math.max(0, math.min(1, (enemy.maxHP - 40) / 120)))
    end
    if owned[2523] and ranged then
        modified = modified * (1 + .1 * math.min(1, ctx.origin:Distance(entity.Position) / 100))
    end
    if owned[6696] and ctx.kind == 'r' then modified = modified * 1.2 end
    if owned[3161] and not isAA and live('shojin') then modified = modified * (1 + .03 * room.shojin) end
    if owned[3071] and clock < (enemy.cleaveEnd or 0) then modified = modified * (1 + .03 * enemy.cleave) end
    local bossId = (owned[6610] or owned[2520]) and boss(entity) and bossKey(entity)
    plan.sky = isAA and (not isYone(p) or first) and owned[6610] and room.combatSeen
        and bossId and not room.skyBosses[bossId] and bossId
    if (not isYone(p) or first) and (ctx.crit or plan.sky) then
        modified = modified * (1.5 + (stats.crit_multiplier_bonus or 0))
    end
    local heartsteelHit = isAA or ctx.kind == 'q' and first and isYone(p)
    if heartsteelHit and owned[3084] and (enemy.steelNear or 0) >= steelChargeFrames
        and clock >= (enemy.steelReady or 0) then
        plan.steel = true
        modified = modified * 1.5
    end
    if first and isAA then
        if owned[1043] then modified = modified + .3 end
        if owned[3153] then modified = modified + .25 * p.Damage end
        if owned[6672] and (run.krakenHits + 1) % 3 == 0 then modified = modified + .5 * p.Damage end
        if owned[3181] and (run.hullHits + 1) % 5 == 0 then modified = modified + 4 end
        if (owned[3078] or owned[3057]) and room.spellblade and live('spellbladeExpires') and ready('spellblade') then
            plan.spellblade, modified = true, modified + (owned[3078] and 3 or 1)
        end
    end
    if (owned[3179] or owned[3144]) and ready('umbral') then
        plan.umbral, modified = true, modified + (owned[3179] and 1.5 or .5)
    end
    if ranged and first and room.energized and owned[room.energized] then
        plan.energized = room.energized
        if plan.energized == 6699 then modified = modified + .4 * p.Damage end
        if plan.energized == 3095 then modified = modified + 1.4 end
        if owned[3094] and plan.energized ~= 6699 then modified = modified + 1.2 end
    end
    if owned[2520] then
        if ready('bastion') then plan.bastion, modified = true, modified + 1.5 end
        if bossId and not room.bastionBosses[bossId] then
            local bonus = .15 * enemy.maxHP
            if isYone(p) then bonus = math.min(bonus, 2 * p.Damage) end
            plan.bastionBoss, modified = bossId, modified + bonus
        end
    end
    room.pending[entityKey(entity)] = plan
    if modified ~= amount then return {Damage = modified} end
end

local function vampChances(owned, stats)
    local lifesteal = stats.lifesteal_chance_pct or 0
    local omni = stats.omnivamp_chance_pct or 0
    if owned[3008] then omni = omni + .15 * run.gluttonous end
    if owned[2517] and live('feast') then omni = omni + 1 end
    return lifesteal, omni
end

local function tryVamp(p, owned, stats, plan)
    if not plan.first then return end
    vampProbe.hits = vampProbe.hits + 1
    if plan.dummy then vampProbe.dummyHits = vampProbe.dummyHits + 1 end
    if not ready('vamp') then return end
    local maximum = p:GetEffectiveMaxHearts()
    if maximum <= 0 then return end
    local full = p:GetHearts() >= maximum
    local lifesteal, omni = vampChances(owned, stats)
    if plan.ctx.kind ~= 'aa' then lifesteal = 0 end
    local percent = full and (owned[3072] and lifesteal or 0) or lifesteal + omni
    if percent <= 0 then return end
    local chance, value = math.min(5, percent), roll() * 100
    vampProbe.rolls = vampProbe.rolls + 1
    vampProbe.lastChance, vampProbe.lastRoll = chance, value
    if value >= chance then return end
    if full then
        room.bloodShield = true
        vampProbe.shields = vampProbe.shields + 1
    elseif heal(p, 1) then
        vampProbe.heals = vampProbe.heals + 1
    else
        return
    end
    start('vamp', 240)
end

local function consumeEnergized(owned, plan)
    if not plan.energized then return end
    room.energized, room.energizedDistance, room.stormHits = nil, 0, 0
    if plan.energized == 6699 then start('voltaicLethality', 120) end
    if owned[3095] and plan.energized ~= 6699 then start('stormrazor', 45) end
end

local function procHeartsteel(p, enemy)
    enemy.steelNear, enemy.steelReady = 0, clock + steelCooldownFrames
    if not enemy.steelCounted then
        enemy.steelCounted = true
        run.heartsteelPairs = run.heartsteelPairs + 1
        if run.heartsteelPairs >= 4 then
            run.heartsteelPairs = 0
            run.heartsteel = run.heartsteel + gainHeart(p, 1)
            reevaluate(p, CacheFlag.CACHE_DAMAGE | CacheFlag.CACHE_SIZE)
        end
    end
    if ids.heartsteelSound then SFXManager():Play(ids.heartsteelSound, .85) end
end

local function autoProcs(p, entity, owned, plan, enemy)
    if plan.sky then
        room.skyBosses[plan.sky] = true
        if not room.skyHeal then
            room.skyHeal = true
            heal(p, 1)
        end
    end
    if not plan.first then return end
    if owned[3153] and ready('ruinedKing') then
        enemy.ruinedKing = (enemy.ruinedKing or 0) + 1
        if enemy.ruinedKing >= 3 then
            enemy.ruinedKing = 0
            start('ruinedKing', 180)
            slow(entity, p)
        end
    end
    if owned[6672] then run.krakenHits = (run.krakenHits + 1) % 3 end
    if owned[3181] then run.hullHits = (run.hullHits + 1) % 5 end
    if plan.spellblade then
        room.spellblade = false
        start('spellblade', 90)
    end
    if owned[3032] then
        run.yunTalHits = math.min(125, run.yunTalHits + 1)
        if room.combatSeen and not room.yunTal then
            room.yunTal = true
            if ready('yunTalCooldown') then
                start('yunTal', 180)
                start('yunTalCooldown', 600)
            end
        end
    end
    local driver = itemCombat(p)
    if owned[6675] and ready('navori') and driver and driver.reduceCooldowns then
        start('navori', 12)
        driver.reduceCooldowns(.15, clock)
    end
    if owned[3095] and not room.energized then
        room.stormHits = (room.stormHits or 0) + 1
        if room.stormHits >= 6 then markEnergized(owned, 3095) end
    end
end

local function firstCastHit(owned)
    if owned[3161] then
        room.shojin = math.min(4, (live('shojin') and room.shojin or 0) + 1)
        start('shojin', 180)
    end
    if owned[3171] then start('crimson', 120) end
    if owned[6699] and ready('voltaic') and not room.energized then
        markEnergized(owned, 6699)
        start('voltaic', 240)
    end
end

local function queueBolts(entity, damage)
    local targets = {}
    for _, other in ipairs(Isaac.FindInRadius(entity.Position, 50, EntityPartition.ENEMY)) do
        if not same(other, entity) and validEnemy(other) then targets[#targets + 1] = other end
    end
    table.sort(targets, function(a, b)
        local da, db = a.Position:Distance(entity.Position), b.Position:Distance(entity.Position)
        if da == db then return a.InitSeed < b.InitSeed end
        return da < db
    end)
    for index = 1, math.min(2, #targets) do
        queues[#queues + 1] = {entity = targets[index], amount = damage * .25, origin = entity.Position}
    end
end

local function axiomRefund(p, entity, enemy)
    if enemy.axiomRefunded or not enemy.deadSeen or not enemy.axiomAt or not isYone(p) or not state(p)[6696] then return end
    local now = game:GetFrameCount()
    if now < enemy.axiomAt or now - enemy.axiomAt > 90 then return end
    local driver = itemCombat(p)
    if driver and driver.reduceUltimateCooldown then
        enemy.axiomRefunded = true
        driver.reduceUltimateCooldown(boss(entity) and .10 or .03, now)
    end
end

local function finishDamage(p, entity, amount, source, extraSource)
    local ctx = contextFrom(p, source, extraSource)
    if not ctx then return end
    local key = entityKey(entity)
    local plan = room.pending[key]
    if not plan or plan.ctx ~= ctx then return end
    room.pending[key] = nil
    -- The native engine can buffer HP subtraction. Reaching the post-damage
    -- callback with our matching plan confirms acceptance even before HP drops.
    if amount <= 0 then return end

    local owned, stats = state(p)
    ctx.accepted, ctx.hit[key] = true, true
    local driver = itemCombat(p)
    if driver and driver.acceptHit then driver.acceptHit(ctx, clock) end
    if not isYone(p) and kills and not plan.dummy then kills.acceptHit(entity, ctx, clock) end
    if plan.dummy then
        tryVamp(p, owned, stats, plan)
        return
    end
    local enemy = enemyState(entity)
    enemy.directAt = clock
    enemy.axiomAt = game:GetFrameCount()
    axiomRefund(p, entity, enemy)
    if owned[2523] and not plan.mortalBefore and mortalDamage(entity) then
        enemy.hexopticsKill = true
        if enemy.deadSeen then defeat(p, entity, enemy) end
    end
    if plan.bastion then start('bastion', 240) end
    if plan.umbral then start('umbral', 240) end
    if plan.bastionBoss then room.bastionBosses[plan.bastionBoss] = true end
    if owned[3033] or owned[6609] or owned[3123] then
        local power = (owned[3033] or owned[6609]) and .15 or .075
        if clock > (enemy.bleedEnd or -1) then
            enemy.bleedNext, enemy.bleedPower = clock + 30, power
        else
            enemy.bleedPower = math.max(enemy.bleedPower or .15, power)
        end
        enemy.bleedEnd = clock + 90
    end
    if owned[3044] then start('cleaverSpeed', 60) end
    if owned[3071] then
        if plan.firstTarget then
            enemy.cleave = math.min(5, (clock < (enemy.cleaveEnd or 0) and enemy.cleave or 0) + 1)
            enemy.cleaveEnd = clock + 180
        end
        start('cleaverSpeed', 60)
    end
    if plan.steel then procHeartsteel(p, enemy) end
    if ctx.kind == 'aa' then
        autoProcs(p, entity, owned, plan, enemy)
    else
        if plan.first then firstCastHit(owned) end
        if owned[6694] and plan.firstTarget and entity.HitPoints > 0 and entity.HitPoints < enemy.maxHP * .5 then
            slow(entity, p)
        end
    end
    if plan.first and owned[6692] then
        if room.eclipseKind and room.eclipseKind ~= ctx.kind and live('eclipsePair') and ready('eclipse') then
            start('eclipseShield', 60)
            start('eclipse', 360)
            room.eclipseKind = nil
        else
            room.eclipseKind = ctx.kind
            start('eclipsePair', 60)
        end
    end
    consumeEnergized(owned, plan)
    tryVamp(p, owned, stats, plan)

    if plan.ranged and plan.first and owned[3085] then queueBolts(entity, amount) end
    if owned[6676] and not enemy.queuedExecution and executionAllowed(entity) then
        enemy.queuedExecution = true
        queues[#queues + 1] = {entity = entity, enemy = enemy, execution = true, ready = game:GetFrameCount() + 1}
    end
end

local function currentLife(p)
    return p:GetHearts() + p:GetSoulHearts() + 2 * p:GetBoneHearts()
end

local function beforeDamage(entity, amount, flags, source, _, extraSource)
    local p = getPlayer()
    if not p or amount <= 0 then return end
    local owned = state(p)
    if same(entity, p) then
        local hostile = enemyDamage(flags, source)
        if hostile then
            local projectile = source and source.Entity
            local projectileExcluded = (DamageFlag.DAMAGE_EXPLOSION or 0) | (DamageFlag.DAMAGE_LASER or 0)
            if owned[3814] and room.edge and flags & projectileExcluded == 0 and hostileProjectile(projectile) then
                room.edge, room.edgeTicks = false, 0
                projectile:Remove()
                return false
            end
            if owned[3072] and room.bloodShield then
                room.bloodShield = false
                return false
            end
            if owned[6692] and live('eclipseShield') then
                room.effects.eclipseShield = nil
                return false
            end
        end
        room.incoming = {life = currentLife(p), hostile = hostile}
        return
    end
    local ctx, ranged = contextFrom(p, source, extraSource)
    local incidental = (DamageFlag.DAMAGE_POISON_BURN or 0) | (DamageFlag.DAMAGE_EXPLOSION or 0)
        | (DamageFlag.DAMAGE_LASER or 0) | (DamageFlag.DAMAGE_FIRE or 0)
    local dummy = trainingDummy(entity)
    local secondary = (DamageFlag.DAMAGE_POISON_BURN or 0) | (DamageFlag.DAMAGE_FIRE or 0)
    if not ctx or flags & secondary ~= 0 or (flags & incidental ~= 0 and not ctx.nativeWeapon) then
        if dummy then vampProbe.dummyUnmatched = vampProbe.dummyUnmatched + 1 end
        return
    end
    if dummy then
        room.pending[entityKey(entity)] = {ctx = ctx, first = not ctx.accepted, dummy = true}
        if ctx.damageMultiplier and ctx.damageMultiplier ~= 1 then return {Damage = amount * ctx.damageMultiplier} end
    elseif validEnemy(entity) then
        return prepareDamage(p, entity, amount, ctx, ranged)
    elseif ctx.damageMultiplier and ctx.damageMultiplier ~= 1 then
        return {Damage = amount * ctx.damageMultiplier}
    end
end

local function afterDamage(entity, amount, flags, source, _, extraSource)
    local p = getPlayer()
    if not p or not room then return end
    if not same(entity, p) then
        local incidental = (DamageFlag.DAMAGE_POISON_BURN or 0) | (DamageFlag.DAMAGE_EXPLOSION or 0)
            | (DamageFlag.DAMAGE_LASER or 0) | (DamageFlag.DAMAGE_FIRE or 0)
        local ctx = contextFrom(p, source, extraSource)
        local secondary = (DamageFlag.DAMAGE_POISON_BURN or 0) | (DamageFlag.DAMAGE_FIRE or 0)
        if flags & secondary == 0 and (flags & incidental == 0 or ctx and ctx.nativeWeapon) then
            finishDamage(p, entity, amount, source, extraSource)
        end
        return
    end

    local hit = room.incoming
    room.incoming = nil
    if not hit or amount <= 0 or currentLife(p) >= hit.life then return end
    room.damaged = true
    local owned, stats = state(p)
    if (stats.iframes_pct or 0) > 0 then
        p:SetMinDamageCooldown(math.ceil(p:GetDamageCooldown() * (1 + stats.iframes_pct / 100)))
    end
    if not hit.hostile then return end

    local capacity = p:GetEffectiveMaxHearts()
    if capacity <= 0 or p:GetHearts() > capacity * .30 or p:IsDead() or currentLife(p) <= 0 then return end
    local lifeline = ensureFloor().lifeline
    if isYone(p) and lifeline.yone then return end
    for _, id in ipairs({6673, 3053, 2525}) do
        local key = tostring(id)
        if owned[id] and not lifeline[key] then
            lifeline[key] = true
            if isYone(p) then lifeline.yone = true end
            heal(p, isYone(p) and 3 or 6)
            return
        end
    end
end

defeat = function(p, entity, enemy)
    if enemy.hexopticsKill then
        enemy.hexopticsKill = nil
        if state(p)[2523] then start('hexoptics', 240) end
    end
    if enemy.deadSeen then return end
    enemy.deadSeen = true
    axiomRefund(p, entity, enemy)
    if not boss(entity) then return end
    local owned = state(p)
    if owned[2517] and enemy.directAt and clock <= enemy.directAt + 90 then start('feast', 180) end
    if owned[3008] then room.bossesDefeated[bossKey(entity)] = true end
end

local function roomCleared(p, owned)
    local floor = ensureFloor()
    if floor.cleared[room.key] then return end
    floor.cleared[room.key] = true
    if owned[6676] and room.executed then p:AddCoins(1) end
    if owned[3008] then
        for _ in pairs(room.bossesDefeated) do run.gluttonous = math.min(10, run.gluttonous + 1) end
    end
    if owned[6697] and not room.damaged then
        run.hubris = run.hubris + 1
        reevaluate(p, CacheFlag.CACHE_DAMAGE)
    end
    local regenClears = owned[3083] and 2 or owned[3801] and 3 or owned[1006] and 4
    if regenClears then
        run.warmogClear = room.damaged and 0 or run.warmogClear + 1
        if run.warmogClear >= regenClears then
            run.warmogClear = 0
            heal(p, 1)
        end
    else
        run.warmogClear = 0
    end
end

local function showBolt(p, origin, target)
    local velocity = (target - origin) * .25
    local bolt = Isaac.Spawn(EntityType.ENTITY_TEAR, TearVariant.BLUE, 0, origin, velocity, p):ToTear()
    bolt.CollisionDamage = 0
    bolt.EntityCollisionClass = EntityCollisionClass.ENTCOLL_NONE
    bolt.GridCollisionClass = EntityGridCollisionClass.GRIDCOLL_NONE
    bolt.Height, bolt.FallingSpeed, bolt.FallingAcceleration = -10, 1, .6
    bolt.Scale = .55
    bolt:SetColor(Color(.8, 1, .4, 1), 6, 1, false, false)
end

local function processQueued(p, owned)
    local batch = queues
    queues = {}
    local confirming = false
    for _, proc in ipairs(batch) do
        local entity = proc.entity
        local enemy = proc.enemy
        if proc.ready and clock < proc.ready then
            queues[#queues + 1] = proc
            if proc.confirm then confirming = true end
        elseif proc.confirm then
            enemy.queuedExecution = false
            if enemy.deadSeen or entity:Exists() and (entity:IsDead() or entity.HitPoints <= 0) then
                room.executed = true
            end
        elseif proc.execution then
            enemy.queuedExecution = false
            if owned[6676] and validEnemy(entity) and executionAllowed(entity)
                and entity.HitPoints < enemy.maxHP * .05 and not mortalDamage(entity) then
                local accepted = entity:TakeDamage(entity.HitPoints + 1, 0, EntityRef(p), 0)
                if accepted ~= false and mortalDamage(entity) then
                    enemy.queuedExecution = true
                    queues[#queues + 1] = {entity = entity, enemy = enemy, confirm = true, ready = clock + 1}
                    confirming = true
                end
            end
        elseif validEnemy(entity) then
            showBolt(p, proc.origin, entity.Position)
            entity:TakeDamage(proc.amount, 0, EntityRef(p), 0)
        end
    end
    return confirming
end

function Items.heartsteelTargets()
    if not room or not room.owned or not room.owned[3084] then return end
    local targets = {}
    for _, enemy in pairs(room.enemies) do
        local charge = enemy.steelNear or 0
        if charge > 0 and validEnemy(enemy.entity) then
            targets[#targets + 1] = {position = enemy.entity.Position,
                fraction = math.min(1, charge / steelChargeFrames)}
        end
    end
    return targets
end

local function updateTargets(p, owned, isCombat)
    if not isCombat and not room.combatSeen then return end
    if room.savedEnemies and next(room.savedEnemies) then
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if room.savedEnemies[tostring(entity.InitSeed)] then enemyState(entity) end
        end
    end
    if owned[3084] and isCombat then
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if validEnemy(entity) then
                local enemy = enemyState(entity)
                if clock >= (enemy.steelReady or 0) and p.Position:Distance(entity.Position) <= steelRange then
                    enemy.steelNear = math.min(steelChargeFrames, (enemy.steelNear or 0) + 1)
                else
                    enemy.steelNear = 0
                end
            end
        end
    end
    for key, enemy in pairs(room.enemies) do
        local entity = enemy.entity
        if (enemy.steelNear or 0) > 0 and (not isCombat or not owned[3084] or not validEnemy(entity)) then
            enemy.steelNear = nil
        end
        if entity:Exists() then
            if entity:IsDead() or entity.HitPoints <= 0 then
                defeat(p, entity, enemy)
            elseif enemy.bleedNext and enemy.bleedNext <= clock and enemy.bleedNext <= enemy.bleedEnd then
                enemy.bleedNext = enemy.bleedNext + 30
                if validEnemy(entity) then entity:TakeDamage((enemy.bleedPower or .15) * p.Damage, 0, EntityRef(p), 0) end
            end
        else
            room.enemies[key] = nil
        end
    end
end

local function updateMovement(p, owned)
    if (owned[3094] or owned[3095]) and not room.energized and room.lastPosition then
        local distance = p.Position:Distance(room.lastPosition)
        room.energizedDistance = (room.energizedDistance or 0) + distance
        if room.energizedDistance >= 120 then markEnergized(owned) end
    end
    room.lastPosition = p.Position
end

local function cacheSignature(owned)
    return ((owned[3071] or owned[3044]) and live('cleaverSpeed') and 1 or 0)
        | (owned[3073] and live('hexplate') and 2 or 0)
        | (owned[3171] and live('crimson') and 4 or 0)
        | (owned[3095] and live('stormrazor') and 8 or 0)
        | (owned[6699] and live('voltaicLethality') and 32 or 0)
        | (owned[3032] and live('yunTal') and 64 or 0)
        | (owned[2512] and live('barrage') and (room.barrageShots or 0) > 0 and 128 or 0)
end

function Items.activate(p)
    if not p then return end
    state(p)
    previousRoom = previousRoom or clone(run)
    activeStats = true
    reevaluate(p, statFlags)
end

function Items.update(p, tick)
    if not run then newRun(false) end
    if not room then resetRoom() end
    clock = tick
    activeStats = true
    local owned, stats, signature = inventory(p)
    local changed = room.inventorySignature ~= signature
    room.owned, room.stats, room.inventorySignature = owned, stats, signature
    local oldHearts = run.warmogGranted
    warmog(p, owned, stats)
    local buffs = cacheSignature(owned)
    if changed or buffs ~= room.cacheSignature or run.warmogGranted ~= oldHearts then
        room.cacheSignature = buffs
        reevaluate(p, statFlags)
    end

    local confirmingExecution = processQueued(p, owned)
    local isCombat = not game:GetRoom():IsClear()
    if isCombat and not ensureFloor().cleared[room.key] then room.combatSeen = true end
    if isCombat and owned[3814] and not room.edge then
        room.edgeTicks = room.edgeTicks + 1
        if room.edgeTicks >= 600 then room.edge = true end
    end
    updateMovement(p, owned)
    updateTargets(p, owned, isCombat)
    if room.combatSeen and not isCombat and not confirmingExecution then roomCleared(p, owned) end
end

function Items.onMelee(p, _, target)
    local owned = state(p)
    if not owned[6695] or not target then return end
    local direction = (target.Position - p.Position):Normalized()
    for _, entity in ipairs(Isaac.FindInRadius(p.Position, 46, EntityPartition.BULLET)) do
        local delta = entity.Position - p.Position
        if delta:Length() <= 38 + entity.Size and delta:Dot(direction) >= delta:Length() * .5
            and hostileProjectile(entity) then entity:Remove() end
    end
end

function Items.movementInput(p, movement)
    if not movement then return end
    local owned = state(p)
    if not (owned[3009] or owned[3170]) then return movement end
    local area = game:GetRoom()
    local grid = area:GetGridEntity(area:GetGridIndex(p.Position))
    local modifier = 1
    if grid and grid:GetType() == GridEntityType.GRID_SPIDERWEB then modifier = 1.25 end
    if p:HasEntityFlags(EntityFlag.FLAG_SLOW) then modifier = modifier * 1.10714286 end
    return movement * modifier
end

local function updateTear(tear)
    local data = tear:GetData()
    local ctx = data.SamiraItemContext
    if not ctx or ctx.room ~= room or ctx.kind ~= 'aa' or not room.owned or not room.owned[6695] then return end
    local from, to = data.SamiraItemPreviousPosition, tear.Position
    data.SamiraItemPreviousPosition = to
    local segment = to - from
    local lengthSquared = segment:Dot(segment)
    local radius = 24 + math.sqrt(lengthSquared) / 2 + tear.Size
    for _, entity in ipairs(Isaac.FindInRadius((from + to) * .5, radius, EntityPartition.BULLET)) do
        if hostileProjectile(entity) then
            local fraction = lengthSquared > 0 and (entity.Position - from):Dot(segment) / lengthSquared or 0
            local closest = from + segment * math.max(0, math.min(1, fraction))
            if entity.Position:Distance(closest) <= tear.Size + entity.Size then entity:Remove() end
        end
    end
end

function Items.setEnabled(enabled)
    if not run then newRun(false) end
    run.enabled = enabled
    if enabled then return end
    if activeStats then
        activeStats = false
        local p = Isaac.GetPlayer(0)
        if p then reevaluate(p, statFlags) end
    end
end

function Items.isEnabled()
    return run and run.enabled == true
end

local function newRoom()
    if not run then return end
    local old = room
    if rewindRoom then
        run, old = rewindRoom, nil
        rewindRoom = nil
        resetRng()
    end
    if old then run.current = nil end
    resetRoom()
    if old then
        for _, key in ipairs(roomCarry) do room[key] = old[key] end
        room.effects.eclipseShield = nil
    end
    previousRoom = clone(run)
end

local function vampStatus()
    local p = getPlayer()
    if not p then
        Isaac.ConsoleOutput('Select Samira or Yone or enable their test mode.\n')
        return
    end
    state(p)
    local owned, stats = inventory(p)
    local ls, omni = vampChances(owned, stats)
    local hearts, capacity = p:GetHearts(), p:GetEffectiveMaxHearts()
    local remaining = math.max(0, (run.timers.vamp or 0) - game:GetFrameCount()) / 30
    local missing = capacity > hearts
    Isaac.ConsoleOutput(('Vamp: LS %.2f%%, omni %.2f%%. Heal chance AA %.2f%%, ability %.2f%%. Red HP %d/%d half-hearts, cooldown %.2fs.\n')
        :format(ls, omni, missing and math.min(5, ls + omni) or 0, missing and math.min(5, omni) or 0,
            hearts, capacity, remaining))
    if capacity > 0 and not missing and owned[3072] then
        Isaac.ConsoleOutput(('Bloodthirster shield chance on AA at full HP: %.2f%%.\n'):format(math.min(5, ls)))
    end
    Isaac.ConsoleOutput(('Accepted actions %d, dummy %d, unmatched dummy damage %d, rolls %d, heals %d, shields %d.\n')
        :format(vampProbe.hits, vampProbe.dummyHits, vampProbe.dummyUnmatched, vampProbe.rolls, vampProbe.heals, vampProbe.shields))
    if vampProbe.lastRoll then
        Isaac.ConsoleOutput(('Last roll %.2f%% vs %.2f%%.\n'):format(vampProbe.lastRoll, vampProbe.lastChance))
    end
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if trainingDummy(entity) then
            Isaac.ConsoleOutput(('Dummy flags: active=%s vulnerable=%s.\n')
                :format(tostring(entity:IsActiveEnemy(false)), tostring(entity:IsVulnerableEnemy())))
            break
        end
    end
end

function Items.init(host, currentGame, playerProvider, saveSettings, yoneModule)
    mod, game, getPlayer, attachSettings, yone = host, currentGame, playerProvider, saveSettings, yoneModule
    ids = {}
    for _, row in ipairs(catalog) do
        local id = Isaac.GetItemIdByName(row.collectibleName)
        if id and id > 0 then ids[row.riotId] = id end
    end
    local sound = Isaac.GetSoundIdByName and Isaac.GetSoundIdByName('Samira Heartsteel Proc')
    if sound and sound > 0 then ids.heartsteelSound = sound end
    statFlags = CacheFlag.CACHE_DAMAGE | CacheFlag.CACHE_FIREDELAY | CacheFlag.CACHE_SPEED | CacheFlag.CACHE_SIZE
    local function callback(name, action, filter)
        if ModCallbacks[name] then mod:AddCallback(ModCallbacks[name], action, filter) end
    end
    callback('MC_EVALUATE_CACHE', function(_, p, flag) cache(p, flag) end)
    if mod.AddPriorityCallback then
        mod:AddPriorityCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, CallbackPriority.LATE,
            function(_, ...) return beforeDamage(...) end)
    else
        callback('MC_ENTITY_TAKE_DMG', function(_, ...) return beforeDamage(...) end)
    end
    callback('MC_POST_ENTITY_TAKE_DMG', function(_, ...) afterDamage(...) end)
    callback('MC_POST_FIRE_TEAR', function(_, tear)
        if directContext and tear.SpawnerEntity and same(tear.SpawnerEntity, directContext.player) then
            Items.tagTear(directContext.player, tear, directContext)
        end
    end)
    callback('MC_POST_TEAR_UPDATE', function(_, tear) updateTear(tear) end)
    callback('MC_POST_NPC_DEATH', function(_, npc)
        local p = getPlayer()
        if p and room then
            local enemy = room.enemies[entityKey(npc)]
            if enemy or boss(npc) then defeat(p, npc, enemy or enemyState(npc)) end
        end
    end)
    callback('MC_POST_GAME_STARTED', function(_, continued) newRun(continued) end)
    callback('MC_PRE_GAME_EXIT', function(_, shouldSave) save(shouldSave) end)
    callback('MC_POST_NEW_ROOM', newRoom)
    callback('MC_POST_GLOWING_HOURGLASS_SAVE', saveCooldownCheckpoint)
    callback('MC_PRE_GLOWING_HOURGLASS_LOAD', function(_, slot)
        loadingCheckpoint = cooldownCheckpoints['slot' .. slot]
    end)
    callback('MC_POST_GLOWING_HOURGLASS_LOAD', function(_, slot)
        pendingCheckpoint = loadingCheckpoint or cooldownCheckpoints['slot' .. slot]
        loadingCheckpoint = nil
    end)
    callback('MC_EXECUTE_CMD', function(_, command)
        if command == 'samiravamp' or command == 'yonevamp' then vampStatus() end
    end)
    if Console and Console.RegisterCommand then
        Console.RegisterCommand('samiravamp', 'Show Samira healing and hit diagnostics', 'samiravamp',
            false, AutocompleteType.NONE)
        Console.RegisterCommand('yonevamp', 'Show Yone healing and hit diagnostics', 'yonevamp',
            false, AutocompleteType.NONE)
    end
    if CollectibleType then
        callback('MC_PRE_USE_ITEM', function()
            if previousRoom then rewindRoom = clone(previousRoom) end
        end, CollectibleType.COLLECTIBLE_GLOWING_HOUR_GLASS)
    end
end

return Items
