"""Exercise Yone's combat on the same Isaac API double used for Samira."""

from pathlib import Path
import sys

from check_samira_navigation import mock_prelude
from lupa.lua54 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src/samira-testroom/mod"


def main():
    lua = LuaRuntime()
    lua.globals().sourceFiles = lua.table_from({
        file.stem: file.read_text(encoding="utf-8") for file in MOD.glob("*.lua")
    })
    lua.execute(mock_prelude() + r"""
start()
local combat = include('yone_combat')
function player:IsFlying() return self.CanFly == true end
local state = combat.new()
local props = {}
GridEntityType = {GRID_POOP = 1, GRID_ROCK_ALT = 2, GRID_ROCK_ALT2 = 3}
function room:GetGridSize() return #props end
function room:GetGridEntity(index) return props[index + 1] end
function room:DestroyGrid(index) props[index + 1].destroyed = true end
local function enemy(x, y, id)
    local e = makeEntity('enemy', x, y, id)
    e.HitPoints = 100
    function e:IsFlying() return self.flying == true end
    local takeDamage = e.TakeDamage
    function e:TakeDamage(value, ...)
        takeDamage(self, value, ...)
        self.HitPoints = self.HitPoints - value
        return true
    end
    return e
end
local aim = Vector(350, 100)
props = {{Position=Vector(95, 100), CollisionClass=1, GetType=function() return GridEntityType.GRID_POOP end}}
assert(combat.cast(state, 'q', player, aim, 1)); combat.update(state, room, player, {}, 8)
assert(props[1].destroyed, 'Q did not break poop')
props = {{Position=Vector(140, 100), CollisionClass=1, GetType=function() return GridEntityType.GRID_ROCK_ALT end}}
state = combat.new(); state.qStacks = 2
assert(combat.cast(state, 'q', player, aim, 20)); combat.update(state, room, player, {}, 27)
assert(props[1].destroyed, 'Q3 did not break a destructible prop')
props = {{Position=Vector(155, 100), CollisionClass=1, GetType=function() return GridEntityType.GRID_POOP end}}
player.Position = Vector(60,100); state = combat.new(); state.qStacks = 2
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
assert(combat.cast(state, 'q', player, aim, 40)); combat.update(state, room, player, {}, 47)
assert(not props[1].destroyed, 'Q3 broke a prop behind a solid wall')
wall = {}; props = {}
player.Position = Vector(60,100); state = combat.new(); state.qStacks, state.qExpires = 2, 52
local q3Edge = enemy(160, 100, 6)
assert(combat.cast(state, 'q', player, aim, 50) == 'q3')
combat.update(state, room, player, {q3Edge}, 57)
assert(#q3Edge.damage == 1, 'Q3 lost its reach when stacks expired after commitment')
player.Position = Vector(60,100)
state = combat.new()
local front, behind = enemy(96, 100, 7), enemy(36, 100, 8)
entities = {front, behind}
local function cast(kind, clock)
    assert(combat.cast(state, kind, player, aim, clock, room) ~= nil, 'failed to cast ' .. kind)
end
local function resolve(clock)
    combat.update(state, room, player, entities, clock)
end

cast('attack', 1); resolve(10)
cast('attack', 20)
assert(combat.presentation(state, 20) == 'attack2', 'second blade reused the first animation')
resolve(29)
assert(#front.damage == 2 and front.damage[1] == 4 and front.damage[2] > 4)
assert(#behind.damage == 0, 'the attack hit behind Yone')
cast('q', 40); resolve(50)
assert(state.qStacks == 1, 'Q did not stack on hit')
local qfx = combat.visual(state, 50).fx
assert(#qfx[#qfx].contacts == 1 and qfx[#qfx].contacts[1].X == 96, 'Q contact incorrect')
cast('q', 80); resolve(90)
assert(state.qStacks == 2, 'second Q did not stack')
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('q', 120); resolve(130)
assert(state.qStacks == 0 and player.Position.X > 60 and player.Position.X < 120,
    'Q3 must stop before a wall')
assert(#front.damage == 5 and #behind.damage == 0)
wall = {}

player.Position = Vector(60,100)
local wide = enemy(135, 155, 55)
entities = {front, wide}
cast('w', 155); resolve(167)
assert(#wide.damage == 1, 'W failed to reach a target within its wider sector')
local wfx = combat.visual(state, 167).fx[#combat.visual(state, 167).fx]
assert(wfx.footprint.reach == 100 and #wfx.contacts == 2, 'W grouped contacts incorrect')
assert(combat.absorb(state, 168) and not combat.absorb(state, 169), 'W shield must stop one hit')
state = combat.new()
entities = {}
cast('w', 1); resolve(20)
assert(not combat.absorb(state, 21), 'W miss granted a shield')
cast('q', 21); resolve(31)
assert(state.qStacks == 0, 'Q miss granted a stack')
local miss = combat.visual(state, 31).fx
assert(#miss[#miss].contacts == 0, 'Q miss emitted phantom contacts')

state = combat.new(); player.Position = Vector(60,100)
local rejected = enemy(90,100,100)
function rejected:TakeDamage() return false end
entities = {rejected}; cast('q', 1); resolve(7)
assert(#combat.visual(state, 7).fx[1].contacts == 0, 'rejected damage produced a contact')
state = combat.new(); entities = {}
for i = 1, 30 do entities[i] = enemy(80 + i * .1,100,100 + i) end
cast('w', 1); resolve(9)
assert(#combat.visual(state, 9).fx[1].contacts == 24 and #entities[30].damage == 1,
    'contact bound changed gameplay or failed to cap packet')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(142, 100, 9)
entities = {front}
cast('e', 1); resolve(7)
assert(state.spirit and player.Position.X > 60)
local returnPreview = combat.footprint(state, player, 'e', aim)
assert(returnPreview.facing.X < 0 and returnPreview.reach == player.Position.X - 60)
local visual = combat.visual(state, 7)
assert(visual.spirit.anchor.X == 60 and visual.spirit.face.X == 1)
assert(visual.fx[1].kind == 'e' and visual.fx[1].target.X == player.Position.X)
cast('attack', 10); resolve(18)
front.Position = Vector(145, 105)
visual = combat.visual(state, 18)
assert(#visual.spirit.marks == 1 and visual.spirit.marks[1].position.X == 145)
assert(math.abs(visual.spirit.marks[1].amount - front.damage[1] * .3) < .0001)
cast('e', 20); resolve(21)
assert(player.Position.X == 60 and not state.spirit and #front.damage == 2)
assert(math.abs(front.damage[2] - front.damage[1] * .3) < .0001)
visual = combat.visual(state, 21)
local recall = visual.fx[#visual.fx]
assert(not visual.spirit and recall.kind == 'e_return' and recall.target.X == 60)
assert(recall.origin.X > recall.target.X and recall.id > visual.fx[1].id)
assert(#recall.contacts == 1 and recall.contacts[1].X == 145 and recall.contacts[1].Y == 105
    and recall.bodyFace.X == 1 and recall.bodyRemaining > 0, 'return contact/body snapshot incorrect')
assert(not combat.cast(state, 'e', player, aim, 22), 'E recast bypassed cooldown')

state = combat.new()
cast('e', 60); resolve(66); cast('attack', 71); resolve(79)
local hits = #front.damage
combat.resetRoom(state, 80)
resolve(260)
assert(not state.spirit and #front.damage == hits, 'room exit replayed E damage')
visual = combat.visual(state, 80)
assert(not visual.spirit and #visual.fx == 0, 'room exit retained old marks or effects')
resolve(20)
assert(state.ready.e > 20 and state.ready.e < 900, 'rewound clock lost E cooldown')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(96,100,13)
entities = {front}
cast('e', 1); resolve(4)
cast('q', 151); resolve(154); resolve(157)
assert(player.Position.X == 60 and #front.damage == 0, 'a windup hit from the E anchor after recall')

state = combat.new()
player.Position = Vector(60,100)
local far, aside, boss = enemy(200,100,10), enemy(190,150,11), enemy(165,100,12)
boss.boss = true
entities = {far, aside, boss}
cast('r', 1); assert(combat.activeFootprint(state, player).reach == 168); resolve(24)
assert(#far.damage == 1 and #boss.damage == 1 and #aside.damage == 0)
assert(player.Position.X > 200 and far.Position.X > 200 and boss.Position.X == 165)
visual = combat.visual(state, 24)
assert(visual.fx[1].kind == 'r' and visual.fx[1].origin.X == 60 and visual.fx[1].target.X > 200)
assert(#visual.fx[1].contacts == 2 and visual.fx[1].contacts[1].X == boss.Position.X
    and visual.fx[1].contacts[2].X == far.Position.X and visual.fx[1].landing.X == player.Position.X,
    'R contacts or landing did not reflect pull')
assert(#combat.visual(state, 90).fx == 0, 'expired combat sound/visual event was retained')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(200,100,22)
local near = enemy(92,100,23)
entities = {front, near}
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('r', 1); resolve(23)
assert(#front.damage == 0 and player.Position.X == 60, 'R hit before windup')
resolve(24)
assert(#front.damage == 1 and #near.damage == 1 and player.Position.X > 160 and near.Position.X > 160,
    'R failed to hit and pull through an interior obstacle')
assert(not combat.cast(state, 'q', player, aim, 25), 'R recovery allowed a new cast')
wall = {}

-- An L-shaped room may contain a second region on the same ray; R must not jump the gap.
local originalInside = room.IsPositionInRoom
function room:IsPositionInRoom(point, margin)
    if point.Y >= 90 and point.Y <= 110 and point.X > 120 and point.X < 170 then return false end
    return originalInside(self, point, margin)
end
state = combat.new(); player.Position = Vector(60,100)
local acrossGap = enemy(200,100,26); entities = {acrossGap}
local footprint = combat.footprint(state, player, 'r', aim, room)
assert(footprint.reach == 60, 'R footprint crossed exterior gap')
cast('r', 1); assert(combat.activeFootprint(state, player, room).reach == 60)
resolve(24)
assert(#acrossGap.damage == 0 and player.Position.X <= 120, 'R crossed exterior gap')
assert(combat.visual(state, 24).fx[1].target.X == 120, 'R effect crossed exterior gap')
room.IsPositionInRoom = originalInside

local pit = GridCollisionClass.COLLISION_WALL - 1
local tile = room:GetGridIndex(Vector(220,100))
wall[tile] = pit
local grounded = enemy(200,100,24)
local flying = enemy(200,100,25); flying.flying = true
assert(not combat.clearPoint(room, grounded, Vector(220,100)), 'grounded enemy accepted a pit')
assert(combat.clearPoint(room, flying, Vector(220,100)), 'flying enemy rejected a pit')
wall[tile] = GridCollisionClass.COLLISION_WALL
assert(not combat.clearPoint(room, flying, Vector(220,100)), 'flying enemy accepted a wall')
wall = {}

state = combat.new()
player.Position = Vector(60,100)
entities = {}
cast('e', 1); resolve(4)
cast('r', 145); resolve(154)
assert(state.spirit and combat.presentation(state, 154) == 'r', 'E timeout interrupted R')
resolve(168)
assert(state.spirit and player.Position.X > 60, 'E returned before R recovery')
resolve(185)
assert(not state.spirit and player.Position.X == 60, 'E did not return after R recovery')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(142,100,14)
entities = {front}
function front:TakeDamage(value, _, source)
    self.damage[#self.damage+1] = value
    -- REPENTOGON can report accepted damage before subtracting HP.
    combat.confirmDamage(state, self, value * .5, source)
    return true
end
cast('e', 1); resolve(4)
cast('attack', 10); resolve(15)
visual = combat.visual(state, 15)
assert(#visual.spirit.marks == 1 and math.abs(visual.spirit.marks[1].amount - .6) < .0001)

state = combat.new()
player.Position = Vector(60,100)
function player:HasCollectible(id) return id == CollectibleType.COLLECTIBLE_20_20 end
local nearest, farther = enemy(80,100,15), enemy(98,100,16)
entities = {farther, nearest}
cast('attack', 1); resolve(9)
assert(math.abs(nearest.damage[1] - 5.6) < .0001 and farther.damage[1] == 4,
    'multishot bonus followed arbitrary entity order instead of the first enemy reached')
-- The authoritative cast area stays fixed through windup even if the player and aim move.
for _, spec in ipairs({{'q', 6}, {'q3', 7}, {'w', 8}, {'r', 23}}) do
    state = combat.new(); player.Position = Vector(60,100)
    if spec[1] == 'q3' then state.qStacks = 2 end
    local target = enemy(250,100,200)
    local displaced = enemy(150,200,201)
    entities = {target, displaced}
    assert(combat.cast(state, spec[1] == 'q3' and 'q' or spec[1], player, aim, 1, room))
    local area, key = combat.activeFootprint(state, player, room)
    assert(area and area.origin.X == 60 and area.facing.X == 1 and key == (spec[1] == 'q3' and 'q' or spec[1]))
    player.Position = Vector(130,200)
    target.Position = Vector(100,100)
    resolve(spec[2])
    assert(#target.damage == 0 and #displaced.damage == 0, 'early hit before windup')
    area = combat.activeFootprint(state, player, room)
    assert(area.origin.X == 60 and area.origin.Y == 100, 'windup area moved with player')
    resolve(spec[2]+1)
    local fx = combat.visual(state, spec[2]+1).fx
    assert(#target.damage == 1 and #displaced.damage == 0 and fx[#fx].origin.X == 60
        and fx[#fx].contacts[1].X == (spec[1] == 'r' and target.Position.X or 100),
        'locked hit area or impact telemetry changed with player movement')
    assert(not combat.activeFootprint(state, player, room), 'area persisted after impact')
end
""")
    print("PASS Yone strikes, spirit presentation, accepted damage marks, transitions and R line/pull")


if __name__ == "__main__":
    sys.exit(main())
