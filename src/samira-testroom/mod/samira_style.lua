local Style = {}
local rank, last, expires, lockedUntil = 0, nil, 0, 0
local TTL = 180

function Style.reset(untilFrame)
    rank, last, expires, lockedUntil = 0, nil, 0, untilFrame or 0
end

local function expire(clock)
    if rank > 0 and clock >= expires then rank, last, expires = 0, nil, 0 end
end

function Style.hit(context, clock)
    expire(clock)
    if not context or clock < lockedUntil then return end
    local kind = ({attack = 'aa', melee = 'aa', qmelee = 'q', eq = 'q'})[context.kind] or context.kind
    if kind ~= 'aa' and kind ~= 'q' and kind ~= 'w' and kind ~= 'e' then return end
    -- A volley/beam can hit many targets and tick repeatedly. Only one rank
    -- per action, except the two independently timed sweeps of W.
    local part = context.stylePart or 1
    context.styleCredited = context.styleCredited or {}
    if context.styleCredited[part] then
        if rank > 0 then expires = clock + TTL end
        return
    end
    context.styleCredited[part] = true
    if kind ~= last then
        rank = math.min(6, rank + 1)
    end
    last, expires = kind, clock + TTL
end

function Style.canCast(clock)
    expire(clock)
    return rank == 6 and clock >= lockedUntil
end

function Style.consume(clock, duration)
    if not Style.canCast(clock) then return false end
    Style.reset(clock + duration)
    return true
end

function Style.status(clock, readyAt)
    expire(clock)
    local cooldown = math.max(0, (readyAt or 0) - clock) / 30
    return {rank = rank, remaining = math.max(0, expires - clock) / 30,
        progress = math.max(0, expires - clock) / TTL, cooldown = cooldown,
        ready = rank == 6 and cooldown == 0 and clock >= lockedUntil}
end

return Style
