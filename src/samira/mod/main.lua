local Health=include('scripts.samira_health')
local mod=RegisterMod('Samira - The Samira Blade',1)
local game=Game();local TYPE=Isaac.GetPlayerTypeByName('Samira',false)
local G=include('scripts.samira_geometry');local N=include('scripts.samira_navigation')
local H=include('scripts.samira_hud');local Probe=include('scripts.samira_render_probe')
local Branding=include('scripts.samira_branding')
local A=include('scripts.samira_abilities')
local Visual=include('scripts.samira_visuals');local View=include('scripts.samira_view')
local Presentation=include('scripts.samira_presentation')
local Terrain=include('scripts.samira_terrain')
local Progress=include('scripts.samira_progression')
local Passive=include('scripts.samira_passive')
local External=include('scripts.samira_external')
local Emotes=include('scripts.samira_emotes')
local Mastery=include('scripts.hero_mastery')
local Features=include('scripts.hero_features')
local Audio=include('scripts.samira_audio')
local Shop=include('scripts.samira_shop')
local Equipment=include('scripts.samira_equipment')
local ItemEffects=include('scripts.samira_item_effects')
local QWeapons=include('scripts.samira_q_weapons')
local Knockup=include('scripts.samira_knockup')
local Camera=include('scripts.samira_camera')
local NativeHits=include('scripts.samira_native_hits')
local Interaction=include('scripts.samira_interaction')
local Controls=include('scripts.samira_controls')
local Fallback=include('scripts.samira_fallback')
local Rewind=include('scripts.samira_rewind')
local json=require('json')
local perf={frames=0,reports=0}
local runReady=false
local savedSettings
local saveProgress
local rewindSlots={};local rewindPending={};local rewindLoading=false;local rewindPreferences={}
local function isSamira(e)local p=e and e:ToPlayer();return p and p:GetPlayerType()==TYPE end
if not REPENTOGON then
    mod:AddCallback(ModCallbacks.MC_POST_RENDER,function()
        if game:GetNumPlayers()>0 and isSamira(Isaac.GetPlayer(0)) then Isaac.RenderText('Samira requires REPENTOGON',40,50,1,.3,.3,1) end
    end)
    return
end
local function state(p)
    local data=p:GetData()
    if not data.Samira then data.Samira={clock=0,hitFlash=0,face=Vector(0,1),keys={},nextQ=1,qReady=0,wReady=0,eReady=0,rReady=0,attackReady=0,weapon=false,fx={}} end
    return data.Samira
end
local function live(e)return e and e:Exists() and not e:IsDead() end
local function enemy(e)return live(e) and e.Type~=EntityType.ENTITY_FIREPLACE and e:IsVulnerableEnemy() and not e:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) end
local function attackable(e)return enemy(e) or Terrain.fire(e) end
local function playable(p)return isSamira(p) and Presentation.canAct(p) end
local function stats(p)
    local st=Equipment.stats(p,Progress.stats(p,G.stats(p.Damage,p.MaxFireDelay,p.TearRange,p.Luck,p.MoveSpeed)))
    local damage,speed=A.modifiers(state(p));st.damage=st.damage*damage*Progress.attackMultiplier(p);st.speed=G.movementSpeed(st.speed*speed);return st
end
local function direction(delta,fallback)return delta:Length()>1 and delta:Normalized() or fallback end
local function mouseScreen()
    local raw=Input.GetMousePosition(false)
    local span=Isaac.ScreenToWorld(Vector(10000,10000))-Isaac.ScreenToWorld(Vector.Zero)
    local scale=Isaac.WorldToScreenDistance(span)*.0001
    local screen=Vector(raw.X*scale.X,raw.Y*scale.Y)
    return screen
end
local function mouseWorld()
    local screen=mouseScreen()
    if game:GetRoom():IsMirrorWorld() then screen.X=Isaac.GetScreenWidth()-screen.X end
    local zero=Isaac.WorldToScreen(Vector.Zero);local axes=Isaac.WorldToScreen(Vector(1000,1000))-zero
    return Vector((screen.X-zero.X)*1000/axes.X,(screen.Y-zero.Y)*1000/axes.Y)
end
local function stop(s)s.goal=nil;s.target=nil;s.gridTarget=nil;s.path=nil;s.exitIntent=nil;s.doorOpeningUntil=nil end
local function move(p,s,destination,speed)
    local room=game:GetRoom();local opening,normal,door,slot=N.exit(room,destination)
    local flying=p.CanFly==true
    if s.pathFlying~=flying then s.path=nil;s.pathFlying=flying end
    s.exitIntent=nil
    if opening then
        if N.atDoor(p.Position,opening,normal) then
            if door:IsLocked() then
                local unlocked=door:TryUnlock(p,false)
                if unlocked then s.doorOpeningUntil=s.clock+30 end
            end
            if N.enter(game,p,s,door,slot) then p.Velocity=Vector.Zero;return true end
            if not door:IsOpen() then
                p.Velocity=Vector.Zero;return not (s.doorOpeningUntil and s.clock<s.doorOpeningUntil)
            end
        end
        if N.atDoor(p.Position,opening,normal) and door:IsOpen() then
            destination=opening+normal*32;s.exitIntent=normal
        else destination=opening-normal*40 end
    end
    local delta=destination-p.Position
    if delta:Length()<5 then p.Velocity=Vector.Zero;return true end
    local waypoint=destination
    if not s.exitIntent and not Terrain.lineClear(room,p,p.Position,destination) then
        local start=room:GetGridIndex(p.Position);local goal=room:GetGridIndex(room:GetClampedPosition(destination,0))
        if not s.path or s.pathGoal~=goal or s.clock>=(s.pathAt or 0) then
            s.path=N.path(start,goal,room:GetGridWidth(),room:GetGridSize(),function(i)return Terrain.walkable(room,p,i) end)
            s.pathGoal=goal;s.pathAt=s.clock+12
        end
        while s.path[1] and p.Position:Distance(room:GetGridPosition(s.path[1]))<8 do table.remove(s.path,1) end
        if not s.path[1] then p.Velocity=Vector.Zero;return false end
        waypoint=room:GetGridPosition(s.path[1])
    end
    local step=waypoint-p.Position;s.face=direction(step,s.face);p.Velocity=s.face*math.min(speed,step:Length())
    return false
end
local function press(s,key)
    local down=Input.IsButtonPressed(key,0);local edge=down and not s.keys[key];s.keys[key]=down;return edge
end
local function hit(p,s,e,amount,critical,spell,healRatio)
    amount=amount*ItemEffects.multiplier(p,s,e,spell)
    local healthBefore=e.HitPoints or amount;local dealt=math.min(amount,healthBefore)
    local oldMark=e:GetData().SamiraLastHit;e:GetData().SamiraLastHit={owner=p,clock=s.clock}
    local accepted=e:TakeDamage(amount,0,EntityRef(p),0)
    if accepted~=false then
        e:SetColor(Color(1,.3,.25,1,.2,0,0),5,1,false,false)
        if not e:IsBoss() then e.Velocity=e.Velocity+direction(e.Position-p.Position,s.face)*(critical and 6 or 3) end
        s.hitFlash=3
        Visual.hit(s,e.Position,critical)
        if e.Type~=EntityType.ENTITY_FIREPLACE then
            local healingDamage=dealt*(healRatio or 1)
            A.onHit(p,s,e,healingDamage);ItemEffects.hit(p,s,e,dealt,spell,healingDamage,healthBefore)
        end
    else e:GetData().SamiraLastHit=oldMark end
    return accepted~=false,dealt
