-- Shared continuous mana regeneration / rage gain policy; gameplay runs at 30 Hz.
local B={MANA_REGEN_MULTIPLIER=3}
function B.resourceGain(amount,shotSpeed)
    return math.max(0,amount)*math.max(0,shotSpeed or 1)
end
function B.manaRegenPerTick(perFiveSeconds,shotSpeed)
    return B.resourceGain(perFiveSeconds,shotSpeed)*B.MANA_REGEN_MULTIPLIER/150
end
function B.rageRegenPerTick(perSecond,shotSpeed)
    return B.resourceGain(perSecond,shotSpeed)/30
end
return B
