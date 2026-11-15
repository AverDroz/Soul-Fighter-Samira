local Health=include('scripts.samira_health')
local P={MAX_LEVEL=18}
local keys={'q','w','e','r'}
-- Client rank curves with the requested Isaac-specific cooldown reductions.
local cooldowns={q={12,11,10,8,6},w={15,13.5,12,10.5,9},e={8,7,6,5,4},r={100,80,60}}
function P.required(level)return 280+100*(level-1)end
function P.growth(level)local n=level-1;return .7025*n+.0175*n*n end
local function integer(value,default,low,high)
    if type(value)~='number' or value~=value or value==math.huge then return default end
    return math.max(low,math.min(high,math.floor(value)))
end
function P.cap(level,key)
    if not cooldowns[key] then return 0 end
    if key=='r' then return level>=16 and 3 or level>=11 and 2 or level>=6 and 1 or 0 end
    return math.min(5,math.floor((level+1)/2))
end
function P.restore(p,saved)
    saved=type(saved)=='table' and saved or {}
    local level=integer(saved.level,1,1,P.MAX_LEVEL)
    local xp=level==P.MAX_LEVEL and 0 or integer(saved.xp,0,0,P.required(level)-1)
    local skills={};local remaining=level
    for _,key in ipairs(keys) do
        local value=type(saved.skills)=='table' and saved.skills[key] or 0
        skills[key]=integer(value,0,0,math.min(remaining,P.cap(level,key)))
        remaining=remaining-skills[key]
    end
    local heal=type(saved.passiveHeal)=='number' and saved.passiveHeal or 0
    if heal~=heal or heal<0 or heal>=1 then heal=0 end
    p:GetData().SamiraProgress={level=level,xp=xp,skills=skills,
        passiveRemaining=integer(saved.passiveRemaining,0,0,660),passiveHeal=heal}
    -- Isaac already saved the granted heart containers; loading must never grant them again.
    return p:GetData().SamiraProgress
end
function P.state(p)return p:GetData().SamiraProgress or P.restore(p)end
function P.rank(p,key)return P.state(p).skills[key] or 0 end
-- The run starts at level 3; reach the unchanged 1.0 ceiling at level 16.
function P.attackMultiplier(p)return .8+.2*math.min(13,math.max(0,P.state(p).level-3))/13 end
function P.points(p)
    local s=P.state(p);local spent=0
    for _,key in ipairs(keys) do spent=spent+P.rank(p,key) end
    return math.max(0,s.level-spent)
end
function P.canUpgrade(p,key)return P.points(p)>0 and P.rank(p,key)<P.cap(P.state(p).level,key) end
function P.upgrade(p,key)
    if not P.canUpgrade(p,key) then return false end
    local skills=P.state(p).skills;skills[key]=skills[key]+1;return true
end
function P.cooldown(p,key)return cooldowns[key][math.max(1,P.rank(p,key))]*30 end
-- Keep Isaac's established rank-one damage and scale subsequent ranks for its encounters.
function P.damage(p,key)return 1+.15*math.max(0,P.rank(p,key)-1) end
function P.killXP(e,floor)
    local npc=e.ToNPC and e:ToNPC()
    local base=e:IsBoss() and 160 or npc and npc:IsChampion() and 75 or 62
    return math.floor(base*(1+.15*(math.max(1,floor)-1))*.5+.5)
end
function P.stats(p,st)
    local growth=P.growth(P.state(p).level)
    local startingGrowth=P.growth(3)
    local damageGrowth=math.min(growth,startingGrowth)+.5*math.max(0,growth-startingGrowth)
    st.damage=st.damage+5*damageGrowth*(6.3/60)
    st.interval=math.max(5,st.interval/(1+.025*growth))
    return st
end
function P.award(p,amount)
    local progress=P.state(p);local before=progress.level
    Health.state(p)
    if before==P.MAX_LEVEL or amount<=0 then return 0 end
    progress.xp=progress.xp+amount
    while progress.level<P.MAX_LEVEL and progress.xp>=P.required(progress.level) do
        progress.xp=progress.xp-P.required(progress.level);progress.level=progress.level+1
    end
    if progress.level==P.MAX_LEVEL then progress.xp=0 end
    if progress.level>before then
        Health.levelUp(p)
        local s=p:GetData().Samira;if s then s.levelUpAt=s.clock;s.levelSoundPending=true end
    end
    return progress.level-before
end
function P.onKill(e,isSamira)
    local data=e:GetData();local mark=data.SamiraLastHit
    if data.SamiraXPClaimed or not mark then return 0 end
    local p=mark.owner
    if not p or not p:Exists() or p:IsDead() or not isSamira(p) then return 0 end
    local s=p:GetData().Samira
    if not s or s.clock-mark.clock>90 or e:HasEntityFlags(EntityFlag.FLAG_FRIENDLY) then return 0 end
    data.SamiraXPClaimed=true
    local level=Game():GetLevel()
    local floor=level:GetAbsoluteStage()
    local amount=P.killXP(e,floor)
    P.award(p,amount)
    return amount
end
return P
