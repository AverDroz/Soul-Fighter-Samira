local Combat = {}
local Artifacts = include('yone_artifacts')

-- Timings are Isaac update frames (30 Hz).
local skills = {
    attack = {windup = 4, duration = 14},
    q = {windup = 6, duration = 16},
    q3 = {windup = 7, duration = 22},
    w = {windup = 8, duration = 22, cooldown = 180},
    e = {windup = 3, duration = 14, cooldown = 450},
    e_return = {windup = 0, duration = 13},
    r = {windup = 23, duration = 40, cooldown = 900},
}
local meleeRange, qRange, q3Range, ultRange, wRange = 44, 124, 212, 168, 112
local spiritDuration, markDamage, wCosine, qStackDuration = 150, .30, .35, 180
local spiritDash, q3Dash, spiritReturnFrames = 84, 156, 8
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

local function releaseReturn(state, relocate)
    local recall = state.returning
    if not recall then return end
    state.returning = nil
    local player = recall.owner
    if not player:Exists() then return end
    if relocate then player.Position, player.Velocity = recall.safe, Vector.Zero end
    if player.GridCollisionClass == EntityGridCollisionClass.GRIDCOLL_NONE then
        player.GridCollisionClass = recall.collision
    end
end

function Combat.resetRoom(state, clock, relocate)
    releaseReturn(state, relocate)
    state.pending, state.action, state.spirit, state.shieldUntil = nil, nil, nil, nil
    state.directImpact, state.effects, state.q3InvulnerableUntil = nil, {}, nil
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

function Combat.cast(state, input, player, aim, clock, room)
    if state.returning or state.pending or (state.action and state.action.key == 'r' and clock < state.action.finish) then return end
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
    if key == 'q' or key == 'q3' or key == 'w' or key == 'r' then
        local footprint = Combat.footprint(state, player, key, aim, room)
        footprint.origin = Vector(player.Position.X, player.Position.Y)
        footprint.facing = Vector(state.face.X, state.face.Y)
        footprint.key = key == 'q3' and 'q' or key
        state.pending.footprint = footprint
    end
    if key ~= 'e_return' then
        local cooldown = skill.cooldown or attackDelay(player)
        if input == 'q' then
            local bonus = math.max(0, 10 / math.max(1, player.MaxFireDelay + 1) - 1)
            cooldown = math.max(10, math.ceil(30 * (1 - math.min(2 / 3, .6 * bonus)) - .000001))
        end
        if input ~= 'attack' and state.items then
            if input ~= 'q' and state.items.cooldown then cooldown = math.max(12, state.items.cooldown(player, input, cooldown)) end
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
    if key == 'q' then reach, width = qRange * Artifacts.range(player), 18
    elseif key == 'q3' then reach, width = q3Range * Artifacts.range(player), 22
    elseif key == 'w' then reach, shape, cosine = wRange, 'sector', wCosine
    elseif key == 'e' then reach, width = spiritDash, math.max(6, player.Size * .6)
    elseif key == 'r' then
        reach, width = ultRange, 16
    else return nil end
    if room and (key == 'q' or key == 'q3' or key == 'r') then
        -- The hit line may cross interior grids but never leave and re-enter a room.
        for distance = 1, math.ceil(reach) do
            local sample = math.min(distance, reach)
            if not room:IsPositionInRoom(player.Position + facing * sample, 0) then
                reach = distance - 1
                break
            end
        end
    end
    return {shape = shape or 'line', origin = player.Position, facing = facing,
        reach = reach, width = width, cosine = cosine}
end

