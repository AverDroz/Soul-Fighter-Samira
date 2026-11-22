local Combat = {}
local Artifacts = include('yone_artifacts')

-- Timings are Isaac update frames (30 Hz).
local skills = {
    attack = {windup = 4, duration = 14},
    q = {windup = 6, duration = 16},
    q3 = {windup = 7, duration = 22},
    w = {windup = 8, duration = 22, cooldown = 300},
    e = {windup = 3, duration = 14, cooldown = 450},
    e_return = {windup = 0, duration = 13},
    r = {windup = 23, duration = 40, cooldown = 900},
}
local meleeRange, qRange, ultRange, wRange = 44, 76, 168, 100
local spiritDuration, markDamage, wCosine = 150, .30, .35
local effectFrames, effectLimit, markerLimit = 21, 12, 24

function Combat.new(items)
    return {ready = {}, qStacks = 0, secondBlade = false, face = Vector(0, 1),
        effects = {}, effectSerial = 0, items = items}
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
            and (not player:IsFlying() or cell >= GridCollisionClass.COLLISION_WALL) then return false end
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
    state.directImpact, state.effects = nil, {}
    state.qStacks, state.qExpires = 0, nil
    if state.lastClock and clock < state.lastClock then
        for key, deadline in pairs(state.ready) do
            state.ready[key] = clock + math.max(0, deadline - state.lastClock)
        end
    end
    state.lastClock = clock
end

function Combat.exportCooldowns(state, clock)
    local remaining = {}
    for key, deadline in pairs(state.ready) do remaining[key] = math.max(0, deadline - clock) end
    return remaining
end

function Combat.restoreCooldowns(state, remaining, clock)
    if type(remaining) ~= 'table' then return end
    state.ready, state.lastClock = {}, clock
    for _, key in ipairs({'attack', 'q', 'w', 'e', 'r'}) do
        local ticks = remaining[key]
        if type(ticks) == 'number' and ticks >= 0 then state.ready[key] = clock + math.min(ticks, 900) end
    end
end

function Combat.reduceCooldowns(state, fraction, clock)
    for _, key in ipairs({'q', 'w', 'e', 'r'}) do
        local remaining = math.max(0, (state.ready[key] or clock) - clock)
        state.ready[key] = clock + math.ceil(remaining * (1 - fraction))
    end
end

function Combat.cast(state, input, player, aim, clock)
    if state.pending or (state.action and state.action.key == 'r' and clock < state.action.finish) then return end
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
    local delta = (key == 'e_return' and state.spirit.anchor or aim) - player.Position
    if delta:Length() > .01 then state.face = delta:Normalized() end
    local clip = key == 'attack' and state.secondBlade and 'attack2' or key
    state.action = {key = clip, at = clock, finish = clock + skill.duration}
    state.pending = {kind = key, clip = clip, at = clock + skill.windup, facing = state.face}
    if key ~= 'e_return' then
        local cooldown = skill.cooldown or attackDelay(player)
        if input == 'q' then cooldown = math.max(18, cooldown * 2) end
        if input ~= 'attack' and state.items then
            if state.items.cooldown then cooldown = math.max(12, state.items.cooldown(player, input, cooldown)) end
            if state.items.onCast then state.items.onCast(player, input, clock) end
        end
        state.ready[input] = clock + cooldown
    end
    return key
end

-- Base world-space geometry shared by targeting and the native range overlay.
function Combat.footprint(state, player, input, aim, room)
    local delta = aim - player.Position
    local facing = delta:Length() > .01 and delta:Normalized() or state.face
    local key = input == 'q' and state.qStacks == 2 and 'q3' or input
    if key == 'e' and state.spirit then
        local toAnchor = state.spirit.anchor - player.Position
        return {shape = 'line', origin = player.Position,
            facing = toAnchor:Length() > .01 and toAnchor:Normalized() or state.face,
            reach = toAnchor:Length(), width = math.max(6, player.Size * .6)}
    end
    local reach, width, shape, cosine
    if key == 'q' then reach, width = qRange * Artifacts.range(player), 14
    elseif key == 'q3' then reach, width = 112 * Artifacts.range(player), 19
    elseif key == 'w' then reach, shape, cosine = wRange, 'sector', wCosine
    elseif key == 'e' then reach, width = 54, math.max(6, player.Size * .6)
    elseif key == 'r' then
        reach, width = ultRange, 16
        if room then
            -- The line may cross interior grids but never leave and re-enter a room.
            for distance = 1, ultRange do
                if not room:IsPositionInRoom(player.Position + facing * distance, 0) then
                    reach = distance - 1
                    break
                end
            end
        end
    else return nil end
    return {shape = shape or 'line', origin = player.Position, facing = facing,
        reach = reach, width = width, cosine = cosine}
