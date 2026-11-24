local Classic = include('yone_progression')
local Runes = {VERSION = 1}
local pressWindow, pressDuration, cometCooldown = 120, 150, 240
local firstStrikeDuration, firstStrikeCooldown, firstStrikeMultiplier = 90, 450, 1.08
local firstStrikeCoinCap, firstStrikeDamagePerCoin = 3, 2
local attackKinds = {aa = true, q = true}
local hitKinds = {aa = true, q = true, e = true, r = true}

Runes.choices = {
    Classic.choices[1], Classic.choices[2],
    {id = 'press_the_attack', name = 'Press the Attack',
        description = '3 attack or Q hits on one enemy deal 50% attack damage and grant +8% damage for 5s.'},
    Classic.choices[3],
    {id = 'arcane_comet', name = 'Arcane Comet',
        description = 'Ability hits call down a comet for 45% attack damage in an area. 8s cooldown.'},
    {id = 'first_strike', name = 'First Strike',
        description = 'Hit before being hit for +8% damage for 3s. Every 2 bonus damage pays a coin, up to 3. 15s cooldown.'},
    Classic.choices[4],
}

local function valid(key)
    for i = 1, #Runes.choices - 1 do
        if Runes.choices[i].id == key then return true end
    end
    return false
end

function Runes.restore(record, clock)
    if type(record) ~= 'table' or record.version ~= Runes.VERSION or not valid(record.rune) then
        return {version = Runes.VERSION}
    end
    local progress = Classic.restore(record, clock)
    progress.rune = record.rune
    local remaining = record.cometRemaining
    if clock and record.rune == 'arcane_comet' and type(remaining) == 'number' and remaining > 0 then
        progress.cometReady = clock + math.min(cometCooldown, math.floor(remaining))
    end
    remaining = record.pressRemaining
    if clock and record.rune == 'press_the_attack' and type(remaining) == 'number' and remaining > 0 then
        progress.pressUntil = clock + math.min(pressDuration, math.floor(remaining))
    end
    if clock and record.rune == 'first_strike' then
        remaining = record.firstStrikeRemaining
        if type(remaining) == 'number' and remaining > 0 then
            progress.firstStrikeReady = clock + math.min(firstStrikeCooldown, math.floor(remaining))
        end
        remaining = record.firstStrikeActive
        if type(remaining) == 'number' and remaining > 0 then
            progress.firstStrikeUntil = clock + math.min(firstStrikeDuration, math.floor(remaining))
            local score = record.firstStrikeDamage
            progress.firstStrikeDamage = type(score) == 'number' and score >= 0
                and math.min(firstStrikeCoinCap * firstStrikeDamagePerCoin, score) or 0
        end
    end
    return progress
end

function Runes.snapshot(progress, clock)
    local classic = Classic.snapshot(progress, clock)
    return {version = Runes.VERSION, rune = progress.rune,
        electrocuteRemaining = classic.electrocuteRemaining,
        cometRemaining = clock and progress.cometReady and math.max(0, progress.cometReady - clock),
        pressRemaining = clock and progress.pressUntil and math.max(0, progress.pressUntil - clock),
        firstStrikeRemaining = clock and progress.firstStrikeReady and math.max(0, progress.firstStrikeReady - clock),
        firstStrikeActive = clock and progress.firstStrikeUntil and math.max(0, progress.firstStrikeUntil - clock),
        firstStrikeDamage = progress.firstStrikeDamage}
end

