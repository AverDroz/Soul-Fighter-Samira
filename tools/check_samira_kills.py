"""Exercise E-reset kill attribution with an Isaac API double."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
lua.globals().source = (ROOT / 'src/samira-testroom/mod/samira_kills.lua').read_text(encoding='utf-8')
lua.execute(r'''
EntityType = {
    ENTITY_DUMMY = 1, ENTITY_FIREPLACE = 2, ENTITY_ENVY = 3, ENTITY_SLOTH = 4,
    ENTITY_LUST = 5, ENTITY_WRATH = 6, ENTITY_GLUTTONY = 7, ENTITY_GREED = 8,
    ENTITY_PRIDE = 9,
}
EntityFlag = {FLAG_FRIENDLY = 1}
RoomType = {ROOM_BOSS = 5, ROOM_DEFAULT = 1}
ModCallbacks = {MC_POST_NPC_DEATH = 29}
local ticks, clear, roomType, active = 0, false, RoomType.ROOM_DEFAULT, true
local calls, entities, death = {}, {}, nil
local function entity(kind, boss, friendly)
    local npc = { Type = kind, InitSeed = #entities + 1, dead = false }
    npc.Exists = function() return true end
    npc.IsDead = function() return npc.dead end
    npc.ToNPC = function() return npc end
    npc.IsBoss = function() return boss == true end
    npc.HasEntityFlags = function(_, flag)
        assert(flag == EntityFlag.FLAG_FRIENDLY)
        return friendly == true
    end
    entities[#entities + 1] = npc
    return npc
end
Isaac = { FindByType = function(kind)
    local found = {}
    for _, npc in ipairs(entities) do
        if npc.Type == kind then found[#found + 1] = npc end
    end
    return found
end }
GetPtrHash = function(entity) return entity.InitSeed + 200 end
local player = {InitSeed = 100}
local context = {player = player}
local room = {
    GetType = function() return roomType end,
    IsClear = function() return clear end,
}
local game = {
    GetFrameCount = function() return ticks end,
    GetRoom = function() return room end,
}
local mod = { AddCallback = function(_, id, callback)
    assert(id == ModCallbacks.MC_POST_NPC_DEATH)
    death = callback
end }
local Kills = assert(load(source))()
Kills.init(mod, game, function() return active and player or nil end,
    function(isBoss, clock)
        assert(clock == ticks)
        calls[#calls + 1] = isBoss
    end)
local function tick(clock)
    ticks = clock
    Kills.update(clock)
end
local function kill(npc, clock)
    ticks = clock
    npc.dead = true
    death(mod, npc)
end

local mob = entity(200)
kill(mob, 10)
Kills.acceptHit(mob, context, 10)
tick(10)
assert(#calls == 0)
tick(11)
assert(#calls == 1 and calls[1] == false)
kill(mob, 12)
tick(13)
assert(#calls == 1)

local recent, expired, otherPlayer = entity(200), entity(200), entity(200)
Kills.acceptHit(recent, context, 20)
Kills.acceptHit(expired, context, 20)
Kills.acceptHit(otherPlayer, {player = {InitSeed = 101}}, 20)
kill(recent, 110)
kill(expired, 111)
kill(otherPlayer, 111)
tick(112)
assert(#calls == 2 and calls[2] == false)

for _, npc in ipairs{entity(EntityType.ENTITY_DUMMY), entity(EntityType.ENTITY_FIREPLACE), entity(200, false, true)} do
    Kills.acceptHit(npc, context, 120)
    kill(npc, 120)
end
tick(121)
assert(#calls == 2)

roomType = RoomType.ROOM_BOSS
local boss, part = entity(300, true), entity(301)
part.Parent = boss
Kills.acceptHit(part, context, 125)
kill(part, 125)
tick(126)
tick(160)
assert(#calls == 2)
Kills.acceptHit(boss, context, 161)
kill(boss, 161)
clear = true
tick(162)
assert(#calls == 2)
tick(163)
tick(164)
assert(#calls == 3 and calls[3] == true)

Kills.reset()
roomType, clear = RoomType.ROOM_DEFAULT, false
local envy = entity(EntityType.ENTITY_ENVY)
Kills.acceptHit(envy, context, 170)
kill(envy, 171)
tick(172)
assert(#calls == 3)
local fragment = entity(EntityType.ENTITY_ENVY)
tick(174)
assert(#calls == 3)
kill(fragment, 175)
tick(176)
assert(#calls == 3)
local lastFragment = entity(EntityType.ENTITY_ENVY)
tick(177)
assert(#calls == 3)
kill(lastFragment, 178)
tick(180)
assert(#calls == 4 and calls[4] == true)

local abandoned = entity(200)
Kills.acceptHit(abandoned, context, 185)
Kills.reset()
kill(abandoned, 185)
tick(186)
active = false
local inactive = entity(200)
Kills.acceptHit(inactive, context, 190)
kill(inactive, 190)
active = true
tick(191)
assert(#calls == 4)
''')
print('Samira kill attribution: ordinary enemies, exclusions, multipart boss, Envy splits, room reset')