end
local function strikeSingle(p,s,c,silent,contacts)
    local st=stats(p);local origin=p.Position;local angle=c.face:GetAngleDegrees()
    local shape=c.stage and G.shape(c.stage,st.scale)
    if c.stage then
        Terrain.qHit(game:GetRoom(),p,c.face,shape,c.stage,Isaac.GetRoomEntities())
        local reach=shape.kind=='circle' and shape.cx+shape.radius or shape.far
        QWeapons.emit(p,s,G.project(c.face):Normalized(),st.damage,reach)
    end
    local soundResult=0;local reduction=0;local consumed=false
    local reach=st.reach+(c.passive and Passive.ready(p) and 50*G.units or 0)
    local thrust=not c.stage and c.passive==true
    -- Right-click attacks already acquired their single target at windup.
    -- Only free attacks select a victim from the cone/passive rectangle.
    local directional=c.cone or thrust and c.target==nil
    local basicTarget=c.target
    if directional then
        -- Entities and breakable terrain compete for the same single contact.
        local grid,nearest=Terrain.basicTarget(game:GetRoom(),p,c.face,reach,thrust)
        basicTarget=nil
        for _,e in ipairs(Isaac.GetRoomEntities()) do if attackable(e) then
            local delta=G.unproject(e.Position-origin):Rotated(-angle)
            local distance=G.basicContact(delta.X,delta.Y,e.Size,reach,thrust)
            if distance and distance<nearest then basicTarget=e;grid=nil;nearest=distance end
        end end
        if grid then grid:Hurt(1);Visual.hit(s,grid.Position,false);soundResult=1 end
    elseif not c.stage and c.gridTarget~=nil then
        local grid=Terrain.poop(game:GetRoom(),c.gridTarget)
        if grid then grid:Hurt(1);Visual.hit(s,grid.Position,false);soundResult=1 end
    end
    local passiveTarget=not c.stage and c.passive and enemy(basicTarget) and basicTarget or nil
    -- A committed auto attack owns its entity reference. Do not depend on a
    -- second room enumeration finding that same target at the contact tick.
    local victims=shape and Isaac.GetRoomEntities() or basicTarget and {basicTarget} or {}
    for _,e in ipairs(victims) do
        if enemy(e) or not shape and attackable(e) then
            local offset=((shape or c.cone) and G.unproject(e.Position-origin) or e.Position-origin):Rotated(-angle);local inside,sweet
            if shape then inside,sweet=G.hit(shape,offset.X,offset.Y,e.Size)
            else inside=Interaction.same(e,basicTarget) end
            if inside then
                local crit=not shape and p:GetCollectibleRNG(1):RandomFloat()<st.crit
                local base=st.damage*(c.stage and (1+c.stage*.25)*Progress.damage(p,'q') or 1)*(sweet and 1.6 or crit and (st.critMultiplier or 1.75) or 1)
                if contacts then
                    -- Aggregate this Q stage before damage callbacks can kill the target.
                    local key=e:GetData();local contact=contacts.byTarget[key]
                    if not contact then
                        contact={entity=e,total=0,best=0,sweet=false}
                        contacts.byTarget[key]=contact;contacts[#contacts+1]=contact
                    end
                    contact.total=contact.total+base
                    if base>contact.best then contact.best=base;contact.sweet=sweet end
                else
                    local proc=enemy(e) and c.passive and not consumed and Passive.ready(p) and Interaction.same(e,passiveTarget)
                    local bonus=proc and Passive.bonus(p,e) or 0
                    local accepted,dealt=hit(p,s,e,base+bonus,sweet or crit or proc,c.stage~=nil)
                    if accepted then
                        soundResult=math.max(soundResult,sweet and 2 or 1)
                        if proc then
                            local _,_,healing=A.modifiers(s);Passive.consume(p,e,dealt*bonus/(base+bonus),healing);consumed=true
                        elseif Passive.large(e) then reduction=math.max(reduction,c.stage and sweet and 4 or 2) end
                        NativeHits.apply(p,e)
                    end
                end
            end
        end
    end
    if not silent then
        if not consumed and reduction>0 then Passive.reduce(p,reduction) end
        if consumed then Audio.play('passive_hit') else Audio.strike(c.stage,soundResult) end
    end
    if not c.cone and (c.stage or soundResult>0) then s.fx[#s.fx+1]={origin=Vector(origin.X,origin.Y),face=c.face,stage=c.stage,scale=st.scale,age=0} end
    return soundResult,reduction
end
local function strike(p,s,c)
    if not c.stage then return strikeSingle(p,s,c) end
    if c.stage==3 then QWeapons.charged(p,s,c,G.project(c.face):Normalized()) end
    local soundResult,reduction=0,0
    local contacts={byTarget={}}
    for _,face in ipairs(c.faces or {c.face}) do
        local shot={};for key,value in pairs(c) do shot[key]=value end
        shot.face=face
        local sound,reduce=strikeSingle(p,s,shot,true,contacts)
        soundResult=math.max(soundResult,sound);reduction=math.max(reduction,reduce)
    end
    for _,contact in ipairs(contacts) do
        local e=contact.entity
        if enemy(e) then
            local amount=contact.best+.5*(contact.total-contact.best)
            if amount>0 and hit(p,s,e,amount,contact.sweet,true,contact.best/amount) then
                Knockup.apply(e)
                soundResult=math.max(soundResult,contact.sweet and 2 or 1)
                if Passive.large(e) then reduction=math.max(reduction,contact.sweet and 4 or 2) end
                NativeHits.apply(p,e)
            end
        end
    end
    if reduction>0 then Passive.reduce(p,reduction) end
    Audio.strike(c.stage,soundResult);game:ShakeScreen(c.stage==3 and 5 or 2)
end
local function beginBasic(p,s,st,target,gridTarget,cone)
    -- Faster attack rates shorten the animation as well as the readiness timer.
    local duration=math.min(13,math.max(3,math.floor(st.interval)))
    s.cast={kind='Attack',face=s.face,age=0,impact=math.max(1,math.floor(duration*7/13)),duration=duration,
        target=target,gridTarget=gridTarget,cone=cone,passive=gridTarget==nil and Passive.ready(p)}
    s.attackReady=s.clock+st.interval;s.weapon=true;s.weaponMotion=nil;s.combatUntil=s.clock+180
    Audio.play(s.cast.passive and 'passive_cast' or 'attack')
end
local function beginQ(p,s,aim)
    if Progress.rank(p,'q')==0 or s.cast or s.clock<s.qReady then return end
    local stage=s.nextQ;s.face=direction(G.unproject(aim-p.Position),s.face)
    s.cast={kind='Q'..stage,stage=stage,face=s.face,age=0,impact=G.qImpact,duration=G.qDuration}
    s.cast.faces=G.qFaces(s.face,G.qCount(p))
    s.nextQ=stage%3+1;s.chainUntil=s.clock+120;s.qReady=s.clock+(stage==3 and Equipment.cooldown(p,Progress.cooldown(p,'q'),false) or G.qRecast)
    if stage==3 then s.nextQ=1;s.chainUntil=nil end
    s.goal=nil;s.path=nil
    s.weapon=true;s.combatUntil=s.clock+180
    Audio.cast(s,'q'..stage);ItemEffects.cast(p,s,'q')
end
local function beginDash(p,s,aim)
    if Progress.rank(p,'e')==0 or s.dash or s.clock<s.eReady then return end
    local delta=G.unproject(aim-p.Position);if delta:Length()<4 then return end
    local length=math.max(G.dashMin,math.min(G.dashRange,delta:Length()))
    if not Terrain.begin(game:GetRoom(),p,s,delta:Normalized(),length) then return end
    s.attackReady=s.clock
    if s.cast and s.cast.kind=='Attack' then s.cast=nil end
    s.eReady=s.clock+Equipment.cooldown(p,Progress.cooldown(p,'e'),false);s.path=nil
    if not s.cast then s.face=s.dash.face end
    Audio.cast(s,'e');ItemEffects.cast(p,s,'e')
end
local function flight(p,s)
    local flying=A.ultimate(s) and not p:IsDead()
    if flying==(s.ultimateFlight==true) then return end
    s.ultimateFlight=flying;p:AddCacheFlags(CacheFlag.CACHE_FLYING);p:EvaluateItems()
    if not flying and not p.CanFly and not p:IsDead() then
        local room=game:GetRoom()
        if not Terrain.clear(room,p,p.Position) then
            local best,distance
            for i=0,room:GetGridSize()-1 do local pos=room:GetGridPosition(i);local d=pos:Distance(p.Position)
                if (not distance or d<distance) and Terrain.clear(room,p,pos) then best=pos;distance=d end
            end
            if best then p.Position=best end
        end
    end
end
local function update(p)
    if rewindLoading then return end
    if not isSamira(p) then
        local previous=p:GetData().Samira;if previous then Terrain.finish(p,previous,true);QWeapons.clear(previous);Audio.stopRMusic() end
        return
    end
    local s=state(p)
    s.inputFrame=(s.inputFrame or 0)+1
    local inputGear=Equipment.state(p)
    local inputDisabled=game:IsPaused() or s.configOpen or s.shopOpen or p:IsDead() or (inputGear.stasis or 0)>inputGear.time
    local masteryDown=(p.ControllerIndex or 0)==0 and (Input.IsButtonPressed(Keyboard.KEY_LEFT_CONTROL,0) or Input.IsButtonPressed(Keyboard.KEY_RIGHT_CONTROL,0)) and Input.IsButtonPressed(Keyboard.KEY_6,0)
    if Mastery.update(s,Features.mastery_emote,not inputDisabled and playable(p) and not s.departing,masteryDown) then Mastery.sound() end
    Controls.pollDrop(p,s,inputDisabled)
    for _,action in ipairs({ButtonAction.ACTION_ITEM,ButtonAction.ACTION_PILLCARD,ButtonAction.ACTION_BOMB}) do Controls.nativeItem(p,s,action,inputDisabled) end
    if game:IsPaused() then return end
    if s.configOpen then p.Velocity=Vector.Zero;return end
    External.poll()
    Presentation.update(p,s)
    if p:IsDead() then flight(p,s);QWeapons.clear(s) end
    Audio.observe(p,s)
    if not playable(p) then ItemEffects.stasis.clear(p);if p:IsDead() and not s.gearDeath then local g=Equipment.state(p);g.soulStacks=math.max(0,(g.soulStacks or 0)-(Equipment.has(p,3041) and 10 or 5));s.gearDeath=true;saveProgress() end;Shop.close(s);s.emote=nil;Audio.stopEmote();Terrain.finish(p,s,true);return end
    s.gearDeath=nil
    if s.departing then
        if Isaac.GetTime()<s.departing then p.Velocity=Vector.Zero;return end
        s.departing=nil
    end
    if s.dashStop then p.Velocity=Vector.Zero;s.dashStop=nil end
    s.clock=s.clock+1;s.updatedAt=Isaac.GetTime and Isaac.GetTime() or 0;s.hitFlash=math.max(0,(s.hitFlash or 0)-1)
    if s.noCD then for _,key in ipairs({'q','w','e','r'}) do s[key..'Ready']=s.clock end end
    Passive.update(p)
    Equipment.syncCoins(p)
    if s.clock%30==0 then Equipment.syncInventory(p) end
    ItemEffects.update(p,s)
    local st=stats(p);local aim=Controls.aim(p,s,mouseWorld());s.aim=aim
    QWeapons.update(s)
    local pad=(p.ControllerIndex or 0)>0
    local movement=Controls.movement(p,s)
    if pad then
        s.padCursor=s.padCursor or Vector(Isaac.GetScreenWidth()/2,Isaac.GetScreenHeight()/2)
        if s.shopOpen then s.padCursor=Vector(math.max(0,math.min(Isaac.GetScreenWidth(),s.padCursor.X+movement.X*5)),math.max(0,math.min(Isaac.GetScreenHeight(),s.padCursor.Y+movement.Y*5))) end
    end
    local pointer=pad and s.shopOpen and s.padCursor or mouseScreen()
    local shopping=Shop.update(s,pointer,Isaac.GetScreenWidth(),Isaac.GetScreenHeight(),External.shop(false),p,game:GetRoom())
    if s.shopChanged or Equipment.state(p).dirty then s.shopChanged=nil;Equipment.state(p).dirty=nil;saveProgress() end
    local gear=Equipment.state(p);local stasis=(gear.stasis or 0)>gear.time
    local ctrl=Controls.upgrade(p)
    for i,key in ipairs(Equipment.keys) do
        if press(s,Keyboard['KEY_'..key]) and not pad and not ctrl and not shopping and not stasis and ItemEffects.use(p,s,i,aim) then saveProgress() end
    end
    -- World effects and passives tick before the actor-command gate, including during stasis.
    local entities=Isaac.GetRoomEntities()
    A.update(p,s,entities,game:GetRoom(),enemy,function(e,multiplier)
        if hit(p,s,e,stats(p).damage*multiplier,false,true) and Passive.large(e) then Passive.reduce(p,2) end
    end)
    stasis=ItemEffects.stasis.active(p,gear) -- Activation above takes effect this same tick.
    if stasis then
        p.Velocity=Vector.Zero;p.FireDelay=3
        for i=#s.fx,1,-1 do s.fx[i].age=s.fx[i].age+1;if s.fx[i].age>90 then table.remove(s.fx,i) end end
        Visual.update(s)
        return
    end
    s.hovered=Interaction.hover(entities,aim,attackable);s.hover=s.hovered~=nil or Terrain.poopAt(game:GetRoom(),aim)~=nil
    local q=Controls.edge(p,s,'q');local w=Controls.edge(p,s,'w');local dash=Controls.edge(p,s,'e');local r=Controls.edge(p,s,'r');local halt=Controls.edge(p,s,'stop')
    local attackCommand=Controls.down(p,'attack') and not ctrl and not shopping
    if pad and not shopping then
        s.gearSelected=s.gearSelected or 1
        s.padEquipment=s.padEquipment or {}
        for code,delta in pairs({[0]=-1,[1]=1,[2]=-3,[3]=3}) do
            local down=Input.IsButtonPressed(code,p.ControllerIndex)
            if down and not s.padEquipment[code] then s.gearSelected=(s.gearSelected-1+delta)%6+1 end
            s.padEquipment[code]=down
        end
        local use=Input.IsButtonPressed(13,p.ControllerIndex)
        if use and not s.padGearUse and ItemEffects.use(p,s,s.gearSelected,aim) then saveProgress() end
        s.padGearUse=use
        if ItemEffects.stasis.active(p,gear) then Visual.update(s);return end
    end
    if ctrl then
        if not shopping then
            for key,down in pairs({q=q,w=w,e=dash,r=r}) do if down and Progress.upgrade(p,key) then Audio.play('ui_level');saveProgress() end end
        end
        q=false;w=false;dash=false;r=false
    end
    local upgradeKey=not pad and H.upgradeAt(p,mouseScreen(),Isaac.GetScreenWidth(),Isaac.GetScreenHeight())
    local left=Input.IsMouseBtnPressed(0)
    if left and not s.skillLeft and not shopping and upgradeKey and Progress.upgrade(p,upgradeKey) then Audio.play('ui_level');saveProgress() end
    s.skillLeft=left
    if s.chainUntil and s.clock>s.chainUntil then s.nextQ=1;s.chainUntil=nil;s.qReady=s.clock+Equipment.cooldown(p,Progress.cooldown(p,'q'),false) end
    if halt then stop(s) end
    local right=not pad and Input.IsMouseBtnPressed(1) and not shopping
    Emotes.update(s,External.available() and not pad and not shopping,shopping or q or w or dash or r or halt or right or attackCommand or s.cast or s.dash)
    Audio.emote(s)
    local overHUD=shopping or upgradeKey~=nil and upgradeKey~=false or not pad and H.contains(mouseScreen(),Isaac.GetScreenWidth(),Isaac.GetScreenHeight())
    if right and (not s.right or s.clock%4==0) and not overHUD then
        local selected,nearest=s.hovered,38
        local clickedDoor=N.exit(game:GetRoom(),aim)
        local gridTarget=not clickedDoor and not selected and Terrain.poopAt(game:GetRoom(),aim) or nil
        if clickedDoor then selected=nil
        elseif not selected and not gridTarget then for _,e in ipairs(entities) do
            if attackable(e) then local d=e.Position:Distance(aim)-e.Size*.5;if d<nearest then selected=e;nearest=d end end
        end end
        if pad and not selected and not gridTarget then
            local best=math.huge
            for _,e in ipairs(entities) do if attackable(e) then local d=e.Position:Distance(p.Position);if d<best and d<st.reach+65 then best=d;selected=e end end end
        end
        if not s.right then s.click={position=Vector(aim.X,aim.Y),at=s.clock,enemy=selected~=nil or gridTarget~=nil} end
        Audio.command(p,s,selected~=nil or gridTarget~=nil,aim)
        if not s.goal or s.goal:Distance(aim)>12 or s.target~=selected then s.path=nil end
        s.target=selected;s.gridTarget=gridTarget;s.goal=aim;if selected or gridTarget then s.goal=nil end
        if (selected or gridTarget) and not s.weapon and not s.cast then
            s.weapon=true;s.combatUntil=s.clock+180;s.weaponMotion={kind='Draw',age=0,duration=27}
        end
    end
    s.right=right
    if q and not overHUD then beginQ(p,s,aim) end
    if w and not overHUD and A.castW(p,s,aim) then ItemEffects.cast(p,s,'w') end
    if dash and not overHUD then beginDash(p,s,aim) end
    if r and not overHUD and A.castR(p,s,entities) then ItemEffects.cast(p,s,'r');st=stats(p) end
    if attackCommand and not halt and not overHUD and not s.cast and not s.dash and s.clock>=s.attackReady then
        Audio.command(p,s,true,aim)
        stop(s);s.face=direction(G.unproject(aim-p.Position),s.face)
        beginBasic(p,s,st,nil,nil,true)
    end
    if s.weapon and not s.cast and not s.emote and not s.target and not s.gridTarget and not A.ultimate(s) and s.clock>(s.combatUntil or 0) then
        s.weaponMotion={kind='Sheathe',age=0,duration=30};s.weapon=false
    end
    flight(p,s)
    s.exitIntent=nil
    if s.dash then
        Terrain.update(game:GetRoom(),p,s)
    elseif s.cast or s.emote or shopping then p.Velocity=Vector.Zero
    elseif movement:Length()>.18 then
        Audio.command(p,s,false,p.Position+movement*200)
        stop(s);s.face=movement:Normalized();p.Velocity=movement*st.speed
        local _,normal,door,slot=N.exit(game:GetRoom(),p.Position+s.face*65)
        if door and N.atDoor(p.Position,door.Position,normal) then
            if door:IsLocked() then door:TryUnlock(p,false) end
            N.enter(game,p,s,door,slot)
        end
    elseif attackable(s.target) then
        local delta=s.target.Position-p.Position;s.face=direction(delta,s.face)
        if delta:Length()<=st.reach+s.target.Size*.7+(Passive.ready(p) and 50*G.units or 0) then
            p.Velocity=Vector.Zero
            if s.clock>=s.attackReady then
                Audio.command(p,s,true,s.target.Position)
                beginBasic(p,s,st,s.target,nil,false)
            end
        else move(p,s,s.target.Position,st.speed) end
    elseif s.gridTarget~=nil then
        local grid=Terrain.poop(game:GetRoom(),s.gridTarget)
        if not grid then stop(s);p.Velocity=Vector.Zero
        else
            local delta=grid.Position-p.Position;s.face=direction(delta,s.face)
            if delta:Length()<=st.reach+18 then
                p.Velocity=Vector.Zero
                if s.clock>=s.attackReady then
                    beginBasic(p,s,st,nil,s.gridTarget,false)
                end
            else move(p,s,grid.Position,st.speed) end
        end
    elseif s.goal then if move(p,s,s.goal,st.speed) then s.goal=nil end
    else s.target=nil;p.Velocity=p.Velocity*.65 end
    if s.weaponMotion then
        s.weaponMotion.age=s.weaponMotion.age+1
        if s.cast or s.dash or s.emote or s.weaponMotion.age>=s.weaponMotion.duration then s.weaponMotion=nil end
    end
    if s.cast then
        local c=s.cast;c.age=c.age+1
        if c.kind=='Attack' and c.target and not c.contactDone and attackable(c.target) then
            c.face=direction(c.target.Position-p.Position,c.face);s.face=c.face
        end
        if c.kind=='Attack' and c.target and c.age>=c.impact and not c.contactDone then
            -- A brief native hurt/invulnerability frame must not silently eat a
            -- locked attack. Retry only within its existing recovery; never
            -- retarget, bypass immunity, extend the cast, or double-proc a hit.
            c.contactDone=strike(p,s,c)>0
        elseif c.age==c.impact then
            if c.kind=='W' then A.launchW(p,s,c) else strike(p,s,c) end
        end
        if c.age>=c.duration then s.cast=nil end
    end
    for i=#s.fx,1,-1 do s.fx[i].age=s.fx[i].age+1;if s.fx[i].age>90 then table.remove(s.fx,i) end end
    for i=#(s.goldFX or {}),1,-1 do if s.clock-s.goldFX[i].at>=42 then table.remove(s.goldFX,i) end end
    Visual.update(s)
    p.FireDelay=math.max(p.FireDelay,3)
    s.walkClock=(s.walkClock or 0)+math.min(2,p.Velocity:Length()/2.45)
end
-- The global simulation tick is 30 Hz and continues through hurt/item states.
-- MC_POST_PLAYER_UPDATE is 60 Hz, so it must not drive these 30 Hz ability clocks.
mod:AddCallback(ModCallbacks.MC_POST_UPDATE,function()
    if rewindLoading then return end
    Camera.update(game,game:GetNumPlayers()==1 and isSamira(Isaac.GetPlayer(0)),false)
    if not game:IsPaused() then Knockup.tick() end
    Branding.update(game,game:GetNumPlayers()==1 and isSamira(Isaac.GetPlayer(0)))
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) and not game:IsPaused() then Health.update(p) end;update(p) end
end)
mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG,function(_,entity,amount,flags,source,countdown)
    if Terrain.blockExplosionDamage(entity,flags,source) then return false end
    if isSamira(entity) then return ItemEffects.hurt(entity:ToPlayer(),state(entity:ToPlayer()),amount,flags,source,countdown) end
end)
mod:AddCallback(ModCallbacks.MC_POST_ENTITY_TAKE_DMG,function(_,entity,damage,flags,source)
    if isSamira(entity) then
        local p=entity:ToPlayer();Health.commit(p);local s=state(p);s.hurtUntil=s.clock+9;s.emote=nil;Audio.stopEmote()
        if not p:IsDead() and (s.cast or s.dash) then p.Velocity=Vector.Zero end
    elseif source and source.Entity then
        local owner=source.Entity
        -- Attribute player-owned bombs/tears/familiars as well as direct Q/W/attack hits.
        for _=1,4 do
            if isSamira(owner) then
                local p=owner:ToPlayer();entity:GetData().SamiraLastHit={owner=p,clock=state(p).clock};break
            end
            owner=owner.SpawnerEntity;if not owner then break end
        end
    end
end)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_ADD_HEARTS,function(_,p,amount,kind)
    if isSamira(p) then Health.preAdd(p,amount,kind) end
