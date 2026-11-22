local Combat = {}
local Style = include('samira_style')
local Navigation = include('samira_navigation')
local Items
local Weapons
function Combat.bindItems(items) Items = items end
function Combat.bindWeapons(weapons) Weapons = weapons end
local state
local cooldownClock
local attackMoveEnabled = true
local generation = 0
local fps = 30
local cooldowns = {q = 60, w = 660, e = 360, r = 150}
local duration = {q = 11, qmelee = 13, w = 24, e = 7, r = 60}
local qMeleeRange = 108
local qWindup = math.ceil(.25 * fps)
-- Three Isaac grid tiles of travel, with room to pass a target at cast range.
local dashRange, dashTargetRange = 120, 110
local sweepRange, ultRange, comboRange = 100, 120, 30
local inputBuffer = 6
local bindings = {
    {'attackMove', Keyboard.KEY_A},
    {'w', Keyboard.KEY_W, Keyboard.KEY_F6}, {'e', Keyboard.KEY_E, Keyboard.KEY_F7},
    {'q', Keyboard.KEY_Q, Keyboard.KEY_F5}, {'r', Keyboard.KEY_R, Keyboard.KEY_F8},
    {'stop', Keyboard.KEY_S}, {'right'},
}

local function direction(delta, fallback)
    return delta:Length() > 0.01 and delta:Normalized() or fallback
end

local screenAxes, worldCursor = Navigation.screenAxes, Navigation.worldCursor

local function releaseDash(dash, relocate)
    local p = dash and dash.owner
    if p and p:Exists() then
        if relocate then
            p.Position = dash.safe
            p.Velocity = Vector.Zero
        end
        if p.GridCollisionClass == EntityGridCollisionClass.GRIDCOLL_NONE then
            p.GridCollisionClass = dash.collision
        end
    end
    if dash then dash.owner = nil end
end

function Combat.cancelDash(relocate)
    if not state then return end
    releaseDash(state.skills.e, relocate)
    state.skills.e = nil
end

function Combat.reset(keepCooldowns)
    Combat.cancelDash(false)
    Style.reset()
    if Weapons then Weapons.reset() end
    local ready = keepCooldowns and state and state.ready or {}
    if not keepCooldowns then cooldownClock = nil end
    generation = generation + 1
    state = {ready = ready, events = {}, serial = 0, tears = {}, presented = {}, held = {}, commands = {}, skills = {}}
    Combat.sampleInput(nil, 0, false)
end

function Combat.acceptHit(context, clock)
    Style.hit(context, clock)
end

function Combat.onKill(isBoss, clock)
    if not state then return end
    state.ready.e = isBoss and clock or math.max(clock, (state.ready.e or 0) - 45)
end

function Combat.refreshCooldowns()
    if state then state.ready = {} end
end

function Combat.exportCooldowns(clock)
    local result = {}
    for key in pairs(cooldowns) do result[key] = math.max(0, ((state and state.ready[key]) or 0) - clock) end
    return result
end

function Combat.restoreCooldowns(saved, clock)
    if not state or type(saved) ~= 'table' then return end
    for key, maximum in pairs(cooldowns) do
        local remaining = type(saved[key]) == 'number' and saved[key] or 0
        state.ready[key] = clock + math.max(0, math.min(maximum, remaining))
    end
    cooldownClock = clock
end

-- Older saves may have no Hourglass checkpoint. Preserve remaining time if the
-- engine rewinds its frame counter, rather than reusing future deadlines.
function Combat.syncCooldownClock(clock)
    if cooldownClock and clock < cooldownClock then
        local remaining = Combat.exportCooldowns(cooldownClock)
        Combat.reset(true)
        Combat.restoreCooldowns(remaining, clock)
    end
    cooldownClock = clock
end

