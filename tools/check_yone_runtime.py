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
    lua.execute(mock_prelude() + r"""
start()
local kind = 130
Isaac.GetPlayerTypeByName = function(name) assert(name == 'Yone'); return 130 end
function player:GetPlayerType() return kind end
Isaac.RenderText = function() end
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
local session = packet.session
assert(callAction('ACTION_SHOOTRIGHT') == 0)
assert(callAction('ACTION_RESTART') == 0, 'holding R can restart the run')
assert(callAction('ACTION_LEFT') == 0)
tick('KEY_RIGHT')
assert(callAction('ACTION_RIGHT') > .9, 'arrow did not start movement')
tick()
assert(callAction('ACTION_RIGHT') == 0, 'movement continued after arrow release')
tick('KEY_Q')
assert(packet.clip == 'q' and packet.hero == 'yone')
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
ack = {version=1, session=session, room=packet.room, time=now, ready=true, visible=true,
    capabilities={mastery=true}}
tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == nil, 'crest ACK hid the native body')
ack.capabilities.yoneModel = true
tick(); tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == false, 'Yone model ACK did not hide the native body')
event('PRE_CHANGE_ROOM')
event('POST_NEW_ROOM')
tick('KEY_6')
assert(packet.hero == 'yone' and packet.mastery == nil and packet.clip == 'idle', 'room transition kept an emote')

input.ctrl = nil
DamageFlag = {DAMAGE_FAKE = 1}
local attacker = makeEntity('enemy', player.Position.X + 25, player.Position.Y, 12)
entities = {attacker}
function player:SetMinDamageCooldown(frames) self.shieldCooldown = frames end
tick('KEY_W')
for _ = 1, 9 do tick() end
assert(event('ENTITY_TAKE_DMG', player, 1, DamageFlag.DAMAGE_FAKE, EntityRef(attacker)) == nil)
assert(event('ENTITY_TAKE_DMG', player, 1, 0, EntityRef(attacker)) == false)
assert(player.shieldCooldown == 15)
assert(event('ENTITY_TAKE_DMG', player, 1, 0, EntityRef(attacker)) == nil)

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
assert(packet.active and packet.transition, 'floor exit did not publish the transition')
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
ack.room, ack.time = packet.room, now
tick(); tick()
assert(event('PRE_PLAYER_RENDER', player, Vector.Zero) == false, 'new level never acquired the model lease')
playerAnimation = 'Walk'
tick('KEY_W')
assert(packet.clip == 'idle', 'W cooldown was lost during floor rebinding')
tick('KEY_Q')
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

kind = 0
tick()
assert(packet.active == false, 'fallback scene was not closed on character change')
""")
    print("PASS Yone registration, input, emotes, independent leases and room/floor lifecycle")


if __name__ == "__main__":
    sys.exit(main())