end)
mod:AddCallback(ModCallbacks.MC_POST_PLAYER_ADD_HEARTS,function(_,p,amount,kind)
    if isSamira(p) then Health.postAdd(p,amount,kind) end
end)
mod:AddCallback(ModCallbacks.MC_POST_PLAYER_REVIVE,function(_,p)
    if isSamira(p) then Health.revive(p) end
end)
local isaacVoice={
    [SoundEffect.SOUND_ISAAC_HURT_GRUNT]=true,
    [SoundEffect.SOUND_ISAACDIES]=true,
    [SoundEffect.SOUND_CHILD_HAPPY_ROAR_SHORT]=true,
}
mod:AddCallback(ModCallbacks.MC_PRE_SFX_PLAY,function(_,id)
    if isaacVoice[id] and game:GetNumPlayers()==1 and isSamira(Isaac.GetPlayer(0)) then return false end
end)
saveProgress=function()
    if not runReady or rewindLoading then return end
    local players={}
    for i=0,game:GetNumPlayers()-1 do
        local p=Isaac.GetPlayer(i)
        if isSamira(p) then local s=Progress.state(p);players[tostring(i)]={level=s.level,xp=s.xp,skills=s.skills,
            passiveRemaining=s.passiveRemaining,equipment=Equipment.save(p),health=Health.save(p)} end
    end
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then savedSettings=Controls.state(p);break end end
    mod:SaveData(json.encode({version=1,seed=game:GetSeeds():GetStartSeed(),players=players,settings=savedSettings,rewind=rewindSlots}))