function Combat.sampleInput(room, clock, actionable, ultimateHeld)
    local manualDown = Input.IsButtonPressed(Keyboard.KEY_A, 0)
    if not actionable or not manualDown then state.manualBlocked = manualDown end
    local manualAttack = not attackMoveEnabled and actionable and manualDown and not state.manualBlocked
    if manualAttack and not state.manualAttack then state.manualPress = worldCursor(room) end
    state.manualAttack = manualAttack
    if not actionable then
        state.commands, state.movement, state.manualPress, state.dragGround = {}, nil, nil, nil
    end
    local aim
    for _, binding in ipairs(bindings) do
        local command, key, alias = table.unpack(binding)
        local down
        if command == 'right' then
            down = Input.IsMouseBtnPressed(1)
        elseif command == 'r' and ultimateHeld ~= nil then
            down = ultimateHeld or Input.IsButtonPressed(alias, 0)
        else
            down = Input.IsButtonPressed(key, 0) or alias ~= nil and Input.IsButtonPressed(alias, 0)
        end
        if actionable and down and not state.held[command]
            and (command ~= 'attackMove' or attackMoveEnabled and not state.manualBlocked) then
            if command == 'right' or command == 'stop' then
                -- An explicit retreat or stop must win over a still-held A.
                state.manualBlocked, state.manualAttack, state.manualPress = manualDown, false, nil
            end
            if command ~= 'stop' then aim = aim or worldCursor(room) end
            if #state.commands >= 12 then table.remove(state.commands, 1) end
            state.commands[#state.commands + 1] = {kind = command, aim = aim, clock = clock}
        end
        state.held[command] = down
    end
end

local function event(clock, kind, position, heading, target, radius, source)
    state.serial = state.serial + 1
    local events = state.events
    if #events == 48 then table.remove(events, 1) end
    events[#events + 1] = {
        id = state.serial, clock = clock, kind = kind, position = position,
        direction = heading, target = target, radius = radius, source = source,
    }
end

function Combat.weaponFired(p, kind, heading, context, clock)
    if not state then return end
    local clip = kind == 'q' and 'q' or 'attack'
    event(clock, clip, p.Position, heading)
    state.weaponPresentation = {kind = clip, heading = heading}
end

local function hostile(entity)
    return entity and entity:Exists() and not entity:IsDead() and entity:IsVulnerableEnemy()
        and not entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

local function nearCursor(entities, cursor, player, reach)
    local target, best
    for _, entity in ipairs(entities) do
        if hostile(entity) and (not reach or entity.Position:Distance(player.Position) <= reach) then
            local distance = entity.Position:Distance(cursor)
            if distance <= math.max(16, entity.Size + 8) and (not best or distance < best) then
                target, best = entity, distance
            end
        end
    end
    return target
end

local function walkable(room, p, point)
    if not room:IsPositionInRoom(point, 0) then return false end
    local collision = room:GetGridCollision(room:GetGridIndex(point))
    return collision == GridCollisionClass.COLLISION_NONE
        or p.CanFly and collision < GridCollisionClass.COLLISION_WALL
end

local function clear(room, p, point, crossing)
    local radius = math.min(18, math.max(8, p.Size * .65))
    if not room:IsPositionInRoom(point, radius) then return false end
    if crossing then
        for slot = 0, 7 do
            local door = room:GetDoor(slot)
            if door and not door:IsOpen() and door.Position:Distance(point) <= radius + 12 then return false end
        end
    end
    local function sample(pos)
        if not crossing then return walkable(room, p, pos) end
        return room:GetGridCollision(room:GetGridIndex(pos)) < GridCollisionClass.COLLISION_WALL
    end
    if not sample(point) then return false end
    for angle = 0, 315, 45 do
        if not sample(point + Vector(radius, 0):Rotated(angle)) then return false end
    end
    return true
end

local function clearSegment(room, p, from, to)
    if not p.CanFly and not room:CheckLine(from, to, 0, 0, false, false) then return false end
    local delta = to - from
    local samples = math.max(1, math.ceil(delta:Length() / 6))
    for sample = 1, samples do
        if not clear(room, p, from + delta * (sample / samples)) then return false end
    end
    return true
end

local function canShoot(room, p, target, ranged, from)
    from = from or p.Position
    if ranged and ((Items and Items.spectral and Items.spectral(p))
        or (Weapons and Weapons.passesGrid and Weapons.passesGrid(p))) then
        local delta = target.Position - from
        local steps = math.max(1, math.ceil(delta:Length() / 4))
        for step = 1, steps do
            local point = from + delta * (step / steps)
            if not room:IsPositionInRoom(point, 0)
                or room:GetGridCollision(room:GetGridIndex(point)) >= GridCollisionClass.COLLISION_WALL then
                return false
            end
        end
        return true
    end
    return room:CheckLine(from, target.Position, 3, 0, false, false)
end

local function attackRange(p)
    local base = math.max(56, math.min(165, p.TearRange * .55))
    if Weapons and Weapons.attackRange then base = Weapons.attackRange(p, base) end
    return Items and Items.attackRange(p, base) or base
end

local function inFiringRange(p, room, target, range)
    return p.Position:Distance(target.Position) <= range + target.Size and canShoot(room, p, target, true)
end

local function stopMovement()
    state.goal, state.target, state.path, state.doorway, state.movement = nil, nil, nil, nil, nil
    state.attackMove, state.dragGround = nil, false
end

function Combat.setAttackMove(enabled)
    if enabled == attackMoveEnabled then return end
    attackMoveEnabled = enabled
    if not state then return end
    if state.attackMove then stopMovement() end
    for i = #state.commands, 1, -1 do
        if state.commands[i].kind == 'attackMove' then table.remove(state.commands, i) end
    end
    state.manualAttack, state.manualPress = false, nil
    local held = Input.IsButtonPressed(Keyboard.KEY_A, 0)
    state.held.attackMove, state.manualBlocked = held, held
end

local function move(p, room, destination, amount, clock, game)
    local doorHeading, approach = Navigation.doorHeading(room, p.Position, state.doorway)
    if doorHeading then
        state.movement = doorHeading * amount
        return doorHeading
    end
    destination = approach or destination
    local distance = p.Position:Distance(destination)
    if distance <= 4 then
        if not state.target then state.goal, state.path = nil, nil end
        return
    end
    local target = state.target
    local function firingPosition(point)
        return point:Distance(target.Position) <= attackRange(p) + target.Size
            and canShoot(room, p, target, true, point)
    end
    local waypoint, final = Navigation.waypoint(state, room, p, destination, clock, clear, clearSegment,
        target and firingPosition)
    if not waypoint then
        if final and not target then state.goal, state.path = nil, nil end
        return
    end
    local delta = waypoint - p.Position
    local heading = delta:Normalized()
    local approach = final and math.max(.35, math.min(1, delta:Length() / 16)) or 1
    state.movement = heading * amount * approach
    return heading
end

function Combat.movement()
    return state and state.movement
end

local nativeInertia, walkScale = false, .85

function Combat.setInertia(enabled)
    nativeInertia = enabled
    if state then state.previousWalkHeading = nil end
end

function Combat.setWalkSpeed(percent)
    walkScale = percent / 100
end

function Combat.walkInput(p)
    local intent = Combat.movement()
    if intent and Items and Items.movementInput then intent = Items.movementInput(p, intent) end
    return intent and intent * walkScale
end

-- Isaac applies acceleration to the directional input on the next physics
-- tick. Leave it in charge of speed. Only redirect or brake the momentum
-- already earned by the preceding walk order.
function Combat.finishWalkTick(p, room, suspended)
    if not state then return end
    if nativeInertia or suspended or state.skills.e or not room:IsPositionInRoom(p.Position, 0)
        or p:HasEntityFlags(EntityFlag.FLAG_KNOCKED_BACK) or p:HasEntityFlags(EntityFlag.FLAG_SLOW)
        or p:HasEntityFlags(EntityFlag.FLAG_SLIPPERY_PHYSICS) then
        state.previousWalkHeading = nil
        return
    end
    local previous = state.previousWalkHeading
    local intent = Combat.movement()
    local heading = intent and intent:Normalized()
    state.previousWalkHeading = heading
    if not previous or heading and previous:Dot(heading) > .999 then return end
    local tile = room:GetGridEntity(room:GetGridIndex(p.Position))
    if tile and tile:GetType() == GridEntityType.GRID_SPIDERWEB then return end
    local velocity = p.Velocity
    local walkingSpeed = math.max(0, velocity:Dot(previous))
    if walkingSpeed == 0 then return end
    local adjusted = velocity - previous * walkingSpeed
    if heading then adjusted = adjusted + heading * walkingSpeed end
    -- Preserve transverse pushes; a change of heading must never add speed.
    if adjusted:Length() > velocity:Length() then adjusted = adjusted:Normalized() * velocity:Length() end
    p.Velocity = adjusted
end

function Combat.reduceCooldowns(fraction, clock)
    if not state then return end
    for _, key in ipairs({'q', 'w', 'e'}) do
        state.ready[key] = clock + math.max(0, (state.ready[key] or clock) - clock) * (1 - fraction)
    end
end

local function itemContext(p, kind, clock)
    return Items and Items.newAttack(p, kind, clock) or nil
end

local function cooldown(p, key)
    return Items and Items.cooldown(p, key, cooldowns[key]) or cooldowns[key]
end

local function attackInterval(p)
    local base = p.MaxFireDelay + 1
    return math.max(1, math.ceil(Items and Items.attackInterval(p, base) or base))
end

local function hurt(p, clock, entity, multiplier, kind, context)
    if not context and state then
        local skill = state.skills[kind == 'qmelee' and 'q' or kind == 'eq' and 'e' or kind]
        context = skill and (kind == 'eq' and skill.comboItemContext or skill.itemContext)
    end
    local function damage() return entity:TakeDamage(p.Damage * multiplier, 0, EntityRef(p), 0) end
    local accepted
    if Items and context then accepted = Items.withContext(context, damage) else accepted = damage() end
    if accepted ~= false then
        event(clock, 'hit', entity.Position, nil, nil, nil, kind)
    end
end

local function fire(p, clock, heading, kind, context)
    context = context or itemContext(p, kind, clock)
    local velocity = heading * (kind == 'q' and 16 or 12) * math.max(.4, p.ShotSpeed)
    local function spawn() return p:FireTear(p.Position, velocity, false, true, false, p, kind == 'q' and 1.5 or 1) end
    local tear
    if Items and context then tear = Items.withContext(context, spawn) else tear = spawn() end
    if tear then
        if Items and context then Items.tagTear(p, tear, context) end
        state.serial = state.serial + 1
        local data = tear:GetData()
        data.SamiraVisual = true
        data.SamiraVisualKind = kind
        data.SamiraVisualId = state.serial
        data.SamiraVisualGeneration = generation
        state.tears[#state.tears + 1] = {id = state.serial, tear = tear, kind = kind}
    end
    event(clock, kind, p.Position, heading)
end

local function projectileHostile(entity)
    if entity.Type ~= EntityType.ENTITY_PROJECTILE or not entity:Exists() or entity:IsDead()
        or entity:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then return false end
    local projectile = entity:ToProjectile()
    if projectile:HasProjectileFlags(ProjectileFlags.CANT_HIT_PLAYER) then return false end
    local spawner = projectile.SpawnerEntity
    return not spawner or spawner.Type ~= EntityType.ENTITY_PLAYER
        and not spawner:HasEntityFlags(EntityFlag.FLAG_FRIENDLY)
end

function Combat.blockProjectile(p, clock, entity)
    local skill = state.skills.w
    if skill and clock < skill.clock + skill.duration
        and entity.Position:Distance(p.Position) <= sweepRange and projectileHostile(entity) then
        event(clock, 'block', entity.Position)
        entity:Remove()
        return true
    end
end

local function radialDamage(p, clock, entities, radius, amount, kind)
    for _, entity in ipairs(entities) do
        if hostile(entity) and entity.Position:Distance(p.Position) <= radius + entity.Size then
            hurt(p, clock, entity, amount, kind)
        end
    end
end

local function dashLanding(room, p, heading, distance, targetDistance)
    local steps = math.max(1, math.ceil(distance / 4))
    local nearSafe, farSafe, crossed, farCrossed
    for step = 1, steps do
        local length = distance * step / steps
        local point = p.Position + heading * length
        if targetDistance and not clear(room, p, point, true) then break end
        if clear(room, p, point) then
            if not crossed then nearSafe = point end
            if targetDistance and length >= targetDistance then
                farSafe, farCrossed = point, crossed
            end
        elseif not targetDistance then
            break
        else
            crossed = true
        end
    end
    if targetDistance then return farSafe, farCrossed end
    return nearSafe
end

local fireplaces = {[0] = true, [1] = true, [2] = true, [3] = true, [10] = true}

local function sweep(p, room, entities, skill, clock)
    if skill.itemContext then skill.itemContext.stylePart = clock == skill.clock and 1 or 2 end
    event(clock, 'w', p.Position, skill.face, nil, sweepRange)
    for _, entity in ipairs(entities) do
        if entity.Type == EntityType.ENTITY_FIREPLACE and fireplaces[entity.Variant]
            and entity:Exists() and not entity:IsDead() and entity.HitPoints > 0
            and entity.Position:Distance(p.Position) <= sweepRange then
            entity:Die()
        end
    end
    for index = 0, room:GetGridSize() - 1 do
        local grid = room:GetGridEntity(index)
        if grid and grid.CollisionClass ~= GridCollisionClass.COLLISION_NONE
            and grid.Position:Distance(p.Position) <= sweepRange then
            local kind = grid:GetType()
            -- GRID_ROCK_ALT is the ordinary pot, mushroom or skull. The
            -- route skull has its own GRID_ROCK_ALT2 type.
            if kind == GridEntityType.GRID_POOP or kind == GridEntityType.GRID_ROCK_ALT then
                room:DestroyGrid(index, false)
            end
        end
    end
    radialDamage(p, clock, entities, sweepRange, .85, 'w')
end

local function blockNearby(p, entities, clock)
    for _, entity in ipairs(entities) do
        if entity.Type == EntityType.ENTITY_PROJECTILE then Combat.blockProjectile(p, clock, entity) end
    end
end

-- The sword sweeps a forward semicircle. Prefer the gun down its firing
-- lane over a sword swing at incidental targets on the flanks.
local function swordQ(p, room, entities, heading)
    local flank, gunTarget = false, false
    for _, entity in ipairs(entities) do
        if hostile(entity) then
            local delta = entity.Position - p.Position
            local ahead, distance = delta:Dot(heading), delta:Length()
            local edge = distance - entity.Size
            if ahead >= -entity.Size and edge <= qMeleeRange and canShoot(room, p, entity) then
                local outward = entity.Velocity:Dot(direction(delta, heading))
                if edge < qMeleeRange - 8 or outward <= 0 or edge + outward * qWindup <= qMeleeRange then
                    if ahead >= distance * .55 then return true end
                    flank = true
                elseif ahead >= distance * .55 then
                    gunTarget = true
                end
            elseif ahead > 0 and edge <= p.TearRange and math.abs(delta.X * heading.Y - delta.Y * heading.X) <= entity.Size + 8
                and canShoot(room, p, entity, true) then
                gunTarget = true
            end
        end
    end
    return flank and not gunTarget
end

local function startSkill(p, room, entities, key, aim, face, clock)
    if key == 'r' and not Style.canCast(clock) then return end
    local heading = direction(aim - p.Position, face)
    local kind, dashGoal, crossing = key, nil, nil
    local dash = state.skills.e
    local context
    local function beginCast(kind)
        context = itemContext(p, kind, clock)
        if Items then Items.onCast(p, key, clock, context) end
        return context
    end
    if key == 'q' and dash then
        dash.comboItemContext = beginCast('eq')
        state.ready.q = clock + cooldown(p, 'q')
        dash.kind, dash.comboAt = 'eq', clock
        event(clock, 'cast', p.Position, dash.face, nil, nil, 'eq')
        return 'eq', dash.face
    elseif key == 'q' then
        if swordQ(p, room, entities, heading) then
            kind = 'qmelee'
        elseif Weapons and not Weapons.requestQ(p, heading, clock, aim, clock + qWindup) then
            return
        end
    elseif key == 'e' then
        local target = nearCursor(entities, aim, p, dashTargetRange)
        local targetDistance
        if target then
            heading = direction(target.Position - p.Position, heading)
            targetDistance = target.Position:Distance(p.Position)
        end
        local origin = p.Position
        dashGoal, crossing = dashLanding(room, p, heading, dashRange, targetDistance)
        if not dashGoal or dashGoal:Distance(origin) < 4 then return end
        stopMovement()
        event(clock, 'e', origin, heading, dashGoal)
    end
    if key == 'q' and Weapons and kind == 'q' then
        -- Native volleys create their own item context when the weapon fires.
        if Items then Items.onCast(p, key, clock) end
    else
        beginCast(kind)
    end
    if key == 'r' then Style.consume(clock, duration.r) end
    state.ready[key] = clock + cooldown(p, key)
    state.skills[key] = {
        kind = kind, clock = clock, duration = duration[kind], face = heading,
        origin = p.Position,
        dashGoal = dashGoal, hit = {},
        itemContext = context,
    }
    if crossing then
        local hop = state.skills.e
        hop.owner, hop.collision, hop.safe = p, p.GridCollisionClass, p.Position
        p.GridCollisionClass = EntityGridCollisionClass.GRIDCOLL_NONE
    end
    event(clock, 'cast', p.Position, heading, nil, nil, kind)
    if key == 'w' then
        blockNearby(p, entities, clock)
        sweep(p, room, entities, state.skills.w, clock)
    end
    return kind, heading
end

local function detonate(p, room, entities, dash, clock)
    local origin, endpoint = dash.origin, p.Position
    local delta = endpoint - origin
    local lengthSquared = math.max(.001, delta:Dot(delta))
    event(clock, 'eq', origin, dash.face, endpoint, comboRange)
    local hit = {}
    for _, entity in ipairs(entities) do
        if not hit[entity.Index] and hostile(entity) then
            local fraction = (entity.Position - origin):Dot(delta) / lengthSquared
            local center = origin + delta * math.max(0, math.min(1, fraction))
            if center:Distance(entity.Position) <= comboRange + entity.Size
                and room:CheckLine(center, entity.Position, 3, 0, false, false) then
                hit[entity.Index] = true
                hurt(p, clock, entity, 1.5, 'eq')
            end
        end
    end
end

local function tickDash(p, room, entities, dash, clock)
    local origin = p.Position
    local remaining = dash.clock + dash.duration - clock
    local delta = (dash.dashGoal - origin) * (1 / remaining)
    local steps = math.max(1, math.ceil(delta:Length() / 4))
    local finished = remaining == 1
    for step = 1, steps do
        local point = origin + delta * (step / steps)
        if not clear(room, p, point, dash.owner ~= nil) then
            finished = true
            dash.duration = clock - dash.clock + 1
            break
        end
        p.Position = point
        if dash.owner and clear(room, p, point) then dash.safe = point end
        for _, entity in ipairs(entities) do
            if not dash.hit[entity.Index] and hostile(entity)
                and entity.Position:Distance(point) <= entity.Size + p.Size then
                dash.hit[entity.Index] = true
                hurt(p, clock, entity, 1.25, 'e')
            end
        end
    end
    p.Velocity = Vector.Zero
    if finished then
        releaseDash(dash, dash.owner ~= nil and not clear(room, p, p.Position))
        if dash.kind == 'eq' then detonate(p, room, entities, dash, clock) end
    end
end

local function tickSkills(p, room, entities, clock)
    local skills = state.skills
    local dash, whirl, ult = skills.e, skills.w, skills.r
    if dash then tickDash(p, room, entities, dash, clock) end
    local q = skills.q
    if q and not q.released and clock >= q.clock + qWindup then
        q.released = true
        if q.kind == 'qmelee' then
            event(clock, q.kind, p.Position, q.face, nil, qMeleeRange)
            for _, entity in ipairs(entities) do
                if hostile(entity) then
                    local delta = entity.Position - p.Position
                    if delta:Length() <= qMeleeRange + entity.Size and delta:Dot(q.face) >= -entity.Size
                        and canShoot(room, p, entity) then
                        hurt(p, clock, entity, 1.5, q.kind, q.itemContext)
                    end
                end
            end
        elseif not Weapons then
            fire(p, clock, q.face, 'q', q.itemContext)
        end
    end
    if whirl then
        if dash or clock ~= whirl.clock then blockNearby(p, entities, clock) end
        if clock - whirl.clock == 18 then sweep(p, room, entities, whirl, clock) end
    end
    local age = ult and clock - ult.clock
    if age and age % 6 == 5 then
        event(clock, 'r', p.Position, ult.face:Rotated(age * 42), nil, ultRange)
        radialDamage(p, clock, entities, ultRange, .55, 'r')
    end
end

local function ends(skill)
    return skill and skill.clock + skill.duration or 0
end

local skillOrder = {'e', 'r', 'w', 'q'}

function Combat.dashing(clock)
    local dash = state and state.skills.e
    -- The final dash displacement lands after the physics pass. Keep it
    -- protected through the next pass, then expire it in Combat.update.
    return dash ~= nil and clock <= ends(dash)
end

function Combat.presentation(clock)
    for _, channel in ipairs(skillOrder) do
        local skill = state.skills[channel]
        if clock < ends(skill) then
            local start = skill.comboAt or skill.clock
            return skill.kind, start, ends(skill) - start
        end
    end
end

local function blockedUntil(key)
    local skills = state.skills
    local q, w, e, r = skills.q, skills.w, skills.e, skills.r
    if key == 'q' then return math.max(ends(q), ends(r), e and 0 or ends(w)) end
    if key == 'w' then return math.max(ends(q), ends(e), ends(r)) end
    if key == 'e' then return ends(e) end
    return math.max(ends(q), e and e.kind == 'eq' and ends(e) or 0)
end

function Combat.styleStatus(clock)
    local status = Style.status(clock, state and state.ready.r)
    if status.ready and state and clock < blockedUntil('r') then status.ready = false end
    return status
end

local function commandMove(kind, room, p, entities, aim, clock)
    local previous = state.attackMove
    stopMovement()
    if kind == 'attackMove' then
        state.goal = room:GetClampedPosition(aim, 10)
        state.target = nearCursor(entities, aim, p)
        -- Reissuing A at the same target must not restart an ongoing windup.
        state.attackMove = {point = aim, explicit = state.target,
            windingTarget = previous and previous.windingTarget, releaseAt = previous and previous.releaseAt}
    elseif kind == 'right' then
        state.target = nearCursor(entities, aim, p)
        state.doorway = not state.target and Navigation.doorAt(room, aim) or nil
        state.goal = not state.target and room:GetClampedPosition(aim, 10) or nil
        state.dragGround = not state.target and not state.doorway
        state.dragAim = aim
    end
    if state.target or state.goal then
        event(clock, state.target and 'target' or 'move', state.target and state.target.Position or state.goal)
    end
end

local function updateAttackMove(p, room, entities)
    local order = state.attackMove
    if not order then return end
    if not state.goal then stopMovement(); return end
    if order.explicit and hostile(order.explicit) then return end
    order.explicit = nil
    local range = attackRange(p)
    if state.target and inFiringRange(p, room, state.target, range) then return end
    local best, bestDistance
    for _, enemy in ipairs(entities) do
        if hostile(enemy) and inFiringRange(p, room, enemy, range) then
            local distance = enemy.Position:Distance(order.point)
            if not best or distance < bestDistance or distance == bestDistance and enemy.Index < best.Index then
                best, bestDistance = enemy, distance
            end
        end
    end
    if best ~= state.target then state.target, state.path = best, nil end
end

function Combat.update(game, p, face, clock)
    local room, entities = game:GetRoom(), Isaac.GetRoomEntities()
    state.movement = nil
    local manualPress = state.manualPress
    state.manualPress = nil
    for _, channel in ipairs(skillOrder) do
        local skill = state.skills[channel]
        if skill and clock >= ends(skill) then
            if channel == 'e' then releaseDash(skill, true) end
            state.skills[channel] = nil
        end
    end
    local presented = state.weaponPresentation
    state.weaponPresentation = nil
    local kind, heading = presented and presented.kind, presented and presented.heading
    local pending = {}
    local commands = state.commands
    -- Two presses can arrive in separate render callbacks before this tick.
    -- Prepare an available E before Q so both can form the dash combo.
    if not state.skills.e and clock >= math.max(blockedUntil('e'), state.ready.e or 0) then
        for index, command in ipairs(commands) do
            if command.kind == 'q' then
                for later = index + 1, #commands do
                    if commands[later].kind == 'e' and clock <= commands[later].clock + inputBuffer then
                        table.insert(commands, index, table.remove(commands, later))
                        break
                    end
                end
                break
            end
        end
    end
    for _, command in ipairs(commands) do
        local key = command.kind
        if not cooldowns[key] then
            commandMove(key, room, p, entities, command.aim, clock)
        elseif clock <= command.clock + inputBuffer and (state.ready[key] or 0) <= command.clock + inputBuffer then
            local busyUntil = blockedUntil(key)
            if clock >= math.max(busyUntil, state.ready[key] or 0) then
                local cast, aim = startSkill(p, room, entities, key, command.aim, heading or face, clock)
                if cast then kind, heading = cast, aim end
            elseif busyUntil <= command.clock + inputBuffer then
                pending[#pending + 1] = command
            end
        end
    end
    state.commands = pending
    if not state.held.right or state.manualAttack or state.skills.e then state.dragGround = false end
    if state.dragGround then
        local cursor = worldCursor(room)
        if cursor:Distance(state.dragAim) >= 8 then
            state.dragAim = cursor
            state.doorway = Navigation.doorAt(room, cursor)
            state.goal = room:GetClampedPosition(cursor, 10)
        end
    end
    if state.target and not hostile(state.target) then
        state.target, state.path = nil, nil
    end
    updateAttackMove(p, room, entities)
    tickSkills(p, room, entities, clock)
    if Weapons and Weapons.trackCursor then Weapons.trackCursor(p, worldCursor(room)) end
    local q = state.skills.q
    if q then
        if Weapons then Weapons.update(p, clock, nil, q.kind == 'q') end
        if not state.skills.e then
            if not q.released then
                p.Velocity = Vector.Zero
            elseif state.target and not inFiringRange(p, room, state.target, attackRange(p))
                or not state.target and state.goal then
                move(p, room, state.target and state.target.Position or state.goal, 1, clock, game)
            end
        end
        return kind, state.skills.e and state.skills.e.face or q.face
    end
    if Weapons then
        -- A reserved native Q can outlast its animation while the weapon charges.
        Weapons.update(p, clock, nil, not Combat.presentation(clock) or Weapons.hasPendingQ(p))
    end
    if state.skills.e then return kind, state.skills.e.face end

    local skill, target = Combat.presentation(clock), state.target
    local attackReady = clock >= (state.attackReady or 0)
    if (state.manualAttack or manualPress) and not skill then
        local mobileCharge = Weapons and Weapons.isChargeWeapon and Weapons.isChargeWeapon(p)
        if mobileCharge then
            if state.goal or state.target then
                move(p, room, state.goal or state.target.Position, 1, clock, game)
            end
        else
            stopMovement()
            p.Velocity = Vector.Zero
        end
        local aim = state.manualAttack and worldCursor(room) or manualPress
        heading = direction(aim - p.Position, face)
        if Weapons then
            Weapons.update(p, clock, heading, true, aim)
            return kind, heading
        end
        if not attackReady then return kind, heading end
        fire(p, clock, heading, 'attack')
        state.attackReady = clock + attackInterval(p)
        return 'attack', heading
    end
    local slow = state.skills.r and .55 or 1
    local targetInRange = target and inFiringRange(p, room, target, attackRange(p))
    local order = state.attackMove
    if order and (not targetInRange or skill) then order.windingTarget = nil end
    if targetInRange then
        if order and not skill and not (Weapons and Weapons.isChargeWeapon and Weapons.isChargeWeapon(p)) then
            -- Stop for acquisition. Once aimed, the native weapon owns the rate
            -- of fire; a new move order can always cancel the attack.
            local targetId = GetPtrHash(target)
            if order.windingTarget ~= targetId then
                order.windingTarget = targetId
                order.releaseAt = clock + math.min(5, math.max(1, math.floor(attackInterval(p) * .25 + .5)))
            end
            if clock < order.releaseAt then
                p.Velocity = Vector.Zero
                return kind, direction(target.Position - p.Position, face)
            end
        end
        if Weapons then
            heading = direction(target.Position - p.Position, face)
            Weapons.update(p, clock, not skill and heading or nil, not skill, target.Position)
            return kind, heading
        end
        if not skill and attackReady then
            heading = direction(target.Position - p.Position, face)
            if p.Position:Distance(target.Position) <= 32 + target.Size
                and room:CheckLine(p.Position, target.Position, 1, 0, false, false) then
                kind = 'melee'
                event(clock, kind, p.Position, heading, target.Position, 38)
                local context = itemContext(p, kind, clock)
                if Items and Items.onMelee then Items.onMelee(p, context, target) end
                hurt(p, clock, target, 1, kind, context)
            else
                kind = 'attack'
                fire(p, clock, heading, kind)
            end
            state.attackReady = clock + attackInterval(p)
        end
    elseif target or state.goal then
        local movement = move(p, room, target and target.Position or state.goal, slow, clock, game)
        if not skill then heading = heading or movement end
    end
    return kind, heading
end

function Combat.tearHit(clock, target, source)
    if source and source.Type == EntityType.ENTITY_TEAR and hostile(target) then
        local data = source:GetData()
        if data.SamiraVisual and data.SamiraVisualGeneration == generation then
            event(clock, 'hit', target.Position, nil, nil, nil, data.SamiraVisualKind)
        end
    end
end

function Combat.rendersTear(tear, seq)
    local data = tear:GetData()
    local first = state and state.presented[data.SamiraVisualId]
    return state and data.SamiraVisual == true and data.SamiraVisualGeneration == generation
        and first and first <= seq
end

function Combat.visual(room, clock, seq)
    local events, projectiles, cooldown = {}, {}, {}
    local axis, width = screenAxes(), Isaac.GetScreenWidth()
    local mirror = room:IsMirrorWorld()
    local function point(world)
        local q = Isaac.WorldToScreen(world)
        return {mirror and width - q.X or q.X, q.Y}
    end
    local function vector(world, unit)
        local q = Vector(world.X * axis.X * (mirror and -1 or 1), world.Y * axis.Y)
        if unit then q = q:Normalized() end
        return {q.X, q.Y}
    end
    for _, e in ipairs(state.events) do
        local age = (clock - e.clock) / fps
        if age >= 0 and age < 1.25 then
            events[#events + 1] = {
                id = e.id, kind = e.kind, age = age, position = point(e.position),
                direction = e.direction and vector(e.direction, true), target = e.target and point(e.target),
                radius = e.radius and math.abs(axis.X) * e.radius, source = e.source,
            }
        end
    end
    local liveTears, presented = {}, {}
    for _, entry in ipairs(state.tears) do
        local tear = entry.tear
        if tear:Exists() and not tear:IsDead() then
            liveTears[#liveTears + 1] = entry
            if #projectiles < 64 then
                presented[entry.id] = state.presented[entry.id] or seq
                local pos = point(tear.Position)
                pos[2] = pos[2] + tear.Height * axis.Y
                projectiles[#projectiles + 1] = {
                    id = entry.id, kind = entry.kind, position = pos, velocity = vector(tear.Velocity),
                }
            end
        end
    end
    state.tears, state.presented = liveTears, presented
    for key in pairs(cooldowns) do cooldown[key] = math.max(0, (state.ready[key] or clock) - clock) / fps end
    local skills = {}
    for _, channel in ipairs(skillOrder) do
        local skill = state.skills[channel]
        if clock < ends(skill) then
            local start = skill.comboAt or skill.clock
            local radius = skill.kind == 'w' and sweepRange or skill.kind == 'r' and ultRange or nil
            skills[#skills + 1] = {
                kind = skill.kind, age = (clock - start) / fps, duration = (ends(skill) - start) / fps,
                windup = skill.kind == 'qmelee' and qWindup / fps or nil,
                radius = radius and radius * math.abs(axis.X),
            }
        end
    end
    return {
        events = events, projectiles = projectiles, cooldowns = cooldown,
        style = Combat.styleStatus(clock),
        charge = Weapons and Weapons.chargeStatus and Weapons.chargeStatus(Isaac.GetPlayer(0)),
        ground = {1, math.abs(axis.Y / axis.X)},
        skill = skills[1], skills = skills,
        target = hostile(state.target) and point(state.target.Position) or nil,
        moveGoal = state.goal and point(state.goal) or nil,
    }
end

return Combat
