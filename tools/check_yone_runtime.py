"""Verify roster selection and the real Yone callback/renderer boundary."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from check_samira_navigation import mock_prelude
from lupa.lua54 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src/samira-testroom/mod"


def main():
    roster = ET.parse(MOD / "content/players.xml").getroot()
    assert [player.get("name") for player in roster] == ["Samira", "Yone"]
    for attribute in ("nameimage", "portrait"):
        path = MOD / "resources" / roster.get(f"{attribute}root") / roster[1].get(attribute)
        assert path.is_file(), path
    lua = LuaRuntime()
    lua.globals().sourceFiles = lua.table_from({
        file.stem: file.read_text(encoding="utf-8") for file in MOD.glob("*.lua")
    })
    prelude = mock_prelude().replace("include('main')", """
local originalInclude = include
function include(name)
    local module = originalInclude(name)
    if name == 'samira_inventory_hud' then
        module.bounds = assert(load(sourceFiles[name], '@' .. name .. '.lua'))().bounds
    end
    return module
end
include('main')
""", 1)
    lua.execute(prelude + r"""
start()
local kind = 130
Options.Fullscreen, Options.UseBorderlessFullscreen = false, false
Isaac.GetPlayerTypeByName = function(name) assert(name == 'Yone'); return 130 end
function player:GetPlayerType() return kind end
function player:GetTrinket(slot) return slot == 0 and 1 or 0 end
local itemUpdates, lastCast = 0, nil
noItems.update = function(owner) assert(owner == player); itemUpdates = itemUpdates + 1 end
noItems.onCast = function(owner, skill) assert(owner == player); lastCast = skill end
Isaac.RenderText = function() end
Isaac.GetTextWidth = function(text) return #text * 6 end
Isaac.DrawLine = function() end
KColor = Color
local function captureHud()
    local originalRender = Isaac.RenderText
    local text = {}
    Isaac.RenderText = function(label, x, y, r, g, b, a)
        text[label] = {x = x, y = y, color = {r, g, b, a}}
    end
    event('POST_RENDER')
    Isaac.RenderText = originalRender
    local previousX = -1
    for _, key in ipairs({'Q', 'W', 'E', 'R'}) do
        local slot = assert(text[key], 'native HUD did not draw a separate ' .. key .. ' slot')
        assert(slot.x > previousX and slot.x + 6 <= Isaac.GetScreenWidth(), 'ability slot fell outside the row')
        assert(slot.y == text.Q.y and slot.y >= 0 and slot.y + 8 <= Isaac.GetScreenHeight(),
            'ability slot fell outside the viewport')
        previousX = slot.x
    end
    return text
end
local function sameSlots(before, after)
    for _, key in ipairs({'Q', 'W', 'E', 'R'}) do
        assert(before[key].x == after[key].x and before[key].y == after[key].y, key .. ' slot moved')
    end
end
local pressed = Input.IsButtonPressed
Input.IsButtonPressed = function(key, ...) return key == input.ctrl or pressed(key, ...) end
local nativeShows = 0
Sprite = function(path)
    assert(path == 'gfx/hero_mastery/badge.anm2')
    return {
        SetFrame=function() end, Render=function() nativeShows = nativeShows + 1 end,
    }, true
end
event('POST_GAME_STARTED', false)
tick()
assert(packet.active and packet.hero == 'yone' and packet.clip == 'idle')
assert(Options.UseBorderlessFullscreen and packet.display.mode == 'windowed')
assert(itemDriver() == player and itemUpdates > 0, 'ordinary Yone run did not bind shared items')
local glyphLines = 0
Isaac.DrawLine = function() glyphLines = glyphLines + 1 end
local readyHud = captureHud()
assert(glyphLines >= 24, 'ability slots did not render their distinct glyph geometry')
Isaac.DrawLine = function() end
assert(readyHud.R.y + 8 < Isaac.GetScreenHeight() - 26, 'narrow ability row collided with the backpack')
local width, height = Isaac.GetScreenWidth, Isaac.GetScreenHeight
Isaac.GetScreenWidth, Isaac.GetScreenHeight = function() return 688 end, function() return 288 end
local wideHud = captureHud()
assert(wideHud.Q.x > 70 + 147 and wideHud.Q.y > 288 - 26, 'wide ability row did not clear the backpack')
Isaac.GetScreenWidth, Isaac.GetScreenHeight = width, height
local session = packet.session
assert(callAction('ACTION_SHOOTRIGHT') == 0)
assert(callAction('ACTION_RESTART') == 0, 'holding R can restart the run')
assert(callAction('ACTION_LEFT') == 0)
tick('KEY_RIGHT')
assert(callAction('ACTION_RIGHT') > .9, 'arrow did not start movement')
tick()
assert(callAction('ACTION_RIGHT') == 0, 'movement continued after arrow release')
local qTarget = makeEntity('enemy', player.Position.X + 25, player.Position.Y, 11)
entities = {qTarget}
local function castKey(key)
    tick(key)
    tick()