end
local function captureRewind(slot)
    local players={}
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i)
        if isSamira(p) then players[tostring(i)]=Rewind.capture(p,state(p)) end
    end
    rewindSlots[tostring(slot)]=players
end
mod:AddCallback(ModCallbacks.MC_POST_GLOWING_HOURGLASS_SAVE,function(_,slot)
    if rewindLoading then return end
    if not runReady then rewindPending[tostring(slot)]=true;return end
    captureRewind(slot);saveProgress()
end)
mod:AddCallback(ModCallbacks.MC_PRE_GLOWING_HOURGLASS_LOAD,function()
    Knockup.clear()
    Mastery.clear()
    rewindLoading=true;rewindPreferences={};Audio.cleanup();Controls.close()
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then
        local s=state(p);QWeapons.clear(s);Terrain.finish(p,s,true);stop(s)
        rewindPreferences[i]={controls=Controls.state(p),noCD=s.noCD,indicators=s.indicators,bannerVisible=s.bannerVisible}
        Health.state(p).syncing=true;Equipment.state(p).syncing=true
    end end
end)
mod:AddCallback(ModCallbacks.MC_POST_GLOWING_HOURGLASS_LOAD,function(_,slot)
    local players=rewindSlots[tostring(slot)]
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then
        local data=p:GetData();local old=state(p);local entry=players and players[tostring(i)]
        if Rewind.valid(entry) then
            local preferences=rewindPreferences[i] or old
            data.Samira=nil;local s=state(p)
            s.noCD=preferences.noCD;s.indicators=preferences.indicators;s.bannerVisible=preferences.bannerVisible
            if preferences.controls then data.SamiraControls=preferences.controls end
            if Rewind.apply(p,s,entry) then
                Equipment.syncHealth(p);Equipment.coinDisplay(p);Equipment.refreshNative(p)
                flight(p,s);Health.sync(p)
            end
        else
            -- Old saves cannot reconstruct a snapshot that was never recorded.
            Health.state(p).syncing=nil;Equipment.state(p).syncing=nil
            Health.restore(p,Health.save(p));Equipment.refreshNative(p)
            Isaac.DebugString('[Samira rewind] No custom snapshot for slot '..tostring(slot))
        end
    end end
    rewindLoading=false;rewindPreferences={};External.newRoom(true);saveProgress()
end)
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED,function(_,continued)
    Knockup.clear()
    Mastery.clear()
    rewindLoading=false;rewindSlots={}
    Audio.cleanup()
    Audio.resetBossRooms()
    External.start()
    local saved
    if mod:HasData() then
        local ok,data=pcall(json.decode,mod:LoadData())
        if ok and type(data)=='table' then
            savedSettings=data.settings
            if continued and data.version==1 and data.seed==game:GetSeeds():GetStartSeed() and type(data.players)=='table' then
                saved=data.players;rewindSlots=type(data.rewind)=='table' and data.rewind or {}
            end
        end
    end
    for i=0,game:GetNumPlayers()-1 do
        local p=Isaac.GetPlayer(i)
        if isSamira(p) then
            Controls.restore(p,savedSettings)
            local entry=saved and saved[tostring(i)]
            p:GetData().SamiraHealth=nil
            Progress.restore(p,entry);Equipment.restore(p,entry and entry.equipment,true)
            Health.restore(p,entry and entry.health,entry~=nil and not entry.health)
            Equipment.syncHealth(p)
            if not entry then Progress.award(p,Progress.required(1)+Progress.required(2)) end
            Equipment.coinDisplay(p)
            Equipment.refreshNative(p)
        end
    end
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then Health.sync(p) end end
    runReady=true
    for slot in pairs(rewindPending) do if not rewindSlots[slot] then captureRewind(slot) end end
    rewindPending={};saveProgress()
    External.toggle(game:GetNumPlayers()==1 and isSamira(Isaac.GetPlayer(0)),false,true)
