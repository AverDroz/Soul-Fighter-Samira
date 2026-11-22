local Yone = {}
local Combat = include('yone_combat')
local Emotes = include('yone_emotes')
local Navigation = include('samira_navigation')
local json = require('json')
local playerType
local badge
local Display
local fps, leaseMs = 30, 500
local spiritWarningTicks = 2 * fps
local floorRebindMs = 650
local abilities = {'q', 'w', 'e', 'r'}
local abilityHudHeight, abilityHudGap = 38, 2
local abilityReady = {.92, .92, 1, 1}
local abilityCooling = {.69, .67, .76, 1}
local abilityRecast = {.56, .83, 1, 1}
local abilityHudPalette
local abilityFont
local abilityIcons
local aimColors = {
    q = {.60, .93, 1}, w = {.99, .49, .60}, e = {.99, .39, .65}, r = {1, .53, .73},
}
local numberKeys = {Keyboard.KEY_1, Keyboard.KEY_2, Keyboard.KEY_3, Keyboard.KEY_4, Keyboard.KEY_5, Keyboard.KEY_6}
local controls = {
    {'q', Keyboard.KEY_Q}, {'w', Keyboard.KEY_W}, {'e', Keyboard.KEY_E}, {'r', Keyboard.KEY_R},
    {'attack', Keyboard.KEY_A}, {'stop', Keyboard.KEY_S}, {'mouse'},
}
local axes = {
    [ButtonAction.ACTION_LEFT] = Vector(-1, 0), [ButtonAction.ACTION_RIGHT] = Vector(1, 0),
    [ButtonAction.ACTION_UP] = Vector(0, -1), [ButtonAction.ACTION_DOWN] = Vector(0, 1),
}
local blocked = {
    [ButtonAction.ACTION_SHOOTLEFT] = true, [ButtonAction.ACTION_SHOOTRIGHT] = true,
    [ButtonAction.ACTION_SHOOTUP] = true, [ButtonAction.ACTION_SHOOTDOWN] = true,
}
local rebound = {[ButtonAction.ACTION_BOMB] = Keyboard.KEY_G, [ButtonAction.ACTION_PILLCARD] = Keyboard.KEY_4}

function Yone.is(player)
    if not player or not player.GetPlayerType then return false end
    if not playerType then
        local result = Isaac.GetPlayerTypeByName('Yone', false)
        if result >= 0 then playerType = result end
    end
    return playerType ~= nil and player:GetPlayerType() == playerType
end

function Yone.player(game)
    if not Isaac.IsInGame() or game:GetNumPlayers() ~= 1 then return end
    local player = Isaac.GetPlayer(0)
    if Yone.is(player) then return player end
end

local function pressed(key)
    return Input.IsButtonPressed(key, 0)
end

local function packet(payload)
    Isaac.DebugString('[SAMIRA_EXTERNAL] ' .. json.encode(payload))
end

local function obscured(game, state, player)
    local sprite = player:GetSprite()
    local name = sprite:GetAnimation()
    local travel = name:find('Trapdoor', 1, true) ~= nil or name:find('Teleport', 1, true) ~= nil
        or name == 'LightTravel' or name == 'HoleIn' or name == 'FallIn'
    return game:IsPaused() or ImGui.IsVisible() or state.leaving
        or RoomTransition.GetTransitionMode() ~= 0 or RoomTransition.IsRenderingBossIntro()
        or state.coverFrame == game:GetFrameCount() or player:IsDead()
        or travel and sprite:IsPlaying(name)
end

local function canControl(game, state, player)
    return player.ControlsEnabled ~= false and not obscured(game, state, player)
end

local function playMasterySound()
    local sound = Isaac.GetSoundIdByName and Isaac.GetSoundIdByName('Yone Mastery')
    if sound and sound > 0 then SFXManager():Play(sound, .8, 0, false, 1) end
end

local function stopSpiritWarning(state)
    local sound = state.spiritWarningSound
    if sound then SFXManager():Stop(sound) end
    state.spiritWarning, state.spiritWarningSound = nil, nil
end

local function updateSpiritWarning(state, clock)
    local spirit = state.combat.spirit
    if state.spiritWarning and state.spiritWarning ~= spirit then stopSpiritWarning(state) end
    if not spirit or state.spiritWarning == spirit then return end
    local ticks = spirit.untilFrame - clock
    if ticks <= 0 or ticks > spiritWarningTicks then return end
    state.spiritWarning = spirit
    local sound = Isaac.GetSoundIdByName and Isaac.GetSoundIdByName('Yone E Warning')
    if sound and sound > 0 then
        state.spiritWarningSound = sound
        SFXManager():Play(sound, .8, 0, false, 1)
    end
end

local function sampleExpressions(state, clock, allowed, interrupted)
    local keys = {ctrl = pressed(Keyboard.KEY_LEFT_CONTROL) or pressed(Keyboard.KEY_RIGHT_CONTROL),
        disabled = not allowed}
    for index, key in ipairs(numberKeys) do keys[index] = pressed(key) end
    local previousStart = state.emotes.masteryAt
    Emotes.update(state.emotes, clock, keys, interrupted)
    if state.emotes.masteryAt ~= previousStart and state.emotes.masteryAt == clock then playMasterySound() end
end

