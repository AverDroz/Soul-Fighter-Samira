local mod = RegisterMod('Soul Fighter Samira', 1)
if not REPENTOGON then
    Isaac.DebugString('[Samira test room] REPENTOGON is required.')
    return
end

local game = Game()
local json = require('json')
local Combat = include('samira_testroom_combat')
local ControlsSettings = include('samira_controls_settings')
local Gait = include('samira_testroom_gait')
local Items = include('samira_items')
local ItemRoom = include('samira_items_room')
local Inventory = include('samira_inventory')
local InventoryHUD = include('samira_inventory_hud')
local StyleHUD = include('samira_style_hud')
local Character = include('samira_character')
local Weapons = include('samira_weapons')
local Kills = include('samira_kills')
local Encounters = include('samira_encounters')
local Yone = include('yone_character')
Combat.bindItems(Items)
Combat.bindWeapons(Weapons)
Items.bindCombat(Combat)
Items.bindWeapons(Weapons)
Items.bindKills(Kills)
local prefix = '[SAMIRA_EXTERNAL] '
local statusFolder = 'samira_testroom_link'
local leaseMs = 500

-- Original lengths in seconds from samira/external/actions.json.
local idle = {{'Idle', 'idle_gun', 1.500000119}}
local walk = {{'Walk', 'run_gun_base', 1}}
local shot = {{'Attack', 'attack1_gun_hit', 0.066666670}, {'Attack', 'attack1_gun_into_idle', 2.333333492}}
local clips = {
    idle = idle,
    walk = walk,
    attack = {{'AttackStart', 'attack1_gun_start', 0.266666681}, table.unpack(shot)},
    q = {{'Q', 'spell1_gun', 0.766666710}},
    qmelee = {{'QMelee', 'spell1_sword_from_idle', 1}},
    w = {{'W', 'spell2', 1.033333420}},
    e = {{'E', 'spell3', 0.700000048}},
    eq = {{'EQ', 'spell1_during_dash', 0.800000072}},
    r = {{'RStart', 'spell4_start_a', 0.633333385}, {'RLoop', 'spell4_loop_a', 1.666666627},
        {'REnd', 'spell4_into_idle', 1.666666627}},
}
local combatClips = {
    attack = {{'Attack', 'attack1_gun_hit', 1 / 30}, {'Attack', 'attack1_gun_into_idle', 5 / 30}},
    melee = {{'MeleeAttack', 'attack1_sword_ht', 8 / 30}},
    q = {{'Q', 'spell1_gun', 11 / 30}},
    qmelee = {{'QMelee', 'spell1_sword_from_idle', 13 / 30}},
    w = {{'W', 'spell2', 24 / 30}},
    e = {{'E', 'spell3', 7 / 30}},
    eq = {{'EQ', 'spell1_during_dash', 7 / 30}},
    r = {{'RStart', 'spell4_start_a', 5 / 30}, {'RLoop', 'spell4_loop_a', 55 / 30},
        {'REnd', 'spell4_into_idle', 9 / 30}},
}
local moveActions = {
    [ButtonAction.ACTION_LEFT] = Vector(-1, 0), [ButtonAction.ACTION_RIGHT] = Vector(1, 0),
    [ButtonAction.ACTION_UP] = Vector(0, -1), [ButtonAction.ACTION_DOWN] = Vector(0, 1),
}
local blockedActions = {
    [ButtonAction.ACTION_SHOOTLEFT] = true, [ButtonAction.ACTION_SHOOTRIGHT] = true,
    [ButtonAction.ACTION_SHOOTUP] = true, [ButtonAction.ACTION_SHOOTDOWN] = true,
    [ButtonAction.ACTION_RESTART] = true,
}
local reboundActions = {[ButtonAction.ACTION_BOMB] = Keyboard.KEY_G, [ButtonAction.ACTION_PILLCARD] = Keyboard.KEY_4}