end)
mod:AddCallback(ModCallbacks.MC_POST_ENTITY_KILL,function(_,e)
    if e.Type==EntityType.ENTITY_FIREPLACE then return end
    A.onKill(e)
    local gold=Equipment.kill(e,isSamira)
    if gold then Audio.voice(state(e:GetData().SamiraLastHit.owner),'kill',0,12) end
    local xp=Progress.onKill(e,isSamira)
    if gold or xp>0 then
        saveProgress()
    end
end)
mod:AddCallback(ModCallbacks.MC_NPC_UPDATE,function(_,npc)A.updateFear(npc)end)
mod:AddCallback(ModCallbacks.MC_PRE_NPC_UPDATE,function(_,npc)return Knockup.preUpdate(npc)end)
if ModCallbacks.MC_PRE_NPC_RENDER then
    mod:AddCallback(ModCallbacks.MC_PRE_NPC_RENDER,function(_,npc,offset)return Knockup.preRender(npc,offset)end)
end
mod:AddCallback(ModCallbacks.MC_POST_KNIFE_UPDATE,function(_,knife)
    if knife.Variant~=0 or knife.SubType~=0 then return end
    local parent=knife.Parent
    if not parent or not isSamira(parent) then return end
    if QWeapons.hideHeld(knife) then return end
    local p=parent:ToPlayer()
    if not playable(p) or game:IsPaused() then return end
    QWeapons.steer(knife,p)
end)
-- Redraw-based outlines can tint persistent NPC sprite layers. Disabled until
-- a proper alpha-mask outline is available; the enemy cursor remains active.
mod:AddCallback(ModCallbacks.MC_PRE_PICKUP_COLLISION,function(_,coin,entity)
    if isSamira(entity) then Interaction.coinBefore(coin,entity:ToPlayer()) end
end,PickupVariant.PICKUP_COIN)
mod:AddCallback(ModCallbacks.MC_POST_PICKUP_COLLISION,function(_,coin,entity)
    if isSamira(entity) then Interaction.coinAfter(coin,entity:ToPlayer()) end
end,PickupVariant.PICKUP_COIN)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_GRID_COLLISION,function(_,p)
    if isSamira(p) and state(p).dash then return true end