function Runes.choose(progress, key, startSeed)
    if progress.rune then return false end
    if key == 'random' then
        local seed = (math.tointeger(startSeed) or 0) & 0xffffffff
        seed = ((seed ~ (seed >> 16)) * 0x45d9f3b) & 0xffffffff
        seed = ((seed ~ (seed >> 16)) * 0x45d9f3b) & 0xffffffff
        key = Runes.choices[1 + (seed ~ (seed >> 16)) % (#Runes.choices - 1)].id
    end
    if not valid(key) then return false end
    progress.rune = key
    return true, key
end

function Runes.resetRoom(progress)
    Classic.resetRoom(progress)
    progress.pressTarget, progress.pressHits, progress.pressExpires = nil, nil, nil
end

function Runes.attackSpeed(progress, clock)
    return Classic.attackSpeed(progress, clock)
end

function Runes.damage(progress, clock, kind)
    local press = progress.rune == 'press_the_attack' and clock < (progress.pressUntil or 0)
    if progress.rune == 'first_strike' and hitKinds[kind] and
        (clock < (progress.firstStrikeUntil or 0) or clock >= (progress.firstStrikeReady or 0)) then
        return firstStrikeMultiplier, true
    end
    return press and 1.08 or Classic.damage(progress, 'attack', clock)
end

function Runes.runeStatus(progress, clock)
    if progress.rune == 'press_the_attack' then
        local active = clock < (progress.pressUntil or 0)
        local untilFrame = active and progress.pressUntil or progress.pressExpires or clock
        return {stacks = active and 3 or clock < untilFrame and progress.pressHits or 0,
            limit = 3, remaining = math.max(0, untilFrame - clock)}
    end
    if progress.rune == 'arcane_comet' then
        local remaining = math.max(0, (progress.cometReady or clock) - clock)
        return {remaining = remaining, duration = cometCooldown, ready = remaining == 0}
    end
    if progress.rune == 'first_strike' then
        local active = math.max(0, (progress.firstStrikeUntil or clock) - clock)
        local remaining = math.max(0, (progress.firstStrikeReady or clock) - clock)
        return {remaining = active > 0 and active or remaining, active = active > 0,
            duration = active > 0 and firstStrikeDuration or firstStrikeCooldown, ready = remaining == 0}
    end
    return Classic.runeStatus(progress, clock)
end

function Runes.acceptHit(progress, ctx, targetKey, clock)
    if not progress.rune or ctx.missFortuneRuneUsed or ctx.corsairSecondary or not hitKinds[ctx.kind] then return end
    if progress.rune == 'first_strike' then return end
    if progress.rune == 'press_the_attack' then
        if not attackKinds[ctx.kind] then return end
        ctx.missFortuneRuneUsed = true
        if clock < (progress.pressUntil or 0) then return end
        if targetKey ~= progress.pressTarget or clock >= (progress.pressExpires or 0) then
            progress.pressTarget, progress.pressHits = targetKey, 0
        end
        progress.pressHits = progress.pressHits + 1
        progress.pressExpires = clock + pressWindow
        if progress.pressHits == 3 then
            progress.pressTarget, progress.pressHits, progress.pressExpires = nil, nil, nil
            progress.pressUntil = clock + pressDuration
            return 'press_the_attack', .50
        end
    elseif progress.rune == 'arcane_comet' then
        if ctx.kind == 'aa' or clock < (progress.cometReady or 0) then return end
        ctx.missFortuneRuneUsed = true
        progress.cometReady = clock + cometCooldown
        return 'arcane_comet', .45
    else
        ctx.missFortuneRuneUsed = true
        local bonus = Classic.onStrike(progress, ctx.kind == 'aa' and 'attack' or ctx.kind, clock)
        if bonus then return 'electrocute', bonus end
    end
end

function Runes.firstStrikeHit(progress, clock, bonusDamage)
    if progress.rune ~= 'first_strike' then return 0 end
    if clock >= (progress.firstStrikeReady or 0) then
        progress.firstStrikeUntil = clock + firstStrikeDuration
        progress.firstStrikeReady = clock + firstStrikeCooldown
        progress.firstStrikeDamage = 0
    end
    if clock >= (progress.firstStrikeUntil or 0) then return 0 end
    local before = progress.firstStrikeDamage
    local after = math.min(firstStrikeCoinCap * firstStrikeDamagePerCoin, before + bonusDamage)
    progress.firstStrikeDamage = after
    return math.floor(after / firstStrikeDamagePerCoin) - math.floor(before / firstStrikeDamagePerCoin)
end

function Runes.tookDamage(progress, clock)
    if progress.rune == 'first_strike' and clock >= (progress.firstStrikeReady or 0) then
        progress.firstStrikeReady = clock + firstStrikeCooldown
    end
end

return Runes
