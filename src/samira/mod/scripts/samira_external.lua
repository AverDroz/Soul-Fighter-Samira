-- Auto telemetry with an external rendering acknowledgement. Gameplay saves are untouched.
local B={enabled=false,connected=false,serial=0,room=0};local json=require('json');local G=include('scripts.samira_geometry')
local Anim=include('scripts.samira_animation_data')
local Screen=include('scripts.samira_screen')
local Emotes=include('scripts.samira_emotes');local Presentation=include('scripts.samira_presentation')
local Shop=include('scripts.samira_shop')
local Equipment=include('scripts.samira_equipment')
local H=include('scripts.samira_hud');local Progress=include('scripts.samira_progression')
local Passive=include('scripts.samira_passive')
local PassivePose=include('scripts.samira_passive_pose')
local Controls=include('scripts.samira_controls')
function B.toggle(on,preview,quiet)
    B.enabled=on;B.preview=preview==true;B.sequence=0;B.last=nil;B.untilTime=math.huge
    B.connected=false;B.actorOwned=false;B.hudOwned=false;B.renderSample=nil;B.lastActorPosition=nil;B.capabilities={};B.ackTime=nil;B.pollAt=nil;B.serial=B.serial+1
    B.session=tostring(Isaac.GetTime())..':'..B.serial
    B.actorRecovering=nil
    Isaac.DebugString('[SAMIRA_EXTERNAL] '..json.encode({version=1,active=false}))
    if not quiet then Isaac.ConsoleOutput(on and 'External actor waiting for renderer; automatic sprite fallback enabled.\n' or 'External actor OFF; sprites restored.\n') end
end
function B.poll()
    if not B.enabled then return end
    local now=Isaac.GetTime()
    if B.pollAt and now<B.pollAt then return end
    -- A single file-sharing/parse miss is not a disconnect. Retain only the last
    -- verified heartbeat's original lease; failures never renew it.
    B.pollAt=now+50;local connected=B.connected and B.ackTime and now-B.ackTime<1000 or false
    if type(Isaac.LoadModDataFromFolder)=='function' then
        local ok,text=pcall(Isaac.LoadModDataFromFolder,'samira_external_link')
        if ok and type(text)=='string' and #text<4096 then
            local parsed,ack=pcall(json.decode,text)
            if parsed and type(ack)=='table' then
                connected=ack.version==1 and ack.session==B.session and ack.ready==true
                    and type(ack.time)=='number' and ack.time<=now+100 and now-ack.time<1000
                if connected then
                    -- A rewind invalidates the old scene's actor acknowledgement.
                    if ack.visible==true and (not B.actorRecovering or ack.room==B.room) then
                        B.actorOwned=true;B.actorRecovering=nil
                    end
                    B.hudOwned=B.hudOwned or ack.hudVisible==true;B.ackTime=math.min(now,ack.time)
                    B.actorVisible=ack.visible;B.hudVisible=ack.hudVisible;B.actorRoom=ack.room
                    B.capabilities=type(ack.capabilities)=='table' and ack.capabilities or {}
                end
            end
        end
    end
    if connected~=B.connected then Isaac.DebugString('[Samira external] '..(connected and 'renderer connected' or 'renderer unavailable; sprite restored')) end
    B.connected=connected
    if not connected then B.capabilities={};B.actorOwned=false;B.hudOwned=false end
end
function B.available()
    return B.enabled and B.connected and B.ackTime and Isaac.GetTime()-B.ackTime<1000
end
function B.replaces(paused)
    return B.available() and not B.preview and B.actorOwned==true
end
function B.visuals(paused)
    return not paused and B.replaces(paused) and B.capabilities.combat==1
end
function B.hud(paused)
    return B.available() and not B.preview and B.hudOwned==true and B.capabilities.hud==1
end
function B.mastery(paused)
    return B.visuals(paused) and B.capabilities.mastery==1
end
function B.shop(paused)
    return not paused and B.replaces(paused) and B.capabilities.shop==1
end
function B.newRoom(recoverActor)
    B.room=B.room+1;B.last=nil;B.roomCoverUntil=nil;B.renderSample=nil;B.revealAt=Isaac.GetTime()+400
    if recoverActor then
        B.actorOwned=false;B.actorRecovering=true;B.pollAt=nil;B.lastActorPosition=nil
    end
end
function B.leaveRoom()B.roomCoverUntil=Isaac.GetTime()+1000;B.last=nil end
function B.roomChanging(s)
    local now=Isaac.GetTime()
    return now<(B.revealAt or 0) or now<(B.roomCoverUntil or 0) or s.departing and now<s.departing
        or RoomTransition and RoomTransition.GetTransitionMode and RoomTransition.GetTransitionMode()~=0 or false
