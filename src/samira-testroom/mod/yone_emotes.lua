local Emotes = {}

-- Durations use Isaac's 30 Hz game clock. Dance presentation keeps advancing
-- after its intro so the renderer can loop the remaining animation.
local expressions = {
    {action = 'joke', duration = 265},
    {action = 'taunt', duration = 124},
    {action = 'dance'},
    {action = 'laugh', duration = 53},
}
local masteryDuration = 120
local masteryCooldown = 180

function Emotes.new()
    return {held = {}, pocketSuppressed = false}
end

function Emotes.update(state, frame, keys, interrupted)
    if state.lastFrame and frame < state.lastFrame then
        local remaining = math.max(0, (state.masteryReady or 0) - state.lastFrame)
        state.masteryReady = frame + remaining
        Emotes.cancel(state, true)
    end
    state.lastFrame = frame
    local selected
    for index = 1, #expressions do
        local down = keys.ctrl == true and keys[index] == true
        if down and not state.held[index] and not selected then selected = index end
        state.held[index] = down
    end
    local masteryDown = keys.ctrl == true and keys[6] == true
    local masteryPressed = masteryDown and not state.held[6]
    state.held[6] = masteryDown

    -- Retain ownership of 4 until it releases, even if Ctrl releases first.
    state.pocketSuppressed = keys[4] == true and (keys.ctrl == true or state.pocketSuppressed)

    if interrupted then Emotes.cancel(state, false) end
    -- Still consume disabled chords so holding a key through pause cannot start an emote.
    if keys.disabled then return end
    if selected and not interrupted then
        state.expression, state.expressionAt = expressions[selected], frame
    end
    if masteryPressed and frame >= (state.masteryReady or 0) then
        state.masteryAt, state.masteryReady = frame, frame + masteryCooldown
    end
end

function Emotes.cancel(state, clearMastery)
    state.expression, state.expressionAt = nil, nil
    if clearMastery then state.masteryAt = nil end
end

function Emotes.action(state, frame)
    local expression = state.expression
    if not expression then return nil end
    local elapsed = frame - state.expressionAt
    if elapsed < 0 or expression.duration and elapsed >= expression.duration then return nil end
    return expression.action, elapsed
end

function Emotes.mastery(state, frame)
    if not state.masteryAt then return nil end
    local elapsed = frame - state.masteryAt
    if elapsed >= 0 and elapsed < masteryDuration then return elapsed / masteryDuration end
end

function Emotes.blocksPocket(state)
    return state.pocketSuppressed
end

return Emotes