end)
mod:AddCallback(ModCallbacks.MC_PRE_PICKUP_COLLISION,function(_,pickup,entity)
    if not isSamira(entity) then return end
    local p=entity:ToPlayer()
    if Equipment.native(pickup.SubType) then
        Equipment.syncInventory(p)
        if not Equipment.free(p) then return true end
    end
end,PickupVariant.PICKUP_COLLECTIBLE)
mod:AddCallback(ModCallbacks.MC_PRE_ADD_COLLECTIBLE,function(_,id,charge,first,slot,var,p)
    if isSamira(p) and Equipment.native(id) and not Equipment.state(p).syncing then
        Equipment.syncInventory(p)
        if not Equipment.free(p) then return false end
    end
end)
mod:AddCallback(ModCallbacks.MC_POST_ADD_COLLECTIBLE,function(_,id,charge,first,slot,var,p)
    if not rewindLoading and isSamira(p) and not Equipment.state(p).syncing then Equipment.syncInventory(p) end
end)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_COLLISION,function(_,p,other)
    if isSamira(p) and Equipment.has(p,3046) and other and other:ToNPC() then return true end
end)
local blocked={}
for _,name in ipairs({'ACTION_LEFT','ACTION_RIGHT','ACTION_UP','ACTION_DOWN','ACTION_SHOOTLEFT','ACTION_SHOOTRIGHT','ACTION_SHOOTUP','ACTION_SHOOTDOWN','ACTION_BOMB','ACTION_PILLCARD','ACTION_ITEM','ACTION_DROP','ACTION_RESTART'}) do blocked[ButtonAction[name]]=true end
mod:AddCallback(ModCallbacks.MC_INPUT_ACTION,function(_,e,hook,action)
    local p=e and e:ToPlayer() or not e and game:GetNumPlayers()==1 and Isaac.GetPlayer(0)
    local controlled=p and isSamira(p)
    if controlled and not game:IsPaused() then
        local s=state(p)
        if s.readingControls then return end
        if s.configOpen and blocked[action] then
            Controls.pollDrop(p,s,true)
            for _,itemAction in ipairs({ButtonAction.ACTION_ITEM,ButtonAction.ACTION_PILLCARD,ButtonAction.ACTION_BOMB}) do Controls.nativeItem(p,s,itemAction,true) end
            return hook==InputHook.GET_ACTION_VALUE and 0 or false
        end
        if action==ButtonAction.ACTION_DROP then
            local gear=Equipment.state(p)
            local down,trigger=Controls.pollDrop(p,s,s.shopOpen or p:IsDead() or (gear.stasis or 0)>gear.time)
            if hook==InputHook.GET_ACTION_VALUE then return down and 1 or 0 end
            if hook==InputHook.IS_ACTION_TRIGGERED then return trigger end
            return down
        end
        if action==ButtonAction.ACTION_ITEM or action==ButtonAction.ACTION_PILLCARD or action==ButtonAction.ACTION_BOMB then
            local gear=Equipment.state(p)
            local down,trigger=Controls.nativeItem(p,s,action,s.shopOpen or p:IsDead() or (gear.stasis or 0)>gear.time)
            if hook==InputHook.GET_ACTION_VALUE then return down and 1 or 0 end
            if hook==InputHook.IS_ACTION_TRIGGERED then return down and trigger or false end
            return down
        end
        if (action==ButtonAction.ACTION_PAUSE or action==ButtonAction.ACTION_MENUBACK)
            and (s.shopAllowed and (Input.IsButtonPressed(Keyboard.KEY_P,0) or (p.ControllerIndex or 0)>0 and Input.IsButtonPressed(14,p.ControllerIndex)) or s.shopOpen or s.shopEscape) then
            return hook==InputHook.GET_ACTION_VALUE and 0 or false
        end
        if (Input.IsButtonPressed(Keyboard.KEY_LEFT_CONTROL,0) or Input.IsButtonPressed(Keyboard.KEY_RIGHT_CONTROL,0))
            and not Input.IsButtonPressed(Keyboard.KEY_ESCAPE,0) and not Input.IsButtonPressed(Keyboard.KEY_P,0)
            and (action==ButtonAction.ACTION_PAUSE or action==ButtonAction.ACTION_MENUBACK) then
            for i=1,5 do if Input.IsButtonPressed(Keyboard['KEY_'..i],0) then return hook==InputHook.GET_ACTION_VALUE and 0 or false end end
        end
        -- Skills own QWER during gameplay. Preserve explicit pause keys and all paused-menu controls.
        if (action==ButtonAction.ACTION_PAUSE or action==ButtonAction.ACTION_MENUBACK)
            and not Input.IsButtonPressed(Keyboard.KEY_ESCAPE,0) and not Input.IsButtonPressed(Keyboard.KEY_P,0)
            and not ((p.ControllerIndex or 0)>0 and Input.IsButtonPressed(15,p.ControllerIndex)) then
            for _,key in ipairs({'q','w','e','r','attack','stop'}) do
                if Controls.down(p,key) then return hook==InputHook.GET_ACTION_VALUE and 0 or false end
            end
        end
        local intent=state(p).exitIntent
        if intent then
            local value=({[ButtonAction.ACTION_LEFT]=-intent.X,[ButtonAction.ACTION_RIGHT]=intent.X,[ButtonAction.ACTION_UP]=-intent.Y,[ButtonAction.ACTION_DOWN]=intent.Y})[action]
            if value then return hook==InputHook.GET_ACTION_VALUE and math.max(0,value) or value>0 end
        end
    end
    if controlled and not game:IsPaused() and blocked[action] then return hook==InputHook.GET_ACTION_VALUE and 0 or false end
end)
mod:AddCallback(ModCallbacks.MC_PRE_MUSIC_PLAY,function(_,id)return Audio.beforeMusic(id)end)
-- Native actives/cards can create rewards without changing coins or position.
-- Any use commits previous shop trades, including zero-charge/debug uses.
mod:AddCallback(ModCallbacks.MC_USE_ITEM,function(_,id,rng,p)if isSamira(p) then Equipment.clearUndo(p) end end)
mod:AddCallback(ModCallbacks.MC_USE_CARD,function(_,id,p)if isSamira(p) then Equipment.clearUndo(p) end end)
mod:AddCallback(ModCallbacks.MC_USE_PILL,function(_,id,p)if isSamira(p) then Equipment.clearUndo(p) end end)
mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM,function()
    Knockup.clear()
    Mastery.clear()
    Audio.cleanup(true,true)
    Audio.newRoom()
    External.newRoom()
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then state(p).emote=nil;state(p).weaponMotion=nil;Shop.close(state(p));Equipment.room(p,game:GetRoom():IsClear()) end end
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);if isSamira(p) then local s=state(p);ItemEffects.stasis.clear(p);Equipment.state(p).stasis=nil;QWeapons.clear(s);Terrain.finish(p,s,false);stop(s);s.departing=nil;s.cast=nil;s.wBolt=nil;s.wChain=nil;s.fx={};s.hitFX={};s.goldFX={};s.dashGhosts=nil;s.heartsteelHits={};s.heartsteelVisuals={};s.heartsteelSoundPending=nil;s.right=true end end
    saveProgress()
