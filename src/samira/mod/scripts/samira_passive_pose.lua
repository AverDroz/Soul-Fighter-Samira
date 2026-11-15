-- Presentation only: original client clips, driven by the actual passive cooldown.
-- Never create a cast, change velocity, or reserve an input while a gesture plays.
local P={}
local Passive=include('scripts.samira_passive')
local clips=include('scripts.samira_external_actions')
local qRecovery={
    Q1={'Q1_INTO_Passive_Idle','Q1_INTO_PASSIVE_RUN'},
    Q2={'Q2_INTO_Passive_Idle','Q2_INTO_PASSIVE_RUN'},
    Q3={'Q3_INTO_Passive_Idle','Q3_INTO_Passive_Run'},
}
function P.frame(p,s,walking,winged,blocked,epoch)
    local t=s.passivePose
    if not t or t.epoch~=epoch or s.clock<t.clock then
        t={epoch=epoch,clock=s.clock,engaged=false};s.passivePose=t
    end
    local ready=Passive.ready(p)
    local becameReady=t.ready==false and ready
    local oldSource=t.source
    local source=blocked and 'blocked' or winged and 'winged'
        or s.cast and (s.cast.passive and 'passiveAttack' or s.cast.kind)
        or s.dash and 'dash' or s.weaponMotion and s.weaponMotion.kind
    t.clock=s.clock;t.ready=ready;t.source=source
    local function start(name)
        t.gesture={name=name,at=s.clock}
    end
    local function gesture()
        local g=t.gesture
        if not g then return end
        local phase=math.max(0,(s.clock-g.at)/(30*clips[g.name]))
        if phase>=1 then t.gesture=nil;return end
        local walk=walking and {kind=ready and t.engaged and 'Passive_Run' or 'Walk',
            phase=(s.walkClock or 0)/(30*clips[ready and t.engaged and 'Passive_Run' or 'Unsheath_run01'])%1} or nil
        return g.name,phase,false,walk
    end
    if blocked or winged then t.gesture=nil;t.engaged=false;return end
    if s.cast or s.dash then
        t.gesture=nil
        if ready then t.engaged=true end
        -- Attacks and skills keep their existing timing and priority.
        return
    end
    if s.weaponMotion then
        if source=='Draw' and ready then
            t.engaged=true;t.gesture=nil
            local m=s.weaponMotion
            local walk=walking and {kind='Passive_Run',phase=(s.walkClock or 0)/(30*clips.Passive_Run)%1} or nil
            return 'Unsheath_to_Passive',math.min(1,m.age/m.duration),false,walk
        elseif source=='Sheathe' and (t.engaged or t.gesture and t.gesture.sheathing) then
            if oldSource~='Sheathe' then
                start(walking and 'Passive_To_Sheathed_Run' or 'passive_into_shth')
                t.gesture.sheathing=true
            end
            t.engaged=false
            return gesture()
        end
        t.gesture=nil;return
    end
    if not ready then
        t.engaged=false
        if oldSource=='passiveAttack' then start('Passive_Attack_out')
        elseif t.gesture and t.gesture.name~='Passive_Attack_out' then t.gesture=nil end
    else
        if becameReady or not t.engaged and s.weapon and oldSource~='Sheathe' then
            t.engaged=true;start('Unsheath_to_Passive')
        end
        if t.engaged then
            local recovery=qRecovery[oldSource]
            if recovery then start(recovery[walking and 2 or 1])
            elseif oldSource=='W' then start(walking and 'Spell3_Passive_to_Run' or 'Passive_INTO_Passive_Idle')
            elseif oldSource=='dash' then start(walking and 'Passive_Idle_INTO_Run' or 'Passive_INTO_Passive_Idle')
            elseif oldSource=='winged' then start('ULT_out_to_passive_idle')
            elseif walking and t.walking==false and not t.gesture then start('Passive_Idle_INTO_Run') end
        end
    end
    t.walking=walking
    local name,phase,looping,walk=gesture()
    if name then return name,phase,looping,walk end
    if ready and t.engaged then
        name=walking and 'Passive_Run' or 'Passive_Idle'
        return name,((walking and s.walkClock or s.clock) or 0)/(30*clips[name])%1,true
    end
end
return P