function Combat.activeFootprint(state, player, room)
    local pending = state.pending
    local area = pending and pending.footprint or nil
    return area, area and area.key or nil
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
    local origin = strike.footprint and strike.footprint.origin or player.Position
    local side = Vector(-facing.Y, facing.X)
    local candidates = {}
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) then
            local delta = enemy.Position - origin
            local along = delta:Dot(facing)
            local across = math.abs(delta:Dot(side))
            local distance = delta:Length()
            local inRange = sweep and distance <= reach + enemy.Size and along >= distance * wCosine
                or not sweep and along >= 0 and along <= reach + enemy.Size and across <= width + enemy.Size
                and (not throughWalls or along <= reach)
            if inRange and (throughWalls or room:CheckLine(origin, enemy.Position, 3, 0, false, false)) then
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
        if grid then
            local kind = grid:GetType()
            local intactPoop = kind == GridEntityType.GRID_POOP and grid.State < 1000
            local intactTnt = kind == GridEntityType.GRID_TNT
                and grid.CollisionClass ~= GridCollisionClass.COLLISION_NONE
            if intactPoop or intactTnt then
                local delta = grid.Position - start
                local along = delta:Dot(facing)
                if along >= 0 and along <= reach and math.abs(delta:Dot(side)) <= width + 16 then
                    if intactPoop then room:DestroyGrid(index, false) else grid:Hurt(1) end
                end
            end
        end
    end
end