local active, session, sessionSerial = false, nil, 0
local selectedCharacter = false
local room, sequence = 0, 0
local capturePosition, captureAt, ackAt, ackVisualSeq, ackStyleHud, pollAt, emitAt
local leaving, lastOccluded, coverUntil, pendingAnimation
local animation, animationAt, hurtUntil
local face = Vector(0, 1)

local function packet(payload)
    Isaac.DebugString(prefix .. json.encode(payload))
end

local function stop()
    if active then
        Combat.cancelDash(not leaving and RoomTransition.GetTransitionMode() == 0)
        packet({version = 1, active = false})
    end
    active = false
    Weapons.reset()
    Kills.reset()
    StyleHUD.render(nil, nil)
end

local function resetRoom(keepCooldowns)
    room = room + 1
    capturePosition, captureAt, ackAt, ackVisualSeq, ackStyleHud, pollAt, emitAt = nil, nil, nil, nil, nil, nil, nil
    leaving, lastOccluded, coverUntil, pendingAnimation = nil, nil, nil, nil
    animation, animationAt, hurtUntil = nil, nil, nil
    Combat.reset(keepCooldowns)
    Kills.reset()
    Gait.reset()
end

local function start(continued)
    stop()
    resetRoom()
    sessionSerial = sessionSerial + 1
    session = tostring(Isaac.GetNanoTime()) .. ':testroom:' .. sessionSerial
    sequence = 0
    face = Vector(0, 1)
    active = true
    selectedCharacter = Character.is(Isaac.GetPlayer(0))
    if Items.setEnabled then Items.setEnabled(true) end
    if Items.activate then Items.activate(Isaac.GetPlayer(0)) end
    if continued and Items.restoreCombatCooldowns then Items.restoreCombatCooldowns() end
    if Items.claimCombatRoomReset then Items.claimCombatRoomReset() end
    Isaac.DebugString('[Samira test room] enabled, session=' .. session)
end

local function player()
    if active and Isaac.IsInGame() and game:GetNumPlayers() == 1 then
        return Isaac.GetPlayer(0)
    end
end

local function itemPlayer()
    return player() or Yone.player(game)
end

local function transition()
    return leaving == true or RoomTransition.GetTransitionMode() ~= 0
end

local function occluded(p, now)
    local name = p:GetSprite():GetAnimation()
    return game:IsPaused() or ImGui.IsVisible() or transition() or now < (coverUntil or 0)
        or RoomTransition.IsRenderingBossIntro() or p:IsDead()
        or name:find('Trapdoor', 1, true) ~= nil or name:find('Teleport', 1, true) ~= nil
        or name == 'LightTravel' or name == 'HoleIn' or name == 'FallIn'
end

local function readAck(now)
    if pollAt and now < pollAt then return end
    pollAt = now + 40

    local ok, raw = pcall(Isaac.LoadModDataFromFolder, statusFolder)
    if not ok or type(raw) ~= 'string' or #raw > 4096 then return end
    local decoded, ack = pcall(json.decode, raw)
    if not decoded or type(ack) ~= 'table' then return end
    if ack.version == 1 and ack.session == session and ack.room == room
        and ack.ready == true and ack.visible == true and type(ack.time) == 'number'
        and ack.time <= now + 100 and now - ack.time < leaseMs then
        ackAt = math.min(now, ack.time)
        local capabilities = ack.capabilities
        ackStyleHud = type(capabilities) == 'table' and capabilities.styleHud == true
        ackVisualSeq = type(capabilities) == 'table' and type(capabilities.visual) == 'number'
            and capabilities.visual >= 1 and capabilities.projectiles == true and type(ack.seq) == 'number'
            and ack.seq <= sequence and ack.seq or nil
    else
        ackAt, ackVisualSeq, ackStyleHud = nil, nil, nil
    end
end

