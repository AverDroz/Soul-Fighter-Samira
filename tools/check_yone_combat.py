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
local state = combat.new()
local function enemy(x, y, id)
    local e = makeEntity('enemy', x, y, id)
    e.HitPoints = 100
    local takeDamage = e.TakeDamage
    function e:TakeDamage(value, ...)
        takeDamage(self, value, ...)
        self.HitPoints = self.HitPoints - value
        return true
    end
    return e
end
local aim = Vector(350, 100)
local front, behind = enemy(96, 100, 7), enemy(36, 100, 8)
entities = {front, behind}
local function cast(kind, clock)
    assert(combat.cast(state, kind, player, aim, clock) ~= nil, 'failed to cast ' .. kind)
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
cast('q', 80); resolve(90)
assert(state.qStacks == 2, 'second Q did not stack')
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('q', 120); resolve(130)
assert(state.qStacks == 0 and player.Position.X > 60 and player.Position.X < 120,
    'Q3 must stop before a wall')
assert(#front.damage == 5 and #behind.damage == 0)
wall = {}

player.Position = Vector(60,100)
cast('w', 155); resolve(167)
assert(combat.absorb(state, 168) and not combat.absorb(state, 169), 'W shield must stop one hit')
state = combat.new()
entities = {}
cast('w', 1); resolve(20)
assert(not combat.absorb(state, 21), 'W miss granted a shield')
cast('q', 21); resolve(31)
assert(state.qStacks == 0, 'Q miss granted a stack')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(142, 100, 9)
entities = {front}
cast('e', 1); resolve(7)
assert(state.spirit and player.Position.X > 60)
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
cast('r', 1); resolve(20)
assert(#far.damage == 1 and #boss.damage == 1 and #aside.damage == 0)
assert(player.Position.X > 200 and far.Position.X > 200 and boss.Position.X == 165)
visual = combat.visual(state, 20)
assert(visual.fx[1].kind == 'r' and visual.fx[1].origin.X == 60 and visual.fx[1].target.X > 200)
assert(#combat.visual(state, 90).fx == 0, 'expired combat sound/visual event was retained')

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
""")
    print("PASS Yone strikes, spirit presentation, accepted damage marks, transitions and R line/pull")


if __name__ == "__main__":
    sys.exit(main())
