local Combat = {}

-- Timings are Isaac update frames (30 Hz).
local skills = {
    attack = {windup = 4, duration = 14},
    q = {windup = 6, duration = 16},
    q3 = {windup = 7, duration = 22},
    w = {windup = 8, duration = 22, cooldown = 300},
    e = {windup = 3, duration = 14, cooldown = 450},
    e_return = {windup = 0, duration = 13},
    r = {windup = 14, duration = 29, cooldown = 900},
}
local meleeRange, qRange, ultRange = 44, 76, 168
local spiritDuration, markDamage = 150, .30

function Combat.new()
    return {ready = {}, qStacks = 0, secondBlade = false, face = Vector(0, 1)}
end

function Combat.hostile(entity)
    return entity and entity:Exists() and not entity:IsDead() and entity:IsVulnerableEnemy()
        and not entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

function Combat.clearPoint(room, player, point)
    local radius = math.min(14, math.max(6, player.Size * .6))
    if not room:IsPositionInRoom(point, radius) then return false end
    for _, offset in ipairs({Vector.Zero, Vector(radius, 0), Vector(-radius, 0),
        Vector(0, radius), Vector(0, -radius)}) do
        local cell = room:GetGridCollision(room:GetGridIndex(point + offset))
        if cell ~= GridCollisionClass.COLLISION_NONE
            and (not player.CanFly or cell >= GridCollisionClass.COLLISION_WALL) then return false end
    end
    return true
end

local function safeDestination(room, player, start, goal)
    local delta, lastSafe = goal - start, start
    local steps = math.max(1, math.ceil(delta:Length() / 4))
    for step = 1, steps do
        local nextPosition = start + delta * (step / steps)
        if not Combat.clearPoint(room, player, nextPosition) then break end
        lastSafe = nextPosition
    end
    return lastSafe
end

function Combat.clearSegment(room, player, start, goal)
    return safeDestination(room, player, start, goal):Distance(goal) < .5
end

local function attackDelay(player)
    return math.max(8, math.ceil((player.MaxFireDelay + 1) * 1.5))
end

function Combat.resetRoom(state, clock)
    state.pending, state.action, state.spirit, state.shieldUntil = nil, nil, nil, nil
    state.qStacks, state.qExpires = 0, nil
    if state.lastClock and clock < state.lastClock then
        for key, deadline in pairs(state.ready) do
            state.ready[key] = clock + math.max(0, deadline - state.lastClock)
        end
    end
    state.lastClock = clock
end

function Combat.cast(state, input, player, aim, clock)
    if state.pending then return end
    local key = input
    if input == 'e' and state.spirit then
        if clock < state.spirit.recastAt then return end
        key = 'e_return'
    elseif clock < (state.ready[input] or 0) then
        return
    elseif input == 'q' and state.qStacks == 2 then
        key = 'q3'
    end

    local skill = skills[key]
    local delta = aim - player.Position
    if delta:Length() > .01 then state.face = delta:Normalized() end
    local clip = key == 'attack' and state.secondBlade and 'attack2' or key
    state.action = {key = clip, at = clock, finish = clock + skill.duration}
    state.pending = {key = key, at = clock + skill.windup, facing = state.face}
    if key ~= 'e_return' then
        local cooldown = skill.cooldown or attackDelay(player)
        if input == 'q' then cooldown = math.max(18, cooldown * 2) end
        state.ready[input] = clock + cooldown
    end
    return key
end

local function damage(state, player, enemy, amount)
    local before = enemy.HitPoints
    if not enemy:TakeDamage(amount, 0, EntityRef(player), 0) then return false end
    if state.spirit then
        local after = enemy:Exists() and math.max(0, enemy.HitPoints) or 0
        local applied = math.max(0, before - after)
        if applied > 0 then
            local id = GetPtrHash(enemy)
            local mark = state.spirit.marks[id] or {entity = enemy, amount = 0}
            mark.amount = mark.amount + applied * markDamage
            state.spirit.marks[id] = mark
        end
    end
    return true
end

local function teleport(player, destination)
    player.Position = destination
    player.Velocity = Vector.Zero
end