local function animationFrame(p, clock)
    local skill, started, ticks = Combat.presentation(clock)
    if skill == 'e' or skill == 'eq' then
        local action = combatClips[skill][1]
        return action[1], action[2], math.max(0, (clock - started) / ticks), false
    elseif skill then
        local age = (clock - started) / 30
        for _, action in ipairs(combatClips[skill]) do
            if age < action[3] then return action[1], action[2], math.max(0, age / action[3]), false end
            age = age - action[3]
        end
    end
    if animation then
        local age = (clock - animationAt) / 30
        for index, action in ipairs(animation) do
            if (animation == shot or animation == combatClips.attack) and index == 2
                and p.Velocity:Length() > 0.6 then break end
            if age < action[3] then
                return action[1], action[2], math.max(0, age / action[3]), false
            end
            age = age - action[3]
        end
        animation, animationAt = nil, nil
    end

    if Gait.moving then return walk[1][1], walk[1][2], Gait.phase, true, Gait.face, Gait.phaseRate end
    return idle[1][1], idle[1][2], (clock / 30 / idle[1][3]) % 1, true
end

local function emit(force)
    local p = player()
    if not p then
        if active then stop() end
        return
    end
    local now = Isaac.GetTime()
    local hidden = occluded(p, now)
    if not force and emitAt and now - emitAt < 30 and hidden == lastOccluded then return end
    emitAt, lastOccluded = now, hidden
    sequence = sequence + 1

    local clock = game:GetFrameCount()
    local kind, clip, phase, looping, walkFace, phaseRate = animationFrame(p, clock)
    local captured = captureAt ~= nil and now - captureAt < 100
    local position = captured and capturePosition or Isaac.WorldToScreen(p.Position)
    local width = Isaac.GetScreenWidth()
    local renderFace = walkFace or face
    local x, fx = position.X, renderFace.X
    if game:GetRoom():IsMirrorWorld() then x, fx = width - x, -fx end

    packet({
        version = 1, companionProtocol = 1, active = true, preview = false,
        presentation = 2, hudVisible = false, renderCaptured = captured,
        session = session, room = room, seq = sequence, time = now, clock = clock,
        screen = {width, Isaac.GetScreenHeight()}, position = {x, position.Y}, face = {fx, renderFace.Y},
        kind = kind, clip = clip, phase = phase, looping = looping, phaseRate = phaseRate,
        bodyScale = p.SpriteScale and {p.SpriteScale.X, p.SpriteScale.Y} or {1, 1},
        paused = game:IsPaused(), transition = transition(), occluded = hidden,
        hurt = clock < (hurtUntil or 0),
        nativeCursor = Options.MouseControl == true,
        sfxVolume = Options.SFXVolume,
        visual = not hidden and Combat.visual(game:GetRoom(), clock, sequence) or nil,
    })
end

Console.RegisterCommand('samiratest', 'Toggle the Soul Fighter test skin', 'samiratest [off]', false, AutocompleteType.NONE)
Console.RegisterCommand('samiraanim', 'Preview a Soul Fighter action',
    'samiraanim idle|walk|attack|q|qmelee|w|e|eq|r', false, AutocompleteType.NONE)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command, args)
    local arg = (args or ''):match('^%s*(.-)%s*$'):lower()
    if command == 'samiratest' then
        if arg == 'off' then
            stop()
            if Items.setEnabled then Items.setEnabled(false) end
            Isaac.ConsoleOutput('Samira test skin disabled.\n')
        elseif arg ~= '' then
            Isaac.ConsoleOutput('Usage: samiratest [off]\n')
        elseif not Isaac.IsInGame() or game:GetNumPlayers() ~= 1 then
            Isaac.ConsoleOutput('Start a single-player run first.\n')
        elseif Yone.is(Isaac.GetPlayer(0)) then
            Isaac.ConsoleOutput('Samira preview is unavailable in a Yone run.\n')
        else
            start()
            Isaac.ConsoleOutput('Samira test skin enabled. Close the console to continue.\n')
            Isaac.ConsoleOutput('RMB move/attack | A attack-move or direct fire (F9 settings) | S stop | QWER skills | G bomb | 4 card | Space item\n')
        end
    elseif command == 'samiraanim' then
        if not active then
            Isaac.ConsoleOutput('Run samiratest first.\n')
        elseif clips[arg] then
            pendingAnimation = clips[arg]
        else
            Isaac.ConsoleOutput('Usage: samiraanim idle|walk|attack|q|qmelee|w|e|eq|r\n')
        end
    end
