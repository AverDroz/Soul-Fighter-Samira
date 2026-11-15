local V={};V.__index=V
function V.__add(a,b)return Vector(a.X+b.X,a.Y+b.Y)end
function V.__sub(a,b)return Vector(a.X-b.X,a.Y-b.Y)end
function V.__mul(a,b)return Vector(a.X*b,a.Y*b)end
function V:Length()return (self.X*self.X+self.Y*self.Y)^.5 end
function V:Normalized()local n=self:Length();return Vector(self.X/n,self.Y/n)end
function V:Distance(b)return (self-b):Length()end
function V:Rotated(d)local r=math.rad(d);return Vector(self.X*math.cos(r)-self.Y*math.sin(r),self.X*math.sin(r)+self.Y*math.cos(r))end
function V:GetAngleDegrees()return math.deg(math.atan(self.Y,self.X))end
Vector=setmetatable({},{__call=function(_,x,y)return setmetatable({X=x,Y=y},V)end});Vector.Zero=Vector(0,0)
local function enum()local nextId=0;return setmetatable({},{__index=function(t,k)nextId=nextId+1;rawset(t,k,nextId);return nextId end})end
ModCallbacks=enum();ButtonAction=enum();InputHook=enum();Keyboard=enum();SoundEffect=enum();EntityFlag=enum();EntityType=enum();PickupVariant=enum();CacheFlag=enum();CollectibleType=enum();LaserOffset=enum()
DamageFlag={DAMAGE_FAKE=1,DAMAGE_NO_PENALTIES=2,DAMAGE_RED_HEARTS=4,DAMAGE_INVINCIBLE=8,DAMAGE_EXPLOSION=16}
SoundEffect.NUM_SOUND_EFFECTS=1091
SoundEffect.SOUND_ISAAC_HURT_GRUNT=55;SoundEffect.SOUND_ISAACDIES=217;SoundEffect.SOUND_CHILD_HAPPY_ROAR_SHORT=56
RoomType={ROOM_CURSE=10};RoomTransitionAnim={WALK=0}
GridCollisionClass={COLLISION_NONE=0,COLLISION_PIT=1,COLLISION_WALL=4};REPENTOGON=true;BlendType={ADDITIVE=2}
GridEntityType=enum();EntityGridCollisionClass={GRIDCOLL_WALLS=3,GRIDCOLL_GROUND=5}
Options={MouseControl=true,FoundHUD=true,MusicVolume=.3,Language='zh'}
Color=setmetatable({Default={R=1,G=1,B=1,A=1}},{__call=function(_,r,g,b,a)return {R=r,G=g,B=b,A=a}end});function EntityRef(e)return {Entity=e}end
function KColor(...)return {...}end
function Font()return {Load=function()end,GetStringWidthUTF8=function(_,s)return #s*6 end,DrawStringScaledUTF8=function()end}end
local callbacks={};local persisted=''
function RegisterMod()return {AddCallback=function(_,id,fn)callbacks[id]=fn end,
 SaveData=function(_,text)persisted=text end,LoadData=function()return persisted end,HasData=function()return persisted~='' end}end
local nativeAnimation='Idle';local extraFinished=true;local dead=false
local nativeSprite={GetAnimation=function()return nativeAnimation end}
local player={Position=Vector(100,100),Velocity=Vector.Zero,SpriteOffset=Vector.Zero,Damage=3.5,MaxFireDelay=10,TearRange=260,Luck=0,MoveSpeed=1,FireDelay=0,Size=12,ControlsEnabled=true,type=10,data={}}
TearFlags={TEAR_NORMAL=0};WeaponType={WEAPON_TEARS=1}
for i,name in ipairs({'POISON','SLOW','FREEZE','CHARM','CONFUSION','FEAR','BURN','MIDAS','GISH','PERMANENT_CONFUSION','GODS_FLESH','MAGNETIZE','BAIT','EXPLOSIVE','SPLIT','BOUNCE','HOMING','ICE'}) do TearFlags['TEAR_'..name]=1<<(i-1) end
function player:GetTearHitParams()return {TearFlags=0} end
function player:GetTearPoisonDamage()return self.Damage end
function player:AddCacheFlags(flag)self.cacheFlag=flag end
function player:EvaluateItems()self.CanFly=false;callbacks[ModCallbacks.MC_EVALUATE_CACHE](nil,self,self.cacheFlag)end
function player:ClearEntityFlags()end
function player:HasEntityFlags()return false end
function player:GetDamageCooldown()return self.damageCooldown or 0 end
function player:ResetDamageCooldown()self.damageCooldown=0 end
function player:SetMinDamageCooldown(n)self.damageCooldown=math.max(self.damageCooldown or 0,n) end
function player:TakeDamage(n)self.taken=(self.taken or 0)+n;return true end
function player:GetCard()return self.card or 0 end;function player:GetPill()return self.pill or 0 end
function player:ToPlayer()return self end;function player:GetPlayerType()return self.type end
function player:GetData()return self.data end;function player:IsDead()return dead end;function player:IsExtraAnimationFinished()return extraFinished end
function player:GetSprite()return nativeSprite end
function player:GetCollectibleRNG()return {RandomFloat=function()return .5 end}end
function player:HasCollectible(id)return self.weapons and self.weapons[id]==true or false end
function player:ChangePlayerType(t)self.type=t end
function player:Exists()return true end
local function addHealth(p,n,kind,action)
 if callbacks[ModCallbacks.MC_PRE_PLAYER_ADD_HEARTS] then callbacks[ModCallbacks.MC_PRE_PLAYER_ADD_HEARTS](nil,p,n,kind) end
 action()
 if callbacks[ModCallbacks.MC_POST_PLAYER_ADD_HEARTS] then callbacks[ModCallbacks.MC_POST_PLAYER_ADD_HEARTS](nil,p,n,kind) end
end
function player:AddHearts(n)addHealth(self,n,1,function()self.red=math.max(0,math.min(self:GetEffectiveMaxHearts(),self:GetHearts()+n));self.healed=(self.healed or 0)+n end)end
function player:GetHearts()return self.red or 6 end;function player:GetSoulHearts()return self.soul or 2 end
function player:AddSoulHearts(n)addHealth(self,n,4,function()self.soul=math.max(0,self:GetSoulHearts()+n) end)end
function player:Kill()dead=true end
function player:GetEffectiveMaxHearts()return 8+(self.addedContainers or 0) end
function player:GetNumCoins()return self.coins or 0 end
function player:GetMaxCoins()return 99 end
function player:AddCoins(n)self.coins=math.max(0,math.min(99,(self.coins or 0)+n))end
function player:AddMaxHearts(n)addHealth(self,n,2,function()self.addedContainers=math.max(-8,math.min(16,(self.addedContainers or 0)+n));self.red=math.min(self:GetHearts(),self:GetEffectiveMaxHearts()) end)end
local entities={};local paused=false;local wall=false
local room={};local doors={};local grids={};local collisionOverride
local bossRoomSeed=1
function room:GetSpawnSeed()return bossRoomSeed end
function room:GetGridEntity(index)return grids[index]end
function room:GetDoor(slot)return doors[slot]end
function room:GetGridWidth()return 20 end;function room:GetGridSize()return 400 end
function room:GetGridIndex(p)return math.floor(p.Y/40)*20+math.floor(p.X/40)end
function room:GetGridPosition(i)return Vector(i%20*40+20,math.floor(i/20)*40+20)end
function room:GetGridCollision(i)if collisionOverride then return collisionOverride(i) end;if wall and i%20==4 then return 3 end;return 0 end
function room:GetClampedPosition(p)return p end;function room:IsPositionInRoom(p,r)r=r or 0;return p.X>=r and p.X<800-r and p.Y>=r and p.Y<800-r end
function room:CheckLine(a,b)return not wall or a.X<160 and b.X<160 end
function room:FindFreePickupSpawnPosition(p)return p end
local game={GetRoom=function()return room end,IsPaused=function()return paused end,GetNumPlayers=function()return 1 end,ShakeScreen=function()end}
local startSeed=12345
function game:GetSeeds()return {GetStartSeed=function()return startSeed end}end
local floorNumber=1
local transitions={};local level={GetDimension=function()return 1 end,RevealMap=function()end,GetAbsoluteStage=function()return floorNumber end}
local bombExplosions={}
function game:BombExplosionEffects(pos,damage,tearFlags,color,source,radius,lineCheck,damageSource,flags)
 assert(damage==100 and tearFlags==0 and not lineCheck and not damageSource and flags==DamageFlag.DAMAGE_EXPLOSION)
 assert(source:GetData().SamiraTerrainExplosion,'Q3 must bracket native damage callbacks')
 bombExplosions[#bombExplosions+1]={position=pos,radius=radius,source=source}
 -- Native environment behavior is mocked; these checks exercise routing and
 -- radius, not a substitute for live engine chest/door tests.
 for _,grid in pairs(grids) do
  if grid.Position:Distance(pos)<=75*radius and grid.kind~=GridEntityType.GRID_DOOR and grid.kind~=GridEntityType.GRID_ROCKB and grid.Destroy then grid:Destroy(false) end
 end
 assert(callbacks[ModCallbacks.MC_ENTITY_TAKE_DMG](nil,source,damage,flags,EntityRef(source),0)==false,'environment blast cannot damage its caster')
 for _,e in ipairs(entities) do
  if e.Position:Distance(pos)<=75*radius and callbacks[ModCallbacks.MC_ENTITY_TAKE_DMG](nil,e,damage,flags,EntityRef(source),0)~=false then e:TakeDamage(damage,flags,EntityRef(source),0) end
 end
end
function level:GetCurrentRoomIndex()return self.roomIndex or 1 end
function level:GetStartingRoomIndex()return 0 end
function room:GetCenterPos()return Vector(320,280)end
function game:GetLevel()return level end
function game:StartRoomTransition(index,direction,animation,who,dimension)
 transitions[#transitions+1]={index,direction,animation,who,dimension}
end
function room:IsClear()return #entities==0 end
function room:IsMirrorWorld()return false end
local playedSounds={};local soundIds={};local soundNames={};local activeSounds={};local stoppedSounds={}
local function soundId(name)
 if not soundIds[name] then local id=10000+#soundNames+1;soundNames[#soundNames+1]=name;soundIds[name]=id end
 return soundIds[name]
end
function Game()return game end;function SFXManager()return {Play=function(_,id,volume,delay,loop)playedSounds[#playedSounds+1]=id;activeSounds[id]=loop or true end,Stop=function(_,id)activeSounds[id]=nil;stoppedSounds[#stoppedSounds+1]=id end,IsPlaying=function(_,id)return activeSounds[id]~=nil end}end
do
 local music={current=1,queued=1,plays=0}
 function music:GetCurrentMusicID()return self.current end
 function music:GetQueuedMusicID()return self.queued end
 function music:Play(id)
  local callback=callbacks[ModCallbacks.MC_PRE_MUSIC_PLAY]
  local result=callback and callback(nil,id,1,false)
  if result==false then return end
  self.current=type(result)=='number' and result or id;self.plays=self.plays+1
 end
 function music:Crossfade(id)self:Play(id)end
 function music:Queue(id)self.queued=id end
 function music:UpdateVolume()self.volumeUpdated=true;self.volume=Options.MusicVolume end
 function music:VolumeSlide(volume)self.volume=volume end
 function music:Fadeout()self.current=0 end
 function MusicManager()return music end
end
local spriteDraws={}
function Sprite()return {Load=function(self,path)self.path=path end,SetFrame=function()end,Render=function(self,pos)spriteDraws[#spriteDraws+1]={path=self.path,pos=pos,scale=self.Scale}end,GetLayer=function()return {GetBlendMode=function()return {SetMode=function()end}end}end}end
local keys={};local right=false;local left=false;local mouse=Vector(300,100)
Input={IsButtonPressed=function(k)return keys[k] or false end,IsButtonTriggered=function(k)return keys[k] or false end,IsMouseBtnPressed=function(button)return button==0 and left or button==1 and right or false end,GetMousePosition=function()return mouse end}
Isaac={GetTime=function()return 0 end,GetSoundIdByName=soundId,GetPlayerTypeByName=function()return 10 end,GetPlayer=function()return player end,GetRoomEntities=function()return entities end,
 ScreenToWorld=function(v)return v end,WorldToScreenDistance=function(v)return v end,WorldToScreen=function(v)return v end,WorldToRenderPosition=function(v)return v end,
 GetScreenWidth=function()return 640 end,GetScreenHeight=function()return 480 end,RenderText=function()end,DebugString=function()end,ConsoleOutput=function()end}
function Isaac.GetMusicIdByName(name)assert(name=='Samira World Ender');return 200 end
local function mob(x,y)
 local e={Position=Vector(x,y),Velocity=Vector.Zero,Size=12,hits=0,total=0,HitPoints=1000,MaxHitPoints=1000,data={}}
 function e:Exists()return true end;function e:IsDead()return false end;function e:IsVulnerableEnemy()return true end
 function e:ToPlayer()return nil end
 function e:ToNPC()return self end;function e:IsChampion()return self.champion==true end
 function e:HasEntityFlags()return false end;function e:IsBoss()return false end;function e:SetColor()end
 function e:GetData()return self.data end
 function e:AddSlowing(_,duration,amount)self.slow={duration,amount}end
function e:AddFear(_,duration)self.fear=duration end
 e.FrameCount=0
 function e:GetFearCountdown()return self.fear or 0 end
 function e:SetFearCountdown(n)self.fear=n end
 function e:ClearEntityFlags(flag)self.clearedFlag=flag end
 function e:TakeDamage(d)self.hits=self.hits+1;self.total=self.total+d;return true end
 return e
end
include('main')
-- Q control is applied once per accepted aggregate hit, including inner hits.
do
 local K=include('scripts.samira_knockup');local e=mob(100,100)
 local pre=callbacks[ModCallbacks.MC_PRE_NPC_UPDATE]
 assert(callbacks[ModCallbacks.MC_PRE_NPC_RENDER]==nil,'Q stagger must not intercept native NPC rendering')
 local offset=Vector(7,9);e.SpriteOffset=offset;local position=e.Position
 assert(pre(nil,e)==nil)
 e.Velocity=Vector(6,3);K.apply(e);assert(pre(nil,e)==true and e.Velocity:Length()==0)
 for i=1,4 do K.tick() end
 assert(e.Position==position and e.SpriteOffset==offset,'stagger preserves native position and sprite offset')
 K.apply(e)
 for i=1,11 do K.tick() end
 e.Velocity=Vector(4,2);assert(pre(nil,e)==true and e.Velocity:Length()==0,'refresh and subsequent movement remain stopped')
 K.tick();assert(pre(nil,e)==nil,'AI resumes after exactly 12 ticks')
 K.apply(e);K.clear();assert(pre(nil,e)==nil,'room/rewind invalidates stagger state')
 K.apply(e);e.IsDead=function()return true end
 assert(pre(nil,e)==nil,'death animation is never suspended')
 print('Q stagger duration, refresh, no render override, velocity/offset preservation, room/rewind and death cleanup passed')
end
-- Model files must be resolved during mod loading, before the render callback context.
local startupInclude=include
include=function(name)
 assert(name~='scripts.samira_skeleton_data','model data must not be loaded from gameplay/render callbacks')
 return startupInclude(name)
end
-- Actual reported crash: engine can render the player before the first effect update.
callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
callbacks[ModCallbacks.MC_POST_RENDER]()
assert(player.data.Samira.hitFlash==0,'first render initializes hit feedback')
assert(callbacks[ModCallbacks.MC_POST_PLAYER_UPDATE]==nil,'60 Hz player callback must not double ability speed')
local function tick(n)for i=1,n or 1 do callbacks[ModCallbacks.MC_POST_UPDATE]();player.Position=player.Position+player.Velocity end end
local function reset()
 include("scripts.samira_audio").cleanup();activeSounds={}
 include("scripts.samira_audio").resetBossRooms();bossRoomSeed=1
 transitions={};doors={};player.data={};player.Position=Vector(100,100);player.Velocity=Vector.Zero;keys={};right=false;left=false;entities={};wall=false;paused=false;player.type=10
 nativeAnimation='Idle';extraFinished=true;dead=false;player.ControlsEnabled=true;player.SpriteOffset=Vector.Zero
 player.red=6;player.soul=2;player.addedContainers=0;player.healed=0;player.coins=25;player.Visible=true
 local external=include('scripts.samira_external');external.revealAt=nil;external.coverUntil=nil;external.startUntil=nil;external.manualHidden=nil;external.roomCoverUntil=nil;external.renderSample=nil;external.lastActorPosition=nil
 -- Combat regressions start with legally learned rank-one skills. New-run tests explicitly reset progression.
 include('scripts.samira_progression').restore(player,{level=6,skills={q=1,w=1,e=1,r=1}});floorNumber=1
 grids={};collisionOverride=nil;player.GridCollisionClass=EntityGridCollisionClass.GRIDCOLL_GROUND;player.CanFly=false;player.damageCooldown=0
end
right=true;tick();assert(player.Velocity.X>0,'right click must move');right=false
keys[Keyboard.KEY_S]=true;tick();assert(player.data.Samira.goal==nil,'S cancels destination')
reset();local e=mob(140,100);entities={e};mouse=e.Position;right=true;tick();right=false
assert(player.data.Samira.cast.kind=='Attack','a target in reach attacks immediately without a cosmetic draw lock')
tick(6);assert(e.hits==1,'one ordinary swing hits once at its contact');tick(5);assert(e.hits==1)
reset();e=mob(260,100);entities={e};mouse=e.Position;keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(16);assert(e.hits==0,'Q cannot damage during the 0.6-second windup');tick();assert(e.hits==1,'Q1 hits outer sword edge');assert(math.abs(e.total-include('scripts.samira_progression').stats(player,{damage=3.5*1.8,interval=22}).damage*include('scripts.samira_progression').attackMultiplier(player)*1.25*1.6)<.001)
tick(12);keys[Keyboard.KEY_Q]=true;tick();assert(player.data.Samira.cast.stage==2);keys[Keyboard.KEY_Q]=false;tick(29);keys[Keyboard.KEY_Q]=true;tick();assert(player.data.Samira.cast.stage==3)
reset();e=mob(350,100);entities={e};mouse=e.Position;keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(16);assert(e.hits==1,'QE relocates the impact instead of fixing it at cast start')
reset();wall=true;mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(11);assert(player.Position.X>=212,'dash crosses a full rock tile and lands clear of its far edge')
reset();mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();local clock=player.data.Samira.clock;paused=true;tick(20);assert(player.data.Samira.clock==clock,'pause must not advance cooldown');paused=false;keys[Keyboard.KEY_Q]=false;tick(125);assert(player.data.Samira.nextQ==1,'expired combo returns to Q1')
local inp=callbacks[ModCallbacks.MC_INPUT_ACTION]
assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_PILLCARD)==0,'Q must not also use a card')
assert(inp(nil,nil,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_RESTART)==0,'holding R must not restart the run')
keys={};keys[Keyboard.KEY_G]=true
assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_BOMB)==1)
assert(inp(nil,player,InputHook.IS_ACTION_TRIGGERED,ButtonAction.ACTION_BOMB)==true,'G routes through native bomb placement')
assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_PILLCARD)==0,'G cannot consume a pocket item')
player.data.Samira.shopOpen=true;assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_BOMB)==0);player.data.Samira.shopOpen=false
keys[Keyboard.KEY_LEFT_CONTROL]=true;assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_BOMB)==0)
keys={};keys[Keyboard.KEY_4]=true;assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_PILLCARD)==1)
assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_BOMB)==0,'4 cannot drop a bomb')
do
 local C=include('scripts.samira_controls');C.state(player).mode='wasd';C.state(player).bindings.stop=Keyboard.KEY_G
 assert(C.key(player,'stop')==Keyboard.KEY_V,'WASD stop cannot conflict with G bombs')
 C.state(player).mode='mouse';C.state(player).bindings={}
end
keys={}
player.type=1;assert(inp(nil,player,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_LEFT)==nil,'other characters keep native controls')
reset();keys[Keyboard.KEY_Q]=true;tick();callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(player.data.Samira.cast==nil and player.data.Samira.goal==nil)
callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero);callbacks[ModCallbacks.MC_POST_RENDER]()
reset();mouse=Vector(70,450);right=true;tick();assert(player.data.Samira.goal==nil,'HUD right click must not order movement underneath it')
keys[Keyboard.KEY_Q]=true;tick();assert(player.data.Samira.cast==nil,'HUD hover must not aim Q behind the panel')
local hud=include('scripts.samira_hud')
local Health=include('scripts.samira_health')
local red,soul,cap=hud.health(player);assert(red==Health.current(player) and soul==100 and cap==Health.max(player)+100,'HUD uses numeric HP and shields')
for _,wh in ipairs({{480,270},{640,360},{1280,720}})do
 local l=hud.layout(wh[1],wh[2]);assert(l.left.x>=0 and l.left.y>=0 and l.right.x+l.right.w<=wh[1]);assert(l.left.x+l.left.w<wh[1]/2-36 and l.right.x>wh[1]/2+36,'bottom door corridor stays clear')
