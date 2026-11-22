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
GridEntityType = {GRID_POOP = 1, GRID_ROCK_ALT = 2, GRID_ROCK_ALT2 = 3, GRID_TNT = 4}
EntityCollisionClass = {ENTCOLL_NONE=0, ENTCOLL_PLAYEROBJECTS=2, ENTCOLL_ALL=4}
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
local function poop(x, stateValue)
    return {Position = Vector(x, 100), State = stateValue, CollisionClass = GridCollisionClass.COLLISION_NONE,
        GetType = function() return GridEntityType.GRID_POOP end}
end
props = {poop(95, 0), poop(105, 1000)}
assert(combat.cast(state, 'q', player, aim, 1)); combat.update(state, room, player, {}, 8)
assert(props[1].destroyed and not props[2].destroyed, 'Q did not distinguish live poop from destroyed poop')
local tnt = {Position=Vector(140,100), CollisionClass=1, GetType=function() return GridEntityType.GRID_TNT end,
    Hurt=function(self, amount) self.hits=(self.hits or 0)+amount end}
local rock = {Position=Vector(135,100), CollisionClass=1, GetType=function() return GridEntityType.GRID_ROCK_ALT end}
props = {tnt,rock}
state = combat.new(); state.qStacks = 2
assert(combat.cast(state, 'q', player, aim, 20)); combat.update(state, room, player, {}, 27)
assert(tnt.hits==1 and not rock.destroyed, 'Q3 must damage TNT but leave bomb-only rocks intact')
props = {poop(155, 0)}
player.Position = Vector(60,100); state = combat.new(); state.qStacks = 2
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
assert(combat.cast(state, 'q', player, aim, 40)); combat.update(state, room, player, {}, 47)
assert(props[1].destroyed, 'Q3 failed to break a prop behind a solid wall')
wall = {}; props = {}
for _,variant in ipairs({0,1,2,3,10}) do
    state=combat.new(); player.Position=Vector(60,100)
    local fire=enemy(95,100,500+variant)
    fire.Type,fire.Variant,fire.EntityCollisionClass=EntityType.ENTITY_FIREPLACE,variant,EntityCollisionClass.ENTCOLL_ALL
    function fire:IsVulnerableEnemy() return false end
    assert(combat.cast(state,'q',player,aim,1,room)); combat.update(state,room,player,{fire},7)
    assert(#fire.damage==1 and state.qStacks==0, 'Q missed a fireplace or granted a stack')
end
state=combat.new(); player.Position=Vector(60,100)
local object=enemy(95,100,520)
function object:IsVulnerableEnemy() return false end
object.EntityCollisionClass=EntityCollisionClass.ENTCOLL_PLAYEROBJECTS
assert(combat.cast(state,'q',player,aim,1,room)); combat.update(state,room,player,{object},7)
assert(#object.damage==1 and state.qStacks==0, 'Q missed a tear-collidable NPC')
state=combat.new(); state.qStacks=2; player.Position=Vector(60,100)
state.spirit={anchor=Vector(60,100),face=Vector(1,0),untilFrame=150,recastAt=1,marks={}}
local prop=enemy(120,100,522)
function prop:IsVulnerableEnemy() return false end
prop.EntityCollisionClass=EntityCollisionClass.ENTCOLL_ALL
assert(combat.cast(state,'q',player,aim,1,room)); combat.update(state,room,player,{prop},8)
assert(#prop.damage==1 and next(state.spirit.marks)==nil and state.qStacks==0,
    'Q3 failed to hit a prop or created a spirit mark')
state=combat.new(); player.Position=Vector(60,100)
local safe=enemy(95,100,521)
function safe:IsVulnerableEnemy() return false end
safe.EntityCollisionClass=EntityCollisionClass.ENTCOLL_NONE
assert(combat.cast(state,'q',player,aim,1,room)); combat.update(state,room,player,{safe},7)
assert(#safe.damage==0, 'Q hit a non-collidable object')
state=combat.new(); player.Position=Vector(60,100)
local friendly=enemy(95,100,523); friendly.friendly=true
friendly.EntityCollisionClass=EntityCollisionClass.ENTCOLL_ALL
assert(combat.cast(state,'q',player,aim,1,room)); combat.update(state,room,player,{friendly},7)
assert(#friendly.damage==0, 'Q hit a friendly entity')
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

do
    local oldRange = player.TearRange
    player.TearRange = 260
    local edge, outside = enemy(129,100,900), enemy(131,100,901)
    edge.Size, outside.Size = 0, 0
    assert(combat.hudStats(state, player).range == 70, 'HUD melee range disagrees with the base attack')
    assert(combat.inMeleeRange(room,player,edge), 'click attack cannot acquire the extended range')
    assert(not combat.inMeleeRange(room,player,outside), 'click attack acquired a foe beyond the extended range')
    state=combat.new(); entities={edge, outside}; cast('attack',1); resolve(5)
    assert(#edge.damage==1 and #outside.damage==0, 'direct attack disagrees with click range on axis')
    player.TearRange = oldRange
    state=combat.new({cooldown=function(_,key,base) return key=='r' and base/2 or base end})
    player.Position=Vector(60,100); entities={}; cast('r',1)
    assert(state.ready.r==451)
    combat.reduceUltimateCooldown(state,.1,31)
    assert(state.ready.r==406 and not state.ready.q, 'refund must remove 10% of full R duration only')
    local saved=combat.exportCooldowns(state,100)
    local restored=combat.new(); combat.restoreCooldowns(restored,saved,1000)
    combat.reduceUltimateCooldown(restored,.03,1000)
    assert(restored.ready.r==1292, 'restored refund lost haste-adjusted full duration')
    combat.reduceUltimateCooldown(restored,1,2000)
    assert(restored.ready.r==2000, 'refund must not produce a past deadline')
    state=combat.new(); player.Position=Vector(60,100); entities={front,behind}
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
assert(math.abs(combat.visual(state,90).qRemaining - 1)<.0001, 'Q3 timer is not full on the second hit')
assert(math.abs(combat.visual(state,180).qRemaining - .5)<.0001, 'Q3 timer did not count down')
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('q', 120); resolve(130)
assert(state.qStacks == 0 and player.Position.X > 60 and player.Position.X < 120,
    'Q3 must stop before a wall')
assert(#front.damage == 5 and #behind.damage == 0)
wall = {}

player.Position = Vector(60,100)
local wide = enemy(135, 155, 55)
local wEdge, wOutside = enemy(177,100,902), enemy(183,100,903)
wEdge.Size, wOutside.Size = 0, 0
entities = {front, wide, wEdge, wOutside}
assert(combat.footprint(state, player, 'w', aim, room).reach == 122)
cast('w', 155); resolve(167)
assert(#wide.damage == 1, 'W failed to reach a target within its wider sector')
assert(#wEdge.damage == 1 and #wOutside.damage == 0, 'W hit disagrees with its extended indicator')
local wfx = combat.visual(state, 167).fx[#combat.visual(state, 167).fx]
assert(wfx.footprint.reach == 122 and wfx.target.X == 182 and #wfx.contacts == 3, 'W grouped contacts incorrect')
assert(combat.absorb(state, 168) and not combat.absorb(state, 169), 'W shield must stop one hit')
state = combat.new()
entities = {}
cast('w', 1); resolve(20)
assert(state.ready.w==181, 'W cooldown must be 180 frames')
assert(not combat.absorb(state, 21), 'W miss granted a shield')
local wBase
local hasteState=combat.new({cooldown=function(_, key, base) wBase=base; return base/2 end})
assert(combat.cast(hasteState,'w',player,aim,1,room) and wBase==180 and hasteState.ready.w==91,
    'W haste must apply to the six-second base cooldown')
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
front = enemy(170, 100, 9)
entities = {front}
cast('e', 1); resolve(7)
assert(state.spirit and math.abs(player.Position.X - 144)<.01, 'E must move 84 units in open space')
local returnPreview = combat.footprint(state, player, 'e', aim)
assert(returnPreview.facing.X < 0 and returnPreview.reach == player.Position.X - 60)
local visual = combat.visual(state, 7)
assert(visual.spirit.anchor.X == 60 and visual.spirit.face.X == 1)
assert(visual.fx[1].kind == 'e' and visual.fx[1].target.X == player.Position.X)
cast('attack', 10); resolve(18)
front.Position = Vector(175, 105)
visual = combat.visual(state, 18)
assert(#visual.spirit.marks == 1 and visual.spirit.marks[1].position.X == 175)
assert(math.abs(visual.spirit.marks[1].amount - front.damage[1] * .3) < .0001)
assert(visual.spirit.marks[1].lethal == false)
front.HitPoints = visual.spirit.marks[1].amount
assert(combat.visual(state, 18).spirit.marks[1].lethal == true)
front.HitPoints = 100
local recallCollision = player.GridCollisionClass
cast('e', 20); resolve(21)
assert(player.Position.X == 144 and state.returning and not state.spirit and #front.damage == 1,
    'E recast teleported or paid the mark before travel')
visual = combat.visual(state, 21)
local recall = visual.fx[#visual.fx]
assert(visual.spirit.returning and visual.spirit.remaining == 0 and recall.kind == 'e_return'
    and recall.target.X == 60 and recall.travel == 8)
assert(recall.origin.X > recall.target.X and recall.id > visual.fx[1].id)
assert(#recall.contacts == 0 and recall.bodyFace.X == 1 and recall.bodyRemaining > 0)
assert(not combat.cast(state, 'e', player, aim, 22), 'E recast bypassed cooldown')
local recallObstacle = room:GetGridIndex(Vector(102,100))
wall[recallObstacle] = GridCollisionClass.COLLISION_WALL - 1
resolve(25)
assert(player.Position.X == 102 and combat.invulnerable(state, 25)
    and player.GridCollisionClass == EntityGridCollisionClass.GRIDCOLL_NONE,
    'E return did not travel through the obstacle while protected')
resolve(29)
assert(player.Position.X == 60 and not state.returning and not combat.invulnerable(state, 29)
    and player.GridCollisionClass == recallCollision and #front.damage == 2)
assert(math.abs(front.damage[2] - front.damage[1] * .3) < .0001)
local echo = combat.visual(state, 29).fx
echo = echo[#echo]
assert(echo.kind == 'e_echo' and #echo.contacts == 1 and echo.contacts[1].X == 175 and echo.contacts[1].Y == 105,
    'E lost the detonation contact on arrival')
wall[recallObstacle] = nil

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
assert(state.returning and #front.damage == 0, 'a windup hit during E recall')
resolve(162)
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
assert(not state.spirit and state.returning and player.Position.X > 60, 'E did not start returning after R recovery')
resolve(193)
assert(not state.returning and player.Position.X == 60, 'E did not reach the body after R')

state = combat.new()
player.Position = Vector(60,100)
front = enemy(170,100,14)
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
state = combat.new(); player.Position = Vector(60,100)
local through = enemy(145,100,301)
entities = {through}
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('q', 1); resolve(7)
assert(#through.damage == 1, 'Q failed to hit across an interior obstacle')
wall = {}
state = combat.new(); player.Position = Vector(60,100)
props = {poop(145, 0)}
wall[2 * room:GetGridWidth() + 3] = GridCollisionClass.COLLISION_WALL
cast('q', 1); resolve(7); assert(props[1].destroyed, 'Q did not break poop behind wall')
wall = {}; props = {}
state = combat.new(); player.Position = Vector(60,100); player.MaxFireDelay = 9; player.TearRange = 260
cast('q', 1); assert(state.ready.q == 31 and combat.activeFootprint(state, player).reach==124,
    'base Q cooldown or footprint range incorrect')
state = combat.new(); state.qStacks = 2; player.Position = Vector(60,100)
local waveTarget = enemy(267, 100, 377)
entities = {waveTarget}
cast('q', 1); assert(combat.activeFootprint(state, player).reach == 212); resolve(8)
assert(#waveTarget.damage == 1 and player.Position.X == 216, 'the Q3 whirlwind fell short of its preview')
state = combat.new(); player.MaxFireDelay = 4
cast('q', 1); assert(state.ready.q == 13, 'bonus attack speed did not reduce Q cooldown')
state = combat.new(); player.MaxFireDelay = 0
cast('q', 1); assert(state.ready.q == 11, 'Q cooldown floor wrong')
player.MaxFireDelay = 9
local castCount, cooldownCount = 0, 0
state = combat.new({onCast=function() castCount = castCount + 1 end,
    cooldown=function() cooldownCount = cooldownCount + 1; return 1 end})
cast('q', 1)
assert(state.ready.q == 31 and castCount == 1 and cooldownCount == 0,
    'Q incorrectly used ability haste or skipped on-cast items')
local baseInside = room.IsPositionInRoom
function room:IsPositionInRoom(point, margin)
    if point.Y >= 90 and point.Y <= 110 and point.X > 120 and point.X < 170 then return false end
    return baseInside(self, point, margin)
end
state = combat.new(); player.Position = Vector(60,100); entities = {enemy(180,100,302)}
cast('q', 1); resolve(7)
assert(#entities[1].damage == 0 and combat.visual(state, 7).fx[1].target.X == 120,
    'Q crossed exterior room gap')
room.IsPositionInRoom = baseInside
state = combat.new(); state.qStacks = 2; player.Position = Vector(60,100); entities = {}
cast('q', 1); resolve(7)
assert(not combat.q3Invulnerable(state, 7), 'Q3 granted protection before impact')
resolve(8)
assert(math.abs(player.Position.X - 216)<.01, 'Q3 dash must travel 156 units in open space')
assert(combat.q3Invulnerable(state, 8) and combat.q3Invulnerable(state, 14)
    and not combat.q3Invulnerable(state, 15), 'Q3 dash immunity timing incorrect')
combat.resetRoom(state, 9)
assert(not combat.q3Invulnerable(state, 9), 'Q3 immunity survived room reset')
""")
    print("PASS Yone strikes, spirit presentation, accepted damage marks, transitions and R line/pull")


if __name__ == "__main__":
    sys.exit(main())