end
local rangeLines = 0
local oldDrawLine = Isaac.DrawLine
Isaac.DrawLine = function(a, b, ...)
    if a.Y < 65 and b.Y < 65 then rangeLines = rangeLines + 1 end
end
tick('KEY_Q', false, player.Position + Vector(100, -80))
assert(lastCast == nil, 'holding Q should show its hitbox before casting')
assert(rangeLines >= 4, 'holding Q did not draw its world-space range')
Isaac.DrawLine = oldDrawLine
tick(nil, false, player.Position + Vector(100, 0))
assert(packet.clip == 'q' and packet.hero == 'yone')
assert(packet.yoneTiming.hit == 6 and packet.yoneTiming.length == 16, 'Q timing was not exported to Companion')
assert(lastCast == 'q', 'Yone ability did not reach item cast hooks')
local locked = {}
local originalLine = Isaac.DrawLine
Isaac.DrawLine = function(a, b, color)
    if color and color[1] == .60 and color[2] == .93 and color[3] == 1 then
        locked[#locked + 1] = {a.X, a.Y, b.X, b.Y}
    end
end
renderOnly(nil, false, player.Position + Vector(0, -100))
assert(#locked > 4, 'committed Q lost its own colored footprint')
local firstLocked = locked
locked = {}
renderOnly(nil, false, player.Position + Vector(-100, 0))
assert(#locked == #firstLocked, 'committed footprint changed after cursor movement')
for i, line in ipairs(locked) do
    for j = 1, 4 do assert(math.abs(line[j] - firstLocked[i][j]) < .001,
        'committed footprint followed the cursor') end
end
Isaac.DrawLine = originalLine
local committedPosition = player.Position
tick('KEY_RIGHT', false, player.Position + Vector(0, -100))
assert(callAction('ACTION_RIGHT') == 0 and player.Position:Distance(committedPosition) < .001,
    'movement resumed during a committed Q windup')
for _ = 1, 7 do tick() end
local stackedHud = captureHud()
sameSlots(readyHud, stackedHud)
assert(stackedHud['+'] and stackedHud['1s'] and stackedHud['1s'].x == stackedHud.Q.x,
    'Q lost its charge or cooldown display')
assert(stackedHud.Q.color[1] < readyHud.Q.color[1], 'cooldown did not dim the ability key')
for _ = 1, 24 do tick() end
castKey('KEY_Q')
for _ = 1, 7 do tick() end
local doubleStackHud = captureHud()
sameSlots(readyHud, doubleStackHud)
assert(doubleStackHud['++'] and doubleStackHud['+'] == nil, 'Q lost its second charge')
assert(packet.yone.qReady == true, 'charged Q state was omitted from the visual packet')
entities = {}
for _ = 1, 18 do tick() end

input.ctrl = 'KEY_LEFT_CONTROL'
tick('KEY_4')
assert(packet.clip == 'laugh' and packet.actionFrame == 0)
assert(callAction('ACTION_PILLCARD', 'IS_ACTION_TRIGGERED') == false)
input.ctrl = nil
assert(callAction('ACTION_PILLCARD', 'IS_ACTION_PRESSED') == false, 'Ctrl released before 4')
tick()
tick('KEY_4')
assert(callAction('ACTION_PILLCARD', 'IS_ACTION_TRIGGERED') == true, 'clean 4 was blocked')
input.ctrl = 'KEY_RIGHT_CONTROL'
tick('KEY_6')
assert(packet.mastery and packet.mastery.at == 0 and packet.clip == 'laugh')
assert(packet.mastery.position[1] == packet.position[1])
assert(nativeShows > 0, 'mastery badge was not rendered without the Companion')
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == nil)
ack = {version=1, session=session, room=packet.room, time=now, ready=true, visible=true, display=packet.display.id,
    capabilities={mastery=true}}
tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == nil, 'crest ACK hid the native body')
ack.capabilities.yoneModel = true
tick(); tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == false, 'Yone model ACK did not hide the native body')
local oldDisplay = packet.display.id
Options.Fullscreen = true
assert(event('PRE_PLAYER_RENDER', player, Vector(0, -80)) == nil,
    'the previous window ACK hid the native body after entering fullscreen')
