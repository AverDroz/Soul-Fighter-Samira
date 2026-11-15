-- Drive the original run clip from the displacement applied by Isaac.
local Gait = {}
local lastClock, lastPosition, blockedLastTick

-- Fitted independently to both planted toe tracks in run_gun_base:
-- R_Toe frames 1..8 = -11.871, L_Toe frames 16..23 = -11.723 client
-- units per authored frame. At 30 frames per cycle their mean is 353.9.
local stride = 354 * .17
local groundDepth = .573576 -- local ground Z projected by model.py at its 35 degree pitch
local firstPlant = 1 / 30

function Gait.reset()
    lastClock, lastPosition, blockedLastTick = nil, nil, false
    Gait.moving, Gait.phase, Gait.phaseRate, Gait.face = false, firstPlant, 0, nil
end

function Gait.update(clock, position, blocked)
    if clock == lastClock then return end
    local previous, elapsed, suspended = lastPosition, lastClock and clock - lastClock, blockedLastTick
    lastClock, lastPosition, blockedLastTick = clock, Vector(position.X, position.Y), blocked
    Gait.moving, Gait.phaseRate, Gait.face = false, 0, nil

    -- Room/clock jumps and both sides of a dash re-anchor the measurement.
    if blocked or suspended or not previous or elapsed ~= 1 then
        Gait.phase = firstPlant
        return
    end

    local world = position - previous
    -- Convert the vector at the current render scale. Differencing positions
    -- passed in world space keeps camera pans out of the distance traveled.
    local axes = (Isaac.WorldToScreen(Vector(1000, 1000)) - Isaac.WorldToScreen(Vector.Zero)) * .001
    local travel = Vector(world.X * axes.X, world.Y * axes.Y / groundDepth)
    local distance = travel:Length()
    if distance < .08 or distance >= stride / 2 then
        Gait.phase = firstPlant
        return
    end

    Gait.moving = true
    Gait.phase = (Gait.phase + distance / stride) % 1
    Gait.phaseRate = 30 * distance / stride
    Gait.face = travel:Normalized()
end

Gait.reset()
return Gait
