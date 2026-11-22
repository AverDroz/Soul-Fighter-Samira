"""Exercise the test-room callbacks with a small Isaac API double."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

MOD = ROOT / 'src/samira-testroom/mod'
LUA = LuaRuntime()
LUA.globals().sourceFiles = LUA.table_from({
    file.stem: file.read_text(encoding='utf-8') for file in MOD.glob('*.lua')
})
LUA.execute(r'''
REPENTOGON = true
local function names()
    return setmetatable({}, {__index = function(_, name) return name end})
end
Keyboard, ButtonAction, ModCallbacks, InputHook = names(), names(), names(), names()
EntityFlag, EntityType, ProjectileFlags = names(), names(), names()
CollectibleType = names()
AutocompleteType, RoomType, RoomTransitionAnim = names(), names(), names()
GridCollisionClass = {COLLISION_NONE = 0, COLLISION_WALL = 4}
GridEntityType = names()
EntityGridCollisionClass = {GRIDCOLL_NONE = 0, GRIDCOLL_WALLS = 3, GRIDCOLL_GROUND = 5}
local vec = {}
vec.__index = vec
Vector = setmetatable({}, {__call = function(_, x, y) return setmetatable({X=x,Y=y}, vec) end})
Vector.Zero = Vector(0,0)
function vec.__add(a,b) return Vector(a.X+b.X,a.Y+b.Y) end
function vec.__sub(a,b) return Vector(a.X-b.X,a.Y-b.Y) end
function vec.__mul(a,b) return Vector(a.X*b,a.Y*b) end
function vec:Dot(b) return self.X*b.X+self.Y*b.Y end
function vec:Length() return math.sqrt(self:Dot(self)) end
function vec:Distance(b) return (self-b):Length() end
function vec:Normalized()
    local length = self:Length()
    return length > 0 and self*(1/length) or Vector.Zero
end
function vec:Rotated(degrees)
    local angle = math.rad(degrees)
    local s,c = math.sin(angle),math.cos(angle)
    return Vector(self.X*c-self.Y*s,self.X*s+self.Y*c)
end

local input, frame, now, shots, entities, wall, paused, mirror, console, doors
local itemContextNow, itemContexts, itemProbe = nil, {}, false
local packet, ack, callbacks, props
local combat, kills, nativeMode, selected, installedWeapon, roomClear, roomKind
local projection = .5
local room = {}
function room:IsMirrorWorld() return mirror end
function room:GetType() return roomKind or RoomType.ROOM_DEFAULT end
function room:IsClear() return roomClear == true end
function room:GetDoor(slot) return doors[slot] end
function room:GetGridWidth() return 10 end
function room:GetGridSize() return 60 end
function room:GetGridIndex(p) return math.floor(p.Y/40)*10+math.floor(p.X/40) end
function room:GetGridPosition(i) return Vector((i%10)*40+20,math.floor(i/10)*40+20) end
function room:GetGridCollision(i) return wall[i] or 0 end
function room:GetGridEntity(i) return props[i] end
function room:DestroyGrid(i, immediate)
    local prop=assert(props[i])
    assert(immediate==false)
    prop.destroyed=(prop.destroyed or 0)+1
    prop.CollisionClass=GridCollisionClass.COLLISION_NONE
end
local function makeGrid(kind,index)
    local grid = {CollisionClass=2,Position=room:GetGridPosition(index),GetType=function() return kind end}
    props[index]=grid
    return grid
end
function room:GetClampedPosition(p,m)
    return Vector(math.max(m,math.min(400-m,p.X)),math.max(m,math.min(240-m,p.Y)))
end
function room:IsPositionInRoom(p,m)
    return p.X>=m and p.X<400-m and p.Y>=m and p.Y<240-m
end
function room:CheckLine(a,b,mode)
    local steps=math.max(1,math.ceil(a:Distance(b)/4))
    for step=1,steps do
        local q=a+(b-a)*(step/steps)
        local obstruction=self:GetGridCollision(self:GetGridIndex(q))
        if obstruction~=0 and (obstruction~=1 or mode~=3) then return false end
    end
    return true
end

local function makeEntity(kind,x,y,index)
    local e = {Type=kind,Variant=0,HitPoints=10,Velocity=Vector.Zero,Position=Vector(x,y),Size=8,Index=index,InitSeed=index,
        damage={},data={},Scale=1,SpriteScale=Vector(1,1)}
    function e:Exists() return not self.removed end
    function e:IsDead() return self.dead==true end
    function e:Die() self.dead=true; self.HitPoints=0;self.deaths=(self.deaths or 0)+1 end
    function e:IsVulnerableEnemy() return self.Type=='enemy' end
    function e:HasEntityFlags() return self.friendly==true end
    function e:HasProjectileFlags(flag) return self.noPlayer==true end
    function e:TakeDamage(value,flags,source,interval)
        self.damage[#self.damage+1]=value
        if itemProbe then itemContexts[#itemContexts+1]=assert(itemContextNow,'missing direct-hit item context') end
        return true
    end
    function e:GetData() return self.data end
    function e:ToProjectile() return self end
    function e:Remove() self.removed=true end
    function e:ToPlayer() return self.Type=='ENTITY_PLAYER' and self or nil end
    function e:ToNPC() return self.Type=='enemy' and self or nil end
    function e:ToTear() return self.Type=='ENTITY_TEAR' and self or nil end
    function e:IsBoss() return self.boss==true end
    function e:SetColor(color) self.color=color end
    return e
end
local player = makeEntity('ENTITY_PLAYER',60,100,0)
player.Damage,player.ShotSpeed,player.MaxFireDelay,player.TearRange,player.MoveSpeed=4,1,9,250,1
function player:FireTear(pos,vel,eye,beam,deadeye,source,multiplier)
    local tear = makeEntity('ENTITY_TEAR',pos.X,pos.Y,1+#shots)
    tear.Velocity,tear.Height,tear.CollisionDamage=vel,-20,self.Damage*multiplier
    shots[#shots+1]=tear
    return tear
end
function player:GetSprite() return {GetAnimation=function() return 'Walk' end} end
function player:HasCollectible() return false end
function player:GetWeapon(slot) assert(slot==1); return installedWeapon end
function GetPtrHash(entity) return entity.InitSeed end
function Color(...) return {...} end

function Game()
    return {
        GetRoom=function() return room end, GetNumPlayers=function() return 1 end,
        GetFrameCount=function() return frame end, IsPaused=function() return paused end,
    }
end
Input={
    IsButtonPressed=function(key) return key==input.held or key==input.key end,
    IsButtonTriggered=function(key) return key==input.key end,
    IsMouseBtnPressed=function(button) return button==1 and input.right end,
    GetMousePosition=function() return input.cursor end,
}
Isaac={
    WorldToScreen=function(p) return p*projection end,
    WorldToRenderPosition=function(p) return p*projection end,
    ScreenToWorld=function(p) return p*(1/projection) end,
    WorldToScreenDistance=function(p) return p*projection end,
    GetScreenWidth=function() return 200 end, GetScreenHeight=function() return 120 end,
    GetRoomEntities=function() return entities end, GetPlayer=function() return player end,
    GetNanoTime=function() return now*1000000 end, GetTime=function() return now end,
    IsInGame=function() return true end, ConsoleOutput=function() end, DebugString=function() end,
    LoadModDataFromFolder=function() return ack and 'ack' end,
    FindByType=function(kind)
        local found={}
        for _, entity in ipairs(entities) do if entity.Type==kind then found[#found+1]=entity end end
        return found
    end,
}
RoomTransition={GetTransitionMode=function() return 0 end, IsRenderingBossIntro=function() return false end}
ImGui={IsVisible=function() return console end}
Console={RegisterCommand=function() end}
Options={MouseControl=false,SFXVolume=.6}
function EntityRef(e) return {Entity=e} end
CallbackPriority = {EARLY = -100, DEFAULT = 0}
function RegisterMod()
    callbacks={}
    local function add(_, name, priority, func, filter)
        local list = callbacks[name] or {}
        callbacks[name] = list
        local function dispatch(_, entity, hook, ...)
            if filter == nil or hook == filter then return func(nil, entity, hook, ...) end
        end
        table.insert(list, priority < 0 and 1 or #list + 1, dispatch)
    end
    return {
        AddCallback = function(self, name, func) add(self, name, CallbackPriority.DEFAULT, func) end,
        AddPriorityCallback = add,
    }
end
package.preload.json=function()
    return {encode=function(value) packet=value;return 'packet' end,decode=function() return ack end}
end
-- This suite isolates locomotion and skills; item behavior has its own suite.
-- The adapter still exercises the real combat module's optional item boundary.
local itemDriver
local noItems = {
    init=function(_, _, provider) itemDriver = provider end, bindCombat=function() end, bindWeapons=function() end,
    bindKills=function(module) kills=module end, update=function() end,
    claimCombatRoomReset=function() return false end,
    applyCooldownCheckpoint=function() end,
    newAttack=function() return nil end, onCast=function() end,
    cooldown=function(_,_,base) return base end,
    attackInterval=function(_,base) return base end,
    attackRange=function(_,base) return base end,
}
local itemSerial = 0
noItems.newAttack = function(owner,kind,clock)
    if not itemProbe and not nativeMode then return end
    itemSerial=itemSerial+1
    return {id=itemSerial,kind=kind,clock=clock,player=owner}
end
noItems.withContext = function(context, fn)
    local previous=itemContextNow;itemContextNow=context
    local result=fn();itemContextNow=previous;return result
end
noItems.tagTear = function(_,tear,context) tear:GetData().ItemContext=context end
local fallbackRenderOffset
function include(name)
    if name == 'samira_controls_settings' then return {init=function() end} end
    if name == 'samira_items' then return noItems end
    if name == 'samira_items_room' then return {init=function() end, render=function() end} end
    if name == 'samira_inventory' then return {init=function() end, update=function() end} end
    if name == 'samira_inventory_hud' then
        return {init=function() end,input=function() end,render=function() end,bounds=function() return nil end}
    end
    if name == 'samira_style_hud' then
        return {render=function(_,_,external) styleExternal=external end,bounds=function() end}
    end
    if name == 'samira_encounters' then
        return {init=function(_,_,provider) encounterPlayer=provider end, update=function() end}
    end
    if name == 'samira_character' then
        return {is=function() return selected == true end,player=function() return selected and player end,
            drawFallback=function(_, _, offset) fallbackRenderOffset=offset; return false end}
    end
    if name == 'samira_weapons' and not nativeMode then
        return {init=function() end,reset=function() end,update=function() end,input=function() end}
    end
    if name == 'samira_testroom_combat' then
        combat=assert(load(sourceFiles[name], '@'..name..'.lua'))()
        -- Legacy movement assertions exercise the untouched native-control option.
        combat.setInertia(true)
        combat.setWalkSpeed(100)
        -- Keep the direct-fire regression cases separate from native discharge.
        if not nativeMode then combat.bindWeapons=function() end end
        return combat
    end
    return assert(load(sourceFiles[name], '@'..name..'.lua'))()
end

local function event(name,...)
    for _, callback in ipairs(callbacks['MC_'..name] or {}) do
        local result=callback(nil,...)
        if result~=nil then return result end
    end
end
local function callAction(action,hook,owner)
    return event('INPUT_ACTION',owner,InputHook[hook or 'GET_ACTION_VALUE'],ButtonAction[action])
end
local function setInput(key,right,cursor)
    input.key,input.right,input.cursor=key,right==true,(cursor or Vector(200,100))*projection
end
local function renderOnly(key,right,cursor)
    now=now+10
    setInput(key,right,cursor)
    event('POST_RENDER')
end
local function tick(key,right,cursor,beforeUpdate)
    frame,now = frame+1,now+34
    setInput(key,right,cursor)
    -- This double consumes native movement action values. Acceleration and
    -- friction in the actual game need to be checked in the running game.
    if not paused and not console then
        local x=(callAction('ACTION_RIGHT') or 0)-(callAction('ACTION_LEFT') or 0)
        local y=(callAction('ACTION_DOWN') or 0)-(callAction('ACTION_UP') or 0)
        player.Velocity=Vector(x,y)*(3*player.MoveSpeed)
        player.Position=player.Position+player.Velocity
    end
    if beforeUpdate then beforeUpdate() end
    event('POST_UPDATE')
    event('POST_RENDER')
end
local function start()
    event('EXECUTE_CMD','samiratest','off')
    input,frame,now,shots,entities,wall,doors,props={},0,0,{},{},{},{},{}
    paused,mirror,ack,console=false,false,nil,false
    roomClear,roomKind=false,RoomType.ROOM_DEFAULT
    player.Position,player.Velocity=Vector(60,100),Vector.Zero
    player.MoveSpeed=1
    player.GridCollisionClass=EntityGridCollisionClass.GRIDCOLL_GROUND
    player.CanFly,player.ControlsEnabled,player.dead=false,true,false
    event('EXECUTE_CMD','samiratest','')
end
local function earnStyle()
    for _, kind in ipairs{'aa','q','w','e','aa','q'} do
        combat.acceptHit({kind=kind},frame)
    end
    assert(combat.styleStatus(frame).rank==6)
end
include('main')
assert(encounterPlayer()==nil, 'debug Samira skin on Isaac enabled encounter doubling')
start()
selected=true
local nativeOffset=Vector(7,-80)
event('PRE_PLAYER_RENDER',player,nativeOffset)
selected=false
assert(fallbackRenderOffset==nativeOffset, 'native Samira fallback lost the room render offset')

-- Mouse door entry uses native walking, not a forced room transition. Test
-- the extended clickable art and recovery from just outside each threshold.
-- The legacy suite below explicitly exercises the optional hold-to-fire binding.
combat.setAttackMove(false)
local doorPositions={Vector(0,100),Vector(200,0),Vector(400,100),Vector(200,240)}
for slot=0,7 do
    start()
    local normal=Vector(-1,0):Rotated((slot%4)*90)
    local center=doorPositions[slot%4+1]
    doors[slot]={Position=center,IsOpen=function() return true end}
    player.Position=center-normal*36
    tick(nil,true,center+normal*48)
    local intent=Vector(callAction('ACTION_RIGHT')-callAction('ACTION_LEFT'),callAction('ACTION_DOWN')-callAction('ACTION_UP'))
    assert(intent:Dot(normal)>.95,'door exit supplied no outward input for slot '..slot)
    assert(player.Position:Distance(center-normal*36)<.001,'door exit teleported the player')
    -- Simulate the receiving room's walk-in threshold beyond its nav grid.
    event('POST_NEW_ROOM')
    player.Position=center+normal*8;player.Velocity=Vector.Zero
    renderOnly(nil,false)
    -- Combat rooms can close their receiving door before walk-in finishes.
    doors[slot].IsOpen=function() return false end
    tick(nil,true,Vector(200,120))
    intent=Vector(callAction('ACTION_RIGHT')-callAction('ACTION_LEFT'),callAction('ACTION_DOWN')-callAction('ACTION_UP'))
    assert(intent:Dot(normal)<-.95,'door threshold trapped the player for slot '..slot)
    for i=1,13 do tick() end
    assert((player.Position-center):Dot(normal)<-24,'player could not walk into the new room')
end
start()
doors[3]={Position=Vector(200,240),IsOpen=function() return true end}
player.Position=Vector(160,120)
tick(nil,true,Vector(200,288))
for i=1,60 do tick() end
assert(player.Position.Y>240,'mouse movement could not reach the bottom door from inside the room')
start()
doors[1]={Position=Vector(200,0),IsOpen=function() return false end}
player.Position=Vector(200,36)
tick(nil,true,Vector(200,-20))
assert(callAction('ACTION_UP')>0,'locked door should still receive native approach input')
start();player.Position=Vector(60,-8)
tick(nil,true,Vector(60,120))
assert(callAction('ACTION_DOWN')==0,'threshold exception leaked to ordinary walls')

-- RMB walks around a rock, resolves a distant enemy, fires at native delay,
-- and switches to a single melee hit at sword range.
start()
wall[room:GetGridIndex(Vector(100,100))]=4
tick(nil,true,Vector(180,100))
for i=1,85 do
    tick()
    assert(room:GetGridCollision(room:GetGridIndex(player.Position))==0, 'RMB crossed a blocked square')
end
assert(player.Position:Distance(Vector(180,100))<6,
    ('RMB route stopped at %.1f, %.1f'):format(player.Position.X, player.Position.Y))
wall={}
local enemy=makeEntity('enemy',350,100,11)
entities={enemy}
tick(nil,true,enemy.Position)
assert(callAction('ACTION_RIGHT')>0 and #shots==0, 'RMB fired before approaching')
for i=1,24 do tick() end
assert(#shots==2, 'autoattack cadence or approach')
assert(shots[1].CollisionDamage==4 and shots[1].Velocity.X>0, 'auto tear damage or heading')
assert(packet.visual.target[1]==175 and shots[1].data.SamiraVisual, 'tracked target or tear')
tick('KEY_S')
for i=1,10 do tick() end
assert(#shots==2 and packet.visual.target==nil, 'S must cancel targeting')
enemy.Position=player.Position+Vector(20,0)
tick(nil,true,enemy.Position)
assert(#enemy.damage==1 and enemy.damage[1]==4 and #shots==2 and packet.kind=='MeleeAttack')

-- Isaac owns velocity. The command supplies the same full directional
-- input for different speed stats, then the engine applies each stat.
local function moveAtSpeed(speed)
    start()
    player.MoveSpeed=speed
    tick(nil,true,Vector(240,100))
    assert(player.Velocity:Length()==0 and callAction('ACTION_RIGHT')==1)
    tick()
    assert(callAction('ACTION_RIGHT')==1)
    return player.Velocity.X
end
assert(moveAtSpeed(1.5)==1.5*moveAtSpeed(1), 'speed stat is being applied outside native motion')
start()
tick(nil,true,Vector(240,100))
tick()
assert(packet.kind=='Walk' and packet.phaseRate>0 and packet.face[1]>0)
local walkingPhase=packet.phase
tick()
assert(packet.kind=='Walk' and packet.phase>walkingPhase)
tick('KEY_S')
tick()
assert(packet.kind=='Idle' and packet.phaseRate==nil)

-- A suppresses movement while held, samples aim at each shot, and shares
-- basic attack cooldown without firing independently on key transitions.
start()
tick(nil,true,Vector(250,100))
tick()
local fireTarget=makeEntity('ENTITY_FIREPLACE',60,180,20)
entities={fireTarget}
tick('KEY_A',false,fireTarget.Position)
local firePosition=player.Position
assert(#shots==1 and shots[1].Position:Distance(firePosition)==0 and shots[1].Velocity.Y>0)
assert(packet.visual.target==nil and packet.visual.moveGoal==nil and player.Velocity:Length()==0)
tick(nil,true,Vector(250,100));tick('KEY_A')
local cooldownStop = player.Position
assert(#shots==1 and packet.visual.moveGoal==nil and player.Velocity:Length()==0,
    'manual A ignored cooldown or failed to stop moving')
for i=1,8 do tick('KEY_A',false,Vector(200,100)) end
assert(#shots==2 and shots[2].Velocity.X>0 and shots[2].Velocity.Y==0)
assert(player.Position:Distance(cooldownStop)==0)
for i=1,10 do tick('KEY_A',false,Vector(60,50)) end
assert(#shots==3 and shots[3].Velocity.Y<0, 'held shot did not update cursor aim')
for i=1,11 do tick() end
assert(#shots==3, 'releasing A or its cooldown produced a shot')

start()
renderOnly('KEY_A',false,Vector(60,50))
renderOnly(nil,false,Vector(200,100))
assert(#shots==0)
tick()
assert(#shots==1 and shots[1].Velocity.Y<0, 'short A lost the press or its cursor position')
for i=1,11 do tick() end
assert(#shots==1, 'short A repeated after release')

for _, blocked in ipairs({'W','R','E','Q'}) do
    start()
    if blocked=='R' then earnStyle() end
    tick('KEY_'..blocked)
    tick('KEY_A')
    assert(#shots==0, 'manual shot interrupted '..blocked)
    for i=1,65 do tick('KEY_A') end
    assert(#shots>(blocked=='Q' and 1 or 0), 'held A did not resume after '..blocked)
end
for _, suspended in ipairs({'pause','console'}) do
    start()
    tick('KEY_A')
    paused,console=suspended=='pause',suspended=='console'
    renderOnly('KEY_A')
    paused,console=false,false
    for i=1,12 do tick('KEY_A') end
    assert(#shots==1, 'held A rearmed while leaving '..suspended)
    tick();tick('KEY_A')
    assert(#shots==2, 'fresh A did not rearm after '..suspended)
end
start()
tick('KEY_A')

-- Native key ownership only in active gameplay and only for the test player.
assert(callAction('ACTION_LEFT')==0 and callAction('ACTION_SHOOTDOWN')==0)
assert(callAction('ACTION_RESTART','IS_ACTION_PRESSED')==false)
assert(callAction('ACTION_ITEM')==nil and callAction('ACTION_PAUSE')==nil and callAction('ACTION_DROP')==nil)
assert(callAction('ACTION_BOMB','IS_ACTION_TRIGGERED')==false)
input.key='KEY_G';assert(callAction('ACTION_BOMB','IS_ACTION_TRIGGERED')==true)
input.held='KEY_4';assert(callAction('ACTION_PILLCARD')==1)
assert(callAction('ACTION_LEFT','GET_ACTION_VALUE',enemy)==nil)
paused=true
assert(callAction('ACTION_LEFT')==nil and callAction('ACTION_BOMB')==nil)
tick('KEY_Q')
assert(#shots==1, 'cast during pause')
paused=false
event('EXECUTE_CMD','samiratest','off')
assert(callAction('ACTION_LEFT')==nil and callAction('ACTION_BOMB')==nil)

-- Q uses cursor heading, native shot multiplier and cooldown. Tear replacement
-- is leased and restricted to the projectiles actually present in a packet.
start()
mirror=true
tick('KEY_Q',false,Vector(20,100))
assert(packet.visual.cooldowns.q==2 and packet.visual.skill.kind=='q')
for i=1,7 do tick(); assert(#shots==0, 'gun fired before windup finished') end
tick()
assert(#shots==1 and shots[1].CollisionDamage==6 and shots[1].Velocity.X>0)
assert(packet.visual.projectiles[1].velocity[1]<0 and packet.visual.projectiles[1].position[2]==40)
for i=1,15 do tick() end
tick('KEY_Q')
assert(#shots==1, 'Q ignored its cooldown')
local tear=shots[1]
local function confirm(capabilities, seq)
    ack={version=1,session=packet.session,room=packet.room,time=now,ready=true,visible=true,
        capabilities=capabilities,seq=seq or packet.seq,display=packet.display.id}
    event('PRE_PLAYER_RENDER',player,Vector.Zero)
end
confirm({})
assert(event('PRE_TEAR_RENDER',tear)==nil, 'old renderer hid the native tear')
tick();tick();confirm({visual=1,projectiles=true},0)
assert(event('PRE_TEAR_RENDER',tear)==nil, 'older renderer frame hid a newly dispatched tear')
tick();tick();confirm({visual=1,projectiles=true})
assert(event('PRE_TEAR_RENDER',tear)==false, 'capable renderer did not replace acknowledged tear')
assert(event('PRE_TEAR_RENDER',makeEntity('ENTITY_TEAR',60,100,999))==nil)
now=now+50
confirm({visual=1,projectiles=true,styleHud=true})
event('POST_RENDER')
assert(styleExternal == true, 'a fresh style HUD lease did not suppress the native duplicate')
now=now+600
event('POST_RENDER')
assert(not styleExternal, 'native style HUD did not return after external lease expired')
assert(event('PRE_TEAR_RENDER',tear)==nil, 'expired acknowledgement hid the native tear')
event('POST_NEW_ROOM')
tick('KEY_Q')
assert(#shots==1 and #packet.visual.projectiles==0, 'room change reset cooldown or kept old tear')
for i=1,60 do tick() end
tick('KEY_Q')
for i=1,8 do tick() end
assert(#shots==2, 'Q never became ready again')
start()
enemy=makeEntity('enemy',86,100,11);entities={enemy}
tick('KEY_Q',false,Vector(100,100))
for i=1,8 do tick() end
assert(#shots==0 and #enemy.damage==1 and enemy.damage[1]==6 and packet.kind=='QMelee')

-- Melee Q faces the actual cursor in each direction. Its rendered radius
-- comes from the same reach used to select and hit the forward enemies.
local directions={Vector(1,0),Vector(-1,0),Vector(0,1),Vector(0,-1),Vector(1,-1):Normalized()}
for _, mirrored in ipairs({false,true}) do
    for index, heading in ipairs(directions) do
        start()
        mirror=mirrored
        local origin=Vector(200,120)
        player.Position=origin
        local edge=origin+heading*(index==#directions and 115 or 116)
        local outside=origin+heading*117
        local reverse=origin-heading*30
        local target=makeEntity('enemy',edge.X,edge.Y,11)
        local beyond=makeEntity('enemy',outside.X,outside.Y,12)
        local behind=makeEntity('enemy',reverse.X,reverse.Y,13)
        entities={target,beyond,behind}
        local aim=origin+heading*60
        if mirrored then aim=Vector(400-aim.X,aim.Y) end
        tick('KEY_Q',false,aim)
        for i=1,8 do tick() end
        assert(packet.kind=='QMelee' and #shots==0 and #target.damage==1)
        assert(#beyond.damage==0 and #behind.damage==0)
        local x=heading.X*(mirrored and -1 or 1)
        local slash
        for _, effect in ipairs(packet.visual.events) do
            if effect.kind=='qmelee' then slash=effect;break end
        end
        assert(slash and slash.radius==54, 'visual radius does not match world reach at half scale')
        assert(math.abs(slash.direction[1]-x)<1e-6 and math.abs(slash.direction[2]-heading.Y)<1e-6)
        assert(math.abs(packet.face[1]-x)<1e-6 and math.abs(packet.face[2]-heading.Y)<1e-6)
    end
end
start()
enemy=makeEntity('enemy',30,100,11);entities={enemy}
tick('KEY_Q',false,Vector(120,100))
for i=1,8 do tick() end
assert(#shots==1 and #enemy.damage==0, 'an enemy behind Samira selected melee Q')

-- Render-only taps must reach the next simulation update even after release.
-- Holding persists through the cooldown without turning into repeated casts.
for _, key in ipairs({'q','w','e','r'}) do
    start()
    if key=='r' then earnStyle() end
    renderOnly('KEY_'..key:upper())
    renderOnly()
    assert(packet.visual.skill==nil)
    tick()
    assert(packet.visual.skill.kind==key, 'short tap lost for '..key)
end
start()
tick('KEY_Q')
assert(#shots==0 and packet.kind=='Q', 'Q windup did not start on press')
for i=1,65 do tick('KEY_Q') end
assert(#shots==1, 'holding Q repeated the cast')
tick()
assert(#shots==1, 'releasing Q produced a cast')
tick('KEY_Q')
for i=1,8 do tick() end
assert(#shots==2, 'next press did not produce a cast after release')

-- The last few frames of the current cast accept one brief tap, while taps
-- made early in a long cast or cooldown are dropped.
start()
tick('KEY_W')
tick('KEY_Q')
for i=1,14 do tick() end
assert(#shots==0)
for i=1,4 do tick() end
renderOnly('KEY_Q')
renderOnly()
for i=1,6 do tick() end
assert(#shots==0 and packet.visual.skill.kind=='q', 'tap near the end of W was not buffered')
tick('KEY_Q')
for i=1,65 do tick() end
assert(#shots==1, 'unavailable Q was buffered indefinitely')

start()
renderOnly('KEY_Q')
console=true
renderOnly('KEY_Q')
console=false
tick('KEY_Q')
assert(#shots==0, 'console did not clear queued input or synchronize a held key')
tick()
tick('KEY_Q')
for i=1,8 do tick() end
assert(#shots==1)

-- W deals two sweeps and continuously eats hostile projectiles. Other
-- projectile ownership, lasers and distant projectiles survive.
start()
enemy=makeEntity('enemy',88,100,11)
local shot=makeEntity('ENTITY_PROJECTILE',88,100,12)
local ally=makeEntity('ENTITY_PROJECTILE',90,100,13);ally.SpawnerEntity=player
local harmless=makeEntity('ENTITY_PROJECTILE',92,100,14);harmless.noPlayer=true
local beam=makeEntity('ENTITY_LASER',90,100,15)
local distant=makeEntity('ENTITY_PROJECTILE',200,100,16)
entities={enemy,shot,ally,harmless,beam,distant}
tick('KEY_W')
assert(shot.removed and #enemy.damage==1)
assert(not ally.removed and not harmless.removed and not beam.removed and not distant.removed)
local late=makeEntity('ENTITY_PROJECTILE',65,100,17)
local collision=event('PRE_PROJECTILE_COLLISION',late,player)
assert(late.removed and collision.SkipCollisionEffects)
for i=1,24 do tick() end
assert(#enemy.damage==2, 'W did not apply exactly two sweeps')
tick('KEY_W')
assert(packet.visual.skill==nil, 'W ignored its cooldown')

-- Both W sweeps break blast-eligible props in their current radius. Quest
-- fixtures, other grid types, and objects outside the radius stay intact.
start()
local red=makeEntity('ENTITY_FIREPLACE',155,100,11);red.Variant=1
local blue=makeEntity('ENTITY_FIREPLACE',70,100,12);blue.Variant=2
local white=makeEntity('ENTITY_FIREPLACE',70,100,13);white.Variant=4
local purple=makeEntity('ENTITY_FIREPLACE',165,100,14);purple.Variant=3
entities={red,blue,white,purple}
local poop=makeGrid(GridEntityType.GRID_POOP,20)
local pot=makeGrid(GridEntityType.GRID_ROCK_ALT,21)
local distantPoop=makeGrid(GridEntityType.GRID_POOP,24)
local protected={}
for i, kind in ipairs({'GRID_ROCK','GRID_DOOR','GRID_TRAPDOOR','GRID_TNT','GRID_ROCK_ALT2'}) do
    protected[i]=makeGrid(GridEntityType[kind],({11,12,13,22,23})[i])
end
tick('KEY_W')
assert(red.deaths==1 and blue.deaths==1 and not white.dead and not purple.dead)
assert(poop.destroyed==1 and pot.destroyed==1 and not distantPoop.destroyed)
for _, prop in ipairs(protected) do assert(not prop.destroyed) end
purple.Position=Vector(140,100)
local secondPoop=makeGrid(GridEntityType.GRID_POOP,10)
for i=1,17 do tick() end
assert(not purple.dead and not secondPoop.destroyed)
tick()
assert(purple.deaths==1 and secondPoop.destroyed==1)
assert(red.deaths==1 and blue.deaths==1 and poop.destroyed==1 and not white.dead and not distantPoop.destroyed)
for _, prop in ipairs(protected) do assert(not prop.destroyed) end

local function effects(kind,source)
    local found={}
    for _, effect in ipairs(packet.visual.events) do
        if effect.kind==kind and (not source or effect.source==source) then
            found[#found+1]=effect
        end
    end
    return found
end

-- W travels with E and resumes its original phase after the dash. An R
-- cast overlaps W without cutting short the sweep or projectile block.
start()
enemy=makeEntity('enemy',220,140,11)
local boundary=makeEntity('enemy',165,100,12)
local beyond=makeEntity('enemy',170,100,13)
entities={enemy,boundary,beyond}
tick('KEY_W')
assert(packet.visual.skill.radius==50 and #boundary.damage==1 and #beyond.damage==0)
assert(packet.sfxVolume==.6 and #effects('cast','w')==1)
local shieldTarget=makeEntity('ENTITY_PROJECTILE',194,100,14)
entities[#entities+1]=shieldTarget
tick('KEY_E',false,Vector(180,100))
assert(packet.kind=='E' and #packet.visual.skills==2)
assert(packet.visual.skills[1].kind=='e' and packet.visual.skills[2].kind=='w')
for i=1,7 do tick() end
assert(packet.kind=='W' and math.abs(packet.phase-8/24)<1e-6 and shieldTarget.removed)
for i=1,16 do tick() end
assert(#effects('w')==2 and #enemy.damage==1)

start()
enemy=makeEntity('enemy',90,100,11);entities={enemy}
tick('KEY_W')
earnStyle()
tick('KEY_R')
assert(packet.kind=='RStart' and #packet.visual.skills==2 and packet.visual.skill.kind=='r'
    and packet.visual.skills[2].kind=='w')
assert(packet.visual.cooldowns.w>0 and #effects('cast','r')==1)
local surviving=makeEntity('ENTITY_PROJECTILE',65,100,12)
entities[#entities+1]=surviving
for i=1,59 do tick() end
assert(#enemy.damage==12 and not surviving:Exists(), 'R interrupted an active W')

start()
enemy=makeEntity('enemy',90,170,11);entities={enemy}
earnStyle()
tick('KEY_R')
tick('KEY_E',false,Vector(180,100))
assert(packet.kind=='E' and #packet.visual.skills==2 and packet.visual.skills[2].kind=='r')
for i=1,7 do tick() end
assert(packet.kind=='RLoop' and packet.phase>0, 'R restarted instead of resuming after E')

-- E truncates at ground pits and walls, and hits each crossed enemy once.
for _,obstruction in ipairs({1,2,4}) do
    start()
    wall[room:GetGridIndex(Vector(100,100))]=obstruction
    tick('KEY_E',false,Vector(180,100))
    for i=1,9 do tick() end
    assert(player.Position.X>60 and player.Position.X<80, 'dash crossed blocked terrain')
end
for _,cursorX in ipairs({61,130,250,390}) do
    start()
    tick('KEY_E',false,Vector(cursorX,100))
    for i=1,7 do tick() end
    assert(math.abs(player.Position.X-180)<1e-6, 'free E changed length with cursor distance')
end

local function startHop(obstruction, oldClass, flying)
    start()
    player.GridCollisionClass, player.CanFly=oldClass, flying==true
    wall[room:GetGridIndex(Vector(100,100))]=obstruction
    local target=makeEntity('enemy',165,100,11)
    entities={target}
    tick('KEY_E',false,target.Position)
    return target
end
for _, obstacle in ipairs({1,2}) do
    local target=startHop(obstacle,EntityGridCollisionClass.GRIDCOLL_GROUND)
    assert(packet.visual.skill.kind=='e' and player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_NONE)
    for i=1,6 do tick() end
    assert(#target.damage==1 and math.abs(player.Position.X-180)<1e-6)
    assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_GROUND)
end
local flyingTarget=startHop(2,EntityGridCollisionClass.GRIDCOLL_WALLS,true)
for i=1,6 do tick() end
assert(#flyingTarget.damage==1 and player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_WALLS)

for _, blocked in ipairs({'wall','closedDoor','noLanding','outside'}) do
    start()
    local target=makeEntity('enemy',165,100,11)
    if blocked=='wall' then
        wall[room:GetGridIndex(Vector(100,100))]=4
    elseif blocked=='closedDoor' then
        doors[0]={Position=Vector(112,100),IsOpen=function() return false end}
    elseif blocked=='noLanding' then
        wall[room:GetGridIndex(Vector(180,100))]=2
        for x=220,340,40 do wall[room:GetGridIndex(Vector(x,100))]=2 end
    else
        player.Position=Vector(300,100)
        target.Position=Vector(410,100)
    end
    local origin=player.Position
    entities={target}
    tick('KEY_E',false,target.Position)
    assert(packet.visual.skill==nil and packet.visual.cooldowns.e==0 and player.Position:Distance(origin)==0,
        'targeted E started with an invalid landing ('..blocked..')')
end

for _, interrupted in ipairs({'off','preRoom','postRoom','disabled','dead','frameJump','pause','landingChanged'}) do
    startHop(2,EntityGridCollisionClass.GRIDCOLL_GROUND)
    assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_NONE)
    if interrupted=='off' then
        event('EXECUTE_CMD','samiratest','off')
    elseif interrupted=='preRoom' then
        event('PRE_CHANGE_ROOM')
    elseif interrupted=='postRoom' then
        player.Position=Vector(335,175)
        event('POST_NEW_ROOM')
        assert(player.Position:Distance(Vector(335,175))==0, 'room reset moved player back into previous room')
    elseif interrupted=='disabled' then
        player.ControlsEnabled=false
        tick()
    elseif interrupted=='dead' then
        player.dead=true
        tick()
    elseif interrupted=='frameJump' then
        frame=frame+9
        tick()
    elseif interrupted=='pause' then
        local current=player.Position
        paused=true
        renderOnly()
        assert(player.Position:Distance(current)==0 and player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_NONE)
        paused=false
        for i=1,6 do tick() end
        assert(math.abs(player.Position.X-180)<1e-6)
    else
        wall[room:GetGridIndex(Vector(175,100))]=2
        wall[room:GetGridIndex(Vector(215,100))]=2
        for i=1,6 do tick() end
        assert(player.Position.X<160, 'targeted E landed in an obstacle added mid-dash')
    end
    assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_GROUND, 'wrong collision after '..interrupted)
    assert(room:GetGridCollision(room:GetGridIndex(player.Position))==0, 'restored mid-obstacle after '..interrupted)
end
start()
enemy=makeEntity('enemy',100,100,11);entities={enemy}
tick('KEY_E',false,enemy.Position)
for i=1,9 do tick() end
assert(player.Position.X>enemy.Position.X and #enemy.damage==1 and enemy.damage[1]==5)
tick('KEY_E',false,Vector(220,100))
assert(packet.visual.skill==nil, 'E ignored its cooldown')

-- Q can be seen by the render callback before E in the same simulation
-- frame. They still form EQ, with one hit per enemy from each applicable
-- skill and one detonation at the end. W does not block the Q extension.
start()
local dashVictim=makeEntity('enemy',100,100,11)
local comboVictim=makeEntity('enemy',125,126,12)
local untouched=makeEntity('enemy',125,145,13)
entities={dashVictim,comboVictim,untouched}
tick('KEY_W')
renderOnly('KEY_Q',false,Vector(180,100))
renderOnly('KEY_E',false,Vector(180,100))
tick()
assert(packet.kind=='EQ' and packet.visual.skills[1].kind=='eq' and packet.visual.skills[2].kind=='w')
assert(packet.visual.cooldowns.q==2 and packet.visual.cooldowns.e==12 and #shots==0)
assert(#effects('cast','e')==1 and #effects('cast','eq')==1 and #effects('cast','q')==0)
assert(#effects('eq')==0, 'EQ detonated before the dash landed')
for i=1,6 do tick() end
local detonation=effects('eq')
assert(#detonation==1 and detonation[1].position[1]==30 and math.abs(detonation[1].target[1]-90)<1e-6)
assert(#dashVictim.damage==3 and dashVictim.damage[2]==5 and dashVictim.damage[3]==6)
assert(#comboVictim.damage==2 and comboVictim.damage[2]==6 and #untouched.damage==1)
tick('KEY_Q')
for i=1,12 do tick() end
assert(#shots==0 and #effects('cast','eq')==1)

-- A wall shortens E, including the EQ blast path. Dash only protects the
-- active player from damage while its displacement is being applied.
start()
wall[room:GetGridIndex(Vector(100,100))]=4
local behindWall=makeEntity('enemy',122,100,11);entities={behindWall}
renderOnly('KEY_Q',false,Vector(180,100))
tick('KEY_E',false,Vector(180,100))
assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==false)
assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(makeEntity('ENTITY_PROJECTILE',60,100,12)))==false)
assert(event('ENTITY_TAKE_DMG',behindWall,1,0,EntityRef(player))==nil)
paused=true
assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==nil)
paused=false
for i=1,6 do tick() end
assert(#behindWall.damage==0 and effects('eq')[1].target[1]<40)
assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==false)
tick(nil,nil,nil,function()
    assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==false,
        'the final displacement lost its protection before physics resolved')
end)
assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==nil)
for _, reset in ipairs({'off','room'}) do
    start()
    tick('KEY_E',false,Vector(180,100))
    if reset=='off' then event('EXECUTE_CMD','samiratest','off') else event('POST_NEW_ROOM') end
    assert(event('ENTITY_TAKE_DMG',player,1,0,EntityRef(behindWall))==nil)
end

-- R maintains exactly ten damage ticks while native autoattack is suspended.
start()
enemy=makeEntity('enemy',122,100,11);entities={enemy}
local inside=makeEntity('enemy',187,100,12)
local outside=makeEntity('enemy',189,100,13)
entities={enemy,inside,outside}
earnStyle()
tick('KEY_R',true,enemy.Position)
assert(packet.visual.skill.radius==60)
for i=1,59 do tick() end
assert(#enemy.damage==10 and #shots==0, 'unexpected R damage count or concurrent autoattack')
assert(#inside.damage==10 and #outside.damage==0, 'R affected the wrong hitboxes at its edge')
tick()
assert(#shots==1 and packet.visual.cooldowns.r==3, 'normal attack did not resume after R')

-- Console inspection is animation-only.
start()
event('EXECUTE_CMD','samiraanim','r')
tick()
assert(packet.kind=='RStart' and packet.visual.skill==nil and #shots==0)
event('POST_ENTITY_TAKE_DMG',player,1,0,nil)
tick()
assert(packet.hurt, 'accepted native player damage was not sent to renderer')
for i=1,5 do tick() end
assert(not packet.hurt, 'player hurt marker did not expire')

-- A whole cast owns one item roll across all targets and delayed hits.
-- E+Q owns a separate Q context without replacing the original dash context.
itemProbe=true
start(); itemContexts={}
enemy=makeEntity('enemy',100,100,11);entities={enemy,makeEntity('enemy',110,100,12)}
earnStyle()
tick('KEY_R');for i=1,59 do tick() end
assert(#itemContexts==20)
for _,ctx in ipairs(itemContexts) do assert(ctx==itemContexts[1] and ctx.kind=='r') end
start();itemContexts={}
enemy=makeEntity('enemy',100,100,11);entities={enemy}
tick('KEY_W');for i=1,18 do tick() end
assert(#itemContexts==2 and itemContexts[1]==itemContexts[2] and itemContexts[1].kind=='w')
start();itemContexts={}
enemy=makeEntity('enemy',100,100,11);entities={enemy}
renderOnly('KEY_Q',false,Vector(180,100));tick('KEY_E',false,Vector(180,100))
for i=1,6 do tick() end
assert(#itemContexts==2 and itemContexts[1].kind=='e' and itemContexts[2].kind=='eq')
assert(itemContexts[1]~=itemContexts[2])
start();itemContexts={}
entities={makeEntity('enemy',100,100,11),makeEntity('enemy',115,100,12)}
tick('KEY_Q',false,Vector(180,100))
for i=1,8 do tick() end
assert(#itemContexts==2 and itemContexts[1]==itemContexts[2] and itemContexts[1].kind=='qmelee')
start();entities={};tick('KEY_A',false,Vector(200,100))
assert(#shots==1 and shots[1]:GetData().ItemContext.kind=='attack')
itemProbe=false
print('Passed legacy direct-fire gait, input, QWER combos, dash protection, lease and preview checks.')

-- Reload the same main/combat callbacks with the production weapon and kill
-- adapters. Model the engine's weapon discharge separately from Lua FireTear.
nativeMode=true
include('main')
start()
local nativeShots = {}
local weapon = {charge=0, maximum=0, fired=0}
function weapon:GetWeaponType() return 'mock weapon' end
function weapon:GetCharge() return self.charge end
function weapon:SetCharge(value) self.charge=value end
function weapon:GetMaxCharge() return self.maximum end
function weapon:GetNumFired() return self.fired end
function weapon:GetMainEntity() return self.output end
installedWeapon=weapon

local function nativeInput()
    event('PRE_PLAYER_UPDATE',player)
    return Vector((callAction('ACTION_SHOOTRIGHT') or 0)-(callAction('ACTION_SHOOTLEFT') or 0),
        (callAction('ACTION_SHOOTDOWN') or 0)-(callAction('ACTION_SHOOTUP') or 0))
end
local function discharge(aim)
    assert(aim:Length()>.001)
    weapon.fired=weapon.fired+1
    local tear=makeEntity('ENTITY_TEAR',player.Position.X,player.Position.Y,1000+weapon.fired)
    tear.Velocity,tear.Height,tear.SpawnerEntity=aim,-20,player
    weapon.output=tear
    nativeShots[#nativeShots+1]=tear
    event('POST_FIRE_TEAR',tear)
    event('POST_TRIGGER_WEAPON_FIRED',aim,1,player,weapon)
    event('POST_PLAYER_UPDATE',player)
    return assert(tear:GetData().ItemContext)
end

-- Selecting Samira starts gameplay automatically. R still requires rank S.
event('EXECUTE_CMD','samiratest','off')
selected=true
event('POST_GAME_STARTED',false)
assert(encounterPlayer()==player, 'selectable Samira was excluded from encounter doubling')
tick('KEY_R')
assert(packet.active and packet.visual.skill==nil and packet.visual.cooldowns.r==0)
assert(combat.styleStatus(frame).rank==0 and #effects('cast','r')==0)
earnStyle()
tick()
tick('KEY_R')
assert(packet.kind=='RStart' and packet.visual.cooldowns.r==5 and combat.styleStatus(frame).rank==0)

-- Production uses sword Q against a nearby enemy, and native gun Q downrange.
start()
local close=makeEntity('enemy',85,100,201)
entities={close}
tick('KEY_Q',false,close.Position)
assert(packet.kind=='QMelee' and packet.visual.cooldowns.q==2)
for i=1,7 do tick(); assert(#close.damage==0 and nativeInput():Length()==0) end
tick()
assert(#close.damage==1 and #effects('qmelee')==1 and #shots==0 and #nativeShots==0)

-- Check both acquisition and hit timing on moving targets and crowds.
start()
close.Position,close.damage=Vector(170,100),{}
entities={close}
tick('KEY_Q',false,close.Position)
assert(packet.kind=='QMelee')
close.Position=Vector(195,100)
for i=1,8 do tick() end
assert(#close.damage==0, 'sword hit an enemy who left during windup')
local flank=makeEntity('enemy',63,165,202)
for _,distant in ipairs({false,true}) do
    start()
    local forward=makeEntity('enemy',220,100,203)
    entities=distant and {flank,forward} or {flank}
    tick('KEY_Q',false,Vector(200,100))
    assert(packet.kind==(distant and 'Q' or 'QMelee'), 'flank selected wrong form')
end
start()
close.Position,close.Velocity=Vector(175,100),Vector(1,0)
entities={close}
tick('KEY_Q',false,close.Position)
assert(packet.kind=='Q', 'enemy retreating at the edge should receive gun Q')
for i=1,7 do tick(nil,false,Vector(60,10)); assert(nativeInput():Length()==0) end
tick(nil,false,Vector(60,10))
local qAim=nativeInput()
assert(qAim.X>.99 and math.abs(qAim.Y)<.01, 'cast turned after keypress')
local qContext=discharge(qAim)
assert(qContext.kind=='q' and qContext.nativeWeapon and qContext.damageMultiplier==1.5)
tick()
assert(packet.kind=='Q' and #effects('q')==1 and #shots==0 and #close.damage==0)

-- Starting E on the next tick during a gun windup still releases the original
-- Q at its scheduled frame. R only becomes ready when its cast lockout ends.
start()
earnStyle()
tick('KEY_Q',false,Vector(60,180))
assert(not combat.styleStatus(frame).ready)
tick('KEY_E',false,Vector(80,100))
assert(packet.visual.skill.kind=='e')
for i=1,6 do tick(); assert(nativeInput():Length()==0) end
tick()
assert(player.Position.X==180 and nativeInput().Y>.99)
assert(discharge(nativeInput()).kind=='q')
for i=1,3 do tick() end
assert(combat.styleStatus(frame).ready)

-- A room change discards both the pending damage and reserved native shot.
for _,near in ipairs({false,true}) do
    start()
    close.Position,close.Velocity=Vector(85,100),Vector.Zero
    entities=near and {close} or {}
    tick('KEY_Q',false,Vector(200,100))
    event('POST_NEW_ROOM')
    for i=1,10 do tick(); assert(nativeInput():Length()==0) end
    assert(#close.damage==0)
end

-- RMB targets drive a normalized native aim vector, including diagonals.
start()
local diagonal=makeEntity('enemy',120,160,202)
entities={diagonal}
tick(nil,true,diagonal.Position)
local autoAim=nativeInput()
assert(math.abs(autoAim.X-math.sqrt(.5))<.001 and math.abs(autoAim.Y-math.sqrt(.5))<.001)
local aaContext=discharge(autoAim)
assert(aaContext.kind=='aa' and aaContext.damageMultiplier==1)
tick()
assert(packet.kind=='Attack' and #shots==0 and #diagonal.damage==0)

-- A taps can direct the real weapon adapter without producing an extra Lua tear.
-- The engine double deliberately fires late, then waits out its native delay.
start()
do
    local enemy=makeEntity('enemy',155,100,250)
    entities={enemy}
    local count=#nativeShots
    tick('KEY_A',false,Vector(230,100))
    local acquired=frame
    assert(nativeInput():Length()==0, 'attack-move skipped windup')
    local readyAt
    for i=1,10 do
        tick()
        local aim=nativeInput()
        if aim.X>.99 then readyAt=readyAt or frame end
    end
    assert(readyAt==acquired+3, 'wrong base attack windup')
    assert(#nativeShots==count and #shots==0, 'unexpected synthetic attack before discharge')
    local aim=nativeInput()
    assert(aim.X>.99 and discharge(aim).kind=='aa')
    tick(nil,true,Vector(60,180))
    assert(nativeInput():Length()==0 and callAction('ACTION_DOWN')>.5,
        'retreat after native discharge was delayed')
    for i=1,12 do tick(); assert(nativeInput():Length()==0) end
    assert(#nativeShots==count+1 and #shots==0, 'retreating fired an extra volley')
end
start()
do
    local enemy=makeEntity('enemy',135,100,251)
    entities={enemy}
    weapon.maximum,weapon.charge=10,0
    tick('KEY_A',false,enemy.Position)
    assert(nativeInput().X>.99, 'charge weapon received a second artificial windup')
    weapon.charge=4
    tick(); assert(nativeInput().X>.99 and weapon.charge==4)
    weapon.maximum,weapon.charge=0,0
end

-- Manual A and a Q request share one native input instead of two shot paths.
start()
combat.setAttackMove(false)
tick('KEY_A',false,Vector(190,100))
input.held='KEY_A'
tick('KEY_Q',false,Vector(60,180))
for i=1,7 do tick('KEY_A',false,Vector(190,100));assert(nativeInput():Length()==0) end
tick('KEY_A',false,Vector(190,100))
local sharedAim=nativeInput()
assert(sharedAim.Y>.99 and #shots==0)
local count=#nativeShots
assert(discharge(sharedAim).kind=='q')
assert(#nativeShots==count+1 and #shots==0)
tick('KEY_A',false,Vector(190,100))
for i=1,3 do tick('KEY_A',false,Vector(190,100)) end
assert(nativeInput().X>.99, 'manual aim did not return after native Q discharged')
weapon.charge=12
paused=true
tick('KEY_A')
assert(weapon.charge==0, 'pause did not release native charge: '..weapon.charge)
assert(callAction('ACTION_SHOOTRIGHT')==0, 'pause did not neutralize shooting input')
paused=false
tick('KEY_A')
assert(nativeInput():Length()==0 and #shots==0, 'paused held A rearmed')
event('POST_PLAYER_UPDATE',player)

-- Real Kills callbacks feed the actual combat cooldown, with room clear for bosses.
start()
tick('KEY_W')
assert(combat.exportCooldowns(frame).w==660)
start()
tick('KEY_E',false,Vector(200,100))
assert(combat.exportCooldowns(frame).e==360)
local ordinary=makeEntity('enemy',100,100,203)
kills.acceptHit(ordinary,{player=player},frame)
ordinary:Die()
event('POST_NPC_DEATH',ordinary)
tick()
assert(combat.exportCooldowns(frame).e==360-1-45, 'standard kill did not shave 1.5 seconds off E')
local boss=makeEntity('enemy',100,100,204)
boss.boss=true
roomKind=RoomType.ROOM_BOSS
kills.acceptHit(boss,{player=player},frame)
boss:Die()
event('POST_NPC_DEATH',boss)
tick()
assert(combat.exportCooldowns(frame).e>0, 'boss reset preceded completion')
roomClear=true
tick()
assert(combat.exportCooldowns(frame).e==0, 'boss completion did not reset E')
-- Old saves without native backup metadata: a backwards frame must never
-- resurrect expired deadlines or add the rewind duration to remaining CDs.
start()
frame = 1541
combat.restoreCooldowns({q=21,w=525,e=0,r=0},frame)
frame = 1001
event('POST_NEW_ROOM'); tick()
assert(frame==1002 and packet.visual.cooldowns.q==.7 and packet.visual.cooldowns.w==17.5)
assert(packet.visual.cooldowns.r==0 and packet.visual.cooldowns.e==0)
frame=4122; tick(); frame=2489; tick()
for _,v in pairs(packet.visual.cooldowns) do assert(v==0, 'expired cooldown came back after a rewind') end
combat.restoreCooldowns({q=3000,w=2000,e=1000,r=500},frame)
local clamped=combat.exportCooldowns(frame)
assert(clamped.q==60 and clamped.w==660 and clamped.e==360 and clamped.r==150)
print('Passed production native Q/AA, R style gating, pause input, E kill reset and rewind clock integration.')
''')