end)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYER_RENDER,function(_,p,offset)
    if not isSamira(p) then return end
    local s=state(p)
    Presentation.state(p,s,game:IsPaused())
    External.capture(p,offset)
    if External.nativeActor(p,game:IsPaused()) then Fallback.draw(p,s,offset);return false end
    -- Native player rendering is beneath the game's fades and cinematics. Let
    -- the compact actor bridge an intentionally hidden external layer as well.
    if External.occluded(p,s) then Fallback.draw(p,s,offset);return false end
    if External.replaces(game:IsPaused()) and External.actorVisible~=false then return false end
    if Probe.enabled and not External.occluded(p,s) and Probe.draw(p,s,offset) then return false end
    Fallback.draw(p,s,offset)
    return false
end)
mod:AddCallback(ModCallbacks.MC_PRE_RENDER,function()
    if game:GetNumPlayers()==0 then Branding.reset();View.restore();return end
    local active=game:GetNumPlayers()==1 and isSamira(Isaac.GetPlayer(0))
    if active then local p=Isaac.GetPlayer(0);Controls.menu(p,state(p),saveProgress) end
    View.fullscreen(active)
    Branding.prepare(game:GetRoom(),active)
    View.prepare(active and not game:IsPaused())
end)
local function cleanup()
    Knockup.clear()
    Mastery.clear()
    Controls.close()
    Audio.cleanup()
    if External.enabled then External.toggle(false) end
    for i=0,game:GetNumPlayers()-1 do local p=Isaac.GetPlayer(i);local s=p:GetData().Samira;if s then ItemEffects.stasis.clear(p);Terrain.finish(p,s,true);QWeapons.clear(s) end end
    Branding.reset();View.finish()
end
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT,function(_,shouldSave)if shouldSave then saveProgress()end;runReady=false;rewindPending={};cleanup()end)
mod:AddCallback(ModCallbacks.MC_PRE_MOD_UNLOAD,function(_,unloaded)if unloaded==mod then cleanup()end end)
local function coverExternalScene()
    External.cover()
    -- MC_POST_RENDER can stop during the stage cinematic. Publish concealment
    -- from the cinematic callback itself, keeping the compositor alive but empty.
    if External.enabled and game:GetNumPlayers()==1 then
        local p=Isaac.GetPlayer(0);if isSamira(p) then External.emit(p,state(p),game:IsPaused()) end
    end