end
function B.cover()
    local now=Isaac.GetTime()
    if now>=(B.coverUntil or 0) then B.last=nil end
    B.coverUntil=now+650
end
function B.start()B.startUntil=Isaac.GetTime()+2200;B.last=nil end
function B.hudAllowed(s,paused,p)
    local now=Isaac.GetTime()
    if B.manualHidden or now<(B.startUntil or 0) or now<(B.coverUntil or 0) then return false end
    if RoomTransition and RoomTransition.IsRenderingBossIntro and RoomTransition.IsRenderingBossIntro() then return false end
    local animation=p and not p:IsDead() and p:GetSprite():GetAnimation() or ''
    if animation:find('Trapdoor',1,true) or animation=='LightTravel' or animation=='HoleIn' or animation=='FallIn' then return false end
    return true
end
function B.nativeActor(p,paused)
    local menu=Game().IsPauseMenuOpen and Game():IsPauseMenuOpen() or false
    local animation=p:GetSprite():GetAnimation() or ''
    return menu or not p:IsDead() and (animation:find('Trapdoor',1,true)~=nil or animation=='LightTravel' or animation=='HoleIn' or animation=='FallIn')
end
function B.occluded(p,s)
    if B.nativeActor(p,Game():IsPaused()) then return true end
    if not B.hudAllowed(s,false,p) then return true end
    -- Cosmetic animations, temporary input locks, pauses and ordinary room
    -- scrolling are not blackouts. Only explicit floor/teleport presentation is.
    local animation=p:GetSprite():GetAnimation() or ''
    return not p:IsDead() and (animation:find('Teleport',1,true)~=nil or animation:find('Trapdoor',1,true)~=nil
        or animation=='LightTravel' or animation=='HoleIn' or animation=='FallIn')
end
function B.capture(p,offset)
    -- This is the same render-space position used by the native sprite. Unlike
    -- world coordinates it includes the scrolling room's actual draw offset.
    local position=Isaac.WorldToRenderPosition(p.Position)+(offset or Vector.Zero)
    B.renderSample={position=position,at=Isaac.GetTime(),room=B.room}
    B.lastActorPosition=position
end
function B.actorPosition(p,s)
    local sample=B.renderSample;local now=Isaac.GetTime()
    if sample and sample.room==B.room and now-sample.at<100 then return sample.position,true end
    if B.roomChanging(s) and B.lastActorPosition then return B.lastActorPosition,false end
    return Isaac.WorldToScreen(p.Position),false