end

function Combat.activeFootprint(state, player, room)
    local pending = state.pending
    if not pending or pending.kind ~= 'r' then return nil end
    return Combat.footprint(state, player, 'r', player.Position + pending.facing, room)
end

function Combat.confirmDamage(state, entity, amount, source)
    local impact = state.directImpact
    local dealer = source and source.Entity
    if impact and amount > 0 and dealer and GetPtrHash(dealer) == impact.player
        and GetPtrHash(entity) == impact.target then
        impact.accepted = amount
    end
end

local function damage(state, player, enemy, amount, strike)
    local before = enemy.HitPoints
    local spirit = state.spirit
    local impact = spirit and {player = GetPtrHash(player), target = GetPtrHash(enemy)}
    local previous = state.directImpact
    state.directImpact = impact
    local source = EntityRef(player)
    if strike then amount = amount * Artifacts.multiplier(player, strike) end
    local accepted
    if strike and strike.itemContext then
        accepted = state.items.withContext(strike.itemContext, function()
            return enemy:TakeDamage(amount, 0, source, 0)
        end)
    else
        accepted = enemy:TakeDamage(amount, 0, source, 0)
    end
    state.directImpact = previous
    if not accepted then return false end
    if impact and state.spirit == spirit then
        local after = enemy:Exists() and math.max(0, enemy.HitPoints) or 0
        -- REPENTOGON can confirm the final damage before HP is subtracted.
        local applied = math.min(before, impact.accepted or math.max(0, before - after))
        if applied > 0 then
            local id = impact.target
            local mark = spirit.marks[id] or {entity = enemy, amount = 0}
            mark.amount = mark.amount + applied * markDamage
            spirit.marks[id] = mark
        end
    end
    if strike then
        Artifacts.onHit(player, strike, enemy)
        if state.items and state.items.onMelee and strike.kind == 'attack' and not strike.itemMelee then
            strike.itemMelee = true
            state.items.onMelee(player, nil, enemy)
        end
    end
    return true
end

local function teleport(player, destination)
    player.Position = destination
    player.Velocity = Vector.Zero
end

