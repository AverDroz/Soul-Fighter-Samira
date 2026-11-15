-- Match the engine's hourglass slots, not room-entry guesses or the latest disk save.
local R={}
local Health=include('scripts.samira_health')
local fields={'clock','qReady','wReady','eReady','rReady','attackReady','nextQ','chainUntil',
    'rUntil','rHasteAt','rStartedAt','rRank','combatUntil','weapon','walkClock'}
local function copy(value)
    if type(value)=='table' then
        local result={};for key,item in pairs(value) do result[key]=copy(item) end;return result
    end
    if type(value)=='number' or type(value)=='boolean' or type(value)=='string' then return value end
end
function R.capture(p,s)
    local data=p:GetData();local core={}
    for _,key in ipairs(fields) do core[key]=s[key] end
    return {core=core,face={x=s.face.X,y=s.face.Y},progress=copy(data.SamiraProgress),
        gear=copy(data.SamiraGear),health=Health.save(p)}
end
function R.valid(entry)
    return type(entry)=='table' and type(entry.progress)=='table' and type(entry.gear)=='table'
        and type(entry.health)=='table' and type(entry.core)=='table' and type(entry.core.clock)=='number'
        and type(entry.face)=='table' and type(entry.face.x)=='number' and type(entry.face.y)=='number'
end
function R.apply(p,s,entry)
    if not R.valid(entry) then return false end
    local data=p:GetData()
    -- Disk-load sanitation intentionally clears buffs; rewind must preserve them,
    -- including fractional healing/debt and equipment-specific cooldowns/stacks.
    data.SamiraProgress=copy(entry.progress);data.SamiraGear=copy(entry.gear)
    data.SamiraGear.syncing=nil;data.SamiraGear.dirty=nil
    for _,key in ipairs(fields) do s[key]=entry.core[key] end
    s.face=Vector(entry.face.x,entry.face.y)
    Health.restore(p,entry.health)
    return true
end
return R
