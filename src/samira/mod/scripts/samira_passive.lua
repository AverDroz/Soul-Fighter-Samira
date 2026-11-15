local Health=include('scripts.samira_health')
-- Source: installed SamiraPassive calculations; healing uses independent numeric HP.
local Progress=include('scripts.samira_progression')
local P={}
local function growth(p)return (Progress.state(p).level-1)/17 end
function P.total(p)return math.floor((22-12*growth(p))*30+.5) end
function P.remaining(p)return Progress.state(p).passiveRemaining or 0 end
function P.ready(p)return P.remaining(p)<=0 end
function P.update(p)local s=Progress.state(p);s.passiveRemaining=math.max(0,P.remaining(p)-1) end
function P.large(e)local npc=e.ToNPC and e:ToNPC();return e:IsBoss() or npc and npc:IsChampion() end
function P.bonus(p,e)
    local n=growth(p)
    return math.min(math.max(0,e.MaxHitPoints or 0)*(.04+.06*n),(100+220*n)*.105)
end
function P.consume(p,e,dealt,healing)
    local s=Progress.state(p);s.passiveRemaining=P.total(p)
    -- Isaac balance: restore 75% of the passive's bonus damage as healing.
    Health.heal(p,math.max(0,dealt)/.105*.75*(healing or 1))
end
function P.reduce(p,seconds)
    local s=Progress.state(p);s.passiveRemaining=math.max(0,P.remaining(p)-seconds*30)
end
return P
