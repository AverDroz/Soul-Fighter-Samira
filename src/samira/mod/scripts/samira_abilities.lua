local Health=include('scripts.samira_health')
-- Isaac-sized distances and cooldowns; W's escape/pull and R's reset rules follow Samira.
local G=include('scripts.samira_geometry')
local Audio=include('scripts.samira_audio')
local Equipment=include('scripts.samira_equipment')
local Progress=include('scripts.samira_progression')
local A={W_RANGE=825*G.units,W_SPEED=1800*G.units/30,W_DELAY=45,R_DURATION=300}
local function live(e)return e and e:Exists() and not e:IsDead() end
function A.ultimate(s)return (s.rUntil or 0)>s.clock end
function A.modifiers(s)
    if not A.ultimate(s) then return 1,1,1 end
    local rank=s.rRank or 1
    return ({1.2,1.3,1.4})[rank],1+(.4+.2*rank)*math.max(0,1-(s.clock-(s.rHasteAt or s.clock))/180),({1.4,1.6,1.8})[rank]
end
function A.segment(a,b,p)
    local d=b-a;local len=d.X*d.X+d.Y*d.Y
    local t=len>0 and math.max(0,math.min(1,((p.X-a.X)*d.X+(p.Y-a.Y)*d.Y)/len)) or 0
    return (p-(a+d*t)):Length(),t
end
function A.inside(chain,pos)
    local v=G.unproject(pos-chain.anchor):Rotated(-chain.face:GetAngleDegrees())
    -- Match the native trapezoidal marker: narrow behind the impact, wide in front.
    return G.hit(G.wShape(),v.X,v.Y,0)
end
function A.castW(p,s,aim)
    if Progress.rank(p,'w')==0 or s.cast or s.clock<(s.wReady or 0) then return false end
    local delta=G.unproject(aim-p.Position);local face=delta:Length()>1 and delta:Normalized() or s.face
    s.face=face;s.weapon=true;s.combatUntil=s.clock+180;s.wReady=s.clock+Equipment.cooldown(p,Progress.cooldown(p,'w'),false)
    s.cast={kind='W',face=face,age=0,impact=8,duration=10};s.goal=nil;s.path=nil
    Audio.cast(s,'w')
    return true
end
function A.launchW(p,s,c)
    local origin=Vector(p.Position.X,p.Position.Y)
    s.wBolt={origin=origin,position=origin,face=c.face,left=A.W_RANGE,born=s.clock}
    Audio.play('w_launch')
end
function A.castR(p,s,entities)
    if Progress.rank(p,'r')==0 or s.cast or s.clock<(s.rReady or 0) then return false end
    s.rRank=Progress.rank(p,'r')
    s.rReady=s.clock+Equipment.cooldown(p,Progress.cooldown(p,'r'),true);s.rUntil=s.clock+A.R_DURATION;s.rHasteAt=s.clock;s.rStartedAt=s.clock
    -- Spell4 is a cosmetic gesture, not a movement/attack lock. Preserve the
    -- current order and let a subsequent attack or skill replace the gesture.
    s.weapon=true;s.combatUntil=s.rUntil;s.weaponMotion={kind='RStart',age=0,duration=50}
    Audio.cast(s,'r')
    Audio.startRMusic()
    s.rAudioActive=true
    for _,e in ipairs(entities) do
        if live(e) and e:IsVulnerableEnemy() and not e:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) and not e:IsBoss() and e.Position:Distance(p.Position)<145 then
            -- Only own the fear we introduce; do not clear pre-existing fears.
            if not e:HasEntityFlags(EntityFlag.FLAG_FEAR) then e:GetData().SamiraRFear={expires=e.FrameCount+45} end
            e:AddFear(EntityRef(p),45)
        end
    end
    return true
end
function A.updateFear(e)
    local data=e:GetData();local fear=data.SamiraRFear
    if not fear or e.FrameCount<fear.expires then return end
    data.SamiraRFear=nil
    -- A longer fear subsequently applied by another item keeps its duration.
    if e:GetFearCountdown()<=45 then e:SetFearCountdown(0);e:ClearEntityFlags(EntityFlag.FLAG_FEAR) end
end
function A.onHit(p,s,e,damage)
    s.combatUntil=s.clock+180
    local rank=Progress.rank(p,'e')
    if rank>0 then
        local _,_,boost=A.modifiers(s)
        Health.heal(p,math.max(0,damage)/.105*({.08,.10,.125,.15,.18})[rank]*boost)
    end
    e:GetData().SamiraLastHit={owner=p,clock=s.clock}
end
function A.onKill(e)
    local data=e:GetData();local mark=data.SamiraLastHit
    if data.SamiraRClaimed or not mark or not live(mark.owner) then return end
    local s=mark.owner:GetData().Samira
    if s and A.ultimate(s) and s.clock-mark.clock<=90 then
        data.SamiraRClaimed=true
        if e:IsBoss() then s.rUntil=s.clock+A.R_DURATION
        else s.rUntil=math.min(s.clock+A.R_DURATION,s.rUntil+30) end
        s.rHasteAt=s.clock;s.combatUntil=s.rUntil
    end
end
function A.update(p,s,entities,room,enemy,damage)
    if s.rAudioActive and not A.ultimate(s) then s.rAudioActive=nil;Audio.stop('r_cast');Audio.stopRMusic();Audio.play('r_end') end
    local bolt=s.wBolt
    if bolt then
        local before=bolt.position;local after=before+G.project(bolt.face*math.min(A.W_SPEED,bolt.left))
        do -- The chain projectile crosses Isaac scenery; the first enemy still receives the tether.
            local target,first=nil,2
            for _,e in ipairs(entities) do
                if enemy(e) then local distance,t=A.segment(before,after,e.Position)
                    if distance<=e.Size+18 and t<first then target=e;first=t end
                end
            end
            if target then
                damage(target,1.2*Progress.damage(p,'w'))
                Audio.play('w_hit')
                if live(target) then
                    local anchor=Vector(target.Position.X,target.Position.Y)
                    s.wChain={target=target,anchor=anchor,face=bolt.face,expires=s.clock+A.W_DELAY}
                    target:AddSlowing(EntityRef(p),A.W_DELAY,.75,Color(.6,.3,.25,1))
                end
                s.wBolt=nil
            else bolt.position=after;bolt.left=bolt.left-A.W_SPEED;if bolt.left<=0 then s.wBolt=nil end end
        end
    end
    local chain=s.wChain
    if chain then
        if not live(chain.target) or not A.inside(chain,chain.target.Position) then s.wChain=nil
        elseif s.clock>=chain.expires then
            local e=chain.target
            if not chain.pulled then damage(e,1.2*Progress.damage(p,'w'));chain.pulled=true;chain.finish=s.clock+7;Audio.play('w_pull') end
            if live(e) and not e:HasEntityFlags(EntityFlag.FLAG_NO_KNOCKBACK) and room:CheckLine(e.Position,chain.anchor,0,0,false,false) then
                local delta=chain.anchor-e.Position;e.Velocity=delta*math.min(.55,18/math.max(1,delta:Length()))
            end
            if s.clock>=chain.finish then s.wChain=nil end
        end
    end
end
return A
