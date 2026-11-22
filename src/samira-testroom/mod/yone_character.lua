local Yone = {}
local Combat = include('yone_combat')
local Emotes = include('yone_emotes')
local Navigation = include('samira_navigation')
local json = require('json')
local playerType
local badge
local fps, leaseMs = 30, 500
local floorRebindMs = 650
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
    [ButtonAction.ACTION_RESTART] = true,
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

local function sampleExpressions(state, clock, allowed, interrupted)
    local keys = {ctrl = pressed(Keyboard.KEY_LEFT_CONTROL) or pressed(Keyboard.KEY_RIGHT_CONTROL),
        disabled = not allowed}
    for index, key in ipairs(numberKeys) do keys[index] = pressed(key) end
    local previousStart = state.emotes.masteryAt
    Emotes.update(state.emotes, clock, keys, interrupted)
    if state.emotes.masteryAt ~= previousStart and state.emotes.masteryAt == clock then playMasterySound() end
end

local function sampleCommands(state, room, allowed)
    if not allowed then state.commands, state.intent = {}, nil end
    for _, control in ipairs(controls) do
        local action, key = table.unpack(control)
        local down
        if key then down = pressed(key) else down = Input.IsMouseBtnPressed(1) end
        if allowed and down and not state.held[action] and #state.commands < #controls then
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
    if target and Combat.inMeleeRange(room, player, target) then
        state.intent = nil
        Combat.cast(state.combat, 'attack', player, target.Position, clock)
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

local function readAck(state, now)
    if state.pollAt and now < state.pollAt then return end
    state.pollAt = now + 40
    local ok, raw = pcall(Isaac.LoadModDataFromFolder, 'samira_testroom_link')
    if not ok or type(raw) ~= 'string' or #raw > 4096 then return end
    local decoded, ack = pcall(json.decode, raw)
    if not decoded or type(ack) ~= 'table' then return end
    if ack.version == 1 and ack.session == state.id and ack.room == state.room
        and type(ack.time) == 'number' and ack.time <= now + 100 and now - ack.time < leaseMs
        and type(ack.capabilities) == 'table' then
        state.ackAt = math.min(now, ack.time)
        state.masteryReady = ack.capabilities.mastery == true
        state.modelReady = ack.ready == true and ack.visible == true and ack.capabilities.yoneModel == true
    else
        state.ackAt = nil
    end
end

local function leased(state, capability, now)
    return state[capability] and state.ackAt and now - state.ackAt < leaseMs
end

local function emit(game, state, player, force)
    local now = Isaac.GetTime()
    local hidden = obscured(game, state, player)
    if not force and state.emitAt and now - state.emitAt < 30 and hidden == state.wasHidden then return end
    state.emitAt, state.wasHidden = now, hidden
    state.seq = state.seq + 1
    local clock = game:GetFrameCount()
    local room = game:GetRoom()
    local captured = state.captureAt and now - state.captureAt < 100
    local position = captured and state.capture or Isaac.WorldToScreen(player.Position)
    local x, y = mirrorPosition(room, position)
    local face = state.combat.face
    local fx = room:IsMirrorWorld() and -face.X or face.X
    local action, phase = Combat.presentation(state.combat, clock)
    local expression, actionFrame = Emotes.action(state.emotes, clock)
    if expression then action, phase = expression, 0 end
    local looping = not action
    if not action then
        action = player.Velocity:Length() > .6 and 'run' or 'idle'
        phase = clock / (action == 'run' and 24 or 60) % 1
    end
    local mastery = not hidden and Emotes.mastery(state.emotes, clock)
    packet({
        version = 1, companionProtocol = 1, active = true, preview = false, hero = 'yone',
        presentation = 2, hudVisible = false, renderCaptured = captured == true,
        session = state.id, room = state.room, seq = state.seq, time = now, clock = clock,
        screen = {Isaac.GetScreenWidth(), Isaac.GetScreenHeight()}, position = {x, y}, face = {fx, face.Y},
        kind = action, clip = action, phase = phase, looping = looping,
        actionFrame = actionFrame, actionId = expression and (clock - actionFrame) or nil,
        bodyScale = player.SpriteScale and {player.SpriteScale.X, player.SpriteScale.Y} or {1, 1},
        paused = game:IsPaused(), transition = state.leaving or RoomTransition.GetTransitionMode() ~= 0,
        occluded = hidden, hurt = clock < (state.hurtUntil or 0),
        nativeCursor = Options.MouseControl == true, sfxVolume = Options.SFXVolume,
        mastery = mastery and {at = mastery, position = {x, y}} or nil,
    })
end

