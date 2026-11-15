"""Exercise Samira encounter ownership and native room-blocking assumptions."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
lua.globals().source = (ROOT / 'src/samira-testroom/mod/samira_encounters.lua').read_text(encoding='utf-8')
lua.execute(r'''
EntityType = {ENTITY_MOTHER=912, ENTITY_MOM=45, ENTITY_MOMS_HEART=78, ENTITY_ULTRA_GREED=406,
    ENTITY_BEAST=951, ENTITY_ENVY=51, ENTITY_FISTULA_BIG=71, ENTITY_FISTULA_MEDIUM=72,
    ENTITY_FISTULA_SMALL=73, ENTITY_DELIRIUM=412, ENTITY_DUMMY=964, ENTITY_FIREPLACE=33}
EntityFlag = {FLAG_FRIENDLY=1}
GridCollisionClass = {COLLISION_NONE=0}
ModCallbacks = setmetatable({}, {__index=function(_, key) return key end})
local callbacks = {}
local mod = {AddCallback=function(_, id, fn) callbacks[id]=fn end}
local function event(name, ...) return callbacks['MC_'..name](mod, ...) end

local vector = {}
vector.__index = vector
Vector = setmetatable({}, {__call=function(_, x, y) return setmetatable({X=x, Y=y}, vector) end})
Vector.Zero = Vector(0, 0)
function vector.__add(a, b) return Vector(a.X+b.X, a.Y+b.Y) end
function vector:Rotated(deg)
    local r = math.rad(deg)
    return Vector(self.X*math.cos(r)-self.Y*math.sin(r), self.X*math.sin(r)+self.Y*math.cos(r))
end
function vector:Distance(other) return math.sqrt((self.X-other.X)^2+(self.Y-other.Y)^2) end

local roomSeed, first, samira, clock = 9520, true, false, 0
local entities, states, nativeData, spawned = {}, {}, {}, {}
local report
local player = {Position=Vector(50, 100), Size=8}
Isaac = {
    GetRoomEntities=function()
        local snapshot={}
        for i, npc in ipairs(entities) do snapshot[i]=npc end
        return snapshot
    end,
    ConsoleOutput=function(value) report=value end,
}
GetPtrHash = function(npc) return npc end
EntitySaveStateManager = {
    GetEntityData=function(_, npc)
        if not nativeData[npc] then nativeData[npc]={} end
        return nativeData[npc]
    end,
    TryGetEntityData=function(_, npc) return nativeData[npc] end,
}
local function npc(kind, seed, extra)
    local value = {Type=kind, Variant=0, SubType=0, InitSeed=seed, Position=Vector(140,100),
        Size=10, MaxHitPoints=40, HitPoints=40, champion=-1}
    for field, datum in pairs(extra or {}) do value[field]=datum end
    value.ToNPC=function() return value end
    value.Exists=function() return true end
    value.IsDead=function() return value.HitPoints<=0 end
    value.IsActiveEnemy=function() return true end
    value.CanShutDoors=not value.nonblocking
    value.IsVulnerableEnemy=function() return true end
    value.HasEntityFlags=function() return value.friendly==true end
    value.GetChampionColorIdx=function() return value.champion end
    value.MakeChampion=function(_,_,color) value.champion=color end
    entities[#entities+1]=value
    return value
end

local function living(bossOnly)
    local count=0
    for _, value in ipairs(entities) do
        if value.CanShutDoors and not value:IsDead() and not value.friendly
            and (not bossOnly or value.Type>=900) then
            count=count+1
        end
    end
    return count
end
local room = {
    GetSpawnSeed=function() return roomSeed end,
    IsFirstVisit=function() return first end,
    IsPositionInRoom=function(_, pos, margin) return pos.X>=margin and pos.Y>=margin and pos.X<400 and pos.Y<240 end,
    GetGridCollisionAtPos=function() return 0 end,
    GetAliveEnemiesCount=function() return living(false) end,
    GetAliveBossesCount=function() return living(true) end,
}
local level = {
    GetDimension=function() return 0 end,
    GetCurrentRoomDesc=function() return {SafeGridIndex=1} end,
}
local game = {
    GetRoom=function() return room end,
    GetFrameCount=function() return clock end,
    GetLevel=function() return level end,
    Spawn=function(_, kind, variant, position, velocity, spawner, subtype, seed)
        if kind==200 then error('spawn failure fixture') end
        assert(seed>0 and position:Distance(player.Position)>20 and spawner==nil)
        assert(event('PRE_SPAWN_CLEAN_AWARD')==true)
        local copy=npc(kind, seed, {Position=position, Variant=variant, SubType=subtype})
        spawned[#spawned+1]=copy
        event('POST_NPC_INIT',copy)
        event('PRE_NPC_UPDATE',copy)
        return copy
    end,
}
local items = {getRoomState=function(key)
    states[key]=states[key] or {}
    return states[key]
end}
local Encounters = assert(load(source))()
Encounters.init(mod,game,function() return samira and player or nil end,items)

local mob=npc(10, 100, {champion=4, MaxHitPoints=72, HitPoints=66})
local linked=npc(10, 101, {ParentNPC=mob})
npc(EntityType.ENTITY_DUMMY, 102)
npc(EntityType.ENTITY_FIREPLACE, 103)
npc(10, 104, {friendly=true})
npc(10, 105, {nonblocking=true})
Encounters.update()
assert(#spawned==0, 'other characters got copies')
samira=true
event('POST_GAME_STARTED',false)
event('ENTITY_TAKE_DMG',mob)
assert(#spawned==1 and spawned[1].champion==4)
assert(spawned[1].HitPoints==66 and spawned[1].MaxHitPoints==72)
assert(spawned[1].Position:Distance(mob.Position)>=24)
local firstSeed=spawned[1].InitSeed
event('PRE_NPC_UPDATE',mob)
local unlinkedChild=npc(11,106)
event('POST_NPC_INIT',unlinkedChild)
event('NPC_UPDATE',mob)
event('PRE_NPC_UPDATE',unlinkedChild)
assert(#spawned==1, 'child or copy was duplicated again')
event('NPC_UPDATE',unlinkedChild)
local wave=npc(11,107)
event('POST_NPC_INIT',wave)
event('PRE_NPC_UPDATE',wave)
event('NPC_UPDATE',wave)
assert(#spawned==2, 'independent wave spawn was not doubled')

-- Restore the same logical clone with an engine-assigned replacement seed.
local reloaded=npc(10,108)
nativeData[reloaded]=nativeData[spawned[1]]
first=false
event('POST_NEW_ROOM')
Encounters.update()
event('PRE_NPC_UPDATE',reloaded)
assert(#spawned==2, 're-entering recreated existing copies')
event('POST_GAME_STARTED',true)
Encounters.update()
assert(#spawned==2, 'continuing spawned new copies')
event('POST_GLOWING_HOURGLASS_LOAD')
Encounters.update()
assert(#spawned==2, 'rewind spawned new copies')

-- The simulated room clears through its native live count only.
roomSeed, first, entities = 9521, true, {}
event('POST_NEW_ROOM')
local boss=npc(910,110)
Encounters.update()
local bossCopy=spawned[3]
assert(bossCopy.Type==boss.Type and room:GetAliveBossesCount()==2)
boss.HitPoints=0
assert(room:GetAliveBossesCount()==1 and event('PRE_SPAWN_CLEAN_AWARD')==nil)
bossCopy.HitPoints=0
assert(room:GetAliveBossesCount()==0 and event('PRE_SPAWN_CLEAN_AWARD')==nil)

-- Story controllers and linked hands do not multiply entities or shared HP.
roomSeed, entities = 9522, {}
event('POST_NEW_ROOM')
local mother=npc(EntityType.ENTITY_MOTHER, 112, {HitPoints=30})
local hand=npc(EntityType.ENTITY_MOTHER, 113, {Variant=2, Parent=mother})
Encounters.update()
assert(mother.MaxHitPoints==80 and mother.HitPoints==60 and hand.MaxHitPoints==40)
event('PRE_NPC_UPDATE',mother)
local minion=npc(12,114)
event('POST_NPC_INIT',minion)
event('NPC_UPDATE',mother)
event('PRE_NPC_UPDATE',minion)
assert(#spawned==4 and spawned[4].Type==12)
event('NPC_UPDATE',minion)
local descendant=npc(12,115,{SpawnerEntity=spawned[4]})
event('PRE_NPC_UPDATE',descendant)
assert(#spawned==4)
event('NPC_UPDATE',descendant)

mother.Variant=10
event('PRE_NPC_UPDATE',mother)
assert(mother.MaxHitPoints==80 and mother.HitPoints==60, 'phase retained HP but was boosted twice')
local restored=npc(EntityType.ENTITY_MOTHER,116,{Variant=10, MaxHitPoints=80, HitPoints=22})
nativeData[restored]=nativeData[mother]
event('POST_GAME_STARTED',true)
Encounters.update()
assert(restored.MaxHitPoints==80 and restored.HitPoints==22 and #spawned==4)
restored.MaxHitPoints=40
event('POST_GAME_STARTED',true)
Encounters.update()
assert(restored.MaxHitPoints==80 and restored.HitPoints==22, 'restore healed saved damage or lost HP scaling')
restored.MaxHitPoints=55
event('POST_GAME_STARTED',true)
Encounters.update()
assert(restored.MaxHitPoints==55 and restored.HitPoints==22, 'restore overwrote an unrelated HP modification')

roomSeed, entities = 9523, {}
event('POST_NEW_ROOM')
local delirium=npc(EntityType.ENTITY_DELIRIUM, 117)
Encounters.update()
delirium.Type=EntityType.ENTITY_MOM
event('PRE_NPC_UPDATE',delirium)
assert(delirium.MaxHitPoints==80 and #spawned==4, 'Delirium transformation became its own boss')
event('EXECUTE_CMD','samiradoubles')
assert(report:find('1 boosted bosses',1,true))
assert(firstSeed==(100 ~ 0x39F6A1C5) & 0x7FFFFFFF)

-- Multiple independent native bosses with the same variant each keep their HP.
roomSeed, entities = 9524, {}
event('POST_NEW_ROOM')
local heart1=npc(EntityType.ENTITY_MOMS_HEART, 119, {Variant=1})
local heart2=npc(EntityType.ENTITY_MOMS_HEART, 120, {Variant=1})
local greedier=npc(EntityType.ENTITY_ULTRA_GREED, 121, {Variant=1})
local beast=npc(EntityType.ENTITY_BEAST, 123)
local ultraWar=npc(EntityType.ENTITY_BEAST, 122, {Variant=30, ParentNPC=beast})
Encounters.update()
assert(heart1.HitPoints==80 and heart2.HitPoints==80 and greedier.HitPoints==80 and ultraWar.HitPoints==80)
assert(#spawned==4)

-- Split death may leave neither a Parent nor a SpawnerEntity on the offspring.
roomSeed, entities = 9525, {}
event('POST_NEW_ROOM')
local fistula=npc(EntityType.ENTITY_FISTULA_BIG,124)
local envy=npc(EntityType.ENTITY_ENVY,125)
Encounters.update()
assert(#spawned==6)
fistula.HitPoints, envy.HitPoints=0,0
event('POST_ENTITY_KILL',fistula)
event('POST_ENTITY_KILL',envy)
local fragment=npc(EntityType.ENTITY_FISTULA_MEDIUM,126)
local envyFragment=npc(EntityType.ENTITY_ENVY,127,{Variant=10})
event('PRE_NPC_UPDATE',fragment)
event('PRE_NPC_UPDATE',envyFragment)
assert(#spawned==6)
clock=3
Encounters.update()
local standalone=npc(EntityType.ENTITY_ENVY,128,{Variant=10})
event('PRE_NPC_UPDATE',standalone)
assert(#spawned==7, 'independent smaller Envy did not get a copy')

-- A rejected native spawn cannot leave the whole room in the spawning guard.
local failing=npc(200,129)
event('PRE_NPC_UPDATE',failing)
assert(event('PRE_SPAWN_CLEAN_AWARD')==nil and #spawned==7)
event('PRE_NPC_UPDATE',failing)
event('EXECUTE_CMD','samiradoubles')
assert(report:find('1 failed copies',1,true))
''')
print('Samira encounter policy: roots, waves, descendants, boss blocking, phases and native-identity restore')