end)

mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_RENDER, function(_, p, offset)
    local driver = player()
    if not driver or p.Index ~= driver.Index then return end
    local now = Isaac.GetTime()
    capturePosition = Isaac.WorldToRenderPosition(p.Position) + offset
    captureAt = now
    if occluded(p, now) then
        ackAt = nil
        return
    end
    readAck(now)
    if ackAt and now - ackAt < leaseMs then return false end
    if Character.is(p) and Character.drawFallback(p, face, offset, game:GetFrameCount()) then return false end
end)

local function canControl(p)
    return p.ControlsEnabled ~= false and not occluded(p, Isaac.GetTime())
end

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    local p = player()
    local owner = p or Yone.player(game)
    local actionable = p and canControl(p) or not p and owner and Yone.canUseItems(owner) or false
    InventoryHUD.input(owner, actionable)
    if p then Combat.sampleInput(game:GetRoom(), game:GetFrameCount(), actionable) end
    if actionable then
        InventoryHUD.render(owner)
        ItemRoom.render(owner, InventoryHUD.bounds(owner), p and StyleHUD.bounds())
    end
    if p and actionable then
        StyleHUD.render(p, Combat.styleStatus(game:GetFrameCount()),
            ackStyleHud and ackAt and Isaac.GetTime() - ackAt < leaseMs)
    end
    if active then emit(false) end
end)

mod:AddCallback(ModCallbacks.MC_INPUT_ACTION, function(_, entity, hook, action)
    local movement, key = moveActions[action], reboundActions[action]
    if not movement and not key and not blockedActions[action] then return end
    local p = player()
    local owner = entity and entity:ToPlayer()
    if not p or entity and (not owner or owner.Index ~= p.Index) then return end
    if not canControl(p) then
        if blockedActions[action] then return hook == InputHook.GET_ACTION_VALUE and 0 or false end
        return
    end
    local shooting = Weapons.input(p, hook, action)
    if shooting ~= nil then return shooting end
    if key then
        if hook == InputHook.IS_ACTION_TRIGGERED then return Input.IsButtonTriggered(key, 0) end
        local held = Input.IsButtonPressed(key, 0)
        if hook == InputHook.GET_ACTION_VALUE then return held and 1 or 0 end
        return held
    end
    local intent = movement and Combat.walkInput(p)
    local value = intent and math.max(0, intent:Dot(movement)) or 0
    if hook == InputHook.GET_ACTION_VALUE then return value end
    return value > 0
end)

mod:AddCallback(ModCallbacks.MC_PRE_TEAR_RENDER, function(_, tear)
    if not ackVisualSeq or not Combat.rendersTear(tear, ackVisualSeq) then return end
    local p, now = player(), Isaac.GetTime()
    if p and not occluded(p, now) and ackAt and now - ackAt < leaseMs then return false end
end)

mod:AddCallback(ModCallbacks.MC_PRE_PROJECTILE_COLLISION, function(_, projectile, collider)
    local p = player()
    local owner = collider:ToPlayer()
    if p and owner and owner.Index == p.Index and canControl(p)
        and Combat.blockProjectile(p, game:GetFrameCount(), projectile) then
        return {Collide = false, SkipCollisionEffects = true}
    end
end)

mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    Encounters.update()
    if active and selectedCharacter and not Character.player(game) then stop() end
    local p = player()
    if p and Yone.is(p) then stop(); return end
    if not p then return end
    local clock = game:GetFrameCount()
    Combat.syncCooldownClock(clock)
    Items.applyCooldownCheckpoint(clock)
    local actionable = canControl(p)
    Combat.sampleInput(game:GetRoom(), clock, actionable)
    if not actionable then
        Combat.finishWalkTick(p, game:GetRoom(), true)
        Weapons.update(p, clock, nil, false)
        if p:IsDead() or p.ControlsEnabled == false and not game:IsPaused() and not ImGui.IsVisible() then
            Combat.cancelDash(not transition())
        end
        Gait.update(clock, p.Position, true)
        return
    end
    local wasDashing = Combat.dashing(clock)
    Inventory.update(p, clock)
    Items.update(p, clock)
    -- Challenge rooms can begin their first fight after their entry callback.
    if Items.claimCombatRoomReset() then Combat.refreshCooldowns() end
    Kills.update(clock)
    local kind, heading = Combat.update(game, p, face, clock)
    Combat.finishWalkTick(p, game:GetRoom(), wasDashing or clock < (hurtUntil or 0))
    Gait.update(clock, p.Position, wasDashing or Combat.dashing(clock) or pendingAnimation ~= nil)
    if heading then face = heading end
    if kind == 'attack' or kind == 'melee' or kind == 'r' then
        animation, animationAt = combatClips[kind], clock
    end
    if pendingAnimation then
        animation, animationAt = pendingAnimation, clock
        pendingAnimation = nil
    end
end)

mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, target)
    local p = player()
    if p and target.Type == EntityType.ENTITY_PLAYER and target.Index == p.Index
        and canControl(p) and Combat.dashing(game:GetFrameCount()) then return false end
end)

mod:AddCallback(ModCallbacks.MC_POST_ENTITY_TAKE_DMG, function(_, target, _, _, source)
    local p = player()
    if not p then return end
    local clock = game:GetFrameCount()
    if target.Type == EntityType.ENTITY_PLAYER and target.Index == p.Index then
        hurtUntil = clock + 5
    else
        Combat.tearHit(clock, target, source and source.Entity)
    end
end)

mod:AddCallback(ModCallbacks.MC_PRE_CHANGE_ROOM, function()
    if not active then return end
    Combat.cancelDash(true)
    Weapons.reset()
    leaving, ackAt = true, nil
    emit(true)
end)

mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
    -- Apply the engine's rewind and the normal first-combat reset in the
    -- first update, after both room entry and Hourglass callbacks have run.
    if active then resetRoom(true) end
end)
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, stop)
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, stop)
mod:AddCallback(ModCallbacks.MC_PRE_MOD_UNLOAD, function(_, unloading)
    if unloading == mod then stop() end
end)

local function hideDuringCinematic()
    if not active then return end
    coverUntil, ackAt = Isaac.GetTime() + 650, nil
    emit(false)
end

mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_SHOW, hideDuringCinematic)
mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_RENDER, hideDuringCinematic)

-- Register item damage hooks after the dash guard so a protected dash never
-- spends an item shield. Items stay native collectibles in the run inventory.
ControlsSettings.init(mod, Combat, player, InventoryHUD.statsSummary)
Items.init(mod, game, itemPlayer, ControlsSettings.attachToSave, Yone)
Inventory.init(mod, game, itemPlayer, Items)
InventoryHUD.init(game, Inventory)
ItemRoom.init(mod, game, itemPlayer, Items)
Encounters.init(mod, game, function()
    if Isaac.IsInGame() then return Character.player(game) end
end, Items)
Weapons.init(mod, game, player, Items, function(kind, heading, context)
    local p = player()
    if not p then return end
    -- Q already started its windup when the player pressed the key.
    if kind ~= 'q' then animation, animationAt = combatClips.attack, game:GetFrameCount() end
    Combat.weaponFired(p, kind, heading, context, game:GetFrameCount())
end)
Kills.init(mod, game, player, Combat.onKill)
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, continued)
    if Yone.is(Isaac.GetPlayer(0)) then return end
    if Character.player(game) or continued and Items.isEnabled and Items.isEnabled() then start(continued) end
end)
Yone.init(mod, game, Items, Inventory)