local function drawRoomHud(game, state, player, clock)
    local combat = state.combat
    local labels = {}
    for _, key in ipairs({'q', 'w', 'e', 'r'}) do
        local remaining = math.max(0, (combat.ready[key] or 0) - clock)
        local label = key:upper()
        if key == 'q' then label = label .. ('+'):rep(combat.qStacks) end
        if key == 'e' and combat.spirit then remaining, label = 0, 'E<' end
        labels[#labels + 1] = label .. (remaining > 0 and (' %ds'):format(math.ceil(remaining / fps)) or '')
    end
    if clock < (combat.shieldUntil or 0) then labels[#labels + 1] = 'SHIELD' end
    local anchor = combat.spirit and combat.spirit.anchor
    if anchor then
        local x, y = mirrorPosition(game:GetRoom(), Isaac.WorldToScreen(anchor))
        Isaac.RenderText('E', x - 3, y - 9, .58, .86, 1, .85)
    end
    local pos = Isaac.WorldToScreen(player.Position)
    local x, y = mirrorPosition(game:GetRoom(), pos)
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
    Isaac.RenderText(table.concat(labels, '  '), 20, Isaac.GetScreenHeight() - 32, .92, .92, 1, 1)
end

function Yone.init(mod, game)
    local state, serial = nil, 0

    local function driver()
        if Isaac.IsInGame() and game:GetNumPlayers() == 1 then
            local player = Isaac.GetPlayer(0)
            if Yone.is(player) then return player end
        end
    end

    local function stop()
        if state then packet({version = 1, active = false}); state = nil end
    end

    local function start()
        serial = serial + 1
        state = {id = tostring(Isaac.GetNanoTime()) .. ':yone:' .. serial, room = 1, seq = 0,
            combat = Combat.new(), emotes = Emotes.new(), commands = {}, held = {}}
        sampleExpressions(state, game:GetFrameCount(), false, false)
        sampleCommands(state, game:GetRoom(), false)
    end

    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
        stop()
        if driver() then start() end
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
        if not state then start() end
        local room, clock = game:GetRoom(), game:GetFrameCount()
        local allowed = canControl(game, state, player)
        sampleCommands(state, room, allowed)
        if not allowed then
            sampleExpressions(state, clock, false, player:IsDead())
            if player:IsDead() then
                Combat.resetRoom(state.combat, clock)
                Emotes.cancel(state.emotes, true)
            end
            return
        end
        state.floorRebindUntil = nil

        local enemies = Isaac.GetRoomEntities()
        Combat.update(state.combat, room, player, enemies, clock)
        for _, command in ipairs(state.commands) do
            local kind, aim = command.kind, command.aim
            if kind == 'stop' then
                stopMoving(state)
            elseif kind == 'mouse' then
                stopMoving(state)
                state.target = targetAt(enemies, aim)
                if not state.target then setGoal(state, room, aim) end
            elseif Combat.cast(state.combat, kind, player, aim, clock) then
                stopMoving(state)
            end
        end
        state.commands = {}
        -- Resolve zero-windup recasts on the press, after issuing the action.
        Combat.update(state.combat, room, player, enemies, clock)
        updateMovement(state, room, player, clock)
        local action = Combat.presentation(state.combat, clock)
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

    mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_RENDER, function(_, player, offset)
        local current = state and driver()
        if not current or current.Index ~= player.Index then return end
        local now = Isaac.GetTime()
        state.capture, state.captureAt = Isaac.WorldToRenderPosition(player.Position) + offset, now
        if obscured(game, state, player) then state.ackAt = nil; return end
        readAck(state, now)
        if leased(state, 'modelReady', now) then return false end
    end)

    mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
        local player = state and driver()
        if not player then return end
        local clock = game:GetFrameCount()
        local allowed = canControl(game, state, player)
        sampleCommands(state, game:GetRoom(), allowed)
        local action = Combat.presentation(state.combat, clock)
        sampleExpressions(state, clock, allowed, action ~= nil or player.Velocity:Length() > .6)
        if allowed then drawRoomHud(game, state, player, clock) end
        emit(game, state, player)
    end)

    mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, target, _, flags, source)
        local player = state and driver()
        local attacker = source and source.Entity
        if not player or target.Type ~= EntityType.ENTITY_PLAYER or target.Index ~= player.Index or not attacker then return end
        if flags & DamageFlag.DAMAGE_FAKE ~= 0 then return end
        if (attacker.Type == EntityType.ENTITY_PROJECTILE or Combat.hostile(attacker))
            and Combat.absorb(state.combat, game:GetFrameCount()) then
            player:SetMinDamageCooldown(15)
            return false
        end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_ENTITY_TAKE_DMG, function(_, target)
        local player = state and driver()
        if player and target.Type == EntityType.ENTITY_PLAYER and target.Index == player.Index then
            state.hurtUntil = game:GetFrameCount() + 6
            Emotes.cancel(state.emotes, false)
        end
    end)

    local function beginDeparture(player)
        if state.leaving then return end
        state.leaving, state.ackAt = true, nil
        stopMoving(state)
        Combat.resetRoom(state.combat, game:GetFrameCount())
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
        state.room = state.room + 1
        state.leaving, state.ackAt, state.captureAt, state.emitAt, state.pollAt = nil, nil, nil, nil, nil
        state.coverFrame, state.hurtUntil = nil, nil
        state.commands = {}
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