local function blade(state, room, player, enemies, strike, width, reach, multiplier, sweep, hitTargets, throughWalls, contacts)
    local hit, furthest = false, 0
    local facing = strike.facing
    local side = Vector(-facing.Y, facing.X)
    local candidates = {}
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) then
            local delta = enemy.Position - player.Position
            local along = delta:Dot(facing)
            local across = math.abs(delta:Dot(side))
            local distance = delta:Length()
            local inRange = sweep and distance <= reach + enemy.Size and along >= distance * wCosine
                or not sweep and along >= 0 and along <= reach + enemy.Size and across <= width + enemy.Size
                and (not throughWalls or along <= reach)
            if inRange and (throughWalls or room:CheckLine(player.Position, enemy.Position, 3, 0, false, false)) then
                candidates[#candidates + 1] = {entity = enemy, along = along, distance = sweep and distance or along,
                    seed = enemy.InitSeed}
            end
        end
    end
    -- First-target item effects follow the strike along its path.
    table.sort(candidates, function(a, b)
        if a.distance ~= b.distance then return a.distance < b.distance end
        return a.seed < b.seed
    end)
    for _, candidate in ipairs(candidates) do
        local enemy = candidate.entity
        local position = Vector(enemy.Position.X, enemy.Position.Y)
        if Combat.hostile(enemy) and damage(state, player, enemy, player.Damage * multiplier, strike) then
            hit = true
            furthest = math.max(furthest, candidate.along)
            if hitTargets then hitTargets[#hitTargets + 1] = enemy end
            if contacts and #contacts < markerLimit then contacts[#contacts + 1] = position end
        end
    end
    return hit, furthest
end

local function breakProps(room, start, facing, width, reach)
    local side = Vector(-facing.Y, facing.X)
    for index = 0, room:GetGridSize() - 1 do
        local grid = room:GetGridEntity(index)
        if grid and grid.CollisionClass ~= GridCollisionClass.COLLISION_NONE then
            local kind = grid:GetType()
            if kind == GridEntityType.GRID_POOP or kind == GridEntityType.GRID_ROCK_ALT then
                local delta = grid.Position - start
                local along = delta:Dot(facing)
                if along >= 0 and along <= reach and math.abs(delta:Dot(side)) <= width + 16
                    and room:CheckLine(start, start + facing * math.max(0, along - 20), 3, 0, false, false) then
                    room:DestroyGrid(index, false)
                end
            end
        end
    end
end

-- R crosses obstacles but must end at an actually clear point.
local function landing(room, entity, start, goal)
    local delta = goal - start
    local steps = math.max(1, math.ceil(delta:Length() / 4))
    for step = steps, 0, -1 do
        local point = start + delta * (step / steps)
        if Combat.clearPoint(room, entity, point) then return point end
    end
    return start
end

local function effect(state, clock, kind, origin, target, footprint, landingPoint, contacts, bodyFace, bodyRemaining)
    state.effectSerial = state.effectSerial + 1
    local effects = state.effects
    if #effects == effectLimit then table.remove(effects, 1) end
    effects[#effects + 1] = {id = state.effectSerial, at = clock, kind = kind,
        origin = origin, target = target, footprint = footprint, landing = landingPoint,
        contacts = contacts, bodyFace = bodyFace, bodyRemaining = bodyRemaining}
end

local function lineEnd(room, start, facing, reach)
    for distance = reach, 4, -4 do
        local endpoint = start + facing * distance
        if room:CheckLine(start, endpoint, 3, 0, false, false) then return endpoint end
    end
    return start
end

local function returnSpirit(state, room, player, clock)
    local spirit = state.spirit
    if not spirit then return end
    state.spirit = nil
    local start = player.Position
    local toAnchor = spirit.anchor - start
    if toAnchor:Length() > .01 then state.face = toAnchor:Normalized() end
    if Combat.clearPoint(room, player, spirit.anchor) then teleport(player, spirit.anchor) end
    local contacts = {}
    effect(state, clock, 'e_return', start, player.Position, nil, nil, contacts, spirit.face,
        math.max(0, math.min(1, (spirit.untilFrame - clock) / spiritDuration)))
    state.action = {key = 'e_return', at = clock, finish = clock + skills.e_return.duration}
    for _, mark in pairs(spirit.marks) do
        if Combat.hostile(mark.entity) then
            local point = Vector(mark.entity.Position.X, mark.entity.Position.Y)
            if damage(state, player, mark.entity, mark.amount) and #contacts < markerLimit then
                contacts[#contacts + 1] = point
            end
        end
    end
end

local function pullFoes(room, enemies, pull)
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) and enemy:ToNPC() and not enemy:IsBoss() then
            enemy.Position = landing(room, enemy, enemy.Position, pull)
        end
    end
end

local function attackReach(player, items)
    local reach = meleeRange * Artifacts.range(player)
    if items and items.attackRange then reach = math.min(84, items.attackRange(player, reach)) end
    return reach
end

local function resolve(state, room, player, enemies, strike, clock)
    local key, facing = strike.kind, strike.facing
    local start = player.Position
    local items = state.items
    local footprint = Combat.footprint(state, player, key, start + facing, room)
    if items and items.newAttack and (key == 'attack' or key == 'q' or key == 'q3' or key == 'w' or key == 'r') then
        strike.itemContext = items.newAttack(player, key == 'q3' and 'q' or key, clock)
    end
    if key == 'attack' then
        state.secondBlade = not state.secondBlade
        local reach = attackReach(player, items)
        blade(state, room, player, enemies, strike, 14, reach, state.secondBlade and 1 or 1.25)
        effect(state, clock, strike.clip, start, start + facing * reach)
    elseif key == 'q' then
        local reach, contacts = footprint.reach, {}
        if blade(state, room, player, enemies, strike, footprint.width, reach, 1.4, false, nil, false, contacts) then
            state.qStacks, state.qExpires = math.min(2, state.qStacks + 1), clock + 180
        end
        breakProps(room, start, facing, footprint.width, reach)
        effect(state, clock, key, start, lineEnd(room, start, facing, reach), nil, nil, contacts)
    elseif key == 'q3' then
        state.qStacks, state.qExpires = 0, nil
        local reach, contacts = footprint.reach, {}
        blade(state, room, player, enemies, strike, footprint.width, reach, 1.6, false, nil, false, contacts)
        breakProps(room, start, facing, footprint.width, reach)
        teleport(player, safeDestination(room, player, start, start + facing * 90))
        effect(state, clock, key, start, lineEnd(room, start, facing, reach), nil, player.Position, contacts)
    elseif key == 'w' then
        local contacts = {}
        if blade(state, room, player, enemies, strike, 0, footprint.reach, 1.15, true, nil, false, contacts) then
            state.shieldUntil = clock + 60
        end
        effect(state, clock, key, start, start + facing * wRange, footprint, nil, contacts)
    elseif key == 'e' then
        state.spirit = {anchor = start, face = facing, untilFrame = clock + spiritDuration, recastAt = clock + 8, marks = {}}
        teleport(player, safeDestination(room, player, start, start + facing * 54))
        effect(state, clock, key, start, player.Position)
    elseif key == 'e_return' then
        returnSpirit(state, room, player, clock)
    elseif key == 'r' then
        local targets, contacts = {}, {}
        local hit, far = blade(state, room, player, enemies, strike, footprint.width, footprint.reach, 2.5, false, targets, true, contacts)
        local destination = landing(room, player, start, start + facing * math.min(footprint.reach, hit and far + 23 or footprint.reach))
        teleport(player, destination)
        pullFoes(room, targets, destination - facing * 10)
        for index = 1, #contacts do
            local enemy = targets[index]
            if enemy:Exists() then contacts[index] = Vector(enemy.Position.X, enemy.Position.Y) end
        end
        effect(state, clock, key, start, start + facing * footprint.reach, nil, destination, contacts)
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
    if state.spirit and clock >= state.spirit.untilFrame
        and not (state.action and state.action.key == 'r' and clock < state.action.finish) then
        -- An unfinished windup belongs to the spirit's former position.
        state.pending = nil
        returnSpirit(state, room, player, clock)
    end
end

function Combat.absorb(state, clock, position)
    if clock >= (state.shieldUntil or 0) then return false end
    state.shieldUntil = nil
    if position then effect(state, clock, 'shield', position, position) end
    return true
end

function Combat.presentation(state, clock)
    local action = state.action
    if action and clock < action.finish then
        local length = action.finish - action.at
        local skill = skills[action.key]
        return action.key, math.max(0, (clock - action.at) / length), skill and skill.windup, length
    end
end

function Combat.inMeleeRange(room, player, target, items)
    return player.Position:Distance(target.Position) <= attackReach(player, items) + target.Size
        and room:CheckLine(player.Position, target.Position, 3, 0, false, false)
end

function Combat.visual(state, clock)
    local picture = {fx = {}, shield = clock < (state.shieldUntil or 0), qReady = state.qStacks == 2}
    for _, event in ipairs(state.effects) do
        local age = clock - event.at
        if age >= 0 and age < effectFrames then
            picture.fx[#picture.fx + 1] = {id = event.id, kind = event.kind, age = age / 30,
                origin = event.origin, target = event.target, footprint = event.footprint, landing = event.landing,
                contacts = event.contacts, bodyFace = event.bodyFace, bodyRemaining = event.bodyRemaining}
        end
    end
    local spirit = state.spirit
    if not spirit then return picture end
    local keys = {}
    for key, mark in pairs(spirit.marks) do
        if Combat.hostile(mark.entity) then keys[#keys + 1] = key end
    end
    table.sort(keys)
    local marks = {}
    for index = 1, math.min(#keys, markerLimit) do
        local mark = spirit.marks[keys[index]]
        marks[index] = {position = mark.entity.Position, amount = mark.amount}
    end
    picture.spirit = {anchor = spirit.anchor, face = spirit.face, marks = marks,
        remaining = math.max(0, math.min(1, (spirit.untilFrame - clock) / spiritDuration))}
    return picture
end

return Combat
