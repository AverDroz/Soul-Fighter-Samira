local Progress = {MAX_LEVEL = 18, VERSION = 1}

local skillKeys = {'q', 'w', 'e', 'r'}
local keystones = {'conqueror', 'lethal_tempo', 'electrocute'}
local strikeKinds = {attack = true, q = true, w = true, e = true, r = true}
local electrocuteWindow, electrocuteCooldown = 90, 240
local stackRunes = {
    conqueror = {limit = 5, duration = 150},
    lethal_tempo = {limit = 6, duration = 120},
}

Progress.choices = {
    {id = 'conqueror', name = 'Conqueror', description = 'Hits grant +2% damage for 5s, up to 5 stacks.'},
    {id = 'lethal_tempo', name = 'Lethal Tempo', description = 'Attack and Q hits grant +4% attack speed for 4s, up to 6 stacks.'},
    {id = 'electrocute', name = 'Electrocute', description = '3 different hits within 3s deal 45% attack damage. 8s cooldown.'},
    {id = 'random', name = 'Random', description = 'Pick a keystone based on the run seed.'},
}

local function validRune(key)
    for _, id in ipairs(keystones) do
        if key == id then return true end
    end
    return false
end

local function integer(value, default, low, high)
    if type(value) ~= 'number' or value ~= value or value == math.huge or value == -math.huge then return default end
    return math.max(low, math.min(high, math.floor(value)))
end

local function ability(key)
    if key == 'q3' then return 'q' end
    if key == 'e_return' then return 'e' end
    return key
end

local function rankCap(level, key)
    if key == 'r' then return level >= 11 and 3 or level >= 6 and 2 or 1 end
    if key == 'q' or key == 'w' or key == 'e' then return math.min(5, 1 + math.floor(level / 2)) end
    return 0
end

function Progress.required(level)
    return 60 + 12 * (level - 1)
end

function Progress.restore(record, clock)
    if type(record) ~= 'table' or record.version ~= Progress.VERSION then record = {} end
    local level = integer(record.level, 1, 1, Progress.MAX_LEVEL)
    local xp = integer(record.xp, 0, 0, Progress.required(level) - 1)
    local ranks = {}
    local remaining = math.min(14, level - 1)
    local savedRanks = type(record.ranks) == 'table' and record.ranks or {}
    for _, key in ipairs(skillKeys) do
        ranks[key] = integer(savedRanks[key], 1, 1, math.min(remaining + 1, rankCap(level, key)))
        remaining = remaining - (ranks[key] - 1)
    end
    local rune = validRune(record.rune) and record.rune or nil
    local remaining = rune == 'electrocute' and integer(record.electrocuteRemaining, 0, 0, electrocuteCooldown) or 0
    return {version = Progress.VERSION, level = level, xp = level == Progress.MAX_LEVEL and 0 or xp,
        ranks = ranks, rune = rune, electrocuteReady = clock and remaining > 0 and clock + remaining or nil}
end

function Progress.snapshot(progress, clock)
    local snapshot = Progress.restore(progress)
    if clock and progress.rune == 'electrocute' and progress.electrocuteReady and progress.electrocuteReady > clock then
        snapshot.electrocuteRemaining = math.min(electrocuteCooldown, progress.electrocuteReady - clock)
    end
    return snapshot
end

function Progress.award(progress, amount)
    amount = integer(amount, 0, 0, math.maxinteger)
    local before = progress.level
    if amount == 0 or before == Progress.MAX_LEVEL then return 0 end
    -- The total XP needed is far smaller than this bound. It also prevents overflow.
    progress.xp = progress.xp + math.min(amount, Progress.MAX_LEVEL * Progress.required(Progress.MAX_LEVEL))
    while progress.level < Progress.MAX_LEVEL and progress.xp >= Progress.required(progress.level) do
        progress.xp = progress.xp - Progress.required(progress.level)
        progress.level = progress.level + 1
    end
    if progress.level == Progress.MAX_LEVEL then progress.xp = 0 end
    return progress.level - before
end

function Progress.points(progress)
    local points = math.min(14, progress.level - 1)
    for _, key in ipairs(skillKeys) do points = points - (progress.ranks[key] - 1) end
    return points
end

function Progress.rank(progress, key)
    return progress.ranks[ability(key)] or 0
end

function Progress.canUpgrade(progress, key)
    key = ability(key)
    return rankCap(progress.level, key) > Progress.rank(progress, key) and Progress.points(progress) > 0
end

function Progress.upgrade(progress, key)
    key = ability(key)
    if not Progress.canUpgrade(progress, key) then return false end
    progress.ranks[key] = progress.ranks[key] + 1
    return true
end

function Progress.choose(progress, key, startSeed)
    if progress.rune then return false end
    if key == 'random' then
        local seed = integer(startSeed, 0, -0x80000000, 0xffffffff)
        local mixed = seed & 0xffffffff
        mixed = ((mixed ~ (mixed >> 16)) * 0x45d9f3b) & 0xffffffff
        mixed = ((mixed ~ (mixed >> 16)) * 0x45d9f3b) & 0xffffffff
        mixed = mixed ~ (mixed >> 16)
        key = keystones[1 + mixed % #keystones]
    end
    if not validRune(key) then return false end
    progress.rune = key
    return true, key
end

function Progress.resetRoom(progress)
    progress.runeStacks, progress.runeExpires, progress.electrocuteHits = nil, nil, nil
end

local function activeStacks(progress, clock)
    if clock < (progress.runeExpires or 0) then return progress.runeStacks end
    return 0
end

function Progress.runeStatus(progress, clock)
    if progress.rune == 'electrocute' then
        local remaining = math.max(0, (progress.electrocuteReady or clock) - clock)
        return {remaining = remaining, duration = electrocuteCooldown, ready = remaining == 0}
    end
    local rule = stackRunes[progress.rune]
    if rule then
        return {stacks = activeStacks(progress, clock), limit = rule.limit,
            remaining = math.max(0, (progress.runeExpires or clock) - clock)}
    end
end

function Progress.onStrike(progress, strikeKind, clock)
    local key = ability(strikeKind)
    if not strikeKinds[key] then return end
    local rule = stackRunes[progress.rune]
    if rule and (progress.rune == 'conqueror' or key == 'attack' or key == 'q') then
        progress.runeStacks = math.min(rule.limit, activeStacks(progress, clock) + 1)
        progress.runeExpires = clock + rule.duration
    elseif progress.rune == 'electrocute' and clock >= (progress.electrocuteReady or 0) then
        local hits = progress.electrocuteHits or {}
        hits[key] = clock
        progress.electrocuteHits = hits
        local count = 0
        for kind, at in pairs(hits) do
            if clock - at < electrocuteWindow then count = count + 1 else hits[kind] = nil end
        end
        if count >= 3 then
            progress.electrocuteHits = nil
            progress.electrocuteReady = clock + electrocuteCooldown
            return .45
        end
    end
end

function Progress.attackSpeed(progress, clock)
    return progress.rune == 'lethal_tempo' and 1 + .04 * activeStacks(progress, clock) or 1
end

function Progress.damage(progress, key, clock)
    key = ability(key)
    local rankBonus = (key == 'q' or key == 'e') and .08 * (Progress.rank(progress, key) - 1) or 0
    local runeBonus = progress.rune == 'conqueror' and .02 * activeStacks(progress, clock) or 0
    return (1 + rankBonus) * (1 + runeBonus)
end

function Progress.cooldown(progress, key)
    key = ability(key)
    if key == 'w' or key == 'e' or key == 'r' then return 1 - .05 * (Progress.rank(progress, key) - 1) end
    return 1
end

return Progress
