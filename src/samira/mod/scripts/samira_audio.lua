-- Original default-skin Wwise events; only our own sound IDs are ever stopped.
local S={};local ids={};local durations=include('scripts.samira_audio_data')
for name,seconds in pairs(include('scripts.samira_voice_data')) do durations[name]=seconds end
for name,seconds in pairs(include('scripts.samira_voice_en_data')) do durations[name]=seconds end
local Controls=include('scripts.samira_controls')
local clips=include('scripts.samira_external_actions')
local Progress=include('scripts.samira_progression')
local Music=include('scripts.samira_music')
local Presentation=include('scripts.samira_presentation')
S.startRMusic=Music.start;S.stopRMusic=Music.stop;S.beforeMusic=Music.beforePlay
local voice,voiceEvent,voicePriority,voiceState,voiceGap,voiceContext,emoteOwner
local R_PRIORITY=math.huge
-- Ordinary cast efforts yield to dialogue. Drop them while speech is playing;
-- never queue a grunt for after the action, or let it reset the dialogue gap.
local efforts={q1=true,q2=true,q3=true,w=true,e=true}
-- The same Wwise dialogue node in both languages, not a random attack sample.
durations.vo_boss=6.928367;durations.vo_en_boss=6.027030
local bossRooms,bossRoom,bossPending,bossScan={},nil,nil,0
local majorBosses={}
for _,name in ipairs({'ENTITY_MOM','ENTITY_MOMS_HEART','ENTITY_ISAAC','ENTITY_SATAN',
    'ENTITY_THE_LAMB','ENTITY_MEGA_SATAN','ENTITY_MEGA_SATAN_2','ENTITY_HUSH',
    'ENTITY_DELIRIUM','ENTITY_ULTRA_GREED','ENTITY_MOTHER','ENTITY_DOGMA','ENTITY_BEAST'}) do
    if EntityType[name] then majorBosses[EntityType[name]]=true end
end
function S.resetBossRooms()
    bossRooms={};bossRoom=nil;bossPending=nil;bossScan=0
end
function S.newRoom()
    bossRoom=nil;bossPending=nil;bossScan=0
end
local function id(name)
    if not ids[name] then ids[name]=Isaac.GetSoundIdByName('Samira '..name) end
    return ids[name]
end
function S.play(name,loop,volume)
    local sound=id(name)
    if sound and sound>0 then SFXManager():Play(sound,volume or .8,0,loop or false,1) end
end
function S.stop(name)
    if ids[name] and ids[name]>0 then SFXManager():Stop(ids[name]) end
end
function S.playing(name)
    return ids[name] and SFXManager():IsPlaying(ids[name]) or false
end
local function releaseVoice(completed)
    if completed and voiceEvent=='boss' and bossPending then
        bossRooms[bossPending]=true;bossPending=nil
    end
    if voiceState and not efforts[voiceEvent] then voiceState.voiceReady=voiceState.clock+math.ceil((voiceGap or 0)*30) end
    voice=nil;voiceEvent=nil;voicePriority=nil;voiceState=nil;voiceGap=nil;voiceContext=nil
end
local function pollVoice()
    if voice and not S.playing(voice) then releaseVoice(true) end
end
function S.voice(s,name,priority,gap)
    pollVoice()
    if name=='r' then priority=R_PRIORITY end
    if efforts[name] then priority=-1 end
    local language=Controls.language()
    local key=(language=='zh' and 'vo_' or 'vo_en_')..name
    if not durations[key] or s.clock<(s.voiceReady or 0) and priority==0 then return end
    if voice and SFXManager():IsPlaying(id(voice)) then
        if priority<=voicePriority then return end
        S.stop(voice);releaseVoice()
    end
    local sound=key
    if name=='r' then
        if not s.rVoiceBag or #s.rVoiceBag==0 or s.rVoiceLanguage~=language then
            s.rVoiceLanguage=language
            s.rVoiceBag={1,2,3,4,5,6,7,8}
            for i=8,2,-1 do local j=math.random(i);s.rVoiceBag[i],s.rVoiceBag[j]=s.rVoiceBag[j],s.rVoiceBag[i] end
            if s.rVoiceBag[8]==s.lastRVoice then s.rVoiceBag[8],s.rVoiceBag[1]=s.rVoiceBag[1],s.rVoiceBag[8] end
        end
        s.lastRVoice=table.remove(s.rVoiceBag);sound=string.format(key..'_%02d',s.lastRVoice)
    elseif name=='attack' then
        -- Select explicit single-sample IDs instead of asking the engine to
        -- randomize a multi-sample event. Blocked requests never consume a line.
        s.attackVoiceBags=s.attackVoiceBags or {}
        local pool=s.attackVoiceBags[language] or {bag={}}
        s.attackVoiceBags[language]=pool
        if #pool.bag==0 then
            for i=1,21 do pool.bag[i]=i end
            for i=21,2,-1 do local j=math.random(i);pool.bag[i],pool.bag[j]=pool.bag[j],pool.bag[i] end
            if pool.bag[21]==pool.last then pool.bag[21],pool.bag[1]=pool.bag[1],pool.bag[21] end
        end
        pool.last=table.remove(pool.bag);sound=string.format(key..'_%02d',pool.last)
        s.lastAttackVoice=sound
    end
    voice=sound;voiceEvent=name;voicePriority=priority;voiceState=s;voiceGap=gap or 3;voiceContext=nil
    S.play(sound,false,name=='r' and .95 or .8)
    -- This upper bound is replaced with the actual finish time by pollVoice.
    if not efforts[name] then s.voiceReady=s.clock+math.ceil((durations[key]+(gap or 3))*30) end
    return true