-- Damage tear-collidable non-hostile NPCs separately so scenery cannot grant
-- Q stacks, E marks, or consume first-target item effects.
local function qObjects(room, player, entities, strike, multiplier, contacts)
    local area = strike.footprint
    local side = Vector(-strike.facing.Y, strike.facing.X)
    for _, entity in ipairs(entities) do
        local collision = entity.EntityCollisionClass
        local tearCollision = EntityCollisionClass and (collision == EntityCollisionClass.ENTCOLL_ALL
            or collision == EntityCollisionClass.ENTCOLL_PLAYEROBJECTS)
        if entity:Exists() and not entity:IsDead() and not Combat.hostile(entity)
            and not entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
            and (entity.Type == EntityType.ENTITY_FIREPLACE or entity:ToNPC() and tearCollision) then
            local delta = entity.Position - area.origin
            local along = delta:Dot(strike.facing)
            if along >= 0 and along <= area.reach and math.abs(delta:Dot(side)) <= area.width + entity.Size then
                if entity:TakeDamage(player.Damage * multiplier, 0, EntityRef(player), 0) and #contacts < markerLimit then
                    contacts[#contacts + 1] = Vector(entity.Position.X, entity.Position.Y)
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
    local entry = {id = state.effectSerial, at = clock, kind = kind,
        origin = origin, target = target, footprint = footprint, landing = landingPoint,
        contacts = contacts, bodyFace = bodyFace, bodyRemaining = bodyRemaining}
    effects[#effects + 1] = entry
    return entry
end

local function returnSpirit(state, room, player, clock)
    local spirit = state.spirit
    if not spirit then return end
    state.spirit = nil
    local start = player.Position
    local toAnchor = spirit.anchor - start
    if toAnchor:Length() > .01 then state.face = toAnchor:Normalized() end
    local destination = Combat.clearPoint(room, player, spirit.anchor) and spirit.anchor or start
    state.returning = {owner = player, collision = player.GridCollisionClass, spirit = spirit,
        start = start, target = destination, safe = start, at = clock, finish = clock + spiritReturnFrames}
    player.GridCollisionClass = EntityGridCollisionClass.GRIDCOLL_NONE
    player.Velocity = Vector.Zero
    local cue = effect(state, clock, 'e_return', start, destination, nil, nil, {}, spirit.face,
        math.max(0, math.min(1, (spirit.untilFrame - clock) / spiritDuration)))
    cue.travel = spiritReturnFrames
    state.action = {key = 'e_return', at = clock, finish = clock + skills.e_return.duration,
        travel = spiritReturnFrames}
end

local function advanceReturn(state, room, player, clock)
    local recall = state.returning
    local progress = math.min(1, (clock - recall.at) / spiritReturnFrames)
    local eased = progress * progress * (3 - 2 * progress)
    local position = recall.start + (recall.target - recall.start) * eased
    if Combat.clearPoint(room, player, position) then recall.safe = position end
    if clock < recall.finish then
        if room:IsPositionInRoom(position, 0) then teleport(player, position) end
        return
    end
    releaseReturn(state, true)
    local contacts = {}
    for _, mark in pairs(recall.spirit.marks) do
        if Combat.hostile(mark.entity) then
            local point = Vector(mark.entity.Position.X, mark.entity.Position.Y)
            if damage(state, player, mark.entity, mark.amount) and #contacts < markerLimit then
                contacts[#contacts + 1] = point
            end
        end
    end
    if #contacts > 0 then effect(state, clock, 'e_echo', player.Position, player.Position, nil, nil, contacts) end
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
    local footprint = strike.footprint
    local start = footprint and footprint.origin or player.Position
    local items = state.items
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
        if blade(state, room, player, enemies, strike, footprint.width, reach, 1.4, false, nil, true, contacts) then
            state.qStacks, state.qExpires = math.min(2, state.qStacks + 1), clock + qStackDuration
        end
        qObjects(room, player, enemies, strike, 1.4, contacts)
        breakProps(room, start, facing, footprint.width, reach)
        effect(state, clock, key, start, start + facing * reach, nil, nil, contacts)
    elseif key == 'q3' then
        state.qStacks, state.qExpires = 0, nil
        local reach, contacts = footprint.reach, {}
        blade(state, room, player, enemies, strike, footprint.width, reach, 1.6, false, nil, true, contacts)
        qObjects(room, player, enemies, strike, 1.6, contacts)
        breakProps(room, start, facing, footprint.width, reach)
        teleport(player, safeDestination(room, player, start, start + facing * math.min(q3Dash, reach)))
        state.q3InvulnerableUntil = clock + 5
        effect(state, clock, key, start, start + facing * reach, nil, player.Position, contacts)
    elseif key == 'w' then
        local contacts = {}
        if blade(state, room, player, enemies, strike, 0, footprint.reach, 1.15, true, nil, false, contacts) then
            state.shieldUntil = clock + 60
        end
        effect(state, clock, key, start, start + facing * wRange, footprint, nil, contacts)
    elseif key == 'e' then
        state.spirit = {anchor = start, face = facing, untilFrame = clock + spiritDuration, recastAt = clock + 8, marks = {}}
        teleport(player, safeDestination(room, player, start, start + facing * spiritDash))
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
    if state.lastClock and clock < state.lastClock then Combat.resetRoom(state, clock, true) end
    state.lastClock = clock
    if state.qExpires and clock >= state.qExpires then state.qStacks, state.qExpires = 0, nil end
    if state.returning then advanceReturn(state, room, player, clock) end
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

function Combat.q3Invulnerable(state, clock)
    return state.q3InvulnerableUntil ~= nil and clock < state.q3InvulnerableUntil
end

function Combat.invulnerable(state, clock)
    return state.returning ~= nil or Combat.q3Invulnerable(state, clock)
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
        return action.key, math.max(0, (clock - action.at) / length), skill and skill.windup, length, action.travel
    end
end

function Combat.inMeleeRange(room, player, target, items)
    return player.Position:Distance(target.Position) <= attackReach(player, items) + target.Size
        and room:CheckLine(player.Position, target.Position, 3, 0, false, false)
end

function Combat.visual(state, clock)
    local picture = {fx = {}, shield = clock < (state.shieldUntil or 0), qReady = state.qStacks == 2}
    if picture.qReady then
        picture.qRemaining = math.max(0, math.min(1, ((state.qExpires or clock) - clock) / qStackDuration))
    end
    for _, event in ipairs(state.effects) do
        local age = clock - event.at
        if age >= 0 and age < effectFrames then
            picture.fx[#picture.fx + 1] = {id = event.id, kind = event.kind, age = age / 30,
                origin = event.origin, target = event.target, footprint = event.footprint, landing = event.landing,
                contacts = event.contacts, bodyFace = event.bodyFace, bodyRemaining = event.bodyRemaining,
                travel = event.travel}
        end
    end
    local returning = state.returning
    local spirit = state.spirit or returning and returning.spirit
    if not spirit then return picture end
    local keys = {}
    for key, mark in pairs(spirit.marks) do
        if Combat.hostile(mark.entity) then keys[#keys + 1] = key end
    end
    table.sort(keys)
    local marks = {}
    for index = 1, math.min(#keys, markerLimit) do
        local mark = spirit.marks[keys[index]]
        marks[index] = {position = mark.entity.Position, amount = mark.amount,
            lethal = mark.amount >= math.max(0, mark.entity.HitPoints)}
    end
    picture.spirit = {anchor = spirit.anchor, face = spirit.face, marks = marks,
        returning = returning ~= nil,
        remaining = returning and 0 or math.max(0, math.min(1, (spirit.untilFrame - clock) / spiritDuration))}
    return picture
end

return Combat
