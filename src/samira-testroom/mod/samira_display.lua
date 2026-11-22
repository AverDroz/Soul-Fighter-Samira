local Display = {}
local owners = {}
local originalBorderless
local sample
local revision = 0

local function setBorderless(enabled)
    local fullscreen = Options.Fullscreen
    if fullscreen then Options.Fullscreen = false end
    Options.UseBorderlessFullscreen = enabled
    if fullscreen then Options.Fullscreen = true end
end

function Display.acquire(owner)
    if owners[owner] then return end
    owners[owner] = true
    if Options.UseBorderlessFullscreen == false then
        if originalBorderless == nil then originalBorderless = false end
        setBorderless(true)
    end
end

function Display.release(owner)
    if not owners[owner] then return end
    owners[owner] = nil
    if not next(owners) and originalBorderless ~= nil then
        setBorderless(originalBorderless)
        originalBorderless = nil
    end
end

local function displayMode()
    if not Options.Fullscreen then return 'windowed' end
    return Options.UseBorderlessFullscreen == true and 'borderless' or 'exclusive'
end

local function calibration(width, height)
    -- ScreenToWorld consumes physical client pixels. WorldToScreen returns
    -- logical render coordinates, including the game's own projection origin.
    -- A long baseline keeps the engine's pixel snapping from magnifying error.
    local span = 8192
    local zero = Isaac.WorldToScreen(Isaac.ScreenToWorld(Vector(0, 0)))
    local far = Isaac.WorldToScreen(Isaac.ScreenToWorld(Vector(span, span)))
    local dx, dy = far.X - zero.X, far.Y - zero.Y
    if dx <= 0 or dy <= 0 or dx ~= dx or dy ~= dy then return end
    local sx, sy = span / dx, span / dy
    if sx < .1 or sx > 32 or sy < .1 or sy > 32 then return end
    return {-zero.X * sx, -zero.Y * sy, width * sx, height * sy}
end

local function sameRectangle(a, b)
    if not a or not b then return a == b end
    for i = 1, 4 do
        if math.abs(a[i] - b[i]) > 3 then return false end
    end
    return true
end

function Display.sample()
    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local mode = displayMode()
    local viewport = calibration(width, height)
    if not sample or sample.width ~= width or sample.height ~= height or sample.info.mode ~= mode
        or not sameRectangle(sample.info.viewport, viewport) then
        revision = revision + 1
        sample = {width = width, height = height, info = {id = revision, mode = mode, viewport = viewport}}
    end
    return width, height, sample.info
end

return Display