tick()
assert(packet.display.id ~= oldDisplay and packet.display.mode == 'borderless')
assert(packet.position[2] == player.Position.Y * projection, 'room-pass offset moved the external actor')
ack.display, ack.time = packet.display.id, now
tick(); tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == false, 'borderless display never reacquired the model')
event('PRE_CHANGE_ROOM')
event('POST_NEW_ROOM')
tick('KEY_6')
assert(packet.hero == 'yone' and packet.mastery == nil and packet.clip == 'idle', 'room transition kept an emote')

input.ctrl = nil
DamageFlag = {DAMAGE_FAKE = 1}
local attacker = makeEntity('enemy', player.Position.X + 25, player.Position.Y, 12)
entities = {attacker}
function player:SetMinDamageCooldown(frames) self.shieldCooldown = frames end
castKey('KEY_W')
for _ = 1, 9 do tick() end
local cleave = packet.yone.fx[#packet.yone.fx]
assert(cleave.kind == 'w' and #cleave.arc == 13, 'W had no projected cleave arc')
assert(math.abs(cleave.arc[7][1] - cleave.target[1]) < .001
    and math.abs(cleave.arc[7][2] - cleave.target[2]) < .001, 'W arc and axial endpoint disagreed')
local shieldHud = captureHud()
sameSlots(readyHud, shieldHud)
assert(shieldHud['10s'] and shieldHud['10s'].x == shieldHud.W.x and shieldHud.SHIELD,
    'W lost its cooldown or shield display')
assert(event('ENTITY_TAKE_DMG', player, 1, DamageFlag.DAMAGE_FAKE, EntityRef(attacker)) == nil)
assert(event('ENTITY_TAKE_DMG', player, 1, 0, EntityRef(attacker)) == false)
assert(player.shieldCooldown == 15)
assert(event('ENTITY_TAKE_DMG', player, 1, 0, EntityRef(attacker)) == nil)

local positionBeforeE = player.Position
castKey('KEY_E')
for _ = 1, 4 do tick() end
local spiritHud = captureHud()
sameSlots(readyHud, spiritHud)
assert(spiritHud['<'], 'E lost its active spirit marker')
assert(spiritHud['4.9s'] or spiritHud['5.0s'], 'E did not show remaining spirit time')
assert(packet.yone.spirit.anchor[1] == positionBeforeE.X * projection)
assert(packet.yone.spirit.anchor[1] < packet.position[1])
attacker.Position = player.Position + Vector(21, 0)
local itemKinds = {}
noItems.newAttack = function(_, skill) return {kind = skill} end
function attacker:TakeDamage(amount, _, source)
    itemKinds[#itemKinds + 1] = itemContextNow and itemContextNow.kind or 'echo'
    event('POST_ENTITY_TAKE_DMG', self, amount, 0, source)
    self.HitPoints = self.HitPoints - amount
    return true
end
tick('KEY_A')
for _ = 1, 8 do tick() end
local mark = packet.yone.spirit.marks[1]
assert(mark and mark.position[1] == attacker.Position.X * projection and mark.amount > 0)
local nativeMarkLines = 0
local drawLineBeforeMark = Isaac.DrawLine
Isaac.DrawLine = function(a, b, ...)
    local mx, my = attacker.Position.X * projection, attacker.Position.Y * projection - 25
    if math.abs(a.X - mx) <= 6 and math.abs(a.Y - my) <= 7
        and math.abs(b.X - mx) <= 6 and math.abs(b.Y - my) <= 7 then
        nativeMarkLines = nativeMarkLines + 1
    end
end
ack.room, ack.time, ack.display = packet.room, now, packet.display.id
ack.capabilities.yoneVfx = false
tick()
assert(nativeMarkLines >= 5, 'native mark did not follow the damaged enemy')
Isaac.DrawLine = drawLineBeforeMark
local rendered = {}
Isaac.RenderText = function(text) rendered[text] = true end
ack.room, ack.time, ack.display = packet.room, now, packet.display.id
ack.capabilities.yoneVfx, ack.capabilities.yoneModel = true, nil
event('PRE_PLAYER_RENDER', player, Vector.Zero)
tick()
assert(rendered.BODY and rendered.SPIRIT and not rendered['*'],
    'VFX-only Companion lease suppressed the native E body or duplicated a mark')
ack.capabilities.yoneModel = true
tick()
event('PRE_PLAYER_RENDER', player, Vector.Zero)
rendered = {}
tick()
assert(not rendered.BODY and not rendered.SPIRIT, 'native E body overlapped the Companion rig')
mirror = true
tick()
assert(packet.yone.spirit.marks[1].position[1] == Isaac.GetScreenWidth() - mark.position[1])
assert(packet.yone.spirit.face[1] == -1)
assert(packet.yone.spirit.viewFace[1] < 0 and packet.yone.spirit.viewFace[2] == 0,
    'the renderer lost the mirrored heading of the detached body')
mirror = false
castKey('KEY_E')
assert(not packet.yone.spirit and packet.yone.fx[#packet.yone.fx].kind == 'e_return')
local recall = packet.yone.fx[#packet.yone.fx]
assert(recall.bodyFace[1] > 0 and recall.bodyRemaining > 0, 'the recall packet lost the original body pose')
assert(#recall.contacts == 1 and recall.contacts[1][1] == attacker.Position.X * projection,
    'E lost the projected mark detonation point')
assert(#itemKinds == 2 and itemKinds[1] == 'attack' and itemKinds[2] == 'echo',
    'E replay repeated a shared on-hit effect')

-- Floor exits have their own player-exit callback, and new-room can fire
-- before the new-level callback while the old cutscene is still rendering.
local doorRoom = packet.room
local playerAnimation, animationPlaying = 'Trapdoor', true
function player:GetSprite()
    return {
        GetAnimation = function() return playerAnimation end,
        IsPlaying = function(_, clip) return clip == playerAnimation and animationPlaying end,
    }
end
event('PRE_ROOM_EXIT', player, true)
event('POST_NIGHTMARE_SCENE_SHOW')
assert(packet.active and packet.transition and packet.yone == nil,
    'floor exit did not hide combat visuals and audio')
kind = 0
tick()
assert(packet.active and packet.session == session, 'temporary player rebinding stopped the Yone session')
event('POST_NEW_ROOM')
kind = 130
event('POST_NIGHTMARE_SCENE_RENDER')
assert(packet.room == doorRoom and packet.occluded, 'published the floor room before level arrival')
kind = 0
event('POST_NEW_LEVEL')
tick()
assert(packet.active, 'new level callback raced player rebinding')
kind = 130
event('POST_NIGHTMARE_SCENE_RENDER')
assert(packet.occluded, 'model painted over the last nightmare frame')
animationPlaying = false
tick()
assert(packet.session == session and packet.room == doorRoom + 1 and not packet.occluded
    and not packet.transition, 'Yone did not resume after the floor and finished trapdoor clip')
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == nil, 'old level ACK hid the native body')
ack.room, ack.time, ack.display = packet.room, now, packet.display.id
tick(); tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == false, 'new level never acquired the model lease')
playerAnimation = 'Walk'
castKey('KEY_W')
assert(packet.clip == 'idle', 'W cooldown was lost during floor rebinding')
castKey('KEY_Q')
assert(packet.clip == 'q', 'combat input did not recover after the floor')

-- The level callback is sufficient even if room entry did not reach this
-- update path and Isaac briefly reports that the run is unavailable.
local firstFloorRoom = packet.room
local inGame = Isaac.IsInGame
renderOnly('KEY_R')
event('PRE_ROOM_EXIT', player, true)
Isaac.IsInGame = function() return false end
tick()
event('POST_NEW_LEVEL')
tick()
Isaac.IsInGame = inGame
tick()
assert(packet.active and packet.session == session and packet.room == firstFloorRoom + 1
    and not packet.occluded, 'direct level arrival did not rebind the same run')
assert(packet.clip == 'idle', 'a queued ability leaked to the next floor')
castKey('KEY_R')
local ultimateHud = captureHud()
sameSlots(readyHud, ultimateHud)
assert(ultimateHud['30s'] and ultimateHud['30s'].x == ultimateHud.R.x, 'R lost its cooldown display')

local roomKey, claimed = 1, {[1] = true}
noItems.claimCombatRoomReset = function()
    if #entities == 0 or claimed[roomKey] then return false end
    claimed[roomKey] = true
    return true
end
renderOnly('KEY_E')
event('PRE_CHANGE_ROOM')
roomKey, entities = 2, {attacker}
local hpOnEntry = attacker.HitPoints
event('POST_NEW_ROOM')
tick('KEY_E')
tick()
assert(packet.clip == 'idle', 'held E leaked into the new room')
assert(attacker:Exists() and attacker.HitPoints == hpOnEntry, 'room transition removed or damaged returning enemy')
assert(claimed[2] and not captureHud()['30s'], 'first combat in a new room did not refresh R')
castKey('KEY_W')
assert(captureHud()['10s'], 'fresh W did not go on cooldown')
event('PRE_CHANGE_ROOM')
event('POST_NEW_ROOM')
tick()
assert(captureHud()['10s'], 're-entering an already claimed room refreshed W again')

kind = 0
tick()
assert(packet.active == false, 'fallback scene was not closed on character change')
assert(Options.Fullscreen and not Options.UseBorderlessFullscreen,
    'the original fullscreen preference was not restored')
""")
    print("PASS Yone registration, input, emotes, independent leases, HUD and room/floor lifecycle")


if __name__ == "__main__":
    sys.exit(main())