end
function S.cast(s,name)
    S.play(name..'_cast');S.voice(s,name,name=='r' and R_PRIORITY or 2)
end
function S.command(p,s,targeted,aim)
    local combat=not Game():GetRoom():IsClear()
    local name='move'
    if combat or targeted then name='attack'
    elseif Progress.rank(p,'r')>0 and s.clock>=(s.rReady or 0) then name='r_ready'
    elseif aim and p.Position:Distance(aim)>180 then name='move_long' end
    if S.voice(s,name,0,12) then voiceContext=combat and 'combat' or targeted and 'attack' or 'move' end
end
function S.strike(stage,result)
    if not stage then if result>0 then S.play('attack_hit') end;return end
    S.play(result==0 and ('q'..stage..'_miss') or ((stage==3 and 'q3' or 'q')..(result==2 and '_sweet' or '_hit')))
end
function S.stopEmote()
    if not emoteOwner then return end
    for _,name in ipairs({'joke','taunt','dance_intro','dance_loop'}) do S.stop(name) end
    if voicePriority==4 and voice then S.stop(voice);releaseVoice() end
    emoteOwner=nil
end
function S.emote(s)
    if emoteOwner~=s.emote then
        S.stopEmote();emoteOwner=s.emote
        if not emoteOwner then return end
        local name=emoteOwner.intro
        if name=='Joke' then S.play('joke');S.voice(s,'joke',4)
        elseif name=='Taunt_Into' or name=='ULT_Taunt_Into' then S.play('taunt');S.voice(s,'taunt',4)
        elseif name=='Dance_Windup' or name=='Dance_Loop' then S.play('dance_intro');S.voiceStop()
        elseif name=='Laugh' then S.voice(s,'laugh',4) end
    end
    local e=s.emote
    if e and (e.intro=='Dance_Windup' or e.intro=='Dance_Loop') and not e.audioLoop
        and (s.clock-e.at)/30>=(e.intro=='Dance_Loop' and 0 or clips[e.intro]) then
        S.stop('dance_intro');S.play('dance_loop',true,.65);e.audioLoop=true
    end
end
function S.voiceStop(force)
    if voice and (force or voicePriority~=R_PRIORITY) then S.stop(voice);releaseVoice() end
end
function S.observe(p,s)
    pollVoice()
    if s.heartsteelSoundPending then s.heartsteelSoundPending=nil;S.play('heartsteel_hit',false,.9) end
    if s.levelSoundPending then s.levelSoundPending=nil;S.play('ui_level') end
    if p:IsDead() then
        if not s.audioDead then S.cleanup(voicePriority==R_PRIORITY);s.audioDead=true;S.play('death');S.voice(s,'death',5) end
    else
        s.audioDead=nil
        -- Scan at most twice a second until a story boss actually exists. Some
        -- entrances (notably Hush/Dogma) spawn the boss after the room callback.
        if not bossRoom then
            local room=Game():GetRoom();local level=Game():GetLevel()
            bossRoom=table.concat({Game():GetSeeds():GetStartSeed(),level:GetAbsoluteStage(),
                level:GetDimension(),room:GetSpawnSeed()},':')
        end
        if not bossRooms[bossRoom] and not bossPending and s.clock>=bossScan then
            bossScan=s.clock+15
            for _,enemy in ipairs(Isaac.GetRoomEntities()) do
                if majorBosses[enemy.Type] and enemy:Exists() and not enemy:IsDead()
                    and not enemy:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then
                    bossPending=bossRoom;break
                end
            end
        end
        -- R can interrupt this line; it remains pending until fully played.
        if bossPending and voiceEvent~='boss' and Presentation.canAct(p) then S.voice(s,'boss',6,6) end
        local combat=not Game():GetRoom():IsClear()
        if not combat and voiceState==s and voiceContext=='combat' then
            -- Clear/room entry ends ambient combat speech. Explicit attack
            -- responses, skill lines and the absolute-priority R line are separate.
            S.voiceStop()
        elseif combat and voiceState==s and (voiceEvent=='move' or voiceEvent=='move_long' or voiceEvent=='r_ready') then
            S.voiceStop();if S.voice(s,'attack',1,12) then voiceContext='combat' end
        end
        if (s.rUntil or 0)>s.clock and Presentation.canAct(p) then Music.start() else Music.stop() end
    end
end
function S.cleanup(keepVoice,keepMusic)
    if not keepMusic then Music.stop() end
    local keep=keepVoice and voice and (voicePriority<4 or voicePriority==R_PRIORITY)
    for name,sound in pairs(ids) do if sound>0 and not (keep and name==voice) then SFXManager():Stop(sound) end end
    if not keep then releaseVoice() end
    emoteOwner=nil
end
return S