end
mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_RENDER,coverExternalScene)
mod:AddCallback(ModCallbacks.MC_POST_NIGHTMARE_SCENE_SHOW,coverExternalScene)
mod:AddCallback(ModCallbacks.MC_PRE_CHANGE_ROOM,function()
    Knockup.clear()
    Mastery.clear()
    External.leaveRoom()
    if game:GetNumPlayers()==1 then local p=Isaac.GetPlayer(0);if isSamira(p) then External.emit(p,state(p),game:IsPaused()) end end
end)
mod:AddCallback(ModCallbacks.MC_POST_ITEM_OVERLAY_RENDER,function(_,giantbook)
    -- Rainbow poop, hearts, cards and item books are gameplay popups, not CGs.
    -- Sleep/nightmare books really transition away from the room.
    if giantbook==33 or giantbook==44 then coverExternalScene() end
end)
mod:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL,function()External.start()end)
mod:AddCallback(ModCallbacks.MC_POST_RENDER,function()
    View.restore()
    if game:GetNumPlayers()~=1 then perf.since=nil;perf.frames=0;return end
    local p=Isaac.GetPlayer(0);if not isSamira(p) then return end
    local s=state(p)
    local pad=(p.ControllerIndex or 0)>0
    local cursor=pad and (s.shopOpen and s.padCursor or Isaac.WorldToScreen(s.aim or p.Position)) or mouseScreen()
    if pad and not s.shopOpen and game:GetRoom():IsMirrorWorld() then cursor.X=Isaac.GetScreenWidth()-cursor.X end
    if s.shopOpen and not game:IsPaused() and not pad and Input.GetMouseWheel then
        local wheel=Input.GetMouseWheel();Shop.wheel(s,cursor,Isaac.GetScreenWidth(),Isaac.GetScreenHeight(),p,wheel and wheel.Y or 0)
    end
    External.emit(p,s,game:IsPaused(),{position={cursor.X,cursor.Y},controller=pad,enemy=s.hover and not H.contains(cursor,Isaac.GetScreenWidth(),Isaac.GetScreenHeight())})
    if External.hudAllowed(s,game:IsPaused(),p) and not External.hud(game:IsPaused()) then H.draw(p,s,stats(p)) end
    if External.occluded(p,s) then return end
    if game:IsPaused() then
        if not s.pauseObserved then
            local held={}
            for _,name in ipairs({'Q','W','E','R','ESCAPE','P'}) do
                if Input.IsButtonPressed(Keyboard['KEY_'..name],0) then held[#held+1]=name end
            end
            Isaac.DebugString('[Samira pause] observed; held='..table.concat(held,',')..'; cast='..(s.cast and s.cast.kind or 'none')..'; tick='..s.clock)
        end
        s.pauseObserved=true;perf.since=nil;perf.frames=0;return
    end
    s.pauseObserved=false
    if Features.mastery_emote and playable(p) and not s.shopOpen and not s.configOpen and not External.mastery(game:IsPaused()) then Mastery.draw(s,Isaac.WorldToScreen(p.Position)+Vector(0,-80)) end
    if not External.visuals(false) then Visual.screen(s) end
    if not External.hud(false) then H.overhead(p,s,Progress.state(p)) end
    if Isaac.GetTime and perf.reports<4 then
        local now=Isaac.GetTime();perf.since=perf.since or now;perf.frames=perf.frames+1
        if now-perf.since>=5000 then
            Isaac.DebugString(string.format('[Samira performance] render callbacks %.1f FPS over %.1fs; animated sprites, mesh probe=%s',perf.frames*1000/(now-perf.since),(now-perf.since)/1000,tostring(Probe.enabled)))
            perf.since=now;perf.frames=0;perf.reports=perf.reports+1
        end
    end
    local hover=s.hover and not H.contains(mouseScreen(),Isaac.GetScreenWidth(),Isaac.GetScreenHeight())
    if not External.hud(false) then Visual.cursor(mouseScreen(),hover) end
end)
mod:AddCallback(ModCallbacks.MC_POST_ROOM_RENDER_ENTITIES,function()
    if game:GetNumPlayers()==0 then return end
    local p=Isaac.GetPlayer(0);if not isSamira(p) then return end
    local s=state(p);local st=stats(p)
    if External.occluded(p,s) then return end
    if not game:IsPaused() and playable(p) then
        if External.visuals(false) then return end
        local c=s.cast
        if c and c.stage and c.age<c.impact and not External.replaces(false) then
            local shape=G.shape(c.stage,st.scale)
            for _,face in ipairs(c.faces or {c.face}) do Visual.indicator(p.Position,face,shape,c.stage,.9,true,c.age/c.impact,s.indicators) end
        end
        for _,fx in ipairs(s.fx) do
            local shape=fx.stage and G.shape(fx.stage,fx.scale) or {kind='circle',cx=20,radius=30,inner=18}
            if not fx.stage or not External.replaces(false) then Visual.impact(fx,shape) end
        end
        Visual.click(s)
        Visual.abilities(p,s)
        Visual.hits(s)
    end
end)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYERHUD_RENDER_HEARTS,function(_,offset,sp,pos,scale,p)
    if isSamira(p) then return true end
end)
mod:AddCallback(ModCallbacks.MC_PRE_PLAYERHUD_TRINKET_RENDER,function(_,slot,pos,scale,p,crop)
    if isSamira(p) then local l=H.layout(Isaac.GetScreenWidth(),Isaac.GetScreenHeight()).left
        return {Position=Vector(l.x+18+(slot or 0)*13,l.y-48),Scale=.55,CropOffset=crop}
    end
end)
mod:AddCallback(ModCallbacks.MC_EVALUATE_CACHE,function(_,p,flag)
    if isSamira(p) and flag==CacheFlag.CACHE_FLYING and state(p).ultimateFlight then p.CanFly=true end
end)
mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD,function(_,command,args)
    if command=='0cd' and game:GetNumPlayers()>0 then
        local p=Isaac.GetPlayer(0);if isSamira(p) then local s=state(p);s.noCD=args=='on' or args~='off' and not s.noCD;Isaac.ConsoleOutput('0cd '..(s.noCD and 'ON' or 'OFF')..'\n') end
        return
    end
    if command~='samira' or game:GetNumPlayers()==0 then return end
    local p=Isaac.GetPlayer(0)
    if args=='start' then local s=p:GetData().Samira;if s then Terrain.finish(p,s,true) end;p:ChangePlayerType(TYPE);p:GetData().Samira=nil;p:GetData().SamiraHealth=nil;Progress.restore(p);Health.restore(p);Equipment.restore(p);Progress.award(p,Progress.required(1)+Progress.required(2));Health.sync(p);Equipment.coinDisplay(p);External.toggle(true,false,true);Isaac.ConsoleOutput('Samira ready. RMB move/attack; Q W E R; S stop.\n')
    elseif args:match('^level %d+$') and isSamira(p) then
        local target=tonumber(args:match('%d+'));local progress=Progress.state(p)
        if p:IsDead() or target<progress.level or target>Progress.MAX_LEVEL then
            Isaac.ConsoleOutput('Choose a level from your current level to 18 while alive.\n');return
        end
        if target>progress.level then
            local xp=-progress.xp
            for level=progress.level,target-1 do xp=xp+Progress.required(level) end
            Progress.award(p,xp);Health.sync(p);saveProgress()
        end
        Isaac.ConsoleOutput(string.format('Level %d | unspent skill points %d\n',progress.level,Progress.points(p)))
    elseif args=='health' and isSamira(p) then
        local h=Health.state(p);Isaac.ConsoleOutput(string.format('HP %.3f / %.3f | shield %.3f | incoming floor multiplier x%.2f\n',h.hp,Health.max(p),h.soul,Health.floorMultiplier()))
    elseif (args=='heal' or args:match('^heal %d+$')) and isSamira(p) then
        local amount=args=='heal' and Health.missing(p) or math.min(Health.missing(p),tonumber(args:match('%d+')))
        local healed=Health.heal(p,amount);Health.sync(p);saveProgress()
        Isaac.ConsoleOutput(string.format('Healed %.3f HP | HP %.3f / %.3f\n',healed,Health.current(p),Health.max(p)))
    elseif args=='config' and isSamira(p) then Controls.open(p,saveProgress)
    elseif args:match('^gold %d+$') and isSamira(p) then
        Equipment.addGold(p,tonumber(args:match('%d+'))-p:GetNumCoins());saveProgress();Isaac.ConsoleOutput('Shop gold: '..Equipment.state(p).gold..'\n')
    elseif args=='indicators client' or args=='indicators debug' or args=='indicators off' then
        state(p).indicators=args:match('indicators (%w+)');Isaac.ConsoleOutput('Indicators: '..state(p).indicators..'\n')
    elseif args=='overlay hide' or args=='overlay show' then External.manualHidden=args=='overlay hide';External.last=nil
    elseif args=='render on' then Probe.toggle(true)
    elseif args=='render off' then Probe.toggle(false)
    elseif args=='external on' then
        if isSamira(p) then External.toggle(true) else Isaac.ConsoleOutput('First enter: samira start\n') end
    elseif args=='external off' then External.toggle(false)
    elseif args=='external preview' then
        if isSamira(p) then External.toggle(true,true) end
    elseif args=='animations' then Isaac.ConsoleOutput(Emotes.list()..'\n')
    elseif args:sub(1,5)=='anim ' then
        if External.available() and isSamira(p) then
            if args=='anim off' then state(p).emote=nil
            elseif not Emotes.start(state(p),args:sub(6)) then Isaac.ConsoleOutput('Unknown animation or currently attacking. Use samira animations.\n') end
        else Isaac.ConsoleOutput('Enable samira external on first.\n') end
    elseif args=='view off' or args=='view on' then Isaac.ConsoleOutput('Native room view is restored; no room scaling is used.\n')
    elseif args=='test' then
        if not isSamira(p) then Isaac.ConsoleOutput('First enter: samira start\n');return end
        -- Explicit test command only: add three ordinary targets, no room/save reset.
        local room=game:GetRoom()
        for _,delta in ipairs({Vector(100,0),Vector(120,-65),Vector(120,65)}) do
            local pos=room:FindFreePickupSpawnPosition(p.Position+delta,0,true)
            Isaac.Spawn(EntityType.ENTITY_GAPER,0,0,pos,Vector.Zero,nil)
        end
    else Isaac.ConsoleOutput('samira level 6 | samira heal [amount] | samira health | samira gold 99 | 0cd on/off | samira test | samira config | samira start | samira external on/off\n') end
end)
Isaac.DebugString('[Samira] External actor 0.7.41 loaded; native size, multishot Q and cast-locked knives')