end
function B.emit(p,s,paused,cursor)
    if not B.enabled then return end
    cursor=cursor or {position={-1,-1}}
    local now=Isaac.GetTime()
    B.poll()
    local transition=B.roomChanging(s)
    if RoomTransition and type(RoomTransition.GetTransitionMode)=='function' then
        transition=transition or RoomTransition.GetTransitionMode()~=0
    end
    local hidden=B.occluded(p,s)
    if B.last and transition==B.transition and hidden==B.hidden and now-B.last<(B.available() and 32 or 200) then return end
    if B.hidden~=hidden then Isaac.DebugString('[Samira visibility] hidden='..tostring(hidden)..'; animation='..(p:GetSprite():GetAnimation() or '')..'; room='..B.room) end
    B.hidden=hidden
    B.transition=transition
    B.last=now;B.sequence=B.sequence+1
    local walking=p.Velocity:Length()>.6;local c=s.cast;local ultimate=(s.rUntil or 0)>s.clock
    local flying=p.CanFly==true;local winged=ultimate or flying
    local kind=c and c.kind or s.dash and 'Dash' or walking and 'Walk' or 'Idle'
    if winged and kind~='RStart' and kind~='W' and kind~='Draw' and kind~='Sheathe' then kind='R'..kind
    elseif not s.weapon and not c and not s.dash then kind=walking and 'SheathedWalk' or 'SheathedIdle' end
    local motion=not c and not s.dash and not s.emote and not p:IsDead() and s.weaponMotion
    if winged and motion and (motion.kind=='Draw' or motion.kind=='Sheathe') then motion=nil end
    if motion then kind=motion.kind end
    local face=c and c.face or s.face;local pos,captured=B.actorPosition(p,s)
    -- The normal client Q1/Q3 clips end at the strike, unlike the longer ULT
    -- clips. Keep the sword contact aligned with the unchanged gameplay impact.
    local groundContact=not winged and (kind=='Q1' or kind=='Q3') and .9 or nil
    local info=Anim[kind];local phase=c and G.castPhase(kind,c,0,groundContact) or s.dash and s.dash.age/s.dash.duration or (walking and (s.walkClock or 0) or s.clock)/(30*info.duration)%1
    local clip,emotePhase,looping=Emotes.frame(s)
    local special=Presentation.state(p,s,paused)
    local passiveClip,passivePhase,passiveLoop,passiveWalk=PassivePose.frame(p,s,walking,winged,special~=nil or clip~=nil,B.room)
    if passiveClip and not clip then clip=passiveClip;emotePhase=passivePhase;looping=passiveLoop end
    if motion then phase=motion.age/motion.duration end
    if c and c.passive then clip='Passive_Attack';looping=false;local contact=.4
        phase=c.age<=c.impact and contact*c.age/c.impact or contact+(1-contact)*(c.age-c.impact)/(c.duration-c.impact)
        emotePhase=phase
    end
    if special then kind=special.kind;phase=math.min(1,special.age/Anim[kind].duration);clip=nil
    elseif clip then phase=emotePhase end
    local function screen(v)local q=Isaac.WorldToScreen(v);return {q.X,q.Y}end
    local function faces(list)local out={};for _,f in ipairs(list) do out[#out+1]={f.X,f.Y} end;return out end
    local bodyScale=G.bodyScale(p)
    local payload={version=1,companionProtocol=1,modVersion='0.0.1',active=true,seq=B.sequence,time=now,clock=s.clock,paused=paused,preview=B.preview,
        session=B.session,room=B.room,presentation=2,renderCaptured=captured,transition=transition,occluded=hidden,hudVisible=B.hudAllowed(s,paused,p),takeover=B.available()==true,
        screen={Isaac.GetScreenWidth(),Isaac.GetScreenHeight()},position={pos.X,pos.Y},face={face.X,face.Y},bodyScale={bodyScale.X,bodyScale.Y},
        kind=kind,phase=phase,clip=clip,looping=clip and looping or (not special and not c and not s.dash and not motion),ultimate=ultimate,flying=flying,banner=s.bannerVisible~=false,
        hurt=(s.hurtUntil or 0)>s.clock,dead=p:IsDead(),cast=c and {kind=c.kind,stage=c.stage,age=c.age,impact=c.impact,duration=c.duration},
        shape=c and c.stage and G.shape(c.stage,G.stats(p.Damage,p.MaxFireDelay,p.TearRange,p.Luck,p.MoveSpeed).scale),fx={}}
    if c and c.stage then payload.cast.faces=faces(c.faces or {c.face}) end
    if clip then payload.looping=looping end
    if motion and walking then
        local walkKind=motion.kind=='RStart' and 'RWalk' or motion.kind=='Sheathe' and 'Walk' or 'SheathedWalk'
        payload.locomotion={kind=walkKind,phase=(s.walkClock or 0)/(30*Anim[walkKind].duration)%1}
    end
    if passiveWalk and clip==passiveClip then payload.locomotion=passiveWalk end
    for _,f in ipairs(s.fx) do if f.stage then
        payload.fx[#payload.fx+1]={position=screen(f.origin),face={f.face.X,f.face.Y},stage=f.stage,age=f.age,shape=G.shape(f.stage,f.scale)}
    end end
    -- Export presentation state only; damage, cooldowns and HP remain owned by Isaac.
    local zero=Isaac.WorldToScreen(Vector.Zero);local axis=Isaac.WorldToScreen(Vector(100,100))-zero
    if s.masteryAt and s.clock>=s.masteryAt and s.clock-s.masteryAt<120 and not s.shopOpen and not s.configOpen then
        local mp=Isaac.WorldToScreen(p.Position)+Vector(0,-80)
        payload.mastery={at=s.masteryAt,position={mp.X,mp.Y}}
    end
    payload.ground={axis.X/100,axis.Y/100*G.groundScale}
    payload.units=G.units;payload.hits={};payload.cursor=cursor;payload.goldFX={}
    payload.heartsteel={}
    for _,v in ipairs(s.heartsteelVisuals or {}) do
        if v.target:Exists() and not v.target:IsDead() then
            payload.heartsteel[#payload.heartsteel+1]={position=screen(v.target.Position),progress=v.charge/90,size=v.target.Size or 12,key=v.key,stage=math.max(1,math.floor(v.charge/15)),age=v.age or 0}
        end
    end
    payload.heartsteelHits={}
    for _,hit in ipairs(s.heartsteelHits or {}) do
        local age=s.clock-hit.at
        if age>=0 and age<90 then payload.heartsteelHits[#payload.heartsteelHits+1]={position=screen(hit.position),age=age,at=hit.at,size=hit.size} end
    end
    for _,f in ipairs(s.goldFX or {}) do if s.clock-f.at<42 then
        payload.goldFX[#payload.goldFX+1]={position=screen(f.position),at=f.at,amount=f.amount,lane=f.lane}
    end end
    for _,f in ipairs(s.hitFX or {}) do payload.hits[#payload.hits+1]={position=screen(f.position),at=f.at,strong=f.strong} end
    if s.wBolt then local b=s.wBolt;payload.bolt={origin=screen(b.origin),position=screen(b.position),face={b.face.X,b.face.Y},age=b.born and (s.clock-b.born)/30} end
    if s.wChain and s.wChain.target:Exists() and not s.wChain.target:IsDead() then
        local w=s.wChain;payload.chain={anchor=screen(w.anchor),target=screen(w.target.Position),face={w.face.X,w.face.Y},expires=w.expires,pulled=w.pulled==true,
            shape=G.wShape()}
    end
    if s.dash then local d=s.dash;payload.dash={origin=screen(d.origin),target=screen(d.target),age=d.age,duration=d.duration} end
    payload.r={started=s.rStartedAt,untilTick=s.rUntil or 0};payload.levelUp=s.levelUpAt;payload.screenHitAt=s.screenHitAt
    if s.click and s.clock-s.click.at<28 then payload.click={position=screen(s.click.position),at=s.click.at,enemy=s.click.enemy} end
    local hp,maxHP=H.healthNumbers(p);local red,soul,capacity=H.health(p);local progress=Progress.state(p)
    payload.hud={hp=hp,maxHP=maxHP,red=red/capacity,soul=soul/capacity,level=progress.level,xp=progress.xp,
        nextXP=Progress.required(progress.level),skillPoints=Progress.points(p),gold=Equipment.state(p).gold,layout=H.layout(Isaac.GetScreenWidth(),Isaac.GetScreenHeight()),skills={}}
    for _,key in ipairs({'q','w','e','r'}) do
        payload.hud.skills[key]={remaining=math.max(0,(s[key..'Ready'] or 0)-s.clock),
            total=key=='q' and s.chainUntil and G.qRecast or Equipment.cooldown(p,Progress.cooldown(p,key),key=='r'),
            rank=Progress.rank(p,key),canUpgrade=Progress.canUpgrade(p,key)}
    end
    payload.shop=Shop.payload(s,Isaac.GetScreenWidth(),Isaac.GetScreenHeight(),p,Game():GetRoom())
    local gear=Equipment.state(p);local attributes=Equipment.sum(p)
    payload.stasis=not p:IsDead() and (gear.stasis or 0)>gear.time
    -- Companion holds the last rendered pose while stasis is active.
    payload.hud.shield=math.floor((gear.shield or 0)*(1+attributes.healPower)*(Equipment.has(p,3065) and 1.25 or 1))
    if gear.redemption then payload.redemption={position=screen(Vector(gear.redemption.x,gear.redemption.y)),remaining=gear.redemption.at-gear.time} end
    payload.hud.inventory=Equipment.state(p).slots;payload.hud.gearTime=Equipment.state(p).time
    payload.hud.heartsteel=gear.heartsteel or 0
    payload.hud.nativeItems=Equipment.nativePayload(p)
    payload.hud.soulHP=math.ceil(soul)
    payload.hud.buffs={}
    for _,entry in ipairs({{'WhiteHeartHalf','GetEternalHearts'},{'GoldHeartOverlay','GetGoldenHearts'},{'BoneHeartEmpty','GetBoneHearts'},{'RottenHeartFull','GetRottenHearts'},{'BrokenHeart','GetBrokenHearts'}}) do
        local count=p[entry[2]] and p[entry[2]](p) or 0
        if count>0 then payload.hud.buffs[#payload.hud.buffs+1]={icon=entry[1],count=count} end
    end
    payload.hud.pocket={card=p.GetCard and p:GetCard(0) or 0,pill=p.GetPill and p:GetPill(0) or 0}
    payload.hud.qStage=s.nextQ
    payload.language=Controls.language();payload.hud.keys={}
    for _,key in ipairs({'q','w','e','r'}) do payload.hud.keys[key]=Controls.label(p,key) end
    payload.hud.gearSelected=(p.ControllerIndex or 0)>0 and s.gearSelected or nil
    payload.indicators=s.indicators or 'client'
    payload.cursor.down=Input.IsMouseBtnPressed(0) or Input.IsMouseBtnPressed(1)
    payload.cursor.shop=s.shopOpen==true
    payload.hud.offset=Options and Options.HUDOffset or 0
    payload.hud.passive={remaining=Passive.remaining(p),total=Passive.total(p),ready=Passive.ready(p)}
    if Game():GetRoom():IsMirrorWorld() then Screen.mirror(payload) end
    Isaac.DebugString('[SAMIRA_EXTERNAL] '..json.encode(payload))
end
return B