local function blade(state, room, player, enemies, facing, width, reach, multiplier, sweep, hitTargets)
    local hit, furthest = false, 0
    local side = Vector(-facing.Y, facing.X)
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) then
            local delta = enemy.Position - player.Position
            local along = delta:Dot(facing)
            local across = math.abs(delta:Dot(side))
            local inRange = sweep and delta:Length() <= reach + enemy.Size and along >= delta:Length() * .35
                or not sweep and along >= 0 and along <= reach + enemy.Size and across <= width + enemy.Size
            if inRange and room:CheckLine(player.Position, enemy.Position, 3, 0, false, false)
                and damage(state, player, enemy, player.Damage * multiplier) then
                hit = true
                furthest = math.max(furthest, along)
                if hitTargets then hitTargets[#hitTargets + 1] = enemy end
            end
        end
    end
    return hit, furthest
end

local function returnSpirit(state, room, player, clock)
    local spirit = state.spirit
    if not spirit then return end
    state.spirit = nil
    if Combat.clearPoint(room, player, spirit.anchor) then teleport(player, spirit.anchor) end
    state.action = {key = 'e_return', at = clock, finish = clock + skills.e_return.duration}
    for _, mark in pairs(spirit.marks) do
        if Combat.hostile(mark.entity) then damage(state, player, mark.entity, mark.amount) end
    end
end

local function pullFoes(room, enemies, pull)
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) and enemy:ToNPC() and not enemy:IsBoss() then
            enemy.Position = safeDestination(room, enemy, enemy.Position, pull)
        end
    end
end

local function resolve(state, room, player, enemies, strike, clock)
    local key, facing = strike.key, strike.facing
    local start = player.Position
    if key == 'attack' then
        state.secondBlade = not state.secondBlade
        blade(state, room, player, enemies, facing, 14, meleeRange, state.secondBlade and 1 or 1.25)
    elseif key == 'q' then
        if blade(state, room, player, enemies, facing, 14, qRange, 1.4) then
            state.qStacks, state.qExpires = math.min(2, state.qStacks + 1), clock + 180
        end
    elseif key == 'q3' then
        state.qStacks, state.qExpires = 0, nil
        blade(state, room, player, enemies, facing, 19, 112, 1.6)
        teleport(player, safeDestination(room, player, start, start + facing * 90))
    elseif key == 'w' then
        if blade(state, room, player, enemies, facing, 0, 74, 1.15, true) then
            state.shieldUntil = clock + 60
        end
    elseif key == 'e' then
        state.spirit = {anchor = start, untilFrame = clock + spiritDuration, recastAt = clock + 8, marks = {}}
        teleport(player, safeDestination(room, player, start, start + facing * 54))
    elseif key == 'e_return' then
        returnSpirit(state, room, player, clock)
    elseif key == 'r' then
        local targets = {}
        local hit, far = blade(state, room, player, enemies, facing, 16, ultRange, 2.5, false, targets)
        local destination = safeDestination(room, player, start, start + facing * (hit and far + 23 or ultRange))
        teleport(player, destination)
        pullFoes(room, targets, destination - facing * 10)
    end
end

function Combat.update(state, room, player, enemies, clock)
    if state.lastClock and clock < state.lastClock then Combat.resetRoom(state, clock) end
    state.lastClock = clock
    if state.qExpires and clock >= state.qExpires then state.qStacks, state.qExpires = 0, nil end
    local strike = state.pending
    if strike and clock >= strike.at then
        state.pending = nil
        resolve(state, room, player, enemies, strike, clock)
    end
    if state.spirit and clock >= state.spirit.untilFrame then
        -- An unfinished windup belongs to the spirit's former position.
        state.pending = nil
        returnSpirit(state, room, player, clock)
    end
end

function Combat.absorb(state, clock)
    if clock >= (state.shieldUntil or 0) then return false end
    state.shieldUntil = nil
    return true
end

function Combat.presentation(state, clock)
    local action = state.action
    if action and clock < action.finish then
        return action.key, math.max(0, (clock - action.at) / (action.finish - action.at))
    end
end

function Combat.inMeleeRange(room, player, target)
    return player.Position:Distance(target.Position) <= meleeRange + target.Size
        and room:CheckLine(player.Position, target.Position, 3, 0, false, false)
end

return Combat