local function sampleCommands(state, room, allowed, ultimateHeld)
    if not allowed then state.commands, state.intent, state.aimAbility, state.qAfterE = {}, nil, nil, nil end
    for _, control in ipairs(controls) do
        local action, key = table.unpack(control)
        local down
        if action == 'r' then
            down = ultimateHeld
        elseif key then
            down = pressed(key)
        else
            down = Input.IsMouseBtnPressed(1)
        end
        local activate = down and not state.held[action]
        if aimColors[action] then
            if allowed and activate then state.aimAbility = action end
            activate = not down and state.held[action] and state.aimAbility == action
            if activate then state.aimAbility = nil end
        end
        if allowed and activate and #state.commands < #controls then
            state.commands[#state.commands + 1] = {kind = action, aim = Navigation.worldCursor(room)}
        end
        state.held[action] = down
    end
end

local function stopMoving(state)
    state.goal, state.target, state.path, state.door, state.intent = nil, nil, nil, nil, nil
end

local function targetAt(enemies, point)
    local target, nearest
    for _, enemy in ipairs(enemies) do
        if Combat.hostile(enemy) then
            local distance = enemy.Position:Distance(point)
            if distance <= math.max(16, enemy.Size + 8) and (nearest == nil or distance < nearest) then
                target, nearest = enemy, distance
            end
        end
    end
    return target
end

local function setGoal(state, room, aim)
    local bestDistance = 36
    for slot = 0, 7 do
        local door = room:GetDoor(slot)
        if door and door:IsOpen() then
            local distance = door.Position:Distance(aim)
            if distance < bestDistance then
                bestDistance = distance
                state.door = {position = door.Position, outward = Vector(-1, 0):Rotated((slot % 4) * 90)}
            end
        end
    end
    state.goal = room:GetClampedPosition(state.door and state.door.position or aim, 12)
end

local function updateMovement(state, room, player, clock)
    local dx = (pressed(Keyboard.KEY_RIGHT) and 1 or 0) - (pressed(Keyboard.KEY_LEFT) and 1 or 0)
    local dy = (pressed(Keyboard.KEY_DOWN) and 1 or 0) - (pressed(Keyboard.KEY_UP) and 1 or 0)
    if room:IsMirrorWorld() then dx = -dx end
    if dx ~= 0 or dy ~= 0 then
        stopMoving(state)
        state.intent = Vector(dx, dy):Normalized()
        return
    end

    local target = state.target
    if target and not Combat.hostile(target) then stopMoving(state); return end
    if target and Combat.inMeleeRange(room, player, target, state.combat.items) then
        state.intent = nil
        Combat.cast(state.combat, 'attack', player, target.Position, clock, room)
        return
    end
    if state.door and player.Position:Distance(state.door.position) < 29 then
        state.intent = state.door.outward
        return
    end
    local goal = target and target.Position or state.goal
    if not goal then state.intent = nil; return end
    if not target and not state.door and player.Position:Distance(goal) <= 6 then
        stopMoving(state)
        return
    end
    local waypoint = Navigation.waypoint(state, room, player, goal, clock, Combat.clearPoint, Combat.clearSegment)
    state.intent = waypoint and (waypoint - player.Position):Normalized() or nil
end

local function mirrorPosition(room, position)
    local x = room:IsMirrorWorld() and Isaac.GetScreenWidth() - position.X or position.X
    return x, position.Y
end

local function screenPoint(room, world)
    return Vector(mirrorPosition(room, Isaac.WorldToScreen(world)))
end

local function screenHeading(room, world, facing)
    local direction = screenPoint(room, world + facing * 40) - screenPoint(room, world)
    return {direction.X, direction.Y}
end

local function sectorArc(area, project)
    local halfAngle = math.deg(math.acos(area.cosine))
    local edge = area.facing * area.reach
    local points = {}
    for i = 0, 12 do
        points[i + 1] = project(area.origin + edge:Rotated((i / 6 - 1) * halfAngle))
    end
    return points
end

local function drawAim(room, combat, player, clock, key)
    if not Isaac.DrawLine or not KColor then return end
    local area, castKey = Combat.activeFootprint(combat, player, room)
    local casting = area ~= nil
    if casting then
        key = castKey or 'r'
    elseif key then
        area = Combat.footprint(combat, player, key, Navigation.worldCursor(room), room)
    end
    if not area or area.reach < 1 then return end
    local r, g, b = table.unpack(aimColors[key])
    local ready = casting or (clock >= (combat.ready[key] or 0))
        or key == 'e' and combat.spirit and clock >= combat.spirit.recastAt
    local edge = KColor(r, g, b, ready and .93 or .35)
    local fill = KColor(r, g, b, casting and .25 or (ready and .15 or .06))
    local function project(point) return screenPoint(room, point) end
    local function line(a, b, color)
        Isaac.DrawLine(a, b, color, color, casting and color == edge and 2 or 1)
    end
    local start = project(area.origin)
    if area.shape == 'sector' then
        local arc = sectorArc(area, project)
        line(start, arc[1], edge)
        local halfAngle = math.deg(math.acos(area.cosine))
        for i = 0, 48 do
            local endpoint = area.origin + (area.facing * area.reach):Rotated((i / 24 - 1) * halfAngle)
            line(start, project(endpoint), fill)
        end
        for i = 2, #arc do line(arc[i - 1], arc[i], edge) end
        line(arc[#arc], start, edge)
    else
        local side = area.facing:Rotated(90) * area.width
        local target = area.origin + area.facing * area.reach
        local a, b = project(area.origin + side), project(target + side)
        local c, d = project(target - side), project(area.origin - side)
        line(a, b, edge)
        line(b, c, edge)
        line(c, d, edge)
        line(d, a, edge)
        for i = -12, 12 do
            local offset = side * (i / 12)
            line(project(area.origin + offset), project(target + offset), fill)
        end
    end
end

local function visualSnapshot(room, picture)
    local function point(world)
        return {mirrorPosition(room, Isaac.WorldToScreen(world))}
    end
    local snapshot = {shield = picture.shield, qReady = picture.qReady, qRemaining = picture.qRemaining, fx = {}}
    for i, event in ipairs(picture.fx) do
        snapshot.fx[i] = {id = event.id, kind = event.kind, age = event.age,
            origin = point(event.origin), target = point(event.target), travel = event.travel}
        if event.landing then snapshot.fx[i].landing = point(event.landing) end
        if event.contacts then
            local contacts = {}
            for index, position in ipairs(event.contacts) do contacts[index] = point(position) end
            snapshot.fx[i].contacts = contacts
        end
        if event.bodyFace then
            snapshot.fx[i].bodyFace = screenHeading(room, event.target, event.bodyFace)
            snapshot.fx[i].bodyRemaining = event.bodyRemaining
        end
        if event.footprint and event.footprint.shape == 'sector' then
            snapshot.fx[i].arc = sectorArc(event.footprint, point)
        end
    end
    local spirit = picture.spirit
    if spirit then
        local marks = {}
        for i, mark in ipairs(spirit.marks) do marks[i] = {position = point(mark.position), amount = mark.amount, lethal = mark.lethal == true} end
        local x = room:IsMirrorWorld() and -spirit.face.X or spirit.face.X
        snapshot.spirit = {anchor = point(spirit.anchor), face = {x, spirit.face.Y},
            viewFace = screenHeading(room, spirit.anchor, spirit.face),
            remaining = spirit.remaining, returning = spirit.returning, marks = marks}
    end
    return snapshot
end

local function readAck(state, now, display)
    if state.ackDisplay ~= display.id then
        state.ackDisplay, state.ackAt, state.pollAt = display.id, nil, nil
    end
    if state.pollAt and now < state.pollAt then return end
    state.pollAt = now + 40
    local ok, raw = pcall(Isaac.LoadModDataFromFolder, 'samira_testroom_link')
    if not ok or type(raw) ~= 'string' or #raw > 4096 then return end
    local decoded, ack = pcall(json.decode, raw)
    if not decoded or type(ack) ~= 'table' then return end
    if ack.version == 1 and ack.session == state.id and ack.room == state.room and ack.display == display.id
        and type(ack.time) == 'number' and ack.time <= now + 100 and now - ack.time < leaseMs
        and type(ack.capabilities) == 'table' then
        state.ackAt = math.min(now, ack.time)
        state.masteryReady = ack.capabilities.mastery == true
        state.modelReady = ack.ready == true and ack.visible == true and ack.capabilities.yoneModel == true
        state.vfxReady = ack.capabilities.yoneVfx == true
    else
        state.ackAt = nil
    end
end

local function leased(state, capability, now)
    return state[capability] and state.ackAt and now - state.ackAt < leaseMs
end

local function emit(game, state, player, force, picture)
    local now = Isaac.GetTime()
    local width, height, display = Display.sample()
    local hidden = obscured(game, state, player)
    if not force and state.emitAt and now - state.emitAt < 30 and hidden == state.wasHidden
        and state.emitDisplay == display.id then return end
    state.emitAt, state.wasHidden, state.emitDisplay = now, hidden, display.id
    state.seq = state.seq + 1
    local clock = game:GetFrameCount()
    local room = game:GetRoom()
    -- Do not combine a room render-pass offset with screen-space marks/FX.
    local x, y = mirrorPosition(room, Isaac.WorldToScreen(player.Position))
    local face = state.combat.face
    local fx = room:IsMirrorWorld() and -face.X or face.X
    local action, phase, hit, length, travel = Combat.presentation(state.combat, clock)
    local expression, actionFrame = Emotes.action(state.emotes, clock)
    if expression then action, phase = expression, 0 end
    local looping = not action
    if not action then
        action = player.Velocity:Length() > .6 and 'run' or 'idle'
        phase = clock / (action == 'run' and 38 or 60) % 1
    end
    local mastery = not hidden and Emotes.mastery(state.emotes, clock)
    packet({
        version = 1, companionProtocol = 1, active = true, preview = false, hero = 'yone',
        presentation = 2, hudVisible = false, renderCaptured = not hidden,
        session = state.id, room = state.room, seq = state.seq, time = now, clock = clock,
        screen = {width, height}, display = display, position = {x, y}, face = {fx, face.Y},
        viewFace = screenHeading(room, player.Position, face),
        kind = action, clip = action, phase = phase, looping = looping,
        yoneTiming = not expression and hit and {hit = hit, length = length, travel = travel} or nil,
        yoneMoving = player.Velocity:Length() > .6,
        actionFrame = actionFrame, actionId = expression and (clock - actionFrame) or nil,
        bodyScale = player.SpriteScale and {player.SpriteScale.X, player.SpriteScale.Y} or {1, 1},
        paused = game:IsPaused(), transition = state.leaving or RoomTransition.GetTransitionMode() ~= 0,
        occluded = hidden, hurt = clock < (state.hurtUntil or 0),
        nativeCursor = Options.MouseControl == true, sfxVolume = Options.SFXVolume,
        mastery = mastery and {at = mastery, position = {x, y}} or nil,
        yone = not hidden and visualSnapshot(room, picture or Combat.visual(state.combat, clock)) or nil,
    })
end

local function drawNativeEffects(room, player, picture, x, y, geometry, clock)
    local function point(world)
        return Vector(mirrorPosition(room, Isaac.WorldToScreen(world)))
    end
    local function line(a, b, thickness, red, green, blue, alpha)
        if not Isaac.DrawLine or not KColor then return end
        local color = KColor(red, green, blue, alpha)
        Isaac.DrawLine(a, b, color, color, thickness)
    end
    local spirit = picture.spirit
    if geometry and picture.qReady then
        local opacity = .72 + .18 * math.sin(clock * .16)
        for layer = 1, 2 do
            local center = Vector(x, y - 4 - (layer - 1) * 12)
            local begin = clock * 8 + (layer - 1) * 185
            local previous
            for index = 0, 9 do
                local offset = Vector(25 - (layer - 1) * 3, 0):Rotated(begin + index * 17)
                local nextPoint = center + Vector(offset.X, offset.Y * .40)
                if previous then
                    line(previous, nextPoint, 4, .20, .72, .92, opacity * .52)
                    line(previous, nextPoint, 1, .85, .98, 1, opacity)
                end
                previous = nextPoint
            end
        end
    end
    if geometry and picture.shield then
        local center = Vector(x, y - 12)
        local radius = Vector(18, 0)
        for angle = 0, 315, 45 do
            line(center + radius:Rotated(angle), center + radius:Rotated(angle + 45), 1, .56, .83, 1, .55)
        end
    end
    if spirit then
        local body = point(spirit.anchor)
        local remaining = spirit.remaining
        local pulse = math.max(0, 1 - 4 * remaining) * (.5 - .5 * math.cos(20 * math.pi * remaining))
        if geometry then
            local active = Vector(x, y)
            local delta = active - body
            local side = delta:Normalized():Rotated(90)
            local previous = body
            for i = 1, 12 do
                local t = i / 12
                local wave = math.sin(math.pi * t) * math.sin(8 * t - clock * .18) * 5
                local nextPoint = body + delta * t + side * wave
                line(previous, nextPoint, 3, .63, .09, .23, .35)
                line(previous, nextPoint, 1, 1, .44, .60, .90)
                previous = nextPoint
            end
            if remaining > 0 then
                local center = body + Vector(0, 2)
                for i = 0, 23 do
                    local angle = i * math.pi / 12
                    local nextAngle = (i + 1) * math.pi / 12
                    local a = Vector(16 * math.cos(angle), 6.4 * math.sin(angle))
                    local b = Vector(16 * math.cos(nextAngle), 6.4 * math.sin(nextAngle))
                    line(center + a, center + b, 1, .55, .20, .30, .40)
                    line(center + a * remaining, center + b * remaining, 3, .30, .04, .09, .90)
                    line(center + a * remaining, center + b * remaining,
                        1.5, 1, .62 - .30 * pulse, .75 - .28 * pulse, .95)
                end
            end
        end
        local opacity = (.42 + .49 * remaining) * (1 - .58 * pulse)
        local sprite = player:GetSprite()
        if sprite.Render and sprite.Color then
            local previous = sprite.Color
            sprite.Color = Color(.92 + .08 * pulse, .48 - .15 * pulse, .57 - .10 * pulse, opacity)
            sprite:Render(body, Vector.Zero, Vector.Zero)
            sprite.Color = previous
        else
            Isaac.RenderText('BODY', body.X - 10, body.Y - 9, 1, .57, .64, opacity)
        end
        Isaac.RenderText('SPIRIT', x - 14, y - 31, 1, .52, .67, .90)
        if geometry then
            for _, mark in ipairs(spirit.marks) do
                local enemy = point(mark.position)
                local c = enemy + Vector(0, -25)
                local top, right, bottom, left = c + Vector(0, -6), c + Vector(5, 0),
                    c + Vector(0, 6), c + Vector(-5, 0)
                local lethal = mark.lethal == true
                local green, blue = lethal and .84 or .36, lethal and .55 or .54
                line(top, right, 2, 1, green, blue, .95)
                line(right, bottom, 2, 1, green, blue, .95)
                line(bottom, left, 2, 1, green, blue, .95)
                line(left, top, 2, 1, green, blue, .95)
                line(c + Vector(-2, 2), c + Vector(2, -2), 1, 1, .83, .88, 1)
                if lethal then line(c + Vector(-4, -9), c + Vector(4, -9), 2, 1, .84, .55, 1) end
            end
        end
    end
    if not geometry then return end
    for _, event in ipairs(picture.fx) do
        if event.age < .28 then
            local opacity = 1 - event.age / .28
            if event.kind == 'w' and event.footprint then
                local arc = sectorArc(event.footprint, point)
                for i = 2, #arc do
                    line(arc[i - 1], arc[i], 5, .81, .09, .24, opacity * .65)
                    line(arc[i - 1], arc[i], 1, 1, .76, .76, opacity)
                end
            elseif event.kind == 'q' or event.kind == 'q3' or event.kind == 'r' then
                local start, finish = point(event.origin), point(event.target)
                local side = (finish - start):Normalized():Rotated(90)
                local width = event.kind == 'r' and 6 or (event.kind == 'q3' and 4 or 1)
                for _, offset in ipairs({-width, width}) do
                    local shift = side * offset
                    local blue = event.kind ~= 'r' and .98 or .64
                    line(start + shift, finish + shift, 2, .98, .59, blue, opacity)
                end
            elseif event.kind == 'e_echo' then
                for _, contact in ipairs(event.contacts or {}) do
                    local center = point(contact) + Vector(0, -9)
                    local radius = 3 + event.age * 26
                    line(center + Vector(-radius, radius), center + Vector(radius, -radius), 3, 1, .44, .60, opacity)
                    line(center + Vector(-radius, -radius), center + Vector(radius, radius), 1, 1, .81, .87, opacity)
                end
            end
        end
    end
end

local function drawHeartsteel(room, items)
    if not items or not items.heartsteelTargets or not Isaac.DrawLine or not KColor then return end
    local targets = items.heartsteelTargets()
    if not targets or #targets == 0 then return end
    local shadow = KColor(.13, .045, .065, .94)
    local charging, ready = KColor(.89, .27, .39, .94), KColor(1, .76, .34, 1)
    for _, target in ipairs(targets) do
        local start = screenPoint(room, target.position) + Vector(-7, 6)
        local length = Vector(14, 0)
        Isaac.DrawLine(start, start + length, shadow, shadow, 4)
        local fill = target.fraction >= 1 and ready or charging
        Isaac.DrawLine(start, start + length * target.fraction, fill, fill, 2)
    end
end

local function drawAbilitySlot(x, y, width, scale)
    if not Isaac.DrawLine or not KColor then return end
    if not abilityHudPalette then
        abilityHudPalette = {rim = KColor(.42, .34, .29, .95), panel = KColor(.075, .065, .09, .95)}
    end
    local middle = y + abilityHudHeight * scale / 2
    Isaac.DrawLine(Vector(x, middle), Vector(x + width, middle),
        abilityHudPalette.rim, abilityHudPalette.rim, abilityHudHeight * scale)
    Isaac.DrawLine(Vector(x + scale, middle), Vector(x + width - scale, middle),
        abilityHudPalette.panel, abilityHudPalette.panel, (abilityHudHeight - 2) * scale)
end

-- Original geometric skill glyphs keep each slot identifiable even at small scale.
local function drawAbilityIcon(key, x, y, tint, scale)
    if not Isaac.DrawLine or not KColor then return end
    local color = KColor(table.unpack(tint))
    local function stroke(ax, ay, bx, by, width)
        Isaac.DrawLine(Vector(x + ax * scale, y + ay * scale), Vector(x + bx * scale, y + by * scale),
            color, color, (width or 1.5) * scale)
    end
    if key == 'q' then
        stroke(-7, 3, 5, -3, 2); stroke(2, -5, 6, -3); stroke(6, -3, 4, 1)
        stroke(-7, -1, -3, -3)
    elseif key == 'w' then
        stroke(-6, -3, -4, 2, 2); stroke(-4, 2, 0, 5, 2); stroke(0, 5, 5, 2, 2)
        stroke(5, 2, 7, -3, 2); stroke(-3, -1, 0, 2); stroke(0, 2, 3, -1)
    elseif key == 'e' then
        stroke(-7, 2, -3, -3, 2); stroke(-3, -3, 1, 2, 2); stroke(1, 2, 5, -3, 2)
        stroke(-6, 5, 6, 5); stroke(4, 3, 6, 5); stroke(6, 5, 4, 7)
    else
        stroke(-6, -4, 5, 4, 2); stroke(-6, 4, 5, -4, 2)
        stroke(5, -4, 7, -1); stroke(5, 4, 7, 1)
    end
end

local function drawAbilityOutline(x, y, size, scale, remaining, color)
    if not Isaac.DrawLine or not KColor then return end
    local x1, y1 = x - scale, y - scale
    local x2, y2 = x + size + scale, y + size + scale
    local corners = {Vector(x1, y1), Vector(x2, y1), Vector(x2, y2), Vector(x1, y2), Vector(x1, y1)}
    for edge = 1, 4 do
        local portion = math.max(0, math.min(1, remaining * 4 - edge + 1))
        if portion > 0 then
            local a, b = corners[edge], corners[edge + 1]
            Isaac.DrawLine(a, a + (b - a) * portion, color, color, 2 * scale)
        end
    end
end

local function drawAbilityText(text, x, y, scale, ...)
    if scale == 1 then
        Isaac.RenderText(text, x, y, ...)
    else
        Isaac.RenderScaledText(text, x, y, scale, scale, ...)
    end
end

local function drawAbilityHud(combat, clock, backpack, aiming, picture, requestedScale)
    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    if abilityFont == nil and Font then
        local candidate, loaded = Font('font/samira_items_ru.fnt')
        abilityFont = loaded and candidate or false
    end
    if abilityIcons == nil then
        local icon, loaded = Sprite('gfx/yone/ability_icons.anm2', true)
        abilityIcons = loaded and icon or false
    end
    local slotWidth, iconSize = 42, 32
    local baseRowWidth = #abilities * (slotWidth + abilityHudGap) - abilityHudGap
    local scale = math.min(requestedScale, (width - 4) / (baseRowWidth + 4), (height - 8) / (abilityHudHeight + 4))
    local right = backpack and backpack.x + backpack.width + 8
    local wrapped = right and right + baseRowWidth * scale + 6 > width
    local hintHeight
    if wrapped then
        hintHeight = 17 * (backpack.scale or 1)
        scale = math.min(scale, (backpack.y - hintHeight) / (abilityHudHeight + 4))
    end
    local keyScale, rowHeight = .72 * scale, abilityHudHeight * scale
    local step, rowWidth = (slotWidth + abilityHudGap) * scale, baseRowWidth * scale
    local iconInset = math.floor((slotWidth - iconSize) / 2) * scale
    iconSize = iconSize * scale
    local x, y = 6, height - rowHeight - 4
    if wrapped then
        y = backpack.y - rowHeight - hintHeight - 2 * scale
    elseif backpack then
        x, y = right, backpack.y
    end
    local border = 2 * scale
    x = math.max(border, math.min(x, width - rowWidth - border))
    y = math.max(border, math.min(y, height - rowHeight - 4))

    if Isaac.DrawLine and KColor then
        local frame = KColor(.025, .025, .045, .94)
        Isaac.DrawLine(Vector(x - border, y + rowHeight / 2), Vector(x + rowWidth + border, y + rowHeight / 2),
            frame, frame, rowHeight + border * 2)
    end
    for index, key in ipairs(abilities) do
        local left = x + (index - 1) * step
        local remaining = (combat.ready[key] or 0) - clock
        local spirit = key == 'e' and combat.spirit
        local q3 = key == 'q' and combat.qStacks >= 2
        local tint = remaining > 0 and abilityCooling or abilityReady
        if spirit and clock >= spirit.recastAt then tint = abilityRecast end
        if aiming == key then
            local r, g, b = table.unpack(aimColors[key])
            tint = {r, g, b, 1}
        end
        drawAbilitySlot(left, y, slotWidth * scale, scale)
        local iconX, iconY = left + iconInset, y + 3 * scale
        if abilityIcons then
            local iconName = q3 and 'Q3' or spirit and 'E2' or key:upper()
            abilityIcons:SetFrame(iconName, 0)
            abilityIcons.Scale = Vector(iconSize / 64, iconSize / 64)
            abilityIcons.Color = Color(1, 1, 1, 1)
            abilityIcons:Render(Vector(iconX, iconY))
            if remaining > 0 and not spirit and Isaac.DrawLine and KColor then
                local shade = KColor(.015, .015, .03, .62)
                local middle = iconY + iconSize / 2
                Isaac.DrawLine(Vector(iconX, middle), Vector(iconX + iconSize, middle), shade, shade, iconSize)
            end
        else
            drawAbilityIcon(key, left + slotWidth * scale / 2, y + 12 * scale, tint, scale)
        end
        local label = key:upper()
        if abilityFont then
            local shadow = KColor(.025, .025, .04, 1)
            abilityFont:DrawStringScaledUTF8(label, left + 4 * scale, y + 28 * scale, keyScale, keyScale, shadow, 0, false)
            abilityFont:DrawStringScaledUTF8(label, left + 3 * scale, y + 27 * scale, keyScale, keyScale,
                KColor(table.unpack(tint)), 0, false)
        else
            drawAbilityText(label, left + 3 * scale, y + 26 * scale, scale, table.unpack(tint))
        end
        if q3 and KColor then
            drawAbilityOutline(iconX, iconY, iconSize, scale, picture.qRemaining or 1, KColor(.60, .93, 1, 1))
        end
        local status
        if spirit then
            local ticks = math.max(0, spirit.untilFrame - clock)
            if KColor then
                drawAbilityOutline(iconX, iconY, iconSize, scale, picture.spirit.remaining, KColor(1, .38, .55, 1))
            end
            status = ticks == 0 and 'HOLD' or ('%.1fs'):format(ticks / fps)
        elseif remaining > 0 then
            status = ('%ds'):format(math.ceil(remaining / fps))
        end
        if status then
            local center = left + math.floor((slotWidth - Isaac.GetTextWidth(status)) / 2) * scale
            drawAbilityText(status, center + scale, y + 14 * scale, scale, .025, .025, .04, 1)
            drawAbilityText(status, center, y + 13 * scale, scale, table.unpack(spirit and abilityRecast or abilityReady))
        end
    end
    if clock < (combat.shieldUntil or 0) then
        drawAbilityText('SHIELD', x + step + 3 * scale, math.max(0, y - 10 * scale), scale, table.unpack(abilityRecast))
    end
end

local function drawRoomEffects(game, state, player, clock, picture)
    local pos = Isaac.WorldToScreen(player.Position)
    local x, y = mirrorPosition(game:GetRoom(), pos)
    local now = Isaac.GetTime()
    local vfx, model = leased(state, 'vfxReady', now), leased(state, 'modelReady', now)
    if not vfx or not model then
        drawNativeEffects(game:GetRoom(), player, picture, x, y, not vfx, clock)
    end
    local phase = Emotes.mastery(state.emotes, clock)
    if phase and not leased(state, 'masteryReady', Isaac.GetTime()) then
        if badge == nil then
            local sprite, loaded = Sprite('gfx/hero_mastery/badge.anm2', true)
            badge = loaded and sprite or false
        end
        local alpha = math.min(1, (phase * 120 + 1) / 6, (1 - phase) * 12)
        if badge then
            badge:SetFrame('Play', math.floor(phase * 120))
            badge.Scale, badge.Color = Vector(.5, .5), Color(1, 1, 1, alpha)
            badge:Render(Vector(x, y - 67))
        else
            Isaac.RenderText('* M *', x - 13, y - 54, 1, .75, .28, alpha)
        end
    end
    if not leased(state, 'modelReady', Isaac.GetTime()) then
        local expression = Emotes.action(state.emotes, clock)
        if expression then
            Isaac.RenderText(expression:upper(), x - 15, y - 35, 1, .88, .72, 1)
        end
    end
end

function Yone.init(mod, game, items, inventory, inventoryBounds, display, readHudScale, readR)
    Display = display
    local state, serial = nil, 0

    local function driver()
        return Yone.player(game)
    end

    local function sampleInput(room, allowed)
        sampleCommands(state, room, allowed, readR() == true)
    end

    function Yone.canUseItems(player)
        return state ~= nil and canControl(game, state, player)
    end

    function Yone.exportCooldowns(clock)
        if state then return Combat.exportCooldowns(state.combat, clock) end
        return {}
    end

    function Yone.reset(keepCooldowns)
        if not state then return end
        stopSpiritWarning(state)
        Combat.resetRoom(state.combat, game:GetFrameCount())
        if not keepCooldowns then state.combat = Combat.new(items) end
        Emotes.cancel(state.emotes, true)
    end

    function Yone.restoreCooldowns(saved, clock)
        if state then Combat.restoreCooldowns(state.combat, saved, clock) end
    end

    function Yone.reduceCooldowns(fraction, clock)
        if state then Combat.reduceCooldowns(state.combat, fraction, clock) end
    end

    local function stop()
        if state then
            stopSpiritWarning(state)
            Combat.resetRoom(state.combat, game:GetFrameCount(), true)
            packet({version = 1, active = false})
            state = nil
            Display.release('yone')
        end
    end

    local function start(player, continued)
        serial = serial + 1
        Display.acquire('yone')
        state = {id = tostring(Isaac.GetNanoTime()) .. ':yone:' .. serial, room = 1, seq = 0,
            combat = Combat.new(items), emotes = Emotes.new(), commands = {}, held = {},
            continuingRoom = continued == true}
        if items and items.activate then items.activate(player) end
        if continued and items and items.restoreCombatCooldowns then items.restoreCombatCooldowns() end
        sampleExpressions(state, game:GetFrameCount(), false, false)
        sampleInput(game:GetRoom(), false)
    end

    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, continued)
        stop()
        local player = driver()
        if player then start(player, continued) end
    end)
    mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, stop)
    mod:AddCallback(ModCallbacks.MC_PRE_MOD_UNLOAD, function(_, unloading)
        if unloading == mod then stop() end
    end)

    mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
        local player = driver()
        if not player then
            if state and (state.floorPending or Isaac.GetTime() < (state.floorRebindUntil or 0)) then return end
            stop()
            return
        end
        if not state then start(player) end
        local room, clock = game:GetRoom(), game:GetFrameCount()
        if items and items.applyCooldownCheckpoint then items.applyCooldownCheckpoint(clock) end
        local allowed = canControl(game, state, player)
        sampleInput(room, allowed)
        if not allowed then
            sampleExpressions(state, clock, false, player:IsDead())
            if player:IsDead() then
                stopSpiritWarning(state)
                Combat.resetRoom(state.combat, clock)
                Emotes.cancel(state.emotes, true)
            end
            return
        end
        state.floorRebindUntil = nil

        if inventory then inventory.update(player, clock) end
        if items and items.update then items.update(player, clock) end
        if items and items.claimCombatRoomReset and items.claimCombatRoomReset() and not state.continuingRoom then
            Combat.reduceCooldowns(state.combat, 1, clock)
        end
        local enemies = Isaac.GetRoomEntities()
        Combat.update(state.combat, room, player, enemies, clock)
        if state.qAfterE and not state.combat.pending then
            local aim = player.Position + state.qAfterE
            if Combat.cast(state.combat, 'q', player, aim, clock, room) then stopMoving(state) end
            state.qAfterE = nil
        end
        for _, command in ipairs(state.commands) do
            local kind, aim = command.kind, command.aim
            if kind == 'stop' then
                stopMoving(state)
            elseif kind == 'mouse' then
                stopMoving(state)
                state.target = targetAt(enemies, aim)
                if not state.target then setGoal(state, room, aim) end
            elseif kind == 'q' and state.combat.pending and state.combat.pending.kind == 'e' then
                local heading = aim - player.Position
                state.qAfterE = state.qAfterE or (heading:Length() > .01 and heading or state.combat.pending.facing)
            elseif Combat.cast(state.combat, kind, player, aim, clock, room) then
                stopMoving(state)
            end
        end
        state.commands = {}
        -- Resolve zero-windup recasts on the press, after issuing the action.
        Combat.update(state.combat, room, player, enemies, clock)
        updateSpiritWarning(state, clock)
        local action = Combat.presentation(state.combat, clock)
        local windup = Combat.activeFootprint(state.combat, player, room)
        if action == 'r' or state.combat.returning or windup then
            state.intent = nil
            player.Velocity = Vector.Zero
        else
            updateMovement(state, room, player, clock)
        end
        if not action and state.intent then state.combat.face = state.intent end
        local moving = state.intent ~= nil or player.Velocity:Length() > .6
        sampleExpressions(state, clock, true, action ~= nil or moving)
    end)

    mod:AddCallback(ModCallbacks.MC_INPUT_ACTION, function(_, entity, hook, action)
        local direction, key = axes[action], rebound[action]
        if not direction and not key and not blocked[action] then return end
        local player = state and driver()
        local owner = entity and entity:ToPlayer()
        if not player or entity and (not owner or owner.Index ~= player.Index)
            or (player.ControllerIndex or 0) ~= 0 then return end
        local value = 0
        local allowed = canControl(game, state, player)
        if action == ButtonAction.ACTION_PILLCARD then
            local clock = game:GetFrameCount()
            local combatAction = Combat.presentation(state.combat, clock)
            sampleExpressions(state, clock, allowed, combatAction ~= nil or player.Velocity:Length() > .6)
        end
        if allowed then
            if key and not (action == ButtonAction.ACTION_PILLCARD and Emotes.blocksPocket(state.emotes)) then
                local down
                if hook == InputHook.IS_ACTION_TRIGGERED then down = Input.IsButtonTriggered(key, 0)
                else down = pressed(key) end
                value = down and 1 or 0
            elseif direction and state.intent then
                value = math.max(0, state.intent:Dot(direction))
            end
        end
        if hook == InputHook.GET_ACTION_VALUE then return value end
        return value > 0
    end)

    mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_RENDER, function(_, player)
        local current = state and driver()
        if not current or current.Index ~= player.Index then return end
        local now = Isaac.GetTime()
        local _, _, display = Display.sample()
        if obscured(game, state, player) or display.mode == 'exclusive' then state.ackAt = nil; return end
        readAck(state, now, display)
        if leased(state, 'modelReady', now) then return false end
    end)

    mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
        local player = state and driver()
        if not player then return end
        local clock = game:GetFrameCount()
        local allowed = canControl(game, state, player)
        sampleInput(game:GetRoom(), allowed)
        local action = Combat.presentation(state.combat, clock)
        sampleExpressions(state, clock, allowed, action ~= nil or player.Velocity:Length() > .6)
        local picture = allowed and Combat.visual(state.combat, clock) or nil
        if picture then
            drawAim(game:GetRoom(), state.combat, player, clock, state.aimAbility)
            drawRoomEffects(game, state, player, clock, picture)
            drawHeartsteel(game:GetRoom(), items)
            local scale = readHudScale and readHudScale() or 1
            drawAbilityHud(state.combat, clock, inventoryBounds and inventoryBounds(player, scale), state.aimAbility,
                picture, scale)
        end
        emit(game, state, player, false, picture)
    end)

    mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, target, _, flags, source)
        local player = state and driver()
        local attacker = source and source.Entity
        if not player or target.Type ~= EntityType.ENTITY_PLAYER or target.Index ~= player.Index then return end
        if flags & (DamageFlag.DAMAGE_FAKE or 0) ~= 0 then return end
        local bypass = (DamageFlag.DAMAGE_IV_BAG or 0) | (DamageFlag.DAMAGE_CHEST or 0)
            | (DamageFlag.DAMAGE_CURSED_DOOR or 0) | (DamageFlag.DAMAGE_INVINCIBLE or 0)
        if flags & bypass == 0 and Combat.invulnerable(state.combat, game:GetFrameCount()) then return false end
        if not attacker or (attacker.Type ~= EntityType.ENTITY_PROJECTILE and not Combat.hostile(attacker)) then return end
        if Combat.absorb(state.combat, game:GetFrameCount(), player.Position) then
            player:SetMinDamageCooldown(15)
            return false
        end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_ENTITY_TAKE_DMG, function(_, target, amount, _, source)
        local player = state and driver()
        if not player then return end
        if target.Type == EntityType.ENTITY_PLAYER and target.Index == player.Index then
            state.hurtUntil = game:GetFrameCount() + 6
            Emotes.cancel(state.emotes, false)
        else
            Combat.confirmDamage(state.combat, target, amount, source)
        end
    end)

    local function beginDeparture(player)
        if state.leaving then return end
        state.leaving, state.ackAt = true, nil
        stopSpiritWarning(state)
        stopMoving(state)
        sampleInput(game:GetRoom(), false)
        Combat.resetRoom(state.combat, game:GetFrameCount(), true)
        Emotes.cancel(state.emotes, true)
        emit(game, state, player, true)
    end

    mod:AddCallback(ModCallbacks.MC_PRE_CHANGE_ROOM, function()
        local player = state and driver()
        if player then beginDeparture(player) end
    end)

    mod:AddCallback(ModCallbacks.MC_PRE_ROOM_EXIT, function(_, player, newLevel)
        if state and newLevel and Yone.is(player) then
            state.floorPending = true
            beginDeparture(player)
        end
    end)

    local function enterRoom()
        stopSpiritWarning(state)
        state.room = state.room + 1
        state.leaving, state.ackAt, state.emitAt, state.pollAt = nil, nil, nil, nil
        state.coverFrame, state.hurtUntil = nil, nil
        state.continuingRoom = nil
        sampleInput(game:GetRoom(), false)
        stopMoving(state)
        Combat.resetRoom(state.combat, game:GetFrameCount())
        Emotes.cancel(state.emotes, true)
    end

    mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
        -- On a floor change this arrives before POST_NEW_LEVEL. Keep the old
        -- scene hidden while the new player and room are being bound.
        if state and not state.floorPending then enterRoom() end
    end)

    mod:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, function()
        if not state then return end
        if state.floorPending or state.leaving then enterRoom() end
        state.floorPending, state.coverFrame = nil, nil
        state.floorRebindUntil = Isaac.GetTime() + floorRebindMs
    end)
    local function hideDuringCutscene()
        local player = state and driver()
        if not player then return end
        -- The game clock is held during the nightmare. A final render can
        -- arrive after level entry, but must not hide the first gameplay tick.
        state.coverFrame, state.ackAt = game:GetFrameCount(), nil
        emit(game, state, player)
    end
    mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_SHOW, hideDuringCutscene)
    mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_RENDER, hideDuringCutscene)
end

return Yone
