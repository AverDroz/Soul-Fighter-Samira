-- Reference balance adapter, NOT tuned for Samira.
-- Load once per module initialization, never during frame/attack processing.
local defaults={uiLanguage='auto',voiceLanguage='auto',eLifestealPercent={8,10,12.5,15,18},rHealingBonusPercent={40,60,80},
    incomingDamageMultiplier=1,floorDamageIncrease=.20,attackDamageMultiplier=1,
    passiveHealingMultiplier=1,hastePerAttackSpeed=4,extraQDamageMultiplier=.5}
local limits={eLifestealPercent={0,100},rHealingBonusPercent={0,900},
    incomingDamageMultiplier={0,10},floorDamageIncrease={0,2},attackDamageMultiplier={.1,10},
    passiveHealingMultiplier={0,10},hastePerAttackSpeed={0,100},extraQDamageMultiplier={0,1}}
local function warn(key)
    if Isaac and Isaac.DebugString then Isaac.DebugString('[Samira config] Invalid '..key..'; using default. Check samira_config.lua.') end
end
local ok,raw=pcall(include,'samira_config')
if not ok or type(raw)~='table' then warn('file');raw={} end
local function number(value,fallback,range,key)
    if value==nil then return fallback end
    if type(value)~='number' or value~=value or value<range[1] or value>range[2] then warn(key);return fallback end
    return value
end
local config={}
for key,fallback in pairs(defaults) do
    if type(fallback)=='string' then
        local value=raw[key]
        if value==nil then value=fallback
        elseif value~='auto' and value~='zh' and value~='en' then warn(key);value=fallback end
        config[key]=value
    elseif type(fallback)=='table' then
        local values=raw[key]
        if values~=nil and type(values)~='table' then warn(key);values=nil end
        config[key]={}
        for rank,value in ipairs(fallback) do config[key][rank]=number(values and values[rank],value,limits[key],key..'['..rank..']') end
    else config[key]=number(raw[key],fallback,limits[key],key) end
end
return config