end
local probe=include('scripts.samira_render_probe');probe.toggle(true)
assert(not probe.enabled,'unsupported mesh APIs leave the existing animation working')
-- Exercise mesh projection through a faithful-shaped surface mock, then inject an API failure.
local submissions=0;local cleared=0;local time=0
local diagnostics={};Isaac.DebugString=function(message)diagnostics[#diagnostics+1]=message end
Isaac.GetTime=function()time=time+1;return time end
local function quad(origin,w,h,uv)
 local q={origin,origin+Vector(w,0),origin+Vector(0,h),origin+Vector(w,h),uv=uv}
 function q:SetTopLeft(v)self[1]=v end;function q:SetTopRight(v)self[2]=v end
 function q:SetBottomLeft(v)self[3]=v end;function q:SetBottomRight(v)self[4]=v end
 return q
end
-- Match native constructors; the live failure was missing model data, not these APIs.
local function corners(_,a,b,c,d)return {a,b,c,d}end
SourceQuad=setmetatable({NewFromRectangle=quad},{__call=corners})
DestinationQuad=setmetatable({NewFromRectangle=quad},{__call=corners})
Renderer={LoadImage=function()return {Render=function()submissions=submissions+1 end}end,
 CreateImage=function(w,h)assert(w==512 and h==512);return {Render=function()end}end,
 RenderToImage=function(_,fn)fn({Clear=function()cleared=cleared+1 end})end}
probe.toggle(true);assert(probe.draw(player,player.data.Samira,Vector.Zero))
assert(submissions>2000 and submissions<4500 and cleared==1,'single-sided mesh emits front faces only and clears its surface')
probe.draw(player,player.data.Samira,Vector.Zero);assert(cleared==1,'unchanged orientation reuses the surface')
Renderer.RenderToImage=function()error('test surface failure')end
player.data.Samira.aim=Vector(400,200);time=time+50
assert(not probe.draw(player,player.data.Samira,Vector.Zero) and not probe.enabled,'renderer errors restore animated fallback')
assert(diagnostics[#diagnostics]:find('[render to surface]',1,true) and diagnostics[#diagnostics]:find('test surface failure',1,true),'failed probe records its exact stage and original error')
print('Runtime: click movement, attack timing, Q combo, QE, collision, pause, room transition and input isolation passed')
print('HUD/mesh: first-render regression, input capture, health, layout, unsupported APIs, triangles, cache and fallback passed')
local branding=include('scripts.samira_branding')
local controls={path='gfx/backdrop/controls.anm2',frame=9,loads=0}
function controls:GetFilename()return self.path end;function controls:GetFrame()return self.frame end
function controls:Load(path)self.path=path;self.loads=self.loads+1 end
function controls:SetFrame(_,frame)self.frame=frame end
function controls:GetAnimation()return 'Controls' end
local originalColor=Color.Default;local buttons={path='gfx/backdrop/controls_buttons.anm2',frame=70,loads=0,Color=originalColor}
buttons.GetFilename=controls.GetFilename;buttons.GetFrame=controls.GetFrame;buttons.Load=controls.Load;buttons.SetFrame=controls.SetFrame
function buttons:GetAnimation()return 'Keyboard' end
local backdrop={GetControlsANM2=function()return controls end,GetControlsButtonsANM2=function()return buttons end}
function room:GetBackdrop()return backdrop end
callbacks[ModCallbacks.MC_PRE_RENDER]()
assert(controls.path=='gfx/samira/branding/controls_hidden.anm2' and controls.frame==9)
assert(buttons.path=='gfx/samira/branding/buttons_hidden.anm2' and buttons.frame==70)
callbacks[ModCallbacks.MC_POST_RENDER]();assert(buttons.path=='gfx/samira/branding/buttons_hidden.anm2','hidden button layers survive the entire render, including floor caching')
callbacks[ModCallbacks.MC_PRE_RENDER]();assert(controls.loads==1 and buttons.loads==1,'floor resources load once, not every render')
player.type=1;callbacks[ModCallbacks.MC_PRE_RENDER]()
assert(controls.path=='gfx/backdrop/controls.anm2' and buttons.path=='gfx/backdrop/controls_buttons.anm2','other characters retain both native tutorial layers')
player.type=10;callbacks[ModCallbacks.MC_PRE_RENDER]();callbacks[ModCallbacks.MC_PRE_GAME_EXIT]()
assert(controls.path=='gfx/backdrop/controls.anm2','exit restores shared backdrop resources')
do
 local oldSpawn,oldFind,oldVariant=Isaac.Spawn,Isaac.FindByType,Isaac.GetEntityVariantByName
 local current,spawns
 spawns=0
 function Isaac.GetEntityVariantByName(name)assert(name=='Samira Floor Tutorial');return 414026 end
 function Isaac.FindByType()return current and current:Exists() and {current} or {} end
 function Isaac.Spawn(kind,variant,subtype,pos)
  assert(kind==EntityType.ENTITY_EFFECT and variant==414026 and pos:Distance(room:GetCenterPos())==0)
  spawns=spawns+1;current={sprite=Sprite()}
  function current:Exists()return not self.removed end
  function current:Remove()self.removed=true end
  function current:GetSprite()return self.sprite end
  return current
 end
 level.roomIndex=0;floorNumber=1
 for _,theme in ipairs({'Basement','Cellar','Burning Basement'}) do
  branding.reset();branding.update(game,true)
  assert(current:Exists() and current.DepthOffset==-10000,theme..' spawns a floor tutorial without native backdrop eligibility')
  local count=spawns;branding.update(game,true);assert(spawns==count,'one decoration per starting room')
 end
 level.roomIndex=1;branding.update(game,true);assert(current.removed,'adjacent rooms do not show the tutorial')
 level.roomIndex=0;branding.update(game,true);assert(not current.removed,'returning to initial room restores tutorial')
 floorNumber=2;branding.update(game,true);assert(current.removed,'later floors do not repeat tutorial')
 floorNumber=1;branding.update(game,true);branding.update(game,false);assert(current.removed,'other characters remove tutorial')
 branding.reset();level.roomIndex=1
 Isaac.Spawn,Isaac.FindByType,Isaac.GetEntityVariantByName=oldSpawn,oldFind,oldVariant
end
print('Branding: hidden native text/buttons, all initial backdrop themes, one native decoration, room/floor/character isolation and cleanup passed')
local A=include('scripts.samira_abilities');local view=include('scripts.samira_view')
reset();mouse=Vector(300,100);e=mob(160,100);local rear=mob(200,100);entities={rear,e}
keys[Keyboard.KEY_W]=true;tick();keys[Keyboard.KEY_W]=false;tick(14)
assert(e.hits==1 and rear.hits==0 and e.slow[2]==.75,'W stops on the first enemy and slows it')
e.Position=Vector(180,100);tick(45)
assert(e.hits==2 and e.Velocity.X<0,'remaining in W zone causes one repeat hit and a pull')
tick(10);assert(e.hits==2 and player.data.Samira.wChain==nil,'W pull cannot repeat indefinitely')
reset();mouse=Vector(300,100);e=mob(160,100);entities={e};keys[Keyboard.KEY_W]=true;tick();keys[Keyboard.KEY_W]=false;tick(14)
e.Position=Vector(160,300);tick(50);assert(e.hits==1 and player.data.Samira.wChain==nil,'escaping W cancels the second hit')
reset();wall=true;mouse=Vector(300,100);e=mob(200,100);entities={e};keys[Keyboard.KEY_W]=true;tick();keys[Keyboard.KEY_W]=false;tick(40);assert(e.hits==1,'W missile crosses scenery and tethers the first enemy')
reset();e=mob(150,100);entities={e};keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
local rs=player.data.Samira;assert(A.ultimate(rs) and e.fear==45,'R starts transformation and fears nearby enemies')
local dmg,speed,heal=A.modifiers(rs);assert(dmg==1.2 and speed>1 and heal==1.4)
tick(100);local before=rs.rUntil;e.data.SamiraLastHit={owner=player,clock=rs.clock};callbacks[ModCallbacks.MC_POST_ENTITY_KILL](nil,e)
assert(rs.rUntil==before+30,'ordinary kill extends R by exactly one second')
A.onKill(e);assert(rs.rUntil==before+30,'duplicate kill cannot extend R twice')
local boss=mob(150,100);function boss:IsBoss()return true end
boss.data.SamiraLastHit={owner=player,clock=rs.clock};A.onKill(boss)
assert(rs.rUntil==rs.clock+300,'boss kill refreshes full ten seconds')
tick(310);assert(not A.ultimate(rs));assert(not A.castR(player,rs,entities),'R cooldown survives its buff ending')
view.prepare(true);view.finish();assert(Options.MouseControl==true and Options.FoundHUD==true,'temporary UI options restore')
assert(callbacks[ModCallbacks.MC_GET_SHADER_PARAMS]==nil,'room must not use the failed viewport shader or late-pass HUD')
reset();mouse=Vector(320,460);right=true;tick()
assert(player.data.Samira.goal and player.data.Samira.goal:Distance(mouse)<.001,'bottom-center input reaches native room without a viewport transform')
for _,wh in ipairs({{426,240},{480,270},{640,360},{960,540}})do
 local w,h=wh[1],wh[2];local l=hud.layout(w,h)
 assert(not hud.contains(Vector(w/2,h-12),w,h),'bottom door is not captured by corner HUD')
 assert(hud.contains(Vector(l.left.x+10,l.left.y+10),w,h))
 assert(hud.contains(Vector(l.right.x+10,l.right.y+10),w,h))
 assert(not hud.contains(Vector(w/2,h/2),w,h),'combat floor input stays free')
end
callbacks[ModCallbacks.MC_POST_RENDER]()
print('W/R mechanics preserved; native room input, corner HUD bounds, center door and render path passed')

local function makeDoor(pos)
 local d={Position=pos,TargetRoomIndex=42,open=true,locked=false,curse=false,keys=0}
 function d:IsOpen()return self.open end;function d:IsLocked()return self.locked end
 function d:IsRoomType(t)return self.curse and t==RoomType.ROOM_CURSE end
 function d:TryUnlock(_,force)
  assert(not force,'native key cost must be retained')
  if self.keys==0 then return false end
  self.keys=self.keys-1;self.locked=false;return true
 end
 return d
end
-- All eight slots enter through the native transition and preserve dimension/entry door.
for slot=0,7 do
 local normal=({Vector(-1,0),Vector(0,-1),Vector(1,0),Vector(0,1)})[slot%4+1]
 reset();local center=Vector(300,200);local doorPos=center+normal*80
 doors[slot]=makeDoor(doorPos)
 player.Position=doorPos-normal*25;mouse=doorPos+normal*12;right=true;tick()
 assert(#transitions==1 and transitions[1][1]==42 and transitions[1][2]==slot%4 and transitions[1][4]==player and transitions[1][5]==1 and level.LeaveDoor==slot,'clicking door enters correct neighbour and dimension')
 tick(10);assert(#transitions==1,'pending transition cannot repeat')
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(not player.data.Samira.departing,'new room releases movement')
end
reset();doors[2]=makeDoor(Vector(380,200));player.Position=Vector(300,240);mouse=Vector(395,210);right=true
entities={mob(390,200)};tick(60)
assert(#transitions==1 and not player.data.Samira.target,'off-axis door approach aligns and door click wins over nearby enemy')
reset();doors[2]=makeDoor(Vector(380,200));doors[2].open=false
player.Position=Vector(355,200);mouse=Vector(390,200);right=true;tick(20)
assert(#transitions==0,'closed combat door is never forced open')
reset();doors[2]=makeDoor(Vector(380,200));doors[2].open=false;doors[2].locked=true
player.Position=Vector(355,200);mouse=Vector(390,200);right=true;tick()
assert(#transitions==0 and doors[2].locked,'locked door without a key cannot be bypassed')
doors[2].keys=1;right=false;tick();right=true;tick();right=false
assert(doors[2].keys==0 and player.data.Samira.goal,'unlock waits for native opening animation')
tick(5);doors[2].open=true;tick();assert(#transitions==1,'unlocked door enters after opening without another click')
reset();doors[2]=makeDoor(Vector(380,200));doors[2].curse=true
player.Position=Vector(355,200);mouse=Vector(390,200);right=true;tick()
assert(#transitions==0 and player.data.Samira.exitIntent,'curse threshold retains native damage/entry handling')
assert(inp(nil,nil,InputHook.GET_ACTION_VALUE,ButtonAction.ACTION_RIGHT)==1,'nil entity input queries preserve native threshold movement')
keys[Keyboard.KEY_S]=true;right=false;tick();assert(not player.data.Samira.exitIntent,'stop cancels threshold movement')
reset();right=true;tick();assert(player.Velocity:Length()<=2.45*1.05*1.10+.000001,'base walking remains controlled after ten percent increase');assert(player.data.Samira.click)
right=false;tick(29);callbacks[ModCallbacks.MC_POST_ROOM_RENDER_ENTITIES]();assert(player.data.Samira.click==nil,'click arrows expire')
local G=include('scripts.samira_geometry')
local point=Vector(75,40);assert(G.unproject(G.project(point)):Distance(point)<.000001,'projected aim and hit coordinates agree')
print('Eight door slots, alignment, native unlock, closed/curse doors, repeat guard and nil-entity input passed')

local groundColors={};local groundQuads={}
Renderer.LoadImage=function()return {Render=function(_,source,destination,color)groundColors[#groundColors+1]=color;groundQuads[#groundQuads+1]=destination end}end
local visuals=include('scripts.samira_visuals')
visuals.indicator(Vector(100,100),Vector(1,0),G.shape(1),1,.8,false)
assert(groundColors[#groundColors][3]>groundColors[#groundColors][1],'preview tint must reach the actual KColor vertex parameter')
visuals.indicator(Vector(100,100),Vector(1,0),G.shape(1),1,.8,true)
assert(groundColors[#groundColors-1][1]>groundColors[#groundColors-1][3],'cast marker is orange, not white')
assert(groundColors[#groundColors][4]<1,'sweet spot retains translucent color')
print('Range colors: cyan preview, orange cast, and translucent sweet spot passed')

-- All headings travel the same unprojected distance, including the final fractional step.
for _,angle in ipairs({0,45,90,180,270}) do
 reset();player.Position=Vector(350,350);local origin=player.Position
 mouse=origin+G.project(Vector(250,0):Rotated(angle));keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false
 tick(11);local delta=G.unproject(player.Position-origin)
 assert(math.abs(delta:Length()-92.4)<.001,'E must stop at the extended 330-unit range')
 assert(player.data.Samira.dash==nil,'full E ends after twelve ticks')
 keys[Keyboard.KEY_S]=true;tick()
end
spriteDraws={}
visuals.abilities(player,{clock=0,wBolt={origin=Vector(100,100),position=Vector(180,100)}})
local chainPieces=0
for _,draw in ipairs(spriteDraws) do if draw.path:find('w_chain_beam',1,true) then chainPieces=chainPieces+1 end end
assert(chainPieces>=3,'flying W must show a chain, not only an orb')
spriteDraws={};e=mob(200,200)
visuals.abilities(player,{clock=0,wChain={target=e,anchor=Vector(200,200),face=Vector(1,0)}})
chainPieces=0
for _,draw in ipairs(spriteDraws) do if draw.path:find('w_chain_beam',1,true) then chainPieces=chainPieces+1 end end
assert(chainPieces>0,'W remains visible when the victim stands exactly on the ground anchor')
print('Q/E distance ratios, impact delay, directional dash endpoints and both W chain states passed')

for _,angle in ipairs({0,45,90,135,180,270}) do
 local shape=G.shape(1);visuals.indicator(Vector(200,200),Vector(1,0):Rotated(angle),shape,1,.8,false)
 local q=groundQuads[#groundQuads];local across=q[2]-q[1];local along=q[3]-q[1]
 local area=math.abs(across.X*along.Y-across.Y*along.X)
 assert(math.abs(area-2*shape.width*(shape.far-shape.near)*.98)<.001,'range has only two percent projection compression')
 assert(math.abs(G.unproject(across):Length()-2*shape.width)<.001,'range width stays consistent in every direction')
end
reset();local heldDraws=0
function player:GetHeldSprite()return {GetFilename=function()return 'collectible.png' end,Render=function()heldDraws=heldDraws+1 end}end
for _,animation in ipairs({'Hit','Pickup','UseItem'}) do
 nativeAnimation=animation;extraFinished=false
 local before=#spriteDraws;local result=callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(result==false and #spriteDraws>before,'engine special state must keep the Samira body: '..animation)
 assert(spriteDraws[before+1].path=='gfx/samira/fallback.anm2','native extra animation does not choose custom pose')
end
for _,animation in ipairs({'Appear','Jump'}) do
 nativeAnimation=animation;extraFinished=false
 local before=#spriteDraws;assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==false and #spriteDraws>before,'transitions retain the lightweight native actor beneath the game fade: '..animation)
end
for _,animation in ipairs({'TeleportUp'}) do
 nativeAnimation=animation;local before=#spriteDraws
 assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==false and #spriteDraws>before,'hidden external actor falls back within the native scene, beneath fades: '..animation)
end
for _,animation in ipairs({'Trapdoor','LightTravel','HoleIn','FallIn'}) do
 nativeAnimation=animation;local before=#spriteDraws
 assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==false and #spriteDraws>before,'floor descent returns to native layered actor: '..animation)
end
assert(heldDraws==0,'native item-holding presentation is suppressed')
dead=true;nativeAnimation='Death';extraFinished=false
assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==false)
assert(spriteDraws[#spriteDraws].path=='gfx/samira/fallback.anm2','death uses Samira source animation')
time=time+100;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
local deathAge=player.data.Samira.presentation.age;assert(deathAge>0)
paused=true;time=time+3000;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
assert(player.data.Samira.presentation.age==deathAge,'pause freezes custom death animation')
paused=false;dead=false;nativeAnimation='Idle';extraFinished=true
assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==false and player.data.Samira.presentation==nil,'revival restores ordinary rendering')
player.type=1;assert(callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)==nil,'other characters keep their native body')
print('Explicit quads, range area in six directions, hurt/pickup/death/transition presentation and revival passed')

-- Damage and cosmetic engine animations cannot pause, replace, or relocate a skill.
for _,animation in ipairs({'Hit','Pickup','UseItem','Happy','Sad'}) do
 reset();mouse=Vector(300,100);e=mob(245,100);entities={e}
 keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(12)
 local cast=player.data.Samira.cast;nativeAnimation=animation;extraFinished=false;player.ControlsEnabled=false
 player.Velocity=Vector(-12,7);player.SpriteOffset=Vector(15,-18)
 callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,1)
 tick(5)
 assert(cast.age==18 and e.hits==1,'Q lands on schedule through '..animation)
 assert(player.Position:Distance(Vector(100,100))==0,'incoming damage cannot displace a planted Q')
 local before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(spriteDraws[before+1].path=='gfx/samira/fallback.anm2','hurt/pickup keeps Q animation instead of idle')
 assert(spriteDraws[before+1].pos:Distance(player.Position)==0,'native hurt animation offset does not move the model')
 tick(12);assert(e.hits==1 and not player.data.Samira.cast,'Q does not repeat after cosmetic state')
end
reset();mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false
nativeAnimation='TeleportUp';extraFinished=false;player.ControlsEnabled=false;local age=player.data.Samira.cast.age;tick(8)
assert(player.data.Samira.cast.age==age,'real room/floor transitions still suspend combat')
reset();mouse=Vector(300,100);e=mob(200,100);entities={e};keys[Keyboard.KEY_W]=true;tick();keys[Keyboard.KEY_W]=false
nativeAnimation='Hit';extraFinished=false;player.ControlsEnabled=false;tick(16)
assert(e.hits==1 and player.data.Samira.wChain,'W launches and hits through hurt state')
reset();mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false
nativeAnimation='Hit';extraFinished=false;player.ControlsEnabled=false;callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,1);tick(11)
assert(math.abs(player.Position.X-192.4)<.001 and not player.data.Samira.dash,'damage does not interrupt or extend E')
reset();keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
nativeAnimation='Hit';extraFinished=false;player.ControlsEnabled=false;tick(23)
assert(not player.data.Samira.cast and A.ultimate(player.data.Samira),'R transformation completes through damage')
for stage=1,3 do
 reset();wall=true;mouse=Vector(300,100)
 e=mob(200,100);local second=mob(220,120);entities={e,second}
 tick();player.data.Samira.nextQ=stage;keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(17)
 assert(e.hits==1 and second.hits==1,'every enemy in Q'..stage..' is hit through scenery')
end
reset();player.Position=Vector(145,100);wall=true;e=mob(175,100);entities={e};mouse=e.Position;right=true;tick();right=false;tick(19)
assert(e.hits==1,'ordinary attack activates and hits across scenery')
local sound=callbacks[ModCallbacks.MC_PRE_SFX_PLAY]
assert(sound(nil,55)==false and sound(nil,217)==false and sound(nil,56)==false,'Samira suppresses only the original character voice')
for id=1,SoundEffect.NUM_SOUND_EFFECTS-1 do
 if id~=55 and id~=217 and id~=56 then assert(sound(nil,id)==nil,'environment, monster, pickup and UI sounds must pass through: '..id) end
end
assert(sound(nil,2000)==nil,'future custom LoL audio is not suppressed')
player.type=1;assert(sound(nil,55)==nil,'other characters retain original sounds')
print('Uninterrupted Q/W/E under damage, invisible native extras, wall-piercing AoE and isolated sound filter passed')

local function rock(kind,x,y)
 local grid={kind=kind,Position=Vector(x,y),CollisionClass=3,breaks=0}
 function grid:GetType()return self.kind end
 function grid:Destroy(immediate)assert(not immediate);self.breaks=self.breaks+1;self.CollisionClass=0;return true end
 return grid
end
reset();wall=true;grids[44]=rock(GridEntityType.GRID_ROCK,180,100)
mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false
assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_WALLS)
assert(callbacks[ModCallbacks.MC_PRE_PLAYER_GRID_COLLISION](nil,player,44,grids[44])==true,'E suppresses collision-based rock crushing')
tick(11)
assert(player.Position.X>=212 and player.Position.X<=240 and grids[44].breaks==0,'E extends only enough to clear one 40-unit rock without destroying it')
assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_GROUND and not player.data.Samira.dash,'E restores normal grid collision on landing')
assert(callbacks[ModCallbacks.MC_PRE_PLAYER_GRID_COLLISION](nil,player,44,grids[44])==nil)
reset();collisionOverride=function(i)return i%20>=4 and i%20<=10 and 3 or 0 end
mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(12)
assert(player.Position.X<=148,'too-thick terrain ends on the near side instead of trapping the player')
reset();collisionOverride=function(i)return i%20==4 and GridCollisionClass.COLLISION_PIT or 0 end
mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(11)
assert(player.Position.X>=212 and player.GridCollisionClass==5,'narrow pit can be crossed, but never used as the landing')
reset();player.Position=Vector(770,100);mouse=Vector(950,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(11)
assert(player.Position.X<788,'E cannot leave the room through its perimeter')
reset();collisionOverride=function(i)return i%20==4 and GridCollisionClass.COLLISION_WALL or 0 end
mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(11)
assert(player.Position.X<148,'actual walls/closed room boundaries cannot be crossed')
reset();wall=true;mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false;tick(6)
assert(player.Position.X>160 and player.Position.X<200)
dead=true;tick();assert(player.GridCollisionClass==5 and player.Position.X<148,'death mid-terrain restores collision and a safe position')
reset();mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();player.Position=Vector(400,400)
callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
assert(player.GridCollisionClass==5 and player.Position:Distance(Vector(400,400))==0,'room transition restores collision without moving back into the old room')
for stage=1,3 do
 reset();mouse=Vector(300,100)
 grids[1]=rock(GridEntityType.GRID_ROCK,180,100);grids[2]=rock(GridEntityType.GRID_ROCKT,180,140)
 grids[3]=rock(GridEntityType.GRID_ROCK_ALT,140,140);grids[4]=rock(GridEntityType.GRID_ROCK,350,100)
 grids[5]=rock(GridEntityType.GRID_DOOR,180,100);grids[6]=rock(GridEntityType.GRID_ROCKB,180,100)
 tick();player.data.Samira.nextQ=stage;keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(25)
 for i=1,3 do assert(grids[i].breaks==(stage==3 and 1 or 0),'only Q3 breaks each in-range ordinary/tinted/alternate rock once') end
 for i=4,6 do assert(grids[i].breaks==0,'Q3 does not break out-of-range rocks, doors or indestructible blocks') end
end
local function health(red,soul,max)
 local data={};return hud.healthNumbers({GetData=function()return data end,GetHearts=function()return red end,GetSoulHearts=function()return soul end,GetEffectiveMaxHearts=function()return max end})
end
local current,maximum=health(6,0,6);assert(current==650 and maximum==650)
current,maximum=health(6,0,8);assert(maximum==750,'a native HP-up adds 100 capacity')
current,maximum=health(24,0,24);assert(current==1550 and maximum==1550)
current,maximum=health(6,2,6);assert(current==650 and maximum==650,'soul hearts are separate shields')
print('Terrain-crossing E, collision restoration, safe landing, Q3 rock destruction and 650-based health display passed')

local progress=include('scripts.samira_progression')
reset();callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false);tick()
assert(progress.state(player).level==3 and progress.points(player)==3 and include('scripts.samira_equipment').state(player).gold==player:GetNumCoins(),'new runs start level 3 with native coins')
progress.restore(player,{level=1});player.addedContainers=0;Health.restore(player)
local kill=callbacks[ModCallbacks.MC_POST_ENTITY_KILL]
e=mob(200,100);kill(nil,e);assert(progress.state(player).xp==0,'unattributed deaths grant no XP')
for i=1,10 do
 e=mob(200,100);e.data.SamiraLastHit={owner=player,clock=player.data.Samira.clock}
 kill(nil,e);kill(nil,e)
end
assert(progress.state(player).level==2 and progress.state(player).xp==30,'ten normal kills level once; duplicate deaths grant nothing')
assert(player.addedContainers==0,'numeric growth never adds proxy heart containers')
local grown=progress.stats(player,{damage=6.3,interval=22})
assert(grown.damage>6.3 and grown.interval<22,'level actually increases damage and attack speed')
e=mob(200,100);e.data.SamiraLastHit={owner=player,clock=player.data.Samira.clock-91};kill(nil,e)
assert(progress.state(player).xp==30,'expired damage ownership grants no XP')
e=mob(200,100);function e:IsBoss()return true end
callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,e,1,0,{Entity=player});kill(nil,e)
assert(progress.state(player).xp==110,'native player damage receives boss XP attribution')
e=mob(200,100);e.data.SamiraLastHit={owner=player,clock=player.data.Samira.clock};kill(nil,e)
callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);local snapshot=persisted
player.data={};callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
assert(persisted==snapshot,'pre-start room callback must not erase the continuing run save')
callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
assert(progress.state(player).level==2 and progress.state(player).xp==141,'continue restores XP below threshold')
tick();progress.award(player,279)
assert(progress.state(player).level==3 and progress.state(player).xp==40 and player.addedContainers==0,'level 3 grows numeric health without adding native containers')
callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);player.data={};callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
assert(player.addedContainers==0 and progress.state(player).level==3,'loading never reapplies health growth')
tick();progress.award(player,999999)
assert(progress.state(player).level==18 and progress.state(player).xp==0,'large XP rewards stop at level 18')
local containers=player.addedContainers;progress.award(player,999999);assert(player.addedContainers==containers)
callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);startSeed=6789;player.data={}
callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
assert(progress.state(player).level==3,'different runs cannot inherit previous XP')
persisted='broken json';callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
assert(progress.state(player).level==3,'invalid saves safely initialize level 3')
progress.restore(player,{level=12,xp=123});callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false)
assert(progress.state(player).level==3 and progress.state(player).xp==0,'new runs reset progression')
print('Kill ownership, boss XP, duplicate prevention, level benefits, native HP cap, continue/new-run and corrupt-save regressions passed')
do
 reset();callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false);include('scripts.samira_external').toggle(false);mouse=Vector(300,100);tick()
 assert(progress.points(player)==3 and progress.rank(player,'q')==0 and not progress.canUpgrade(player,'r'))
 local s=player.data.Samira;local soundBefore=#playedSounds
 keys[Keyboard.KEY_Q]=true;keys[Keyboard.KEY_W]=true;keys[Keyboard.KEY_E]=true;keys[Keyboard.KEY_R]=true;tick()
 assert(not s.cast and not s.dash and not s.rUntil and s.qReady==0 and s.wReady==0 and s.eReady==0 and s.rReady==0 and #playedSounds==soundBefore,'unlearned skills cannot cast, consume cooldowns or play sound')
 keys={};tick();keys[Keyboard.KEY_LEFT_CONTROL]=true;keys[Keyboard.KEY_Q]=true;tick()
 assert(progress.rank(player,'q')==1 and progress.points(player)==2 and not s.cast,'Ctrl+Q spends one point without casting')
 tick(4);assert(progress.rank(player,'q')==1,'holding upgrade cannot repeat')
 keys={};tick();keys[Keyboard.KEY_Q]=true;tick();assert(s.cast and s.cast.stage==1,'learned Q casts on next press')
 callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);player.data={};callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
 assert(progress.rank(player,'q')==1 and progress.points(player)==2 and progress.state(player).level==3,'continue keeps spent ranks without creating points')
 progress.restore(player,{level=11,xp=123});assert(progress.points(player)==11 and progress.rank(player,'q')==0 and progress.state(player).xp==123,'old saves retain level/XP and receive all unspent points')
 for _,pair in ipairs({{1,0},{5,0},{6,1},{10,1},{11,2},{15,2},{16,3},{18,3}}) do
   progress.restore(player,{level=pair[1]})
   for i=1,pair[2] do assert(progress.upgrade(player,'r')) end
   assert(not progress.upgrade(player,'r'),'R respects 6/11/16 gates')
 end
 progress.restore(player,{level=2});assert(progress.upgrade(player,'q') and not progress.upgrade(player,'q'),'Q rank two waits for hero level three')
 progress.award(player,progress.required(2));assert(progress.points(player)==2 and progress.upgrade(player,'q'))
 progress.restore(player,{level=18})
 for _,key in ipairs({'q','w','e','r'}) do for i=1,(key=='r' and 3 or 5) do assert(progress.upgrade(player,key)) end end
 assert(progress.points(player)==0 and not progress.upgrade(player,'q'),'18 levels provide exactly 18 legal ranks')
 progress.restore(player,{level=2,skills={q=99,w=99,e=99,r=99}})
 assert(progress.points(player)==0 and progress.rank(player,'q')==1 and progress.rank(player,'r')==0,'corrupt ranks cannot exceed level, rank gate or available budget')
 reset();progress.restore(player);tick();s=player.data.Samira
 mouse=Vector(60,423);left=true;tick();assert(progress.rank(player,'q')==1 and not s.cast and not s.goal,'click plus upgrades without issuing a movement/cast command')
 left=false;tick();progress.restore(player,{level=3,skills={q=1}});s.qReady=s.clock+100;local deadline=s.qReady
 keys[Keyboard.KEY_LEFT_CONTROL]=true;keys[Keyboard.KEY_Q]=true;tick()
 assert(progress.rank(player,'q')==2 and progress.points(player)==1 and s.qReady==deadline,'learning cannot refresh an active cooldown')
 reset();progress.restore(player);tick();s=player.data.Samira
 e=mob(100,100);assert(progress.killXP(e,1)==31 and progress.killXP(e,2)==36 and progress.killXP(e,10)==73)
 e.champion=true;assert(progress.killXP(e,1)==38 and progress.killXP(e,2)==43)
 function e:IsBoss()return true end
 assert(progress.killXP(e,1)==80 and progress.killXP(e,2)==92,'boss category takes precedence over champion')
 floorNumber=2;e.data.SamiraLastHit={owner=player,clock=s.clock};kill(nil,e);kill(nil,e)
 assert(progress.state(player).xp==92,'current floor scales each attributed kill once')
 local saved=require('json').decode(persisted).players['0'];assert(saved.xp==92,'sub-level XP is persisted after the kill, not before')
 e=mob(100,100);e.champion=true;e.data.SamiraLastHit={owner=player,clock=s.clock};kill(nil,e)
 assert(progress.state(player).xp==135,'champion uses cannon XP through the real kill callback')
 e=mob(100,100);e.data.SamiraLastHit={owner=player,clock=s.clock};kill(nil,e)
 assert(progress.state(player).level==1 and progress.state(player).xp==171 and progress.points(player)==1)
 for _,key in ipairs({'q','w','e','r'}) do
   progress.restore(player,{level=18,skills={[key]=1}});local low=progress.cooldown(player,key)
   progress.restore(player,{level=18,skills={[key]=key=='r' and 3 or 5}})
   assert(progress.cooldown(player,key)<low,'rank reduces actual base cooldown for '..key)
 end
 local function qDamage(rank)
   reset();progress.restore(player,{level=9,skills={q=rank}});e=mob(260,100);entities={e};mouse=e.Position
   keys[Keyboard.KEY_Q]=true;tick();keys={};tick(17);return e.total
 end
 local low=qDamage(1);local high=qDamage(5);assert(math.abs(high/low-1.6)<.0001,'Q rank changes accepted damage, not just the UI')
 for _,rank in ipairs({1,5}) do
   reset();progress.restore(player,{level=9,skills={e=rank,w=rank==5 and 4 or 1}});mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();s=player.data.Samira
   assert(s.eReady-s.clock==include('scripts.samira_equipment').cooldown(player,rank==1 and 240 or 120,false),'E uses its learned rank cooldown')
   keys={};tick(12);keys[Keyboard.KEY_W]=true;tick();assert(s.wReady-s.clock==include('scripts.samira_equipment').cooldown(player,progress.cooldown(player,'w'),false))
 end
 reset();progress.restore(player,{level=16,skills={r=3}});keys[Keyboard.KEY_R]=true;tick();s=player.data.Samira
 assert(s.rReady-s.clock==include('scripts.samira_equipment').cooldown(player,1800,true) and select(1,A.modifiers(s))==1.4,'R rank three updates cooldown and transformation strength')
 print('Rank gates/budget, unlearned input, Ctrl/click upgrades, migration, saved ranks, floor-scaled XP and live rank damage/cooldowns passed')
end

reset();mouse=Vector(300,100);e=mob(260,100);entities={e};keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false
tick(16);assert(not player.data.Samira.hitFX,'no target hit effects before contact')
callbacks[ModCallbacks.MC_POST_ROOM_RENDER_ENTITIES]()
tick();assert(#player.data.Samira.hitFX==1 and player.data.Samira.hitFX[1].strong,'sweetspot produces independent strong impact')
callbacks[ModCallbacks.MC_POST_ROOM_RENDER_ENTITIES]()
tick(91);assert(#player.data.Samira.hitFX==0 and #player.data.Samira.fx==0,'source particle lifetimes expire in simulation time')
reset();mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(17)
assert(not player.data.Samira.hitFX and #player.data.Samira.fx==1,'missed Q has ground impact but no fabricated target feedback')
local visual=include('scripts.samira_visuals')
for i=1,100 do visual.hit(player.data.Samira,Vector(200,100),true) end
assert(#player.data.Samira.hitFX==16,'crowded-room hit particles are bounded')
for stage=1,3 do visual.impact({age=2,stage=stage,origin=Vector(100,100),face=Vector(1,0)},include('scripts.samira_geometry').shape(stage,1)) end
reset();keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false;tick(3)
spriteDraws={};visual.screen(player.data.Samira);assert(#spriteDraws==64,'R draws a bounded edge vignette')
visual.abilities(player,player.data.Samira);hud.overhead(player,player.data.Samira,progress.state(player))
tick(300);spriteDraws={};visual.screen(player.data.Samira);assert(#spriteDraws==0,'red screen edges end with R')
print('Cast/contact separation, AoE feedback cap, Q1/Q2/Q3 rendering, overhead level bar and R overlay lifecycle passed')
reset();mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys[Keyboard.KEY_E]=false
for i=1,5 do
 callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero);tick()
end
assert(player.data.Samira.dashGhosts==nil,'lightweight emergency actor does not allocate full animation echoes')
tick(20);callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
assert(player.data.Samira.dashGhosts==nil,'fallback leaves no E afterimages')
reset()
for _,key in ipairs({Keyboard.KEY_Q,Keyboard.KEY_W,Keyboard.KEY_E,Keyboard.KEY_R}) do
 keys={[key]=true}
 for _,action in ipairs({ButtonAction.ACTION_PAUSE,ButtonAction.ACTION_MENUBACK}) do
  for _,hook in ipairs({InputHook.IS_ACTION_PRESSED,InputHook.IS_ACTION_TRIGGERED,InputHook.GET_ACTION_VALUE}) do
   assert(inp(nil,player,hook,action)==(hook==InputHook.GET_ACTION_VALUE and 0 or false),'skill key must not leak into a pause/back action')
   assert(inp(nil,nil,hook,action)==(hook==InputHook.GET_ACTION_VALUE and 0 or false),'global pause input has no entity')
  end
  for _,explicit in ipairs({Keyboard.KEY_ESCAPE,Keyboard.KEY_P}) do
   keys[explicit]=true;assert(inp(nil,player,InputHook.IS_ACTION_TRIGGERED,action)==nil,'deliberate pause remains possible during a skill');keys[explicit]=nil
  end
  paused=true;assert(inp(nil,nil,InputHook.IS_ACTION_TRIGGERED,action)==nil,'paused menu controls stay native');paused=false
 end
end
keys={};assert(inp(nil,nil,InputHook.IS_ACTION_TRIGGERED,ButtonAction.ACTION_PAUSE)==nil,'normal pause/gamepad remains native without skill keys')
keys[Keyboard.KEY_Q]=true;player.type=1;assert(inp(nil,player,InputHook.IS_ACTION_TRIGGERED,ButtonAction.ACTION_PAUSE)==nil,'other characters keep their menu mappings')
reset();include('scripts.samira_external').toggle(false);paused=true;local logStart=#diagnostics
callbacks[ModCallbacks.MC_POST_RENDER]();callbacks[ModCallbacks.MC_POST_RENDER]()
assert(#diagnostics==logStart+1 and diagnostics[#diagnostics]:find('[Samira pause]',1,true),'one diagnostic per observed pause, not every render frame')
paused=false;callbacks[ModCallbacks.MC_POST_RENDER]();paused=true;callbacks[ModCallbacks.MC_POST_RENDER]()
assert(#diagnostics==logStart+2,'a later pause is recorded separately')
print('Skill/menu isolation, explicit Escape/P, native paused controls, other characters and bounded pause diagnostics passed')
local external=include('scripts.samira_external');local codec=require('json')
reset();external.toggle(false);local countBefore=#diagnostics;external.emit(player,{clock=0},false)
assert(#diagnostics==countBefore,'explicit off stops telemetry')
callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false)
assert(external.enabled and not external.replaces(false),'new Samira run automatically waits without hiding the original body')
local ackMode='ready';local ackCapabilities
Isaac.LoadModDataFromFolder=function(folder)
 assert(folder=='samira_external_link','heartbeat never accesses gameplay save data')
 if ackMode=='missing' then return nil end
 if ackMode=='broken' then return 'broken json' end
 return codec.encode({version=1,session=ackMode=='wrong' and 'old-session' or external.session,
     time=ackMode=='stale' and time-1500 or time,ready=ackMode~='stopped',visible=true,hudVisible=true,room=external.room,capabilities=ackCapabilities})
end
tick();external.toggle(true);external.emit(player,player.data.Samira,false)
local packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.active and packet.version==1 and packet.kind=='SheathedIdle' and packet.position[1]==player.Position.X)
assert(packet.hud.skillPoints==3 and packet.hud.skills.q.rank==0 and packet.hud.skills.q.canUpgrade and not packet.hud.skills.r.canUpgrade,'new-run HUD exports unlearned skills and legal upgrades')
assert(progress.upgrade(player,'q'))
countBefore=#diagnostics;external.emit(player,player.data.Samira,false);assert(#diagnostics==countBefore,'telemetry rate limit is independent of render FPS')
mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();time=time+70
external.emit(player,player.data.Samira,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.cast.stage==1 and packet.shape.kind=='box','external Q receives the actual native shape and timeline')
time=time+120001;external.emit(player,player.data.Samira,false)
assert(external.enabled and external.replaces(false),'connected renderer does not expire after two minutes')
for _,mode in ipairs({'missing','broken','wrong','stale','stopped'}) do
 ackMode='ready';time=time+220;external.poll();ackMode=mode;time=time+220;external.poll()
 if mode=='missing' or mode=='broken' then
   assert(external.replaces(false),'one temporary read/parse failure retains the verified lease: '..mode)
   time=time+1100;external.poll()
 end
 assert(not external.replaces(false),'expired or explicitly rejected acknowledgement restores body: '..mode)
end
ackMode='ready';time=time+220;external.poll();assert(external.replaces(false),'renderer reconnect automatically restores external mode')
print('Automatic connection, missing/crashed/stale/wrong-session fallback, reconnection and unlimited session passed')
local mode=1;RoomTransition={GetTransitionMode=function()return mode end}
external.emit(player,player.data.Samira,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.transition and external.replaces(false),'room transition hides external window without restoring the sprite')
assert(external.replaces(true) and not external.visuals(true),'pause retains actor ownership')
local oldRoom=packet.room
callbacks[ModCallbacks.MC_POST_NEW_ROOM]();external.emit(player,player.data.Samira,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.room==oldRoom+1 and packet.transition,'new room has a new interpolation epoch even while transition continues')
mode=0;time=time+450;external.emit(player,player.data.Samira,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(not packet.transition,'transition end bypasses telemetry throttle')
player.data.Samira.departing=time+1500;external.emit(player,player.data.Samira,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.transition,'door departure hides the model before the engine transition begins')
player.data.Samira.departing=nil;RoomTransition=nil
print('Door departure, room epoch, native transition visibility and immediate reveal telemetry passed')
assert(not external.visuals(false) and not external.hud(false),'older renderer must retain native effects and HUD')
ackCapabilities={combat=1,hud=1};time=time+220;external.poll()
assert(external.visuals(false) and external.hud(false),'complete renderer explicitly takes over effects and HUD')
assert(not external.visuals(true) and external.hud(true),'pause retains external HUD')
local exportState=player.data.Samira;local exportTarget=mob(150,120)
exportState.wBolt={origin=Vector(100,100),position=Vector(130,100),face=Vector(1,0)}
exportState.wChain={target=exportTarget,anchor=Vector(150,120),face=Vector(1,0),expires=exportState.clock+45}
exportState.hitFX={{position=Vector(150,120),at=exportState.clock,strong=true}}
time=time+40;external.emit(player,exportState,false,{position={400,200},enemy=true})
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.hud.hp==select(1,hud.healthNumbers(player)) and packet.hud.level==progress.state(player).level,'HUD exports real native HP and saved level')
assert(packet.chain.shape.width==G.wShape().width and packet.chain.target[1]==150 and packet.bolt.position[1]==130,'W escape geometry and target sync')
assert(packet.hits[1].strong and packet.cursor.enemy and packet.ground[2]==.98,'accepted-hit events and ground projection exported')
ackMode='stopped';time=time+220;external.poll();assert(not external.visuals(false) and not external.hud(false),'crashed renderer restores both presentation layers')
ackMode='ready';ackCapabilities=nil;time=time+220;external.poll()
print('Versioned effects/HUD takeover, fallback, real HP, W boundaries and accepted-hit telemetry passed')
-- External actor owns only presentation; emotes never consume skills or grant ultimate stats.
reset();tick();external.toggle(true);external.poll()
assert(external.replaces(false) and external.replaces(true),'pause cannot restore the old actor')
local beforeDraw=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
assert(#spriteDraws==beforeDraw,'external actor must not also draw the baked body')
keys[Keyboard.KEY_LEFT_CONTROL]=true;keys[Keyboard.KEY_3]=true;tick();keys[Keyboard.KEY_3]=false
local emotes=include('scripts.samira_emotes');local es=player.data.Samira
assert(es.emote.intro=='Dance_Windup' and player.Velocity:Length()==0)
tick(102);local name,phase,loop=emotes.frame(es)
assert(name=='Dance_Loop' and loop and phase<.1,'dance intro enters the original loop once')
keys[Keyboard.KEY_5]=true;tick();assert(es.bannerVisible==false and not es.rUntil,'Ctrl+5 hides default banners without granting R')
tick(3);assert(es.bannerVisible==false,'held Ctrl+5 toggles only once')
keys[Keyboard.KEY_5]=false;tick();keys[Keyboard.KEY_5]=true;tick();assert(es.bannerVisible==true)
keys={};keys[Keyboard.KEY_Q]=true;tick();assert(es.emote==nil and es.cast.stage==1,'Q cancels emote and starts immediately')
keys={};tick(30);assert(emotes.start(es,'Laugh'));right=true;tick();assert(not es.emote,'right click cancels emote')
right=false;assert(emotes.start(es,'Joke'));callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,1,0,nil);assert(not es.emote,'damage cancels cosmetic emote')
assert(emotes.start(es,'Respawn'));callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(not es.emote)
assert(not emotes.start(es,'missing_clip'))
external.toggle(true,true);assert(not external.replaces(false),'preview preserves original body')
external.toggle(true);dead=true;time=time+70;external.emit(player,es,false)
packet=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
assert(packet.active and packet.kind=='Death' and not packet.looping,'external renderer plays death instead of disappearing')
dead=false;external.toggle(false);assert(not external.replaces(false),'off restores body immediately')
print('External takeover/preview/pause restore, dance transition, wing edge toggle, combat cancellation and death passed')
-- A whole AoE impact produces one audio event, not one loud copy per target.
reset();playedSounds={};entities={mob(170,100),mob(260,100)};mouse=Vector(300,100)
keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(17)
assert(#playedSounds==3 and playedSounds[1]==soundId('Samira q1_cast') and playedSounds[3]==soundId('Samira q_sweet'),'Q cast and strongest accepted AoE hit each play once')
tick(20);assert(#playedSounds==3,'render/update frames cannot replay original SFX')
reset();playedSounds={};mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(17)
assert(playedSounds[3]==soundId('Samira q1_miss'),'empty swing uses its ground impact sound')
reset();playedSounds={};e=mob(260,100);function e:TakeDamage()return false end;entities={e};mouse=e.Position
keys[Keyboard.KEY_Q]=true;tick();keys[Keyboard.KEY_Q]=false;tick(17)
assert(playedSounds[3]==soundId('Samira q1_miss'),'rejected damage cannot claim sweetspot hit audio')
print('Original sound events: cast/contact timing, one cue per AoE, miss/rejected-hit and no repeated playback passed')

-- Voice ownership, cooldowns, interrupted emotes and death are lifecycle events.
local audio=include('scripts.samira_audio')
local function soundCount(name)
 local names={[soundId('Samira '..name)]=true}
 if name=='vo_attack' or name=='vo_en_attack' then
  for i=1,21 do names[soundId(string.format('Samira '..name..'_%02d',i))]=true end
 end
 local n=0;for _,id in ipairs(playedSounds) do if names[id] then n=n+1 end end;return n
end
do
 for _,language in ipairs({'zh','en'}) do
  reset();tick();Options.Language=language;local s=player.data.Samira
  local prefix=language=='zh' and 'vo_' or 'vo_en_';local previous
  for cycle=1,3 do
   local seen={}
   for i=1,21 do
    audio.voiceStop(true);s.clock=s.voiceReady or s.clock
    assert(audio.voice(s,'attack',0,12))
    local pool=s.attackVoiceBags[language];local selected=pool.last
    assert(not seen[selected] and selected~=previous,'attack lines must not repeat within a bag or across its boundary')
    assert(s.lastAttackVoice==string.format(prefix..'attack_%02d',selected))
    assert(activeSounds[soundId('Samira '..s.lastAttackVoice)],'play the selected single-sample ID')
    seen[selected]=true;previous=selected
    local remaining=#pool.bag
    assert(not audio.voice(s,'attack',0,12) and #pool.bag==remaining,'blocked speech must not consume a candidate')
   end
  end
  audio.voiceStop(true);local remaining=#s.attackVoiceBags[language].bag
  s.clock=s.voiceReady-1
  assert(not audio.voice(s,'attack',0,12) and #s.attackVoiceBags[language].bag==remaining,'cooldown does not consume a candidate')
 end
 reset();tick();Options.Language='zh';local s=player.data.Samira
 audio.voice(s,'attack',0,12);local zh=s.attackVoiceBags.zh
 audio.voiceStop(true);s.clock=s.voiceReady;Options.Language='en';audio.voice(s,'attack',0,12)
 assert(#zh.bag==20 and #s.attackVoiceBags.en.bag==20,'languages retain separate bags')
 audio.voiceStop(true);s.clock=s.voiceReady;Options.Language='zh';audio.voice(s,'attack',0,12)
 assert(s.attackVoiceBags.zh==zh and #zh.bag==19,'switching languages resumes the previous bag')
 -- Force the refill collision to verify the explicit boundary guard.
 audio.voiceStop(true);s.clock=s.voiceReady;zh.bag={};zh.last=21
 local random=math.random;math.random=function(n)return n end
 audio.voice(s,'attack',0,12);math.random=random
 assert(zh.last~=21 and #zh.bag==20,'refill cannot immediately repeat the last line')
 reset();Options.Language='zh'
 print('Attack dialogue: three unique 21-line cycles per language, explicit sound IDs, cooldown/priority rejection, language isolation and forced refill collision passed')
end
reset();playedSounds={};e=mob(140,100);entities={e};mouse=e.Position;right=true;tick();right=false;tick(19)
assert(soundCount('passive_hit')==1 and soundCount('attack_hit')==0,'empowered first swing has one original passive impact cue')
reset();playedSounds={};local s=player.data.Samira;tick();s=player.data.Samira
s.emote={intro='Dance_Windup',loop='Dance_Loop',at=s.clock};audio.emote(s)
assert(soundCount('dance_intro')==1)
s.clock=s.clock+101;audio.emote(s);audio.emote(s)
assert(soundCount('dance_loop')==1 and activeSounds[soundId('Samira dance_loop')],'dance loop begins once')
s.emote=nil;audio.emote(s);assert(not activeSounds[soundId('Samira dance_loop')],'cancelled dance stops its loop')
s.emote={intro='Joke',at=s.clock};audio.emote(s)
assert(soundCount('vo_joke')==1)
callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player)
assert(not activeSounds[soundId('Samira vo_joke')],'damage cancels emote voice without muting the room')
reset();playedSounds={};tick();s=player.data.Samira
for i=1,10 do audio.voice(s,'move',0,12) end
assert(soundCount('vo_move')==1,'repeated clicks do not stack voice lines')
activeSounds[soundId('Samira vo_move')]=nil;audio.voice(s,'move',0,12)
assert(soundCount('vo_move')==1,'ambient cooldown survives the end of a sample')
audio.cast(s,'r');assert(soundCount(string.format('vo_r_%02d',s.lastRVoice))==1,'ultimate voice can interrupt ambient cooldown')
local before=#playedSounds;paused=true;tick(10);assert(#playedSounds==before,'paused updates emit nothing');paused=false
dead=true;tick(10);assert(soundCount('death')==1 and soundCount('vo_death')==0,'death sound plays once while ultimate speech retains priority')
assert(not activeSounds[soundId('Samira r_cast')],'death stops the long ultimate effect')
dead=false;tick();dead=true;tick();assert(soundCount('death')==2,'a revived player can die again')
activeSounds[999]=true;callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
assert(activeSounds[999] and not activeSounds[soundId('Samira vo_death')],'cleanup leaves unrelated game sounds alone')
reset();playedSounds={};player.type=1;dead=true;tick();assert(#playedSounds==0,'other characters never acquire Samira voice')
print('Expanded audio: ordinary impact, dance loop/cancel, voice throttling/priority, pause, death/revive and room cleanup passed')
do
 reset();tick();local s=player.data.Samira;local target=mob(150,100);target.FrameCount=100
 assert(A.castR(player,s,{target}));target.FrameCount=144;A.updateFear(target);assert(target.fear==45)
 target.FrameCount=145;A.updateFear(target)
 assert(target.fear==0 and target.clearedFlag==EntityFlag.FLAG_FEAR and not target.data.SamiraRFear,'R fear force-expires independently of the player ultimate')
 target.data.SamiraRFear={expires=145};target.fear=90;A.updateFear(target)
 assert(target.fear==90,'later longer fear from another source is preserved')
 target=mob(150,100);function target:HasEntityFlags(flag)return flag==EntityFlag.FLAG_FEAR end
 s.cast=nil;s.rReady=0;assert(A.castR(player,s,{target}));assert(not target.data.SamiraRFear,'pre-existing fear is not claimed')
 playedSounds={};local pr=progress.state(player);pr.xp=progress.required(pr.level)-1
 local originalInclude=include;include=function()error('runtime module reload is forbidden during level award')end
 local gained=progress.award(player,2);include=originalInclude
 assert(gained==1 and s.levelSoundPending and s.levelUpAt==s.clock,'level gain queues sound without reloading modules')
 audio.observe(player,s);audio.observe(player,s);assert(soundCount('ui_level')==1 and not s.levelSoundPending,'loaded audio system consumes the upgrade sound once')
 progress.award(player,1);assert(soundCount('ui_level')==1,'ordinary XP does not replay the upgrade sound')
 external.toggle(true);time=time+250;external.poll()
 local oldMenu=game.IsPauseMenuOpen;game.IsPauseMenuOpen=function()return true end;paused=true
 local before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws==before+1 and external.occluded(player,s),'pause menu draws only native layered body')
 external.emit(player,s,true)
 local wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.occluded and wire.hudVisible,'pause hides external actor while preserving the corner HUD')
 game.IsPauseMenuOpen=function()return false end
 assert(not external.occluded(player,s),'non-menu pauses such as rainbow poop keep external actor')
 paused=false;nativeAnimation='Trapdoor';before=#spriteDraws
 callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws==before+1 and not external.hudAllowed(s,false,player),'trapdoor immediately uses native body and hides external HUD')
 nativeAnimation='Idle';game.IsPauseMenuOpen=oldMenu;external.toggle(false)
 print('Fear expiry/ownership, actual level-up feedback, pause-menu versus rainbow pause and trapdoor native fallback passed')
end
do
 reset();tick();local s=player.data.Samira;playedSounds={}
 local savedInclude=include
 include=function()error('movement audio must use initialized dependencies, not runtime include')end
 audio.command(player,s,false,player.Position+Vector(50,0))
 assert(soundCount('vo_r_ready')==1,'learned and ready R has its own movement lines')
 entities={mob(500,100)};audio.observe(player,s)
 assert(not activeSounds[soundId('Samira vo_r_ready')] and soundCount('vo_attack')==1,'uncleared room replaces peaceful movement voice')
 audio.voiceStop(true);s.voiceReady=0;audio.command(player,s,false,player.Position+Vector(200,0))
 assert(soundCount('vo_attack')==2,'clicking empty ground during battle still uses combat voice')
 entities={};audio.voiceStop(true);s.voiceReady=0;s.rReady=s.clock+100
 audio.command(player,s,false,player.Position+Vector(200,0));assert(soundCount('vo_move_long')==1)
 audio.voiceStop(true);s.voiceReady=0;audio.command(player,s,false,player.Position+Vector(50,0));assert(soundCount('vo_move')==1)
 progress.restore(player,{level=3,skills={q=1,e=1,w=1}})
 audio.voiceStop(true);s.voiceReady=0;s.rReady=0
 audio.command(player,s,false,player.Position+Vector(50,0));assert(soundCount('vo_move')==2,'unlearned R still permits ordinary movement speech')
 include=savedInclude
 audio.cast(s,'r');local rKey=string.format('vo_r_%02d',s.lastRVoice)
 audio.cast(s,'q1');assert(activeSounds[soundId('Samira '..rKey)],'Q cannot interrupt the ultimate speech')
 audio.voice(s,'death',5);audio.voice(s,'taunt',4);audio.voiceStop()
 assert(activeSounds[soundId('Samira '..rKey)],'death, taunt and ordinary voice cancellation cannot interrupt R')
 s.emote={intro='Dance_Windup',at=s.clock};audio.emote(s)
 assert(activeSounds[soundId('Samira '..rKey)],'dance cannot stop R speech')
 dead=true;audio.observe(player,s)
 assert(activeSounds[soundId('Samira '..rKey)],'death cleanup preserves ultimate speech')
 dead=false;s.emote=nil;audio.stopEmote()
 assert(math.abs(G.stats(3.5,10,260,0,1).speed-2.45*1.05*1.10)<.000001,'base move speed increases another ten percent')

 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(activeSounds[soundId('Samira '..rKey)],'ordinary room change retains ultimate speech')
 audio.voiceStop(true);local seen={}
 s.rVoiceBag=nil
 for i=1,8 do audio.cast(s,'r');assert(not seen[s.lastRVoice],'R variants do not repeat within the playlist');seen[s.lastRVoice]=true;audio.voiceStop(true) end
 local last=s.lastRVoice;audio.cast(s,'r');assert(s.lastRVoice~=last,'adjacent R playlists do not repeat at the boundary');audio.cleanup();assert(not audio.playing(string.format('vo_r_%02d',s.lastRVoice)))
 callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,1,0,nil)
 assert(s.hurtUntil==s.clock+9,'accepted hit remains visibly red for 0.3 seconds')
 external.toggle(true);time=time+250;external.emit(player,s,false)
 local wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'));assert(wire.hurt)
 tick(9);time=time+250;external.emit(player,s,false)
 wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'));assert(not wire.hurt,'red tint expires')
 external.toggle(false)
 print('Uncleared-room voice, ready/long movement, all 8 R variants, speech priority/room continuity and hurt telemetry passed')
end

-- Weapon presentation never owns movement; the passive owns one accepted contact.
do
 local P=include('scripts.samira_passive')
 reset();tick();local s=player.data.Samira;s.weapon=true;s.combatUntil=0;s.goal=Vector(500,100)
 tick();assert(s.weaponMotion.kind=='Sheathe' and not s.cast and player.Velocity:Length()>0)
 ackMode='ready';external.toggle(true);time=time+250;external.emit(player,s,false)
 local wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.kind=='Sheathe' and wire.locomotion.kind=='Walk' and not wire.looping and wire.hud.passive.ready,'renderer receives a separate walk cycle and passive state')
 callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player)
 for i=1,29 do tick();assert(player.Velocity:Length()>0,'sheathing must keep walking through its entire duration') end
 assert(not s.weaponMotion)
 reset();e=mob(500,100);entities={e};mouse=e.Position;right=true;tick();right=false;s=player.data.Samira
 assert(s.weaponMotion.kind=='Draw' and not s.cast and player.Velocity:Length()>0,'drawing while approaching cannot lock movement')
 keys[Keyboard.KEY_Q]=true;tick();assert(s.cast.stage==1 and not s.weaponMotion,'a skill replaces drawing immediately')
 reset();e=mob(140,100);local other=mob(145,105);entities={other,e};mouse=e.Position;right=true;tick();right=false
 time=time+250;external.emit(player,player.data.Samira,false);wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.clip=='Passive_Attack' and not wire.looping,'empowered swing uses the source passive attack clip')
 tick(6)
 assert(e.hits==1 and other.hits==0,'one passive belongs to the selected target, not every enemy in the swing')
 assert(P.remaining(player)==P.total(player) and Health.current(player)>Health.max(player)*.75)
 time=time+250;external.emit(player,player.data.Samira,false);wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.hud.passive.remaining==P.remaining(player) and not wire.hud.passive.ready,'HUD receives the authoritative cooldown')
 local remaining=P.remaining(player);paused=true;tick(10);paused=false;assert(P.remaining(player)==remaining,'pause freezes passive cooldown')
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(P.remaining(player)==remaining,'rooms do not reset passive')
 reset();e=mob(140,100);function e:TakeDamage()return false end;entities={e};mouse=e.Position;right=true;tick();right=false;tick(6)
 assert(P.ready(player) and progress.state(player).passiveHeal==0,'rejected hit cannot consume or heal')
 reset();progress.state(player).passiveRemaining=400;e=mob(140,100);entities={e};mouse=e.Position;right=true;tick();right=false;e.Position=Vector(500,100);tick(6)
 assert(e.hits==1,'locked ordinary basic attack follows its valid target through the windup')
 reset();e=mob(140,100);entities={e};mouse=e.Position;right=true;tick();right=false;e.Position=Vector(500,100);tick(6)
 assert(not P.ready(player) and e.hits==1,'locked right-click passive follows its victim beyond the original rectangle')
 reset();tick();s=player.data.Samira;e=mob(140,100);local champion=mob(145,105);champion.champion=true;entities={e,champion}
 progress.state(player).passiveRemaining=400;s.cast={kind='Attack',target=champion,face=Vector(1,0),age=6,impact=7,duration=13};tick()
 assert(P.remaining(player)==339,'ordinary attack against a champion refunds two seconds once')
 reset();tick();s=player.data.Samira;e=mob(250,100);e.champion=true;other=mob(252,100);other.champion=true;entities={e,other}
 progress.state(player).passiveRemaining=400;s.cast={kind='Q1',stage=1,face=Vector(1,0),age=17,impact=18,duration=24};tick()
 assert(e.hits==1 and P.remaining(player)==279,'Q sweetspot refunds four seconds once for the entire AoE')
 reset();progress.restore(player,{level=1});e=mob(140,100)
 assert(P.total(player)==660 and math.abs(P.bonus(player,e)-10.5)<.001)
 Health.state(player).hp=200;P.consume(player,e,10.5,1);local minionHeal=Health.current(player)-200
 progress.restore(player,{level=1});e.champion=true;Health.state(player).hp=200;P.consume(player,e,10.5,1)
 assert(math.abs(Health.current(player)-200-minionHeal)<.001,'all Isaac enemies use the minion healing fraction')
 progress.restore(player,{level=18});assert(P.total(player)==300 and math.abs(P.bonus(player,e)-33.6)<.001)
 Health.state(player).hp=200;P.consume(player,e,33.6,1);assert(math.abs(Health.current(player)-440)<.001,'passive heals exactly 240 HP without half-heart rounding')
 reset();callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false);progress.restore(player,{level=6,passiveRemaining=321})
 Health.state(player).hp=123.456
 callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);player.data={};callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
 assert(P.remaining(player)==321 and math.abs(Health.current(player)-123.456)<.001,'continue retains cooldown and fractional HP')
 progress.restore(player,{level=1});assert(P.ready(player),'old saves default to ready')
 progress.restore(player,{passiveRemaining=-3,passiveHeal=0/0});assert(P.ready(player) and progress.state(player).passiveHeal==0)
 reset()
 print('Moving draw/sheath, immediate skill takeover, single-target passive, miss/rejection, refund, healing, pause/room and continue regressions passed')
end

-- Native-currency, bounded catalog and shared inventory regressions.
do
 reset();local T=include('scripts.samira_terrain');local G=include('scripts.samira_geometry')
 for stage=1,3 do
  local poop={Position=Vector(140,100),CollisionClass=1,damage=0,GetType=function()return GridEntityType.GRID_POOP end,Hurt=function(self,n)self.damage=self.damage+n end}
  local outside={Position=Vector(20,100),CollisionClass=1,damage=0,GetType=poop.GetType,Hurt=poop.Hurt}
  local f=mob(150,100);f.Type=EntityType.ENTITY_FIREPLACE
  local room={GetGridSize=function()return 2 end,GetGridEntity=function(_,i)return i==0 and poop or outside end}
  T.qHit(room,player,Vector(1,0),G.shape(stage),stage,{f})
  assert(poop.damage==(stage==3 and 3 or 2) and outside.damage==0)
  assert(f.total==player.Damage*(stage==3 and 3 or 2),'Q fire damage equals the requested number of native tear hits')
 end
 print('Q1/Q2/Q3 poop and fire hits respect shared range and 2/2/3 tear equivalents')
end
do
 local E=include('scripts.samira_equipment');local F=include('scripts.samira_item_effects');local S=include('scripts.samira_shop');local I=include('scripts.samira_interaction')
 local function setup(n)reset();tick();player.coins=n or 99;E.restore(player);return player.data.Samira,E.state(player) end
 for id,price in pairs({[1001]=12,[1036]=12,[1028]=12,[1042]=12,[1055]=15,[6333]=55,[3161]=50,[6610]=50,[2501]=50,[3071]=50}) do
  assert(E.items[id].price==price and E.items[id].sell==math.floor(price/2),'requested buy/sell prices')
  if price>=50 then setup();assert(E.buy(player,id,true));assert(not E.quote(player,id),'advanced uniqueness must survive the price reduction') end
 end
 setup();local oldDelay=player.MaxFireDelay
 for _,rate in ipairs({1,3,5,10}) do
  player.MaxFireDelay=30/rate-1
  assert(E.cooldown(player,300,false)==math.floor(300*100/(100+rate*4)),'one displayed tear rate gives four ability haste')
 end
 player.MaxFireDelay=oldDelay
 local s,g=setup(0);assert(g.gold==0 and not E.buy(player,1036,true))
 player:AddCoins(20);E.syncCoins(player);assert(g.gold==20)
 assert(E.buy(player,1036,true) and g.gold==8 and player:GetNumCoins()==8)
 E.syncCoins(player);assert(g.gold==8)
 assert(E.sell(player,1,true) and g.gold==14 and player:GetNumCoins()==14)
 player:AddCoins(-9);E.syncCoins(player);assert(g.gold==5,'native machines share the same wallet')
 E.restore(player,{gold=999999});assert(E.state(player).gold==5,'legacy wallet cannot mint coins')
 E.addGold(player,99999);assert(E.state(player).gold==99,'native coin cap applies')
 local count=0
 for id,item in pairs(E.items) do
  count=count+1;s,g=setup();assert(E.buy(player,id,true));assert(g.gold==99-item.price)
  e=mob(150,100);entities={e};g.time=30
  E.stats(player,{damage=6.3,interval=22,crit=0,speed=2,reach=80});F.cast(player,s,'q');F.hit(player,s,e,3,true);F.hit(player,s,e,3,false)
  F.update(player,s);F.hurt(player,s,1,0,EntityRef(e),0);E.restore(player,E.save(player))
 end
 assert(count==28 and #S.items(2)==28 and not E.quote(player,3157),'curated crafting shop contains 28 supported items')
 -- Components pay their full original value, including descendants and duplicates.
 s,g=setup();assert(E.buy(player,1036,true));assert(E.buy(player,1036,true))
 local q=E.quote(player,3133);assert(q.cost==2 and q.credit==24)
 assert(E.buy(player,3133,true));assert(g.gold==73 and E.sum(player).ad==20)
 q=E.quote(player,3161);assert(q.cost==24 and q.credit==26)
 s,g=setup();assert(E.buy(player,1028,true));assert(E.buy(player,1028,true))
 q=E.quote(player,3084);assert(q.cost==41 and q.credit==24,'two rubies must not count three times')
 for n=3,6 do E.addGold(player,99);assert(E.buy(player,1036,true)) end
 q=E.quote(player,3084);assert(q and q.cost==41,'combining frees slots in a full inventory')
 local before=E.save(player);local coins=player.coins
 player.coins=0;assert(not E.buy(player,3084,true));assert(g.slots[1].id==before.slots[1].id,'failed purchase cannot consume ingredients')
 player.coins=coins;assert(E.buy(player,3084,true));assert(E.has(player,3084) and not E.has(player,1028))
 -- Three-second charge, per-target cooldown, saved fractional stacks and sale/rebuy.
 s,g=setup();assert(E.buy(player,3084,true));e=mob(150,100);e.InitSeed=101
 local other=mob(170,100);other.InitSeed=102;entities={e,other}
 for i=1,89 do F.update(player,s) end
 assert(s.heartsteelVisuals[1].charge==89 and s.heartsteelVisuals[1].age==14,'five-stack playback has a stable age')
 F.hit(player,s,e,3,false);assert(not g.heartsteel,'cannot proc before 3 seconds')
 assert(not s.heartsteelSoundPending,'unready hits must not play the proc sound')
 F.update(player,s);local hp=Health.max(player);F.hit(player,s,e,3,false)
 local gain=(70+hp*.06)*.1;assert(math.abs(g.heartsteel-gain)<.0001)
 assert(#s.heartsteelHits==1,'proc emits an original impact event')
 assert(s.heartsteelSoundPending,'a successful stack emits the original proc sound')
 local soundsBefore=soundCount('heartsteel_hit');audio.observe(player,s);audio.observe(player,s)
 assert(soundCount('heartsteel_hit')==soundsBefore+1 and not s.heartsteelSoundPending,'play one proc cue, never once per frame')
 local sizeBefore=G.bodyScale(player);local nativeScale=player.SpriteScale or Vector(1,1)
 local steelScale=1+math.min(.3,Health.max(player)/1000*.03)
 assert(math.abs(sizeBefore.X-nativeScale.X*steelScale)<.00001,'Heartsteel scales the visible body by max HP')
 local healthState=Health.state(player);local originalGearHP=healthState.gear;healthState.gear=20000
 player.SpriteScale=Vector(.8,1.2);local capped=G.bodyScale(player)
 assert(math.abs(capped.X-1.04)<.00001 and math.abs(capped.Y-1.56)<.00001,'size cap composes with native shrinking/stretching')
 healthState.gear=originalGearHP;player.SpriteScale=nativeScale
 F.update(player,s);F.hit(player,s,e,3,false);assert(g.heartsteel==gain,'same target has cooldown')
 assert(not s.heartsteelSoundPending,'target cooldown prevents repeated proc sounds')
 F.update(player,s);F.hit(player,s,other,3,false);assert(g.heartsteel>gain,'other enemy has independent charge')
 assert(#s.heartsteelHits==2,'separate targets cannot truncate previous impact tails')
 local saved=E.save(player);local stacks=g.heartsteel;g.heartsteelTargets[next(g.heartsteelTargets)].charge=20
 E.restore(player,saved);g=E.state(player);assert(g.heartsteel==stacks,'fractional permanent stacks persist')
 for key,v in pairs(g.heartsteelTargets) do assert(v.stageAt==saved.heartsteelTargets[key].stageAt,'persist particle stage clock') end
 assert(E.sell(player,1,true));assert(E.sum(player).hp==0,'selling disables health bonus without erasing stacks')
 assert(G.bodyScale(player).X==nativeScale.X,'selling removes only Heartsteel size')
 E.addGold(player,99);assert(E.buy(player,3084,true));assert(E.sum(player).hp==600+stacks)
 F.update(player,s);F.hit(player,s,e,3,false);assert(g.heartsteel==stacks,'selling and rebuying cannot reset target cooldown')
 local Rewind=include('scripts.samira_rewind');local snapshot=Rewind.capture(player,s)
 g.heartsteel=999;assert(Rewind.apply(player,s,snapshot));assert(E.state(player).heartsteel==stacks)
 -- Range break resets charge; spells do not consume it.
 s,g=setup();E.buy(player,3084,true);e=mob(150,100);entities={e}
 for i=1,90 do F.update(player,s) end
 F.hit(player,s,e,3,true);assert(not g.heartsteel)
 e.Position=Vector(1000,1000);for i=1,91 do F.update(player,s) end
 e.Position=Vector(150,100);F.update(player,s);F.hit(player,s,e,3,false);assert(not g.heartsteel)
 -- BORK slow needs three hits on the SAME enemy, not three global attacks.
 s,g=setup();E.buy(player,3153,true);e=mob(150,100);other=mob(170,100);e.InitSeed=1;other.InitSeed=2
 for _,target in ipairs({e,other,e}) do g.time=g.time+1;F.hit(player,s,target,0,false,0,100) end
 assert(not e.slow and not other.slow)
 g.time=g.time+1;F.hit(player,s,e,0,false,0,100);assert(e.slow and e.slow[1]==30 and e.slow[2]==.7)
 assert(math.abs(e.total-24)<.001,'8 percent current-health on-hit damage')
 e.slow=nil;for i=1,3 do g.time=g.time+1;F.hit(player,s,e,0,false,0,100) end;assert(not e.slow)
 print('Crafting credits/full inventory/failed transactions, Heartsteel charge/save/rewind/sale and BORK per-target slow passed')
 s,g=setup();assert(not E.buy(player,1036,false),'combat purchases are blocked')
 for n=1,6 do E.addGold(player,99);assert(E.buy(player,1036,true)) end
 assert(not E.buy(player,1042,true),'six slots are enforced')
 s,g=setup();E.buy(player,6610,true);e=mob(150,100);entities={e};g.time=30
 F.hit(player,s,e,3,false);local heal=Health.current(player);g.time=g.time+1;F.hit(player,s,e,3,false);assert(Health.current(player)==heal,'Sundered Sky does not repeatedly heal on the same target')
 s,g=setup();local old=Health.current(player);A.onHit(player,s,mob(150,100),1000);assert(Health.current(player)>old,'learned E restores a bounded fraction of damage as healing')
 -- Use real ownership counts to exercise mixed slots, quality-zero sales and full inventory rejection.
 ItemType={ITEM_ACTIVE=3};local config={};local owned={}
 for id=1,8 do config[id]={Name='Test '..id,Type=1,Quality=id%5,GfxFileName='test.png'} end
 config[9]={Name='Active',Type=3,Quality=4}
 local previous=Isaac.GetItemConfig
 Isaac.GetItemConfig=function()return {GetCollectible=function(_,id)return config[id] end,GetCollectibles=function()return {Size=10} end}end
 function player:GetCollectibleNum(id)return owned[id] or 0 end
 function player:RemoveCollectible(id)owned[id]=math.max(0,(owned[id] or 0)-1) end
 s,g=setup();assert(E.buy(player,1036,true))
 for id=1,5 do owned[id]=1 end;E.syncInventory(player)
 assert(not E.free(player) and g.slots[2].id==-1,'native and shop items share six slots')
 assert(callbacks[ModCallbacks.MC_PRE_ADD_COLLECTIBLE](nil,6,0,true,0,0,player)==false)
 assert(callbacks[ModCallbacks.MC_PRE_ADD_COLLECTIBLE](nil,9,0,true,0,0,player)==nil,'active items do not consume passive slots')
 local before=g.gold;assert(E.sell(player,6,true));assert(owned[5]==0 and g.gold==before,'quality-zero items can be sold for zero')
 owned[6]=1;E.syncInventory(player);assert(g.slots[6].id==-6)
 owned[1]=0;E.syncInventory(player);assert(g.slots[2].id==0,'removing/rerolling an item releases its slot')
 local saved=E.save(player);E.restore(player,saved);assert(E.state(player).slots[6].id==-6,'native inventory survives continue')
 E.items[-6]=nil
 assert(E.nativePayload(player)['-6'].native==6,'separate include consumers lazily resolve native slot metadata')
 -- Removing ownership alone deliberately leaves cached stats/familiars stale.
 -- The transaction must ask the engine to rebuild them, without deleting all familiars.
 local oldEvaluate=player.EvaluateItems;local oldDamage=player.Damage;local oldDelay=player.MaxFireDelay
 local cachedFamiliars,refreshes=0,0
 function player:EvaluateItems()
  assert(self.cacheFlag==CacheFlag.CACHE_ALL,'sale must rebuild stats and familiars, not just health')
  self.Damage=3.5+(owned[1] or 0)*2;self.MaxFireDelay=10-(owned[1] or 0)
  cachedFamiliars=owned[2] or 0;refreshes=refreshes+1
 end
 owned={};s,g=setup();owned[1]=1;owned[2]=2;E.syncInventory(player);E.refreshNative(player)
 assert(player.Damage==5.5 and player.MaxFireDelay==9 and cachedFamiliars==2)
 local function slot(id)for i,a in ipairs(g.slots)do if a.id==-id then return i end end end
 local evaluated=refreshes;assert(E.sell(player,slot(1),true))
 assert(player.Damage==3.5 and player.MaxFireDelay==10 and refreshes==evaluated+1,'sold stats disappear immediately')
 assert(E.sell(player,slot(2),true) and cachedFamiliars==1,'one remaining copy retains one familiar')
 assert(E.sell(player,slot(2),true) and cachedFamiliars==0,'last copy removes its cached familiar')
 owned[3]=1;E.syncInventory(player);local index=slot(3);local coins=player:GetNumCoins()
 local originalRemove=player.RemoveCollectible
 player.RemoveCollectible=function()end
 assert(not E.sell(player,index,true) and player:GetNumCoins()==coins and g.slots[index].id==-3,'failed removal cannot grant coins or empty its slot')
 player.RemoveCollectible=function(self,id,ignore)
  assert(ignore==true,'sell the real owned item, not a temporary modifier');originalRemove(self,id)
 end
 assert(E.sell(player,index,true))
 player.EvaluateItems=oldEvaluate;player.Damage=oldDamage;player.MaxFireDelay=oldDelay
 Isaac.GetItemConfig=previous;player.GetCollectibleNum=nil;player.RemoveCollectible=nil
 for id=1,8 do E.items[-id]=nil end
 local a,b=mob(140,100),mob(145,105);local valid=function(e)return e:IsVulnerableEnemy() end
 assert(I.hover({b,a},Vector(140,100),valid)==a and I.hover({a},Vector(140,78),valid)==a)
 GetPtrHash=function(e)return e.pointer end
 assert(I.same({pointer=7},{pointer=7}) and not I.same({pointer=7},{pointer=8}));GetPtrHash=nil
 local original=Color(1,1,1,.7);local draws={};local sp={Color=original,Render=function(self,pos)draws[#draws+1]={self.Color,pos} end}
 function a:GetSprite()return sp end;a.SpriteOffset=Vector(0,-3)
 I.outline(a,Vector(2,4));assert(#draws==8 and sp.Color==original)
 print('Native coin authority/cap, ten-item effects, six mixed slots, ownership/removal/sale/continue, minion healing and pointer-based outline passed')
end


do
 reset();tick();local s=player.data.Samira
 assert(not external.occluded(player,s))
 player.Visible=false;assert(not external.occluded(player,s));player.Visible=true
 external.manualHidden=true;assert(external.occluded(player,s));external.manualHidden=nil
 external.toggle(true);time=time+250;external.poll();external.emit(player,s,false)
 local beforeScene=#diagnostics
 callbacks[ModCallbacks.MC_POST_NIGHTMARE_SCENE_SHOW]()
 assert(#diagnostics>beforeScene,'scene-show sends concealment without waiting for MC_POST_RENDER')
 local function scenePacket()
  return codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 end
 local packet=scenePacket();assert(packet.occluded and not packet.hudVisible,'scene hides model, particles, overhead, cursor and corner HUD together')
 -- Only cinematic callbacks run; the normal render/update callback never fires.
 for i=1,150 do
  time=time+34;callbacks[ModCallbacks.MC_POST_NIGHTMARE_SCENE_RENDER]()
  local nextPacket=scenePacket();assert(nextPacket.seq>packet.seq and nextPacket.occluded and not nextPacket.hudVisible)
  packet=nextPacket
 end
 assert(external.occluded(player,s));time=time+750;assert(not external.occluded(player,s))
 external.emit(player,s,false);assert(not scenePacket().occluded and scenePacket().hudVisible,'ordinary rendering restores after the scene finishes')
 external.toggle(false)
 local previous=RoomTransition
 RoomTransition={GetTransitionMode=function()return 0 end,IsRenderingBossIntro=function()return true end}
 assert(external.occluded(player,s));RoomTransition=previous
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(not external.occluded(player,s));time=time+750;assert(not external.occluded(player,s))
 -- R replaces native music, uses its volume channel, and survives room changes.
 reset();playedSounds={};keys[Keyboard.KEY_R]=true;tick();keys={};s=player.data.Samira
 local music=MusicManager();local count=music.plays
 assert(music.current==200 and music.volumeUpdated and soundCount('r_music')==0 and math.abs(music.volume-.9)<.000001)
 Options.MusicVolume=.8;tick();assert(music.volume==1,'R boost is capped at full volume')
 Options.MusicVolume=0;tick();assert(music.volume==0,'R preserves music mute')
 Options.MusicVolume=.3;tick();assert(math.abs(music.volume-.9)<.000001 and Options.MusicVolume==.3,'R does not rewrite the user setting')
 tick(10);callbacks[ModCallbacks.MC_POST_NEW_ROOM]();tick()
 assert(music.current==200 and music.plays==count,'room changes and kills cannot restart the BGM')
 music:Play(12);assert(music.current==200,'remember new room/boss music while R owns the music channel')
 tick(310);assert(music.current==12 and music.volume==.3,'expiration restores the latest requested native track and normal volume')
 s.rUntil=s.clock+100;tick();assert(music.current==200);dead=true;tick();assert(music.current==12)
 print('Native invisibility/boss/nightmare/room occlusion and replacement R music lifecycle passed')
end

-- 0.6.2: alternate input and live-render ownership regressions.
do
 local C=include('scripts.samira_controls')
 reset();tick();local s=player.data.Samira
 local fire=mob(140,100);fire.Type=EntityType.ENTITY_FIREPLACE;entities={fire};mouse=fire.Position
 keys[Keyboard.KEY_A]=true;tick();keys={};left=true;tick();left=false;tick(12)
 assert(fire.hits==1 and include('scripts.samira_passive').ready(player),'A + click attacks fire without consuming passive')
 local xp=progress.state(player).xp;callbacks[ModCallbacks.MC_POST_ENTITY_KILL](nil,fire);assert(progress.state(player).xp==xp,'fires cannot be farmed for XP')
 reset();C.state(player).mode='wasd';keys[Keyboard.KEY_D]=true;tick();assert(player.Velocity.X>0 and not player.data.Samira.cast,'WASD moves without casting')
 keys={};keys[Keyboard.KEY_E]=true;mouse=Vector(300,100);tick();assert(player.data.Samira.cast.kind=='W','WASD E key owns W skill')
 reset();tick();s=player.data.Samira
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'0cd','on');s.qReady=s.clock+900;s.wReady=s.clock+900;tick()
 assert(s.qReady==s.clock and s.wReady==s.clock,'0cd resets actual readiness')
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'0cd','off');assert(not s.noCD)
 reset();keys[Keyboard.KEY_R]=true;tick();keys={};s=player.data.Samira;assert(player.CanFly,'R grants actual native flight')
 s.rUntil=s.clock;tick();assert(not player.CanFly,'R expiry recalculates native flight')
 local placement=callbacks[ModCallbacks.MC_PRE_PLAYERHUD_TRINKET_RENDER](nil,0,Vector.Zero,1,player,Vector.Zero)
 assert(placement.Scale==.55 and placement.Position.Y<hud.layout(Isaac.GetScreenWidth(),Isaac.GetScreenHeight()).left.y-19,'trinket lies above passive at reduced scale')
 Options.Language='zh';assert(C.language()=='zh');Options.Language='en';assert(C.language()=='en');Options.Language='zh'
 C.restore(player,{mode='wasd',bindings={q=Keyboard.KEY_Z}});assert(C.key(player,'q')==Keyboard.KEY_Z)
 C.restore(player,{mode='broken',bindings={q=-4}});assert(C.key(player,'q')==Keyboard.KEY_Q,'invalid settings fall back safely')
 local originalButton=Input.IsButtonPressed;local originalAction=Input.GetActionValue;local padButtons={};local actions={}
 player.ControllerIndex=1
 Input.IsButtonPressed=function(code,index)if index==1 then return padButtons[code]==true end;return originalButton(code,index) end
 Input.GetActionValue=function(action,index)
  assert(inp(nil,player,InputHook.GET_ACTION_VALUE,action)==nil,'raw stick sampling cannot block itself');return actions[action] or 0
 end
 actions[ButtonAction.ACTION_RIGHT]=.6;local v=C.movement(player,s);assert(v.X==.6 and v.Y==0,'analog speed preserved')
 padButtons[8]=true;assert(C.edge(player,s,'q'));assert(not C.edge(player,s,'q'),'held shoulder casts once')
 padButtons[8]=false;C.edge(player,s,'q');padButtons[8]=true;assert(C.edge(player,s,'q'))
 Input.IsButtonPressed=originalButton;Input.GetActionValue=originalAction;player.ControllerIndex=0
 reset();tick();s=player.data.Samira;external.start();assert(external.occluded(player,s),'startup remains native during fade')
 time=time+2300;assert(not external.occluded(player,s),'startup gate releases')
 external.toggle(true);external.poll();assert(external.replaces(false));external.actorRoom=external.room-1
 assert(external.replaces(false),'room epoch change retains verified renderer ownership')
 external.actorRoom=external.room;external.actorVisible=false;assert(external.replaces(false),'intentional hiding cannot restore the old actor')
 external.toggle(false)
 assert(callbacks[ModCallbacks.MC_PRE_NPC_RENDER]==nil,'enemies retain native rendering without red redraw or Q lift')
 print('A/fire, WASD keys, gamepad analog/edges, 0cd, R flight, trinkets, languages, settings and fresh-frame ownership passed')
end

-- Presentation ownership survives ordinary overlays and room scrolls.
do
 reset();tick();local s=player.data.Samira
 ackCapabilities={combat=1,hud=1};external.toggle(true);external.poll()
 for _,book in ipairs({5,29}) do
  callbacks[ModCallbacks.MC_POST_ITEM_OVERLAY_RENDER](nil,book)
  player.ControlsEnabled=false;paused=true
  assert(external.hudAllowed(s,true) and not external.occluded(player,s),'card/rainbow overlay is not a blackout')
  local before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
  assert(#spriteDraws==before and external.hud(true),'rainbow pause retains external actor and HUD')
 end
 for _,book in ipairs({33,44}) do
  callbacks[ModCallbacks.MC_POST_ITEM_OVERLAY_RENDER](nil,book)
  assert(not external.hudAllowed(s,true) and external.occluded(player,s),'sleep CG hides both layers')
  time=time+750
 end
 paused=false;player.ControlsEnabled=true;external.poll()
 external.capture(player,Vector(37,-12))
 local pos,captured=external.actorPosition(player,s)
 assert(captured and pos.X==player.Position.X+37 and pos.Y==player.Position.Y-12,'actual room rendering offset is exported')
 external.newRoom();player.Position=Vector(580,100)
 pos,captured=external.actorPosition(player,s)
 assert(not captured and pos.X==137,'room notification alone cannot teleport the external actor')
 external.capture(player,Vector(-440,0));pos,captured=external.actorPosition(player,s)
 assert(captured and pos.X==140,'new room render offset resumes continuous screen motion')
 assert(external.replaces(true) and external.hud(true),'new room cannot relinquish either layer')
 nativeAnimation='Trapdoor';assert(not external.hudAllowed(s,false,player),'floor descent hides HUD before new-level callback')
 nativeAnimation='Idle'
 external.toggle(false);ackCapabilities=nil
 print('Rainbow/card pause, CG blackout, persistent ownership and native room-scroll coordinates passed')
end

-- 0.6.3: target terrain through the same click/A-click commands, never as a mob.
do
 local P=include('scripts.samira_passive')
 for _,attackMove in ipairs({false,true}) do
  reset();tick();local s=player.data.Samira;local pos=Vector(140,100);local index=room:GetGridIndex(pos)
  local poop={Position=pos,CollisionClass=1,damage=0,GetType=function()return GridEntityType.GRID_POOP end,
   Hurt=function(self,n)self.damage=self.damage+n;if self.damage>=3 then self.CollisionClass=0 end end}
  grids[index]=poop;mouse=pos
  if attackMove then keys[Keyboard.KEY_A]=true else right=true end
  tick();left=false;right=false;tick(120)
  assert(poop.damage==3 and s.gridTarget==nil,'right-click and held A break poop; destroyed terrain stops taking hits')
  assert(P.ready(player),'terrain attacks do not consume the champion passive')
  grids[index]=poop;poop.CollisionClass=1;s.gridTarget=index
  callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(s.gridTarget==nil,'room change discards terrain indices')
 end
 reset();tick();local s=player.data.Samira;external.toggle(true);external.poll();external.leaveRoom()
 assert(external.roomChanging(s) and external.hudAllowed(s,true),'room pause keeps corner HUD')
 local before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws==before,'no old sprite appears during room handoff')
 external.start();assert(not external.hudAllowed(s,false),'new floor blackout hides HUD')
 time=time+2400
 local view=include('scripts.samira_view');view.finish()
 Options.Fullscreen=true;Options.UseBorderlessFullscreen=false
 callbacks[ModCallbacks.MC_PRE_RENDER]();assert(Options.Fullscreen and Options.UseBorderlessFullscreen)
 local oldCount=game.GetNumPlayers;game.GetNumPlayers=function()return 0 end
 callbacks[ModCallbacks.MC_PRE_RENDER]();game.GetNumPlayers=oldCount
 assert(Options.Fullscreen and Options.UseBorderlessFullscreen,'temporary zero players cannot restore exclusive fullscreen')
 view.finish();assert(Options.Fullscreen and Options.UseBorderlessFullscreen==false,'explicit cleanup restores display preference')
 Options.Fullscreen=nil;Options.UseBorderlessFullscreen=nil
 print('Poop right/A-click, passive exclusion, room actor/HUD split and transient-player fullscreen regressions passed')
end

-- 0.6.4: direct cone input and native Q emissions.
do
 local G=include('scripts.samira_geometry');local P=include('scripts.samira_passive')
 assert(G.basicHit(50,0,0,60) and not G.basicHit(61,0,0,60))
 for _,degrees in ipairs({-49,49}) do local d=Vector(50,0):Rotated(degrees);assert(G.basicHit(d.X,d.Y,0,60)) end
 for _,degrees in ipairs({-51,51,180}) do local d=Vector(50,0):Rotated(degrees);assert(not G.basicHit(d.X,d.Y,0,60)) end
 assert(G.basicHit(62,0,3,60) and not G.basicHit(65,0,3,60),'body collision must respect reach')
 reset();tick();local s=player.data.Samira
 local near=mob(130,100);local second=mob(140,110);local behind=mob(70,100);local side=mob(100,145)
 local far=mob(280,100);entities={second,near,behind,side,far};mouse=Vector(300,100);wall=true
 keys[Keyboard.KEY_A]=true;tick();keys={}
 assert(s.cast and s.cast.cone and s.goal==nil,'A immediately swings without a click or ground movement')
 tick(6)
 assert(near.hits==1 and second.hits==0 and behind.hits==0 and side.hits==0 and far.hits==0)
 assert(P.remaining(player)==P.total(player),'only the first thrust victim takes damage and consumes passive')
 assert(#s.fx==0,'cone uses attack animation and contact feedback without a slash/range effect')
 local count=near.hits;tick(45);assert(near.hits==count,'releasing A cannot leave an automatic target')
 -- Whiffs and terrain cannot consume the passive; facing is locked during the swing.
 reset();tick();s=player.data.Samira;mouse=Vector(300,100);near=mob(130,100);entities={near}
 keys[Keyboard.KEY_A]=true;tick();keys={};mouse=Vector(100,20);tick(6);assert(near.hits==1)
 reset();mouse=Vector(300,100);keys[Keyboard.KEY_A]=true;tick(7);keys={};assert(P.ready(player))
 local oldDelay,oldRange=player.MaxFireDelay,player.TearRange
 local function attacks(delay,range,targetX)
  reset();player.MaxFireDelay=delay;player.TearRange=range;progress.state(player).passiveRemaining=9999
  local target=mob(targetX,100);target.Size=1;entities={target};mouse=Vector(300,100);keys[Keyboard.KEY_A]=true;tick(120)
  return target.hits
 end
 assert(attacks(2,260,140)>attacks(10,260,140),'held cone uses real attack-speed cadence')
 assert(attacks(10,260,180)==0 and attacks(10,600,180)>0,'range bonuses extend the actual hit area')
 player.MaxFireDelay=oldDelay;player.TearRange=oldRange;reset()
 local C=include('scripts.samira_controls');C.state(player).mode='wasd';mouse=Vector(300,100);keys[Keyboard.KEY_T]=true;tick()
 assert(player.data.Samira.cast.cone,'remapped attack also performs a cone')
 print('100-degree cone boundary, single victim, no extra slash, locked aim, attack speed/range and WASD mapping passed')

 -- 0.6.5: ordinary cone and empowered rectangle both stop at first contact.
 assert(G.basicContact(65,11,0,70,true)==65 and G.basicContact(65,13,0,70,true)==nil)
 assert(G.basicContact(72,12,3,70,true)==69 and G.basicContact(-5,0,1,70,true)==nil)
 for _,empowered in ipairs({false,true}) do
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  local front=mob(130,100);local rear=mob(150,100);entities={rear,front};mouse=Vector(300,100)
  keys[Keyboard.KEY_A]=true;tick(7);keys={}
  assert(front.hits==1 and rear.hits==0,'entity enumeration order cannot select a target behind the first')
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  front=mob(130,100);rear=mob(150,100);function front:TakeDamage()return false end
  entities={rear,front};mouse=Vector(300,100);keys[Keyboard.KEY_A]=true;tick(7);keys={}
  assert(rear.hits==0 and (progress.state(player).passiveHeal or 0)==0,'rejected first contact cannot pierce to another victim or heal')
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  local pos=Vector(120,100);local poop={Position=pos,CollisionClass=1,damage=0,
   GetType=function()return GridEntityType.GRID_POOP end,Hurt=function(self,n)self.damage=self.damage+n end}
  grids[room:GetGridIndex(pos)]=poop;rear=mob(150,100);entities={rear};mouse=Vector(300,100)
  keys[Keyboard.KEY_A]=true;tick(7);keys={}
  assert(poop.damage==1 and rear.hits==0,'terrain and enemies share one hit budget')
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  local fire=mob(125,100);fire.Type=EntityType.ENTITY_FIREPLACE;rear=mob(150,100);entities={rear,fire};mouse=Vector(300,100)
  keys[Keyboard.KEY_A]=true;tick(7);keys={}
  assert(fire.hits==1 and rear.hits==0 and (progress.state(player).passiveHeal or 0)==0,'first fire blocks further contacts without healing')
 end
 for _,empowered in ipairs({false,true}) do
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  local lateral=mob(140,130);lateral.Size=1;entities={lateral};mouse=Vector(300,100)
  keys[Keyboard.KEY_A]=true;tick(7);keys={}
  assert(lateral.hits==(empowered and 0 or 1),'passive uses a narrow rectangle rather than the normal 100-degree sector')
 end
 print('Single-hit cone, rectangular first-contact thrust, rejected hits, terrain/fire competition and healing exclusions passed')

 reset();local calls={}
 local function projectile(kind,origin,velocity)
  local e={kind=kind,Position=origin,Velocity=velocity,CollisionDamage=3.5,flying=true,data={}}
  function e:GetData()return self.data end
  function e:Exists()return not self.removed end
  function e:Remove()self.removed=true end
  function e:SetTimeout(n)self.timeout=n end
  function e:SetMaxDistance(n)self.range=n end
  function e:SetExplosionCountdown(n)self.fuse=n end
  function e:Shoot(charge,range)self.charge=charge;self.range=range end
  function e:IsFlying()return self.flying end
  calls[#calls+1]=e;return e
 end
 function player:FireBrimstone(dir,owner,mult)assert(owner==self);return projectile('brim',self.Position,dir)end
 function player:FireTechLaser(origin,offset,dir,leftEye,oneHit,owner,mult)assert(owner==self);return projectile('tech',origin,dir)end
 function player:FireTechXLaser(origin,velocity,radius,owner,mult)assert(owner==self and radius==25);return projectile('techx',origin,velocity)end
 function player:FireBomb(origin,velocity,owner)assert(owner==self);return projectile('bomb',origin,velocity)end
 function player:FireKnife(parent,rotation,cantOverwrite)assert(parent==self and cantOverwrite);return projectile('knife',self.Position,Vector.Zero)end
 player.weapons={}
 for _,name in ipairs({'BRIMSTONE','TECHNOLOGY','TECHNOLOGY_2','TECH_X','DR_FETUS','MOMS_KNIFE'}) do player.weapons[CollectibleType['COLLECTIBLE_'..name]]=true end
 for stage=1,3 do
  mouse=Vector(300,100);tick();s=player.data.Samira;s.qReady=0
  keys[Keyboard.KEY_Q]=true;tick();keys={};assert(s.cast.stage==stage)
  assert(#calls==(stage-1)*6,'no emission before Q contact')
  mouse=Vector(100,20);player.Position=Vector(120,100);tick(17)
  assert(#calls==stage*6,'each Q emits each owned weapon once, even with no victims')
  for i=(stage-1)*6+1,#calls do local e=calls[i]
   assert(e.Position.X==120 and e.Position.Y==100,'Q effects start at impact position')
   if e.kind=='knife' then assert(e.Rotation==0 and e.charge==1 and e.range>0)
   else assert(e.Velocity.X>0 and math.abs(e.Velocity.Y)<.001,'Q locks native weapons to its cast direction') end
   if e.kind=='bomb' then assert(e.IsFetus and e.fuse==30) end
  end
  tick(6);assert(#calls==stage*6,'holding/end frames do not emit again')
 end
 local W=include('scripts.samira_q_weapons');local first=calls[6];first.flying=false;W.update(s);assert(first.removed,'returned knives are removed')
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(calls[12].removed and calls[18].removed and s.qKnives==nil,'room change clears Q knives')
 W.emit(player,s,Vector(0,-1),8,150);local last=calls[#calls];for i=1,90 do W.update(s) end;assert(last.removed,'knife lifetime is bounded')
 W.emit(player,s,Vector(1,0):Rotated(18),8,150);local steering=calls[#calls]
 mouse=player.Position+Vector(0,100);steering.Rotation=90;W.update(s)
 assert(math.abs(steering.Rotation-18)<.001,'knife retains its emitted Q direction after cursor movement')
 local art={loads=0};function art:ReplaceSpritesheet(layer,path)self.path=path;assert(layer==0)end
 function art:LoadGraphics()self.loads=self.loads+1 end
 function steering:GetSprite()return art end
 steering.Parent=player;steering.Variant=0;steering.SubType=0
 local knifeUpdate=callbacks[ModCallbacks.MC_POST_KNIFE_UPDATE]
 -- Simulate vanilla overwriting the direction before the callback, on every tick.
 for _,angle in ipairs({0,90,180,-90,37}) do
  steering.Position=player.Position+Vector(40,0);steering.Rotation=90
  mouse=player.Position+Vector(100,0):Rotated(angle);knifeUpdate(nil,steering)
  assert(math.abs(steering.Rotation-18)<.001)
  assert(steering.Position:Distance(player.Position+Vector(40,0):Rotated(18))<.001,'native facing changes cannot swing the visible knife off its locked Q axis')
 end
 assert(art.loads==1 and art.path=='gfx/samira/native/effect_momsknife.png','load private vanilla art once')
 assert(steering.Visible and steering.CollisionDamage==8,'Q knife remains visible and damaging')
 -- Overlapping Q casts keep separate projected directions throughout outward/return travel.
 local locked={};local G=include('scripts.samira_geometry')
 for _,angle in ipairs({-24,-8,8,24,135}) do
  local face=G.project(Vector(1,0):Rotated(angle)):Normalized()
  W.emit(player,s,face,8,150);local knife=calls[#calls]
  knife.Parent=player;knife.Variant=0;knife.SubType=0
  function knife:GetSprite()return art end
  locked[#locked+1]={knife=knife,face=face}
 end
 for _,distance in ipairs({5,50,130,75,20,0}) do
  player.Position=player.Position+Vector(3,-2);s.face=Vector(0,-1);mouse=player.Position+Vector(-100,50)
  W.update(s)
  for _,entry in ipairs(locked) do
   local knife=entry.knife
   assert(math.abs(knife.Rotation-entry.face:GetAngleDegrees())<.001)
   knife.Position=player.Position+Vector(0,distance);knife.Rotation=-90;knife.RotationOffset=45
   knifeUpdate(nil,knife)
   assert(math.abs(knife.Rotation-entry.face:GetAngleDegrees())<.001 and knife.RotationOffset==0)
   assert(knife.Position:Distance(player.Position+entry.face*distance)<.001,'moving/turning and later Q casts preserve each knife axis and native travel distance')
  end
 end
 steering.data.SamiraQAngle=nil;mouse=player.Position+Vector(0,-100);knifeUpdate(nil,steering)
 assert(not steering.Visible and steering.CollisionDamage==0,'held knife is hidden without invisible contact damage')
 steering.Parent={ToPlayer=function()return nil end};steering.Rotation=12;knifeUpdate(nil,steering)
 assert(steering.Rotation==12,'familiar knives retain native behavior')
 steering.Parent=player;player.type=1;knifeUpdate(nil,steering);assert(steering.Rotation==12,'other characters remain unchanged');player.type=10
 player.weapons=nil;local emitted=#calls;W.emit(player,s,Vector(1,0),8,150);assert(#calls==emitted,'unowned native weapons never spawn')
 reset()
 print('Native Q weapon ownership, all three contacts, locked direction, QE origin, knife return/timeout/room cleanup passed')
end

do
 local G=include('scripts.samira_geometry')
 WeaponType={WEAPON_TEARS=1}
 for _,count in ipairs({1,2,4}) do
  reset();local samples=0
  function player:GetMultiShotParams(weapon)
   assert(weapon==WeaponType.WEAPON_TEARS);samples=samples+1
   return {GetNumTears=function()return count end}
  end
  for stage=1,3 do
   reset();mouse=Vector(300,100);tick();local s=player.data.Samira;s.nextQ=stage;s.qReady=0
   local victim=mob(170,100);victim.Size=200;entities={victim}
   local health=include('scripts.samira_health');health.state(player).hp=100
   keys[Keyboard.KEY_Q]=true;tick();keys={}
   assert(#s.cast.faces==count,'native multishot count drives each Q stage')
   local faces=s.cast.faces
   assert(math.abs(faces[1]:GetAngleDegrees()+faces[count]:GetAngleDegrees())<.001,'Q spread is centered on aim')
   local before=samples;tick(17)
   assert(victim.hits==1 and #s.fx==count,'simultaneous Q merges target damage but retains every original effect')
   assert(victim.data.SamiraQStagger and callbacks[ModCallbacks.MC_PRE_NPC_UPDATE](nil,victim)==true,'every Q stage and multishot count stops its victim')
   local base=progress.stats(player,{damage=3.5*1.8,interval=22}).damage*progress.attackMultiplier(player)*(1+stage*.25)*progress.damage(player,'q')
   local shape=G.shape(stage,1);local total,best=0,0
   for _,face in ipairs(faces) do
    local offset=G.unproject(victim.Position-player.Position):Rotated(-face:GetAngleDegrees())
    local inside,sweet=G.hit(shape,offset.X,offset.Y,victim.Size)
    assert(inside);local damage=base*(sweet and 1.6 or 1);total=total+damage;best=math.max(best,damage)
   end
   assert(math.abs(victim.total-(best+.5*(total-best)))<1e-6,'only the strongest overlap deals full damage')
   assert(math.abs(health.current(player)-100-best/.105*.08)<1e-6,'E heals from the strongest hit once per victim and Q stage')
   assert(samples==before,'count is locked at cast start')
  end
 end
 player.GetMultiShotParams=nil;reset()
 for _,scale in ipairs({.5,1,1.5}) do
  player.SpriteScale=Vector(scale,scale);local size=G.bodyScale(player)
  assert(size.X==scale and size.Y==scale,'native size changes are preserved')
 end
 player.SpriteScale=nil
 print('Native multishot count, symmetric Q1/Q2/Q3 hits/effects, locked casts and body size passed')
end

do
 local E=include('scripts.samira_equipment');local H=include('scripts.samira_health')
 local function near(a,b)assert(math.abs(a-b)<1e-6,tostring(a)..' ~= '..tostring(b))end
 for rank=1,5 do
  reset();progress.restore(player,{level=18,skills={e=rank,r=3}});tick()
  local s=player.data.Samira;H.state(player).hp=100
  A.onHit(player,s,mob(150,100),10.5);near(H.current(player),100+({8,10,12.5,15,18})[rank])
  H.state(player).hp=100;s.rRank=3;s.rUntil=s.clock+300;s.rHasteAt=s.clock
  A.onHit(player,s,mob(150,100),10.5);near(H.current(player),100+1.8*({8,10,12.5,15,18})[rank])
 end
 reset();player.MoveSpeed=1.2;tick();player.coins=99;assert(E.buy(player,1001,true))
 local s=player.data.Samira;s.rRank=1;s.rUntil=s.clock+300;s.rHasteAt=s.clock+1
 mouse=Vector(700,100);right=true;tick()
 near(player.Velocity:Length(),2.82975*(1+(1.2*(1+45/345)*1.6-1)/2))
 right=false;player.MoveSpeed=.8;reset();mouse=Vector(700,100);right=true;tick()
 near(player.Velocity:Length(),2.82975*.8)
 player.MoveSpeed=1;reset()
 print('E ranks heal 8/10/12.5/15/18 percent, rank-three R amplifies to 32.4 percent, stacked speed bonuses halve once and slows remain intact')
end

-- Numeric health is authoritative; native hearts are a compatibility proxy.
do
 local H=include('scripts.samira_health');local E=include('scripts.samira_equipment');local F=include('scripts.samira_item_effects')
 local function near(a,b,msg)assert(math.abs(a-b)<1e-6,(msg or '')..': '..a..' ~= '..b)end
 local function fresh()
  reset();player.red=6;player.soul=0;player.addedContainers=-2
  progress.restore(player,{level=1,skills={e=1}});H.restore(player);E.restore(player);tick()
  return H.state(player),E.state(player),player.data.Samira
 end
 local function take(amount,flags,accepted)
  local result=callbacks[ModCallbacks.MC_ENTITY_TAKE_DMG](nil,player,amount,flags or 0,EntityRef(mob(150,100)),0)
  if type(result)=='table' then
   assert((result.DamageFlags & DamageFlag.DAMAGE_FAKE)~=0,'engine must not subtract proxy hearts')
   if accepted~=false then callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,0,result.DamageFlags,EntityRef(player)) end
  end
  return result
 end
 local h,g,s=fresh();near(H.max(player),650);near(h.hp,650)
 take(1);near(h.hp,600,'half heart damage');tick();near(h.hp,600,'proxy cannot double-charge damage')
 H.heal(player,.25);near(h.hp,600.25);tick();near(h.hp,600.25,'sub-HP heal survives native synchronization')
 player:AddHearts(1);near(h.hp,650,'half heart healing clamps at max')
 h.hp=300;H.sync(player);player:AddHearts(2);near(h.hp,400,'one native heart heals exactly 100')
 player:AddHearts(-1);near(h.hp,350,'direct native half-heart cost')
 player:AddMaxHearts(2,false);near(H.max(player),750,'native HP-up grants 100 capacity')
 player:AddHearts(2);near(h.hp,450);tick();near(h.hp,450)
 for stage=1,10 do
  h,g,s=fresh();floorNumber=stage;take(1);near(h.hp,650-(50+10*(stage-1)),'linear floor damage')
  h.hp=300;H.heal(player,.75);near(h.hp,300.75,'floor does not scale healing')
 end
 for amount=1,2 do for _,nativeFrames in ipairs({0,6,12,40,60,80,120,240}) do
  h,g,s=fresh();floorNumber=1;player.damageCooldown=nativeFrames;take(amount)
  assert(player:GetDamageCooldown()==math.min(nativeFrames,amount*40),'half/full-heart hits use 40/80 frames without extending shorter timers')
 end end
 for amount=1,2 do
  h,g,s=fresh();floorNumber=5;player.damageCooldown=120;take(amount)
  assert(player:GetDamageCooldown()==amount*40,'floor scaling cannot change the native half/full-heart protection tier')
  h,g,s=fresh();g.slots[1]={id=1029,count=1,ready=0,charges=0};g.shield=1000;g.shieldUntil=g.time+100;player.damageCooldown=120;take(amount)
  assert(player:GetDamageCooldown()==amount*40,'armor and shield absorption cannot change the protection tier')
 end
 for _,flag in ipairs({DamageFlag.DAMAGE_NO_PENALTIES,DamageFlag.DAMAGE_RED_HEARTS,DamageFlag.DAMAGE_INVINCIBLE,DamageFlag.DAMAGE_FAKE}) do
  h,g,s=fresh();player.damageCooldown=120;take(1,flag)
  assert(player:GetDamageCooldown()==120,'scripted costs and fake/forced damage do not truncate protection')
 end
 h,g,s=fresh();player.damageCooldown=180;take(1,0,false);tick()
 assert(player:GetDamageCooldown()==180,'a canceled hit cannot shorten protection')
 h,g,s=fresh();player:SetMinDamageCooldown(180);tick(10)
 assert(player:GetDamageCooldown()==180,'ordinary updates leave item-granted protection alone')
 g.stasis=g.time+120;take(1);assert(player:GetDamageCooldown()==180,'equipment stasis still blocks hits without resetting protection')
 h,g,s=fresh();player.type=1;player.damageCooldown=120
 callbacks[ModCallbacks.MC_ENTITY_TAKE_DMG](nil,player,1,0,EntityRef(mob(150,100)),0)
 callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,1,0,EntityRef(mob(150,100)))
 assert(player:GetDamageCooldown()==120,'other characters retain their native protection')
 h,g,s=fresh();take(1,DamageFlag.DAMAGE_FAKE);near(h.hp,650,'native fake feedback is not damage')
 take(1,0,false);take(1,DamageFlag.DAMAGE_FAKE);callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,0,DamageFlag.DAMAGE_FAKE,EntityRef(player));near(h.hp,650,'a canceled hit cannot leak to the next fake event')
 take(1,0,false);tick();near(h.hp,650,'a later mod can cancel the pending hit')
 callbacks[ModCallbacks.MC_POST_ENTITY_TAKE_DMG](nil,player,0,DamageFlag.DAMAGE_FAKE,EntityRef(player));near(h.hp,650,'canceled pending damage cannot leak to a later fake event')
 h.hp=300;h.soul=25.5;H.sync(player);take(1);near(h.hp,275.5);near(h.soul,0,'fractional shield absorbs first');tick();near(h.hp,275.5)
 player:AddSoulHearts(2);near(h.soul,100,'soul heart grants a 100-point shield')
 take(1,DamageFlag.DAMAGE_RED_HEARTS);near(h.hp,225.5);near(h.soul,100,'red-heart costs bypass shields')
 -- Nested AddBlackHearts -> AddSoulHearts is one collection transaction.
 callbacks[ModCallbacks.MC_PRE_PLAYER_ADD_HEARTS](nil,player,2,8);player:AddSoulHearts(2)
 callbacks[ModCallbacks.MC_POST_PLAYER_ADD_HEARTS](nil,player,2,8);near(h.soul,200)
 h.hp=10;h.soul=0;H.sync(player);take(1);assert(dead and h.hp==0,'lethal numeric damage triggers native death')
 dead=false;player.red=2;player.soul=0;callbacks[ModCallbacks.MC_POST_PLAYER_REVIVE](nil,player);near(h.hp,100,'native revive restores numeric HP');tick();assert(not dead)
 h,g,s=fresh();h.hp=1;H.sync(player);assert(player:GetHearts()==1);take(.01);near(h.hp,.5);assert(not dead,'fractional life cannot die from proxy rounding')
 H.heal(player,.125);near(h.hp,.625)
 h,g,s=fresh();h.hp=400;progress.award(player,progress.required(1));near(H.max(player),732.08);near(h.hp,482.08,'level growth is exact and preserves missing HP')
 progress.award(player,progress.required(2));near(H.max(player),818.15);near(h.hp,568.15)
 local data=H.save(player);H.restore(player,data);near(H.current(player),568.15,'numeric save/load does not regrant growth')
 h=H.state(player);h.hp=H.max(player);local label,cap=hud.healthNumbers(player);assert(label==cap,'full HP must never round above its label maximum')
 -- Old level-three save: 7 native half containers; one was granted by leveling.
 h,g,s=fresh();progress.restore(player,{level=3});player.addedContainers=-1;player.red=4;g.grantedHP=0
 H.restore(player,nil,true);E.syncHealth(player);near(H.max(player),818.15);near(H.current(player),818.15*4/7,'legacy migration preserves health fraction');assert(player:GetEffectiveMaxHearts()==6)
 data=H.save(player);H.restore(player,data);E.syncHealth(player);near(H.current(player),818.15*4/7,'migration runs only once')
 h,g,s=fresh();h.hp=200;A.onHit(player,s,mob(150,100),.105);near(h.hp,200.08,'rank-one E heals immediately for eight percent')
 include('scripts.samira_passive').consume(player,mob(150,100),.105,1);near(h.hp,200.83,'passive restores fractional HP directly')
 E.heal(player,.125);near(h.hp,200.955,'equipment healing is not heart-quantized')
 -- Death's Dance defers only accepted damage, then applies each fractional tick once.
 h,g,s=fresh();player.coins=99;assert(E.buy(player,6333,true));floorNumber=2
 local defense=E.sum(player).armor;local total=60*100/(100+defense)
 take(1,0,false);tick();near(g.debt or 0,0,'canceled hits cannot create deferred damage')
 local before=h.hp;take(1);near(before-h.hp,total*.7);near(g.debt,total*.3)
 for _=1,90 do F.update(player,s) end
 near(g.debt,0);near(before-h.hp,total,'deferred damage is not multiplied by floor twice')
 h,g,s=fresh();g.shield=30;take(1,0,false);tick();near(g.shield,30,'canceled hit preserves temporary shield')
 take(1);near(g.shield,0);near(h.hp,630,'temporary shield absorbs exact HP')
 -- Native costs can spend containers without killing the living numeric proxy.
 h,g,s=fresh();player:AddMaxHearts(-6,false);near(H.max(player),350);assert(not dead and player:GetEffectiveMaxHearts()==2)
 for _=1,4 do player:AddMaxHearts(-2,false) end
 assert(dead and H.max(player)==0,'replenished proxy containers never provide infinite paid HP')
 h,g,s=fresh();h.hp=200;g.heal=.1;progress.state(player).passiveHeal=.2;g.damageBank=.3
 H.restore(player,nil,true);E.syncHealth(player);near(H.current(player),650-15,'legacy healing is capped, old fractional damage is charged once')
 assert(g.heal==0 and g.damageBank==0 and progress.state(player).passiveHeal==0)
 -- Native full-heal requests remain bounded and numeric depletion cannot revive itself.
 h,g,s=fresh();h.hp=200;player:AddHearts(24);near(h.hp,650)
 H.damage(player,10000);assert(dead);H.heal(player,1000);near(h.hp,0)
 reset()
 print('Numeric HP: fractional healing, native pickups/costs, floor scaling, accepted/canceled damage, shields, death/revive, exact growth, legacy/continue and deferred damage passed')
end

-- Extinguished/destroyed targets stop being hovered, chased or hit.
do
 reset();local T=include('scripts.samira_terrain');local G=include('scripts.samira_geometry')
 local fire=mob(140,100);fire.Type=EntityType.ENTITY_FIREPLACE;local anim='Idle2'
 function fire:GetSprite()return {GetAnimation=function()return anim end}end
 assert(T.fire(fire))
 for _,a in ipairs({'NoFire','NoFire2','NoFire3','Dissapear','Dissapear2','Disappear'}) do anim=a;assert(not T.fire(fire),a) end
 anim='Idle';entities={fire};mouse=fire.Position;right=true;tick();right=false
 assert(player.data.Samira.cast)
 anim='NoFire';tick(40);assert(fire.hits==0 and not player.data.Samira.target and not player.data.Samira.hovered,'a fire extinguished during windup is never hit again')
 local poop={Position=Vector(140,100),State=1000,CollisionClass=1,hits=0,GetType=function()return GridEntityType.GRID_POOP end,Hurt=function(self)self.hits=self.hits+1 end}
 local index=room:GetGridIndex(poop.Position);grids={[index]=poop};entities={};mouse=poop.Position
 assert(not T.poop(room,index) and T.poopAt(room,mouse)==nil and T.basicTarget(room,player,Vector(1,0),90,false)==nil)
 T.qHit(room,player,Vector(1,0),G.shape(1),1,{});assert(poop.hits==0,'destroyed poop ignores Q1/Q2 too')
 poop.State=0;assert(T.poop(room,index)==poop,'regrown red poop can be attacked again')
 right=true;tick();right=false;poop.State=1000;tick(40);assert(poop.hits==0 and not player.data.Samira.gridTarget)
 reset();tick();local s=player.data.Samira;local target=mob(160,100);entities={target}
 local before=#bombExplosions
 for stage=1,2 do T.qHit(room,player,Vector(1,0),G.shape(stage),stage,{}) end
 assert(#bombExplosions==before,'Q1/Q2 do not call bomb interactions')
 for _,face in ipairs({Vector(1,0),Vector(0,-1),Vector(-1,0)}) do
  local shape=G.shape(3,1.5);T.qHit(room,player,face,shape,3,entities)
  local blast=bombExplosions[#bombExplosions]
  assert(blast.position:Distance(player.Position+G.project(face*shape.cx))<.001 and math.abs(blast.radius*75-shape.radius)<.001)
  assert(not player:GetData().SamiraTerrainExplosion and target.hits==0,'Q3 environment explosion cannot double-hit an enemy or leave its guard enabled')
 end
 local nativeBomb=game.BombExplosionEffects;game.BombExplosionEffects=function()error('test engine failure')end
 local ok=pcall(T.smash,room,player,Vector(1,0),G.shape(3));game.BombExplosionEffects=nativeBomb
 assert(not ok and not player:GetData().SamiraTerrainExplosion,'failed explosion always releases its guard')
 local other=mob(140,100);player:GetData().SamiraTerrainExplosion=true
 assert(not T.blockExplosionDamage(target,DamageFlag.DAMAGE_EXPLOSION,EntityRef(other)),'TNT with its own source keeps normal damage')
 player:GetData().SamiraTerrainExplosion=nil
 reset()
 print('Dead fire/poop targeting, regrowth, windup revalidation, Q3-only native explosion, scaled/directional center, no bonus combat damage and guard cleanup passed')
end

-- Q3 charge release belongs to the cast, not to each sword/victim.
do
 local P=include('scripts.samira_progression');local W=include('scripts.samira_q_weapons')
 for level=1,18 do
  reset();P.restore(player,{level=level})
  assert(math.abs(P.attackMultiplier(player)-(.8+.2*math.min(13,math.max(0,level-3))/13))<1e-9)
 end
 local oldFire=player.FireBrimstone;local oldHash=GetPtrHash
 FamiliarVariant=FamiliarVariant or {};FamiliarVariant.LIL_BRIMSTONE=87
 Direction={LEFT=0,UP=1,RIGHT=2,DOWN=3};GetPtrHash=function(e)return e end
 local shots={}
 function player:FireBrimstone(face,owner,scale)
  local beam={face=face,source=owner,scale=scale}
  function beam:SetMaxDistance(n)self.range=n end
  function beam:SetTimeout(n)self.timeout=n end
  shots[#shots+1]=beam;return beam
 end
 local function familiar(owner,mult)
  local f=mob(95,100);f.Type=EntityType.ENTITY_FAMILIAR;f.Variant=FamiliarVariant.LIL_BRIMSTONE;f.Player=owner
  function f:ToFamiliar()return self end
  function f:IsVulnerableEnemy()return false end
  function f:GetMultiplier()return mult end
  function f:PlayShootAnim(dir)self.shootDirection=dir end
  return f
 end
 for stage=1,3 do
  reset();shots={};local f=familiar(player,2);local other=familiar({},1);entities={f,other}
  player.GetMultiShotParams=function()return {GetNumTears=function()return 4 end}end
  tick();local s=player.data.Samira;s.nextQ=stage;mouse=Vector(350,100)
  keys[Keyboard.KEY_Q]=true;tick();keys={};local cast=s.cast
  tick(16);assert(#shots==0,'no charge release during Q windup')
  tick();assert(#shots==(stage==3 and 1 or 0),'only Q3 triggers one charged attack, even with four blades')
  if stage==3 then
   assert(shots[1].source==f and shots[1].CollisionDamage==7 and shots[1].range==360 and shots[1].timeout==20)
   assert(f.shootDirection==Direction.RIGHT and shots[1].face.X>.99,'release follows cast direction')
   W.charged(player,s,cast,Vector(1,0));assert(#shots==1,'same impact cannot release twice')
  end
  tick(10);assert(#shots==(stage==3 and 1 or 0))
 end
 player.GetMultiShotParams=nil;player.FireBrimstone=oldFire;GetPtrHash=oldHash;reset()
 print('Level 1-18 damage curve, Q3-only charged Lil Brimstone, owner isolation, BFFS multiplier and multishot dedup passed')
end

-- Native drop/swap must survive custom modifier chords and modal input capture.
do
 local C=include('scripts.samira_controls')
 local function value(action)return inp(nil,player,InputHook.GET_ACTION_VALUE,action) end
 local function drop()return value(ButtonAction.ACTION_DROP) end
 local function advance(n)
  for i=1,n or 1 do
   local s=player.data.Samira;s.inputFrame=(s.inputFrame or 0)+1
   C.pollDrop(player,s,paused or s.shopOpen or s.configOpen)
  end
 end
 reset();drop();local s=player.data.Samira
 keys[Keyboard.KEY_LEFT_CONTROL]=true;assert(drop()==0,'Ctrl press waits for possible modifier chord')
 advance(2);keys={};assert(drop()==1,'plain short Ctrl tap submits native swap on release')
 assert(inp(nil,player,InputHook.IS_ACTION_TRIGGERED,ButtonAction.ACTION_DROP)==true)
 assert(inp(nil,player,InputHook.IS_ACTION_PRESSED,ButtonAction.ACTION_DROP)==true)
 assert(drop()==1,'multiple hook queries cannot consume the tap')
 advance();assert(drop()==0,'tap pulse ends next update')
 keys[Keyboard.KEY_RIGHT_CONTROL]=true;assert(drop()==0);advance(6)
 assert(drop()==1,'bare held Ctrl reaches native long-hold handling')
 advance(60);assert(drop()==1,'long hold remains continuous for trinket/pocket drop')
 assert(inp(nil,player,InputHook.IS_ACTION_TRIGGERED,ButtonAction.ACTION_DROP)==false,'held drop does not repeat trigger edges')
 keys={};assert(drop()==0,'long hold release does not create another swap pulse')
 for _,key in ipairs({Keyboard.KEY_Q,Keyboard.KEY_W,Keyboard.KEY_E,Keyboard.KEY_R,Keyboard.KEY_1,Keyboard.KEY_2,Keyboard.KEY_3,Keyboard.KEY_4,Keyboard.KEY_5}) do
  reset();drop();keys[Keyboard.KEY_LEFT_CONTROL]=true;drop();advance(2);keys[key]=true
  assert(drop()==0,'Ctrl skill/emote chord cannot drop');keys[key]=nil;advance(60)
  assert(drop()==0,'modifier remains consumed until Ctrl release')
  keys={};assert(drop()==0,'chord release cannot swap pockets or active items')
 end
 for _,field in ipairs({'shopOpen','configOpen'}) do
  reset();drop();s=player.data.Samira;s[field]=true;keys[Keyboard.KEY_LEFT_CONTROL]=true
  assert(drop()==0);s[field]=false;advance(60);assert(drop()==0,'modal-held key cannot leak after closing')
  keys={};assert(drop()==0)
 end
 reset();drop();keys[Keyboard.KEY_LEFT_CONTROL]=true;drop();paused=true;advance(10)
 assert(inp(nil,player,InputHook.IS_ACTION_PRESSED,ButtonAction.ACTION_DROP)==nil,'pause retains native menu input')
 paused=false;advance(10);assert(drop()==0);keys={};assert(drop()==0,'pause cannot queue a swap on resume')
 reset();drop();s=player.data.Samira;s.configOpen=true
 for _,action in ipairs({ButtonAction.ACTION_MAP,ButtonAction.ACTION_FULLSCREEN,ButtonAction.ACTION_PAUSE,ButtonAction.ACTION_MENUCONFIRM}) do
  assert(value(action)==nil,'configuration only captures gameplay actions, not unrelated native controls')
 end
 reset();drop();keys[Keyboard.KEY_LEFT_CONTROL]=true;keys[Keyboard.KEY_4]=true
 assert(value(ButtonAction.ACTION_PILLCARD)==0);keys[Keyboard.KEY_LEFT_CONTROL]=nil
 assert(value(ButtonAction.ACTION_PILLCARD)==0,'releasing Ctrl first cannot consume the emote-4 pocket item')
 keys={};value(ButtonAction.ACTION_PILLCARD);keys[Keyboard.KEY_4]=true
 assert(value(ButtonAction.ACTION_PILLCARD)==1,'new plain 4 press uses pocket item')
 keys={};value(ButtonAction.ACTION_ITEM);keys[Keyboard.KEY_SPACE]=true
 assert(value(ButtonAction.ACTION_ITEM)==1,'Space still invokes native active-item handling')
 for _,binding in ipairs({{Keyboard.KEY_SPACE,ButtonAction.ACTION_ITEM},{Keyboard.KEY_4,ButtonAction.ACTION_PILLCARD},{Keyboard.KEY_G,ButtonAction.ACTION_BOMB}}) do
  reset();drop();s=player.data.Samira;s.shopOpen=true;keys[binding[1]]=true
  assert(value(binding[2])==0);s.shopOpen=false
  assert(value(binding[2])==0,'closing a modal cannot use an item whose key was pressed inside it')
  keys={};value(binding[2]);keys[binding[1]]=true;assert(value(binding[2])==1)
 end
 for _,code in ipairs({Keyboard.KEY_LEFT_CONTROL,Keyboard.KEY_RIGHT_CONTROL,Keyboard.KEY_4,Keyboard.KEY_1,Keyboard.KEY_TAB,Keyboard.KEY_SPACE,Keyboard.KEY_G}) do
  C.restore(player,{bindings={q=code}});assert(C.key(player,'q')==Keyboard.KEY_Q,'reserved saved binding must fall back safely')
 end
 reset();drop();s=player.data.Samira
 local originalButton,originalTrigger=Input.IsButtonPressed,Input.IsButtonTriggered;local buttons={}
 player.ControllerIndex=1
 Input.IsButtonPressed=function(code,index)if index==1 then return buttons[code]==true end;return originalButton(code,index) end
 Input.IsButtonTriggered=Input.IsButtonPressed
 keys[Keyboard.KEY_Q]=true;keys[Keyboard.KEY_LEFT_CONTROL]=true
 assert(not C.down(player,'q') and not C.upgrade(player),'keyboard cannot control the gamepad player')
 buttons[12]=true;assert(drop()==0 and C.down(player,'r'),'RT remains R and cannot invoke native drop')
 buttons={};buttons[10]=true;buttons[7]=true
 assert(drop()==1 and value(ButtonAction.ACTION_PILLCARD)==0,'L3+Y drops/swaps without using the card')
 buttons[10]=nil;assert(drop()==0 and value(ButtonAction.ACTION_PILLCARD)==0,'release L3 first cannot consume Y pocket')
 buttons={};value(ButtonAction.ACTION_PILLCARD);buttons[7]=true
 assert(value(ButtonAction.ACTION_PILLCARD)==1)
 buttons={};value(ButtonAction.ACTION_ITEM);buttons[10]=true;buttons[6]=true
 assert(value(ButtonAction.ACTION_BOMB)==1 and value(ButtonAction.ACTION_ITEM)==0,'L3+X bomb does not use active')
 buttons[10]=nil;assert(value(ButtonAction.ACTION_ITEM)==0,'modifier release cannot turn bomb into active use')
 buttons={};value(ButtonAction.ACTION_ITEM);buttons[6]=true
 assert(value(ButtonAction.ACTION_ITEM)==1 and value(ButtonAction.ACTION_BOMB)==0)
 Input.IsButtonPressed=originalButton;Input.IsButtonTriggered=originalTrigger;player.ControllerIndex=0
 reset();player.type=1
 for _,action in ipairs({ButtonAction.ACTION_DROP,ButtonAction.ACTION_ITEM,ButtonAction.ACTION_PILLCARD,ButtonAction.ACTION_BOMB,ButtonAction.ACTION_MAP}) do
  assert(value(action)==nil,'non-Samira controls remain entirely native')
 end
 reset()
 print('Native Ctrl tap/hold, modifier cancellation, modal release safety, native item routing, reserved bindings and controller isolation passed')
end

do
 local E=include('scripts.samira_equipment');local H=include('scripts.samira_health')
 local P=include('scripts.samira_progression');local C=include('scripts.samira_controls')
 local capture=callbacks[ModCallbacks.MC_POST_GLOWING_HOURGLASS_SAVE]
 local pre=callbacks[ModCallbacks.MC_PRE_GLOWING_HOURGLASS_LOAD]
 local post=callbacks[ModCallbacks.MC_POST_GLOWING_HOURGLASS_LOAD]
 local function near(a,b)assert(math.abs(a-b)<1e-7,tostring(a)..' ~= '..tostring(b))end
 reset();callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false);tick()
 P.restore(player,{level=6,xp=123,skills={q=2,e=2,r=1},passiveRemaining=321})
 H.levelUp(player)
 local g=E.state(player);g.slots[1]={id=1055,count=1,ready=99,charges=2};g.time=140
 g.shojin=3;g.shojinUntil=290;g.debt=12.125;g.debtUntil=210;g.cooldowns.test=400
 E.syncHealth(player);local h=H.state(player);h.hp=367.125;h.soul=42.5;H.sync(player)
 local s=player.data.Samira;s.clock=100;s.qReady=190;s.rUntil=220;s.rRank=1;s.rHasteAt=95
 s.rStartedAt=90;s.weapon=true;s.face=Vector(1,0)
 player.coins=22;capture(nil,0)
 local baseMax=H.max(player);local baseAD=E.sum(player).ad
 local native={red=player.red,soul=player.soul,containers=player.addedContainers,coins=player.coins}
 -- Mutate both nested data and the newest disk save after the checkpoint.
 P.award(player,3000);P.upgrade(player,'w');g.slots[1].id=3071;g.cooldowns.test=900
 g.shojin=4;g.debt=88.75;h.hp=17;s.clock=900;s.qReady=1200;s.rUntil=0
 s.cast={kind='Q1',face=Vector(1,0)};s.fx={{age=1}};s.noCD=true;s.indicators='off'
 C.state(player).mode='wasd';callbacks[ModCallbacks.MC_POST_NEW_ROOM]()
 local latest=persisted
 pre(nil,0);assert(H.state(player).syncing and E.state(player).syncing)
 player:AddHearts(1);near(h.hp,17) -- native load operations must not award healing
 callbacks[ModCallbacks.MC_POST_UPDATE]();assert(s.clock==900,'simulation is suspended during engine restoration')
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();assert(persisted==latest,'intermediate native restore cannot overwrite disk data')
 -- The engine owns native inventory/coins. A recreated Lua entity data table is safe.
 player.data={};player.red=native.red;player.soul=native.soul;player.addedContainers=native.containers;player.coins=native.coins
 post(nil,0)
 s=player.data.Samira;g=E.state(player);h=H.state(player)
 assert(P.state(player).level==6 and P.state(player).xp==123 and P.rank(player,'q')==2 and P.rank(player,'w')==0)
 assert(P.state(player).passiveRemaining==321 and s.qReady==190 and s.clock==100)
 assert(g.slots[1].id==1055 and g.slots[1].ready==99 and g.slots[1].charges==2)
 assert(g.cooldowns.test==400 and g.shojin==3 and g.shojinUntil==290 and g.time==140)
 near(g.debt,12.125);near(h.hp,367.125);near(h.soul,42.5);near(H.max(player),baseMax);near(E.sum(player).ad,baseAD)
 assert(g.gold==22 and s.ultimateFlight and player.CanFly,'native coins and restored ultimate flight agree')
 assert(not s.cast and #s.fx==0 and not s.target and not h.syncing and not g.syncing)
 assert(s.noCD and s.indicators=='off' and C.state(player).mode=='wasd','preferences are not rolled back')
 -- Repeated loads must not consume/mutate the checkpoint itself.
 g.slots[1].id=3071;h.hp=1;pre(nil,0);post(nil,0)
 assert(E.state(player).slots[1].id==1055);near(H.current(player),367.125)
 -- A separate slot is restored independently and persists across save/continue.
 P.state(player).xp=222;H.state(player).hp=444.25;player.data.Samira.rUntil=0;capture(nil,1)
 callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true);player.data={}
 callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,true)
 pre(nil,0);post(nil,0);assert(P.state(player).xp==123);near(H.current(player),367.125)
 pre(nil,1);post(nil,1);assert(P.state(player).xp==222);near(H.current(player),444.25)
 assert(not player.CanFly,'expired ultimate flight does not survive rewind')
 -- Fresh runs cannot use a previous run's checkpoint.
 callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false);near(P.attackMultiplier(player),.8)
 local current=H.current(player);pre(nil,0);post(nil,0);near(H.current(player),current)
 assert(not H.state(player).syncing and not E.state(player).syncing,'missing legacy snapshot cannot leave sync guards stuck')
 callbacks[ModCallbacks.MC_PRE_GAME_EXIT](nil,true)
 capture(nil,2);callbacks[ModCallbacks.MC_POST_GAME_STARTED](nil,false)
 P.state(player).xp=99;pre(nil,2);post(nil,2);assert(P.state(player).xp==0,'early native checkpoint is initialized after new-run setup')
 reset()
 print('Native rewind slots, deep snapshots, XP/skills/gear/HP/fractional debt/cooldowns, engine-load guards, repeat/continue/new-run isolation passed')
end

-- World Ender must not discard the move order or immobilize its activation.
do
 reset();mouse=Vector(700,100);right=true;tick();right=false
 local s=player.data.Samira;local goal=s.goal;local speed=player.Velocity:Length()
 keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
 assert(s.goal==goal and not s.cast and s.weaponMotion.kind=='RStart')
 assert(player.Velocity:Length()>speed and player.CanFly,'R movement boost and flight apply on the activation tick')
 local deadline=s.rUntil;local cooldown=s.rReady
 ackMode='ready';external.toggle(true);time=time+250;external.emit(player,s,false)
 local wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.kind=='RStart' and wire.locomotion.kind=='RWalk' and not wire.looping and wire.ultimate)
 assert(wire.r.started==s.rStartedAt and wire.r.untilTick==deadline and not wire.cast,'R effects keep their own timeline without a blocking cast')
 for i=1,49 do tick();assert(player.Velocity.X>0,'activation never stops the existing mouse move order') end
 assert(not s.weaponMotion and s.rUntil==deadline and s.rReady==cooldown,'cosmetic animation does not change buff duration or cooldown')
 reset();tick();s=player.data.Samira;keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
 assert(s.weaponMotion.kind=='RStart' and player.Velocity:Length()==0,'stationary activation keeps the full gesture')
 mouse=Vector(700,100);right=true;tick();right=false;assert(player.Velocity.X>0,'new movement works during activation')
 for _,key in ipairs({Keyboard.KEY_Q,Keyboard.KEY_W,Keyboard.KEY_E,Keyboard.KEY_A}) do
  reset();mouse=Vector(500,100);keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
  s=player.data.Samira;keys[key]=true;tick()
  assert(not s.weaponMotion and (s.cast or s.dash),'attacks and skills can replace the activation gesture')
  assert(A.ultimate(s),'interrupting only the gesture cannot cancel R')
 end
 reset();local C=include('scripts.samira_controls');C.state(player).mode='wasd'
 keys[Keyboard.KEY_D]=true;tick();keys[Keyboard.KEY_C]=true;tick();keys[Keyboard.KEY_C]=false
 assert(player.Velocity.X>0 and player.data.Samira.weaponMotion.kind=='RStart','WASD movement continues through R')
 reset();e=mob(700,100);entities={e};mouse=e.Position;right=true;tick();right=false
 s=player.data.Samira;keys[Keyboard.KEY_R]=true;tick();keys[Keyboard.KEY_R]=false
 assert(s.target==e and player.Velocity.X>0,'activation preserves enemy chase orders')
 reset()
 print('R activation: uninterrupted mouse/WASD movement, chase, immediate haste, original upper-body gesture with RWalk, and attack/skill followups passed')
end

do
 reset();local music=MusicManager();local audio=include('scripts.samira_audio')
 music:Play(21);music:Queue(22);keys[Keyboard.KEY_R]=true;tick();keys={}
 local s=player.data.Samira;local count=music.plays
 s.rUntil=s.clock+500;tick(20)
 assert(music.current==200 and music.plays==count,'extending R continues the same music playback')
 paused=true;tick(20);paused=false;assert(music.plays==count,'pause cannot restart the background track')
 audio.cleanup();assert(music.current==21 and music.queued==22,'cleanup restores original music and its queued successor')
 tick();assert(music.current==200,'restored active ultimate can reacquire music')
 nativeAnimation='Trapdoor';extraFinished=false;tick();assert(music.current==21,'native cutscene releases R music')
 nativeAnimation='Idle';extraFinished=true;tick();assert(music.current==200)
 music:Queue(25);s.rUntil=s.clock;tick();assert(music.current==21 and music.queued==25,'a newly queued track is not lost')
 music:Play(30);keys[Keyboard.KEY_R]=true;s.rReady=0;tick();keys={}
 player.type=999;tick();assert(music.current==30,'changing character releases music ownership')
 reset();music:Play(1);music:Queue(1)
 print('R background music: queue preservation, extension, pause, scene/character cleanup and resumption passed')
end

-- A rewind must receive an actually visible frame from its new room before takeover.
do
 reset();tick();time=time+2500
 local originalLoad=Isaac.LoadModDataFromFolder
 local ackRoom,ackVisible
 Isaac.LoadModDataFromFolder=function()
  return codec.encode({version=1,session=external.session,time=time,ready=true,
   visible=ackVisible,hudVisible=true,room=ackRoom,capabilities={hud=1}})
 end
 external.toggle(true);ackRoom=external.room;ackVisible=true;external.poll()
 assert(external.replaces(false))
 external.newRoom(true)
 time=time+60;external.poll()
 assert(not external.replaces(false),'old room visible ACK cannot claim the rewound actor')
 local before=#spriteDraws
 callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws>before and spriteDraws[before+1].path=='gfx/samira/fallback.anm2','rewind waits with compact native Samira')
 assert(external.hud(false),'actor recovery does not release the HUD')
 ackRoom=external.room;ackVisible=false;time=time+60;external.poll()
 assert(not external.replaces(false),'new room ready but hidden is not a displayed actor')
 ackVisible=true;time=time+60;external.poll()
 assert(external.replaces(false),'first displayed new-room frame ends recovery')
 before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws==before,'no native duplicate after new scene takeover')
 ackVisible=false;time=time+60;external.poll()
 before=#spriteDraws;callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws>before,'confirmed hidden renderer cannot leave an empty player')
 external.start();before=#spriteDraws
 callbacks[ModCallbacks.MC_PRE_PLAYER_RENDER](nil,player,Vector.Zero)
 assert(#spriteDraws>before,'startup concealment uses the game-layer fallback too')
 Isaac.LoadModDataFromFolder=originalLoad;external.toggle(false);time=time+2500;reset()
 print('Rewind stale-room/hidden/visible handoff, persistent HUD and native fade fallback passed')
end

-- Right-click attacks retain the committed victim, including empowered thrusts.
do
 local P=include('scripts.samira_passive')
 for _,empowered in ipairs({false,true}) do
  for _,outcome in ipairs({'moved','dead','removed','invulnerable','rejected'}) do
   reset();if not empowered then progress.state(player).passiveRemaining=900 end
   local target=mob(135,100);entities={target};mouse=target.Position;right=true;tick();right=false
   local s=player.data.Samira;local cast=s.cast
   assert(cast and cast.target==target and not cast.cone and cast.passive==empowered)
   local other=mob(120,100);entities={other,target};wall=true
   -- Both the mouse and victim cross outside the original strike geometry.
   target.Position=Vector(65,245);mouse=Vector(400,50)
   if outcome=='dead' then function target:IsDead()return true end
   elseif outcome=='removed' then entities={other};function target:Exists()return false end
   elseif outcome=='invulnerable' then function target:IsVulnerableEnemy()return false end
   elseif outcome=='rejected' then function target:TakeDamage()return false end end
   tick(cast.impact-cast.age)
   assert(target.hits==(outcome=='moved' and 1 or 0),'committed right-click contact: '..outcome)
   assert(other.hits==0,'no retarget or additional target on a committed strike')
   if outcome=='moved' then
    assert(cast.face:Distance((target.Position-player.Position):Normalized())<.001,'windup faces its locked victim')
    if empowered then assert(P.remaining(player)==P.total(player),'confirmed passive hit consumes cooldown exactly once') end
   elseif empowered then
    assert(P.ready(player),'invalid or rejected victim cannot consume passive')
   end
  end
 end
 reset()
 print('Right-click basic/passive guaranteed moving-target contact, tracking, single victim and invalid-target guards passed')
end

-- Locked attacks recover transient contact rejection without another swing.
do
 local P=include('scripts.samira_passive')
 for _,empowered in ipairs({false,true}) do
  for _,outcome in ipairs({'rejected','invulnerable','not-enumerated','permanent','removed'}) do
   reset();if not empowered then progress.state(player).passiveRemaining=900 end
   local target=mob(135,100);entities={target};mouse=target.Position;right=true;tick();right=false
   local s=player.data.Samira;local cast=s.cast;local ready=s.attackReady
   local other=mob(120,100);entities={other,target}
   local attempts=0;local accept=false;local damage=target.TakeDamage
   function target:TakeDamage(amount)
    attempts=attempts+1
    if outcome~='not-enumerated' and not accept then return false end
    return damage(self,amount)
   end
   if outcome=='invulnerable' then function target:IsVulnerableEnemy()return accept end
   elseif outcome=='removed' then function target:Exists()return false end
   elseif outcome=='not-enumerated' then entities={other} end
   tick(cast.impact-cast.age)
   assert(target.hits==(outcome=='not-enumerated' and 1 or 0),'first contact outcome: '..outcome)
   if empowered and outcome~='not-enumerated' then assert(P.ready(player),'failed contact must preserve passive') end
   tick();accept=outcome~='permanent' and outcome~='removed'
   tick(cast.duration-cast.age)
   local expected=accept and 1 or 0
   assert(target.hits==expected and other.hits==0,'bounded retry must hit its committed victim exactly once: '..outcome)
   assert(s.cast==nil and s.attackReady==ready,'retry never extends recovery or changes attack speed')
   if empowered then assert(P.ready(player)==(expected==0),'passive consumed only on accepted contact') end
   if outcome=='removed' then assert(attempts==0,'removed entity cannot receive damage') end
  end
 end
 -- Free attacks retain their single contact tick, even if damage is refused.
 reset();progress.state(player).passiveRemaining=900
 local target=mob(130,100);entities={target};mouse=target.Position
 local attempts=0;function target:TakeDamage()attempts=attempts+1;return false end
 keys[Keyboard.KEY_A]=true;tick();keys[Keyboard.KEY_A]=false
 local cast=player.data.Samira.cast;assert(cast and not cast.target)
 tick(cast.duration-cast.age);assert(attempts==1,'free A attacks must not gain retries')
 reset();target=mob(135,100);entities={target};mouse=target.Position;right=true;tick();right=false
 local s=player.data.Samira;cast=s.cast;attempts=0
 function target:TakeDamage()attempts=attempts+1;return false end
 tick(cast.impact-cast.age);assert(attempts==1)
 mouse=Vector(300,100);keys[Keyboard.KEY_E]=true;tick();keys={}
 assert(s.dash and not s.cast and s.attackReady==s.clock,'E still cancels pending contact and resets attacks')
 tick(2);assert(attempts==1,'canceled contact cannot retry during E')
 reset()
 print('Locked basic/passive transient rejection, immunity, missing enumeration, bounded retries and free-attack isolation passed')
end

-- Flight grants the ultimate stance, without claiming the actual R buff/scale.
do
 reset();tick();local s=player.data.Samira
 external.toggle(true);player.CanFly=true;s.weapon=false;s.bannerVisible=false
 local function packet()
  time=time+250;external.emit(player,s,false)
  return codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 end
 local data=packet();assert(data.flying and not data.ultimate and data.kind=='RIdle')
 local scale=data.bodyScale
 player.Velocity=Vector(2,0);s.weaponMotion={kind='Sheathe',age=1,duration=30}
 data=packet();assert(data.kind=='RWalk' and not data.locomotion,'flight does not fall back into sheathed walking')
 s.weaponMotion=nil;s.cast={kind='Q2',stage=2,face=Vector(1,0),age=1,impact=18,duration=24}
 data=packet();assert(data.kind=='RQ2' and not data.ultimate,'flying casts use original ultimate motions without R gameplay')
 s.cast=nil;s.rUntil=s.clock+100;data=packet()
 assert(data.ultimate and data.flying and data.bodyScale[1]==scale[1] and data.bodyScale[2]==scale[2])
 s.rUntil=0;data=packet();assert(data.kind=='RWalk' and not data.ultimate,'item flight survives R expiry at normal size')
 player.CanFly=false;data=packet();assert(not data.flying and data.kind=='SheathedWalk','losing flight restores the normal stance')
 external.toggle(false);reset()
 print('Native flight idle/walk/Q, sheathing isolation, real R flag and flight removal passed')
end

-- Flying routes and landings accept rocks/objects/pits, but not actual walls.
do
 local T=include('scripts.samira_terrain')
 for _,collision in ipairs({1,2,3}) do
  reset();player.CanFly=true;wall=true
  collisionOverride=function(i)return i%20==4 and collision or 0 end
  local target=Vector(180,100)
  assert(T.walkable(room,player,44) and T.clear(room,player,target))
  assert(T.lineClear(room,player,player.Position,target),'flight ignores ground-only obstruction')
  mouse=target;right=true;tick();right=false;tick(40)
  assert(player.Position:Distance(target)<5,'right-click can stop on a flying-passable obstacle')
  assert(math.abs(player.Position.Y-100)<.001,'flight does not detour around the obstacle')
 end
 reset();wall=true;mouse=Vector(180,100);right=true;tick();right=false
 local s=player.data.Samira;local oldPath=s.path;assert(oldPath and not s.pathFlying)
 player.CanFly=true;tick();assert(s.path==nil and s.pathFlying,'gaining flight discards the ground route')
 player.CanFly=false;tick();assert(s.path and not s.pathFlying,'losing flight rebuilds a ground route')
 reset();player.CanFly=true;wall=true
 collisionOverride=function(i)return i%20==4 and GridCollisionClass.COLLISION_WALL or 0 end
 assert(not T.lineClear(room,player,player.Position,Vector(250,100)))
 assert(not T.clear(room,player,Vector(180,100)))
 mouse=Vector(250,100);right=true;tick();right=false;tick(40)
 assert(player.Position.X<160,'flight pathfinding cannot cross a solid wall')
 assert(not T.lineClear(room,player,player.Position,Vector(-40,100)),'room bounds still block flight')
 reset();tick();player.CanFly=true;wall=true;s=player.data.Samira
 assert(T.begin(room,player,s,Vector(1,0),80))
 assert(s.dash.target:Distance(Vector(180,100))<.001,'flying E lands on the chosen rock instead of extending past it')
 while s.dash do T.update(room,player,s) end
 assert(player.Position:Distance(Vector(180,100))<.001 and player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_WALLS)
 reset();tick();s=player.data.Samira;assert(T.begin(room,player,s,Vector(1,0),80));player.CanFly=true;T.finish(player,s,false)
 assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_WALLS,'gaining flight during E cannot restore ground collision')
 reset();tick();player.CanFly=true;s=player.data.Samira;assert(T.begin(room,player,s,Vector(1,0),80));player.CanFly=false;T.finish(player,s,false)
 assert(player.GridCollisionClass==EntityGridCollisionClass.GRIDCOLL_GROUND,'losing flight during E restores ground collision')
 reset()
 print('Flying obstacle routes/targets, flight-mode path invalidation, walls/bounds and E landing/collision transitions passed')
end

do
 local H=include('scripts.samira_health');local E=include('scripts.samira_equipment')
 local G=include('scripts.samira_geometry')
 local function near(a,b)assert(math.abs(a-b)<1e-6,tostring(a)..' ~= '..tostring(b))end
 for level=1,18 do
  reset();progress.restore(player,{level=level})
  local st=progress.stats(player,{damage=10,interval=22})
  local growth=progress.growth(level);local baseline=progress.growth(3)
  local old=10+5*growth*.105;local start=10+5*baseline*.105
  near(st.damage,level<=3 and old or start+(old-start)/2)
  near(st.interval,math.max(5,22/(1+.025*growth)))
  near(progress.attackMultiplier(player),.8+.2*math.min(13,math.max(0,level-3))/13)
 end
 for rank=1,3 do near(select(3,A.modifiers({clock=0,rUntil=1,rRank=rank})),({1.4,1.6,1.8})[rank]) end
 -- Separate victims retain their own full strongest hit; invalid/rejected targets cannot heal.
 for _,mode in ipairs({'normal','reversed','rejected','overkill'}) do
  reset();tick();local s=player.data.Samira;H.state(player).hp=100
  local a,b=mob(270,100),mob(260,118);entities={a,b}
  if mode=='rejected' then function b:TakeDamage()return false end end
  if mode=='overkill' then a.HitPoints=1;b.HitPoints=1 end
  local faces={Vector(1,0):Rotated(-15),Vector(1,0),Vector(1,0):Rotated(15),Vector(1,0):Rotated(30)}
  if mode=='reversed' then faces={faces[4],faces[3],faces[2],faces[1]} end
  local st=progress.stats(player,G.stats(player.Damage,player.MaxFireDelay,player.TearRange,player.Luck,player.MoveSpeed))
  local base=st.damage*progress.attackMultiplier(player)*1.25
  local expectedHeal=0
  for _,victim in ipairs(entities) do
   local best,total=0,0
   for _,face in ipairs(faces) do
    local v=G.unproject(victim.Position-player.Position):Rotated(-face:GetAngleDegrees())
    local inside,sweet=G.hit(G.shape(1,st.scale),v.X,v.Y,victim.Size)
    if inside then local amount=base*(sweet and 1.6 or 1);best=math.max(best,amount);total=total+amount end
   end
   victim.expected=best+.5*(total-best)
   if not(mode=='rejected' and victim==b) then
    expectedHeal=expectedHeal+math.min(victim.expected,victim.HitPoints)*best/victim.expected/.105*.08
   end
  end
  s.cast={kind='Q1',stage=1,face=Vector(1,0),faces=faces,age=17,impact=18,duration=24};tick()
  near(a.total,a.expected);assert(a.hits==1)
  near(b.total,mode=='rejected' and 0 or b.expected)
  near(H.current(player),100+expectedHeal)
 end
 -- Equipment omnivamp also uses the strongest contact, but ordinary hits keep their full basis.
 reset();tick();local s=player.data.Samira;local g=E.state(player);g.hungerUntil=g.time+120
 H.state(player).hp=100
 include('scripts.samira_item_effects').hit(player,s,mob(170,100),21,true,10.5)
 near(H.current(player),110)
 include('scripts.samira_item_effects').hit(player,s,mob(170,100),21,true)
 near(H.current(player),130)
 reset()
 print('Post-level-three AD only, preserved attack scaling, R healing ranks, per-target multi-Q, strongest-hit healing, order/rejection/overkill and equipment vamp passed')
end

do
 local C=include('scripts.samira_controls')
 reset();tick();local s=player.data.Samira;playedSounds={};s.rReady=s.clock+5000
 audio.command(player,s,false,player.Position+Vector(200,0))
 assert(soundCount('vo_move_long')==1)
 tick(60);activeSounds[soundId('Samira vo_move_long')]=nil
 audio.observe(player,s);local ready=s.voiceReady
 assert(ready==s.clock+360,'12-second ambient gap starts at actual sample end, not the longest sample in the group')
 for i=1,359 do s.clock=s.clock+1;audio.command(player,s,false,player.Position+Vector(200,0)) end
 assert(soundCount('vo_move_long')==1,'held commands cannot overlap or bypass the gap')
 s.clock=ready;audio.command(player,s,false,player.Position+Vector(200,0))
 assert(soundCount('vo_move_long')==2,'a short sample no longer causes 34 seconds of silence')
 -- Finished peaceful speech must not be treated as still playing on combat entry.
 activeSounds[soundId('Samira vo_move_long')]=nil;audio.observe(player,s)
 entities={mob(400,100)};audio.observe(player,s);assert(soundCount('vo_attack')==0)
 s.clock=s.voiceReady;audio.command(player,s,false,mouse);assert(soundCount('vo_attack')==1)
 -- Exercise real movement paths, including continuous right-click and alternative controls.
 for _,mode in ipairs({'mouse','wasd','pad','freeAttack'}) do
  reset();playedSounds={};local oldAction=Input.GetActionValue
  if mode=='wasd' then C.state(player).mode='wasd';keys[Keyboard.KEY_D]=true
  elseif mode=='pad' then
   player.ControllerIndex=1
   Input.GetActionValue=function(action)return action==ButtonAction.ACTION_RIGHT and 1 or 0 end
  elseif mode=='freeAttack' then keys[Keyboard.KEY_A]=true
  else right=true end
  mouse=Vector(500,100);tick();s=player.data.Samira
  local name=mode=='freeAttack' and 'vo_attack' or 'vo_r_ready'
  assert(soundCount(name)==1,mode..' must trigger original speech')
  tick(10);assert(soundCount(name)==1,'playing speech is never restarted by held input')
  activeSounds[soundId('Samira '..(mode=='freeAttack' and s.lastAttackVoice or name))]=nil;tick(380)
  assert(soundCount(name)==2,mode..' resumes speech without releasing and pressing again')
  Input.GetActionValue=oldAction;player.ControllerIndex=0
 end
 reset();tick();s=player.data.Samira;playedSounds={}
 audio.cast(s,'r');local name=string.format('vo_r_%02d',s.lastRVoice)
 tick(400);audio.command(player,s,true,mouse);audio.cast(s,'q1')
 assert(activeSounds[soundId('Samira '..name)] and soundCount('vo_attack')==0 and soundCount('vo_q1')==0,'R retains priority while it is actually playing')
 activeSounds[soundId('Samira '..name)]=nil;tick(91)
 audio.command(player,s,true,mouse);assert(soundCount('vo_attack')==1,'completed R releases the voice channel')
 reset()
 print('Actual voice finish cooldown, no stale peaceful voice, held mouse/WASD/gamepad/free attack, non-overlap and R priority/release passed')
end

do
 local P=include('scripts.samira_passive');local originalDelay=player.MaxFireDelay
 player.MaxFireDelay=60
 for _,empowered in ipairs({false,true}) do
  reset();if not empowered then progress.state(player).passiveRemaining=900 end
  local victim=mob(140,100);entities={victim};mouse=victim.Position;right=true;tick();right=false
  local s=player.data.Samira;tick(s.cast.impact-s.cast.age)
  assert(victim.hits==1);local oldReady=s.attackReady;local passive=P.remaining(player)
  keys[Keyboard.KEY_E]=true;tick();keys={}
  assert(s.dash and not s.cast and s.attackReady==s.clock,'successful E cancels attack recovery and resets the timer')
  assert(P.remaining(player)==passive-1,'E does not reset the passive cooldown')
  tick(s.dash.duration-s.dash.age);tick()
  assert(s.cast and s.cast.kind=='Attack' and not s.cast.passive and s.clock<oldReady,'the next attack begins after E without waiting for the old attack interval')
  tick(s.cast.impact-s.cast.age);assert(victim.hits==2,'AA-E-AA produces exactly two contacts')
 end
 -- Canceling a windup has not landed a hit and cannot consume or duplicate a passive.
 reset();local victim=mob(140,100);entities={victim};mouse=victim.Position;right=true;tick();right=false
 local s=player.data.Samira;keys[Keyboard.KEY_E]=true;tick();keys={}
 assert(victim.hits==0 and P.ready(player) and not s.cast)
 tick(s.dash.duration-s.dash.age);tick();assert(s.cast.passive)
 tick(s.cast.impact-s.cast.age);assert(victim.hits==1 and not P.ready(player))
 for _,reason in ipairs({'cooldown','unlearned','tooClose','blocked'}) do
  reset();tick();s=player.data.Samira;mouse=Vector(140,100)
  s.cast={kind='Attack',age=0,impact=80,duration=100,face=Vector(1,0)};local cast=s.cast;s.attackReady=900
  if reason=='cooldown' then s.eReady=900
  elseif reason=='unlearned' then progress.state(player).skills.e=0
  elseif reason=='tooClose' then mouse=player.Position
  else collisionOverride=function()return GridCollisionClass.COLLISION_WALL end end
  keys[Keyboard.KEY_E]=true;tick();keys={}
  assert(not s.dash and s.cast==cast and s.attackReady==900,'failed E must not reset or cancel attacks: '..reason)
 end
 reset();mouse=Vector(300,100);keys[Keyboard.KEY_Q]=true;tick();keys={};s=player.data.Samira;local cast=s.cast
 keys[Keyboard.KEY_E]=true;tick();keys={}
 assert(s.dash and s.cast==cast and s.attackReady==s.clock,'QE keeps the active Q while resetting the basic attack timer')
 player.MaxFireDelay=originalDelay;reset()
 print('E attack reset: ordinary/passive AA-E-AA, canceled windup, no passive refresh, rejected casts and preserved QE passed')
end

do
 local names={'q1','q2','q3','w','e','r','death','joke','taunt','laugh','move','attack','kill','move_long','r_ready'}
 for _,language in ipairs({'zh','zh_CN','zh-TW','en','en_US','fr'}) do
  reset();tick();local s=player.data.Samira;Options.Language=language;playedSounds={}
  local prefix=language:find('zh',1,true) and 'vo_' or 'vo_en_'
  for _,name in ipairs(names) do
   audio.voiceStop(true);s.voiceReady=0;audio.voice(s,name,2)
   local key=name=='r' and string.format(prefix..'r_%02d',s.lastRVoice) or prefix..name
   assert(soundCount(key)==1,'correct language for '..language..' / '..name)
  end
 end
 reset();tick();local s=player.data.Samira;Options.Language='en';playedSounds={}
 audio.command(player,s,false,player.Position+Vector(50,0));assert(soundCount('vo_en_r_ready')==1)
 entities={mob(400,100)};audio.observe(player,s)
 assert(not activeSounds[soundId('Samira vo_en_r_ready')] and soundCount('vo_en_attack')==1,'English peaceful lines switch to combat on entering an uncleared room')
 audio.cast(s,'r');local rkey=string.format('vo_en_r_%02d',s.lastRVoice)
 callbacks[ModCallbacks.MC_POST_NEW_ROOM]();audio.cast(s,'q1');audio.voice(s,'death',5)
 assert(activeSounds[soundId('Samira '..rkey)] and soundCount('vo_en_q1')==0,'English R keeps absolute priority across rooms')
 Options.Language='zh';audio.command(player,s,true,mouse)
 assert(activeSounds[soundId('Samira '..rkey)] and soundCount('vo_attack')==0,'language selection does not interrupt the current R line')
 activeSounds[soundId('Samira '..rkey)]=nil;tick(91);audio.command(player,s,true,mouse)
 assert(soundCount('vo_attack')==1,'the next available line uses the newly selected language')
 audio.voiceStop(true);Options.Language='en';local seen={}
 s.rVoiceBag=nil
 for i=1,8 do
  audio.cast(s,'r');assert(not seen[s.lastRVoice]);seen[s.lastRVoice]=true
  assert(activeSounds[soundId(string.format('Samira vo_en_r_%02d',s.lastRVoice))]);audio.voiceStop(true)
 end
 audio.cleanup();assert(next(activeSounds)==nil,'both language sound IDs can be stopped cleanly')
 Options.Language='zh';reset()
 print('All 15 voice events in Chinese/English, locale variants, English combat/R priority, room continuity, language switching and all 8 R variants passed')
end

do
 local E=include('scripts.samira_equipment');local S=include('scripts.samira_shop');local F=include('scripts.samira_item_effects');local H=include('scripts.samira_health')
 local function fresh()
  reset();tick();player.coins=99;E.syncCoins(player);player.data.Samira.cast=nil;player.data.Samira.dash=nil;player.Velocity=Vector.Zero
  H.sync(player);return E.state(player),H.state(player)
 end
 local g,h=fresh();local startHP=h.hp
 assert(not E.canUndo(player) and not E.undo(player,true))
 assert(E.buy(player,1036,true) and E.buy(player,1036,true))
 assert(E.buy(player,3133,true) and E.has(player,3133) and E.canUndo(player))
 assert(E.undo(player,true) and player:GetNumCoins()==75 and E.sum(player).ad==20)
 assert(g.slots[1].id==1036 and g.slots[2].id==1036,'undo crafting restores duplicate ingredients in original slots')
 assert(E.undo(player,true) and player:GetNumCoins()==87 and E.sum(player).ad==10)
 assert(E.undo(player,true) and player:GetNumCoins()==99 and E.sum(player).ad==0 and not E.canUndo(player))
 assert(H.current(player)==startHP,'trade cycles cannot heal')
 g,h=fresh();assert(E.buy(player,1028,true));h.hp=H.max(player);H.sync(player);local beforeSale=h.hp
 assert(E.sell(player,1,true) and H.current(player)<beforeSale)
 assert(E.undo(player,true) and H.current(player)==beforeSale and E.has(player,1028),'undo max-HP sale restores the exact pre-sale HP')
 g,h=fresh();assert(E.buy(player,1036,true));E.addGold(player,99)
 assert(E.sell(player,1,true) and player:GetNumCoins()==99)
 assert(E.undo(player,true) and player:GetNumCoins()==99 and E.has(player,1036),'capped sale refunds actual gold rather than subtracting listed proceeds')
 g,h=fresh();assert(E.buy(player,1036,true));tick(10);assert(E.canUndo(player),'idle frames must retain the receipt');assert(not E.buy(player,3157,true));assert(E.canUndo(player),'failed purchase preserves last valid receipt')
 assert(not E.sell(player,nil,true));assert(E.canUndo(player));assert(E.undo(player,true))
 for _,reason in ipairs({'move','coins','health','combat','cast','active','room','restore','inventory'}) do
  g,h=fresh();assert(E.buy(player,1036,true))
  if reason=='move' then player.Position=player.Position+Vector(1,0)
  elseif reason=='coins' then E.addGold(player,1)
  elseif reason=='health' then H.damage(player,1)
  elseif reason=='combat' then assert(not E.undo(player,false))
  elseif reason=='cast' then F.cast(player,player.data.Samira,'q')
  elseif reason=='active' then callbacks[ModCallbacks.MC_USE_ITEM](nil,33,nil,player)
  elseif reason=='room' then E.room(player,true)
  elseif reason=='restore' then E.restore(player,E.save(player))
  elseif reason=='inventory' then g.slots[2]={id=1042,count=1,ready=0,charges=0} end
  assert(not E.canUndo(player),'gameplay must commit receipts: '..reason)
 end
 -- Native sale undo restores exactly one copy and rebuilds stats/familiars.
 local oldConfig=Isaac.GetItemConfig;local oldEvaluate=player.EvaluateItems
 ItemType={ITEM_ACTIVE=3};local owned={};local restores=0;local familiars=0
 Isaac.GetItemConfig=function()return {GetCollectible=function(_,id)if id==1 then return {Name='Test familiar',Type=1,Quality=3} end end,GetCollectibles=function()return {Size=2} end}end
 function player:GetCollectibleNum(id)return owned[id] or 0 end
 function player:RemoveCollectible(id)owned[id]=(owned[id] or 0)-1 end
 function player:AddCollectible(id,charge,first)assert(first==false,'undo must not trigger first-pickup rewards');owned[id]=(owned[id] or 0)+1;restores=restores+1 end
 function player:EvaluateItems()familiars=owned[1] or 0 end
 g,h=fresh();owned[1]=2;E.syncInventory(player);E.refreshNative(player)
 assert(E.sell(player,1,true) and familiars==1);assert(E.undo(player,true) and owned[1]==2 and familiars==2 and restores==1)
 assert(g.slots[1].id==-1 and g.slots[2].id==-1 and not E.canUndo(player))
 player.GetCollectibleNum=nil;player.RemoveCollectible=nil;player.AddCollectible=nil;player.EvaluateItems=oldEvaluate;Isaac.GetItemConfig=oldConfig;E.items[-1]=nil
 -- Draw and input share a Lua-authored grid and recipe-node payload.
 g,h=fresh();local cells=S.grid();assert(#cells==28)
 local ids={};for _,cell in ipairs(cells) do assert(not ids[cell.id]);ids[cell.id]=true;assert(cell.x+28<320 and cell.y+36<308) end
 local nodes=S.tree(3084);local belts=0;for _,n in ipairs(nodes) do if n.id==1011 then belts=belts+1 end;assert(n.x>=322 and n.x+n.size<=526) end;assert(belts==2)
 local s=player.data.Samira;s.shopOpen=true;s.shopClick=false;s.shopSelected=1036
 assert(E.buy(player,1036,true));local l=S.layout(640,360);left=true
 S.update(s,Vector(l.x+350*l.scale,l.y+345*l.scale),640,360,true,player,room);left=false
 assert(s.shopChanged and not E.has(player,1036) and player:GetNumCoins()==99,'Undo button uses the new footer hitbox')
 reset();print('Shop undo: multi-step crafting, duplicate materials, exact capped coins/HP, native ownership and familiars, failed trades, gameplay invalidation and new layout input passed')
end

do
 for _,language in ipairs({'zh','en'}) do
  reset();tick();Options.Language=language;local s=player.data.Samira
  local prefix=language=='zh' and 'vo_' or 'vo_en_';playedSounds={};s.rReady=s.clock+9999
  entities={mob(400,100)};audio.command(player,s,false,mouse)
  assert(activeSounds[soundId('Samira '..s.lastAttackVoice)])
  entities={};audio.observe(player,s)
  assert(not activeSounds[soundId('Samira '..s.lastAttackVoice)],'clearing a room releases ambient combat speech')
  s.clock=s.voiceReady;audio.command(player,s,false,player.Position+Vector(50,0))
  assert(soundCount(prefix..'move')==1,'cleared rooms resume peaceful movement lines')
  entities={mob(400,100)};audio.observe(player,s)
  assert(activeSounds[soundId('Samira '..s.lastAttackVoice)],'entering a new fight still switches to combat')
  entities={};callbacks[ModCallbacks.MC_POST_NEW_ROOM]();audio.observe(player,s)
  assert(not activeSounds[soundId('Samira '..s.lastAttackVoice)],'room-preserved combat voice cannot leak into an already cleared room')
  s.clock=s.voiceReady;s.rUntil=s.clock+450
  audio.command(player,s,false,player.Position+Vector(50,0))
  assert(activeSounds[soundId('Samira '..prefix..'move')],'active R alone does not make an empty room a battle')
  audio.voiceStop(true);s.clock=s.voiceReady;audio.command(player,s,true,mouse);audio.observe(player,s)
  assert(activeSounds[soundId('Samira '..s.lastAttackVoice)],'deliberate A attacks retain their response without being cut every tick')
  entities={mob(400,100)};audio.cast(s,'r');local rkey=string.format(prefix..'r_%02d',s.lastRVoice)
  entities={};audio.observe(player,s);callbacks[ModCallbacks.MC_POST_NEW_ROOM]();audio.observe(player,s)
  assert(activeSounds[soundId('Samira '..rkey)],'clearing rooms must never interrupt the ultimate voice')
  audio.voiceStop(true);audio.cast(s,'q1');audio.observe(player,s)
  assert(activeSounds[soundId('Samira '..prefix..'q1')],'skill voices are independent of ambient combat state')
 end
 Options.Language='zh';reset()
 print('Chinese/English combat speech: clear/room exit, renewed combat, R in cleared rooms, explicit attack responses and R/skill priority passed')
end

do
 for _,language in ipairs({'zh','en'}) do
  reset();tick();Options.Language=language;local s=player.data.Samira
  local prefix=language=='zh' and 'vo_' or 'vo_en_';playedSounds={}
  entities={mob(400,100)};audio.observe(player,s)
  assert(soundCount(prefix..'boss')==0,'ordinary enemies cannot trigger a story-boss line')
  entities[1].Type=EntityType.ENTITY_MEGA_SATAN;s.clock=s.clock+15
  player.ControlsEnabled=false;audio.observe(player,s)
  assert(soundCount(prefix..'boss')==0,'wait for the intro to release player controls')
  player.ControlsEnabled=true;audio.cast(s,'r');audio.observe(player,s)
  assert(soundCount(prefix..'boss')==0,'an existing R line retains absolute priority')
  activeSounds={};audio.observe(player,s)
  assert(soundCount(prefix..'boss')==1,'queued intro starts as soon as R ends')
  audio.cast(s,'q1');audio.command(player,s,true,mouse);audio.observe(player,s)
  assert(activeSounds[soundId('Samira '..prefix..'boss')],'ordinary skills and movement cannot interrupt the boss quote')
  audio.cast(s,'r');audio.observe(player,s);activeSounds={};audio.observe(player,s)
  assert(soundCount(prefix..'boss')==2,'R-interrupted boss dialogue is retried')
  activeSounds={};audio.observe(player,s)
  entities[1].Type=EntityType.ENTITY_MEGA_SATAN_2;s.clock=s.clock+30;audio.observe(player,s)
  assert(soundCount(prefix..'boss')==2,'phase two does not repeat the completed quote')
  callbacks[ModCallbacks.MC_POST_NEW_ROOM]();audio.observe(player,s)
  assert(soundCount(prefix..'boss')==2,'returning to the same encounter does not repeat the quote')
  bossRoomSeed=2;callbacks[ModCallbacks.MC_POST_NEW_ROOM]();entities={};audio.observe(player,s)
  entities={mob(400,100)};entities[1].Type=EntityType.ENTITY_DOGMA;s.clock=s.clock+15;audio.observe(player,s)
  assert(soundCount(prefix..'boss')==3,'delayed boss spawn in a new room is recognized')
 end
 for _,name in ipairs({'ENTITY_MOM','ENTITY_MOMS_HEART','ENTITY_ISAAC','ENTITY_SATAN','ENTITY_THE_LAMB',
  'ENTITY_MEGA_SATAN','ENTITY_MEGA_SATAN_2','ENTITY_HUSH','ENTITY_DELIRIUM','ENTITY_ULTRA_GREED','ENTITY_MOTHER','ENTITY_DOGMA','ENTITY_BEAST'}) do
  reset();tick();playedSounds={};entities={mob(400,100)};entities[1].Type=EntityType[name]
  player.data.Samira.clock=player.data.Samira.clock+15;audio.observe(player,player.data.Samira)
  assert(soundCount('vo_en_boss')==1,name..' must trigger the exact boss quote')
 end
 Options.Language='zh';reset()
 print('Bilingual boss dialogue: exact event, major bosses, delayed spawn, intro wait, R priority/retry, phase and room deduplication passed')
end

do
 local H=include('scripts.samira_health');reset();tick();local h=H.state(player)
 local s=player.data.Samira;s.clock=45
 H.queue(player,10,false,0,nil,1)
 assert(s.screenHitAt==nil,'queued/rejected damage must not flash the screen')
 H.commit(player);assert(s.screenHitAt==45,'accepted damage publishes a deterministic hit time')
 s.clock=60;H.heal(player,10);assert(s.screenHitAt==45,'healing does not retrigger screen damage')
 h.hp=100.25;h.soul=20.5;H.sync(player);local maximum=H.max(player)
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal 100')
 assert(H.current(player)==200.25 and h.soul==20.5 and H.max(player)==maximum,'heal command adds numeric HP without changing capacity or shields')
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal')
 assert(H.current(player)==maximum and h.soul==20.5,'bare heal restores exactly full health')
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal 999999')
 assert(H.current(player)==maximum,'healing cannot exceed maximum')
 h.hp=100;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal -100');assert(h.hp==100)
 player.type=1;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal');assert(h.hp==100,'other characters are untouched')
 player.type=10;dead=true;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','heal');assert(h.hp==100,'heal does not resurrect a dead player')
 reset();print('Numeric heal command: amount/full/cap, shields, invalid input, other characters and death passed')
end

do
 for _,language in ipairs({'zh','en'}) do
  local prefix=language=='zh' and 'vo_' or 'vo_en_'
  for _,line in ipairs({'move','move_long','r_ready','attack','kill','joke','taunt','boss'}) do
   reset();tick();Options.Language=language;local s=player.data.Samira
   playedSounds={};s.voiceReady=0
   assert(audio.voice(s,line,0,6));local ready=s.voiceReady
   for _,cast in ipairs({'q1','q2','q3','w','e'}) do
    audio.cast(s,cast)
    assert(activeSounds[soundId('Samira '..(line=='attack' and s.lastAttackVoice or prefix..line))],line..' must survive '..cast..' effort')
    assert(soundCount(prefix..cast)==0,'blocked efforts must not overlap dialogue')
    assert(soundCount(cast..'_cast')==1,'physical skill sound still plays')
    assert(s.voiceReady==ready,'skipped efforts must not extend the dialogue gap')
   end
   activeSounds[soundId('Samira '..(line=='attack' and s.lastAttackVoice or prefix..line))]=nil
   audio.observe(player,s)
   for _,cast in ipairs({'q1','q2','q3','w','e'}) do
    assert(soundCount(prefix..cast)==0,'skipped efforts must not replay after dialogue finishes')
   end
  end
  reset();tick();Options.Language=language;local s=player.data.Samira
  playedSounds={};s.voiceReady=s.clock+180;local ready=s.voiceReady
  audio.cast(s,'e')
  assert(soundCount(prefix..'e')==1,'efforts remain audible when no dialogue is playing')
  assert(s.voiceReady==ready,'starting an effort must preserve the existing dialogue cooldown')
  s.clock=s.clock+10;activeSounds[soundId('Samira '..prefix..'e')]=nil;audio.observe(player,s)
  assert(s.voiceReady==ready,'finishing an effort must neither extend nor bypass the dialogue cooldown')
  s.clock=ready;audio.cast(s,'q1');audio.command(player,s,true,mouse)
  assert(activeSounds[soundId('Samira '..s.lastAttackVoice)] and not activeSounds[soundId('Samira '..prefix..'q1')],
   'ready dialogue takes precedence over an already playing effort')
  audio.cast(s,'r');local rkey=string.format(prefix..'r_%02d',s.lastRVoice)
  audio.cast(s,'e');audio.voice(s,'boss',6)
  assert(activeSounds[soundId('Samira '..rkey)],'R still interrupts dialogue and retains absolute priority')
 end
 Options.Language='zh';reset()
 print('Bilingual dialogue survives all five cast efforts; no delayed grunts, intact SFX, preserved gaps and absolute R priority passed')
end

-- Accepted inner and sweetspot Q hits stop every victim; rejected hits never do.
do
 reset();local inner=mob(135,100);local edge=mob(260,100);local rejected=mob(180,100)
 function rejected:TakeDamage()return false end
 function edge:IsBoss()return true end
 entities={inner,edge,rejected};mouse=Vector(300,100)
 keys[Keyboard.KEY_Q]=true;tick();keys={};tick(17)
 local pre=callbacks[ModCallbacks.MC_PRE_NPC_UPDATE]
 assert(pre(nil,inner)==true and pre(nil,edge)==true,'inner hits and boss sweetspot hits both stop')
 assert(inner.Velocity:Length()==0 and edge.Velocity:Length()==0,'Q stagger cancels hit knockback')
 assert(pre(nil,rejected)==nil,'blocked damage cannot stagger')
 paused=true;tick(30);assert(pre(nil,inner)==true,'pause freezes stagger duration')
 paused=false;tick(12);assert(pre(nil,inner)==nil and pre(nil,edge)==nil,'all victims recover after 0.4 seconds')
 reset();local basic=mob(140,100);entities={basic};mouse=basic.Position;right=true;tick();right=false;tick(6)
 assert(basic.hits==1 and pre(nil,basic)==nil,'ordinary attacks do not stagger')
 reset()
 print('Q inner/outer/boss/multiple targets, blocked damage, pause and basic attack isolation passed')
end

-- Native status dispatch preserves luck rolls/ownership without extra tear damage.
do
 local N=include('scripts.samira_native_hits');local original=player.GetTearHitParams
 local calls,rolls,rolled=0,0,0
 function player:GetTearHitParams(weapon,scale,displacement,source)
  assert(weapon==WeaponType.WEAPON_TEARS and scale==1 and displacement==1 and source==self)
  rolls=rolls+1;return {TearFlags=rolled}
 end
 local function target(x,y)
  local e=mob(x,y)
  function e:ApplyTearflagEffects(pos,flags,source,damage)
   assert(source==player and damage==player:GetTearPoisonDamage() and pos==self.Position)
   self.statusCount=(self.statusCount or 0)+1;self.applied=flags;calls=calls+1
  end
  return e
 end
 for _,name in ipairs({'POISON','SLOW','FREEZE','CHARM','CONFUSION','FEAR','BURN','MIDAS','GISH','PERMANENT_CONFUSION','GODS_FLESH','MAGNETIZE','BAIT'}) do
  local e=target(140,100);rolled=TearFlags['TEAR_'..name];N.apply(player,e)
  assert(e.applied==rolled and e.hits==0,'native status '..name..' must not add direct damage')
 end
 local excluded=TearFlags.TEAR_EXPLOSIVE | TearFlags.TEAR_SPLIT | TearFlags.TEAR_BOUNCE | TearFlags.TEAR_HOMING | TearFlags.TEAR_ICE
 local e=target(140,100);rolled=excluded;N.apply(player,e);assert(not e.applied,'projectile/death behavior needs its own adapter')
 rolled=excluded | TearFlags.TEAR_POISON;N.apply(player,e);assert(e.applied==TearFlags.TEAR_POISON)
 local before=rolls;e.Type=EntityType.ENTITY_FIREPLACE;N.apply(player,e)
 e.Type=0;e.IsDead=function()return true end;N.apply(player,e);assert(rolls==before,'terrain and dead enemies do not roll statuses')
 for stage=1,3 do
  reset();tick();local s=player.data.Samira;s.nextQ=stage;s.qReady=0
  local a=target(160,100);local b=target(165,100);local blocked=target(170,100)
  a.Size=200;b.Size=200;blocked.Size=200
  function blocked:TakeDamage()return false end
  function player:GetMultiShotParams()return {GetNumTears=function()return 4 end}end
  entities={a,b,blocked};mouse=Vector(300,100);rolled=TearFlags.TEAR_POISON | TearFlags.TEAR_FEAR
  before=rolls;keys[Keyboard.KEY_Q]=true;tick();keys={};tick(17)
  assert(a.statusCount==1 and b.statusCount==1 and not blocked.statusCount and rolls-before==2,'four Q blades roll once per accepted target, never per overlap or rejected hit')
  assert(a.hits==1 and b.hits==1,'status adapter cannot duplicate the Q damage hit')
 end
 player.GetMultiShotParams=nil
 for _,passive in ipairs({false,true}) do
  reset();tick();local state=player.data.Samira
  if not passive then include('scripts.samira_progression').state(player).passiveRemaining=999999 end
  local victim=target(140,100);entities={victim};mouse=victim.Position
  rolled=TearFlags.TEAR_SLOW;before=rolls;right=true;tick();right=false;tick(6)
  assert(victim.statusCount==1 and rolls-before==1,'basic/passive attacks inherit one native status roll')
 end
 rolled=0;e=target(140,100);N.apply(player,e);assert(not e.applied,'selling/removing status items immediately removes the effect')
 player.GetTearHitParams=original;reset()
 print('13 native on-hit flags, unsupported flag filtering, ownership, three-stage multishot dedup, rejected hits and basic/passive compatibility passed')
end

-- Passive-ready gestures are cosmetic; combat/input timing stays authoritative.
do
 local Pose=include('scripts.samira_passive_pose')
 local Progress=include('scripts.samira_progression')
 local clips=include('scripts.samira_external_actions')
 reset();tick();local s=player.data.Samira;s.weapon=true;s.walkClock=12
 local progress=Progress.state(player);progress.passiveRemaining=1
 local function frame(walk,wing,blocked,epoch)return Pose.frame(player,s,walk or false,wing or false,blocked or false,epoch or 1) end
 assert(frame()==nil)
 progress.passiveRemaining=0
 local velocity=Vector(2,0);player.Velocity=velocity
 local name,phase,loop,walk=frame(true)
 assert(name=='Unsheath_to_Passive' and phase==0 and loop==false and walk.kind=='Passive_Run')
 assert(player.Velocity==velocity and not s.cast and not s.weaponMotion,'ready gesture cannot reserve movement or cast input')
 s.clock=s.clock+10;name,phase=frame(true);assert(name=='Unsheath_to_Passive' and phase>0)
 local frozen=phase;name,phase=frame(true);assert(phase==frozen,'same simulation clock keeps a paused gesture still')
 s.clock=s.clock+30;name,phase,loop=frame(true);assert(name=='Passive_Run' and loop)
 name,phase,loop=frame();assert(name=='Passive_Idle' and loop)
 name,phase,loop,walk=frame(true);assert(name=='Passive_Idle_INTO_Run' and not loop and walk.kind=='Passive_Run')
 s.cast={kind='Q1',stage=1};assert(frame()==nil,'Q interrupts the readiness gesture immediately')
 for stage=1,3 do
  s.cast={kind='Q'..stage,stage=stage};assert(frame()==nil)
  s.cast=nil;name=frame();assert(name=='Q'..stage..'_INTO_Passive_Idle')
  s.cast={kind='Q'..stage,stage=stage};frame(true);s.cast=nil;name,phase,loop,walk=frame(true)
  local expected=stage==3 and 'Q3_INTO_Passive_Run' or 'Q'..stage..'_INTO_PASSIVE_RUN'
  assert(name==expected and walk.kind=='Passive_Run','Q recovery preserves locomotion')
 end
 s.cast={kind='Attack',passive=true};assert(frame()==nil)
 progress.passiveRemaining=300;s.cast=nil;name=frame();assert(name=='Passive_Attack_out')
 s.clock=s.clock+30;assert(frame()==nil,'consumed passive cannot keep its ready stance')
 progress.passiveRemaining=0;s.cast={kind='Q1'};assert(frame()==nil)
 s.cast=nil;assert(frame()=='Q1_INTO_Passive_Idle','cooldown completed during a cast joins the original recovery')
 s.dash={};assert(frame()==nil,'E interrupts any cosmetic recovery');s.dash=nil
 assert(frame(true)=='Passive_Idle_INTO_Run')
 assert(frame(false,true)==nil,'R/flight keep their winged stance')
 assert(frame()=='ULT_out_to_passive_idle')
 assert(frame(false,false,true)==nil,'death, emotes and presentation take priority')
 frame();s.weaponMotion={kind='Sheathe',age=1,duration=30};s.weapon=false
 assert(frame()=='passive_into_shth')
 s.clock=s.clock+30;s.weaponMotion=nil;assert(frame()=='passive_into_shth')
 s.clock=s.clock+60;assert(frame()==nil,'completed sheathing stays sheathed until a new readiness or draw event')
 s.weapon=true;s.weaponMotion={kind='Draw',age=9,duration=27}
 name,phase,loop,walk=frame(true);assert(name=='Unsheath_to_Passive' and phase==1/3 and walk.kind=='Passive_Run')
 s.weaponMotion=nil;s.weapon=false;assert(frame(false,false,false,2)==nil,'room change drops old recovery')
 s.weapon=true;s.clock=s.clock-100;name,phase=frame();assert(name=='Unsheath_to_Passive' and phase==0,'rewind cannot retain an old gesture timestamp')
 -- Verify actual telemetry chooses the original clip and lets active attacks win.
 s.cast=nil;s.weaponMotion=nil;s.emote=nil;s.passivePose=nil;s.weapon=true;player.Velocity=Vector.Zero
 ackMode='ready';external.toggle(true);time=time+250;external.emit(player,s,false)
 local wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.clip=='Unsheath_to_Passive' and not wire.looping)
 s.cast={kind='Attack',passive=true,face=Vector(1,0),age=1,impact=4,duration=10}
 time=time+250;external.emit(player,s,false)
 wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
 assert(wire.clip=='Passive_Attack' and not wire.looping)
 for _,stage in ipairs({1,3}) do
  s.cast={kind='Q'..stage,stage=stage,face=Vector(1,0),age=18,impact=18,duration=24}
  s.rUntil=0;time=time+250;external.emit(player,s,false)
  wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
  assert(math.abs(wire.phase-.9)<.000001 and wire.cast.age==wire.cast.impact and not wire.clip,'normal Q sword contact follows the unchanged hit tick')
  s.rUntil=s.clock+100;time=time+250;external.emit(player,s,false)
  wire=codec.decode(diagnostics[#diagnostics]:match('%[SAMIRA_EXTERNAL%] (.*)'))
  assert(wire.kind=='RQ'..stage and math.abs(wire.phase-(stage==1 and .60 or .53))<.000001,'winged Q retains its existing timing')
 end
 reset()
 print('Original passive ready/idle/run/recoveries, movement, cast priority, cooldown consumption, pause, room/rewind and wire clips passed')
end

-- Exact target level follows ordinary XP growth without replacing skills/passive.
do
 reset();local P=include('scripts.samira_progression');local H=include('scripts.samira_health')
 P.restore(player,{level=3,xp=123,skills={q=2,e=1},passiveRemaining=250});H.restore(player);tick()
 local progress=P.state(player);local health=H.state(player);local shield=health.soul
 local before=H.max(player);local points=P.points(player)
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','level 6')
 assert(progress.level==6 and progress.xp==0 and P.points(player)==points+3)
 assert(P.rank(player,'q')==2 and P.rank(player,'e')==1 and P.rank(player,'r')==0)
 assert(H.max(player)>before and health.soul==shield and progress.passiveRemaining==249)
 local hp=H.current(player);progress.xp=12
 callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','level 6')
 assert(progress.xp==12 and H.current(player)==hp,'same level cannot reset XP or heal')
 for _,arg in ipairs({'level 2','level 0','level 19','level -1','level 6.5'}) do
  callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira',arg);assert(progress.level==6 and progress.xp==12)
 end
 dead=true;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','level 18');assert(progress.level==6)
 dead=false;player.type=1;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','level 18');assert(progress.level==6)
 player.type=10;callbacks[ModCallbacks.MC_EXECUTE_CMD](nil,'samira','level 18')
 assert(progress.level==18 and progress.xp==0 and P.points(player)==15)
 reset();print('Target level command: exact XP, growth, points, retained skills/passive/shields, same-level no-op and invalid/dead/other-player guards passed')
end
