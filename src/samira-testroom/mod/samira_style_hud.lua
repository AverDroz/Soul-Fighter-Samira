local StyleHUD = {}
local RANKS = {'-', 'E', 'D', 'C', 'B', 'A', 'S'}
local RANK_COLORS = {
    {0.68, 0.64, 0.66}, {0.85, 0.70, 0.58}, {0.90, 0.63, 0.50},
    {0.98, 0.57, 0.43}, {1.00, 0.46, 0.35}, {1.00, 0.66, 0.32}, {1.00, 0.84, 0.47},
}
local WIDTH, HEIGHT = 39, 28
local TIME_SCALE = 0.66
local TRANSITION_MS = 200

local font, palette, fontChecked
local currentRank, changedAt, readySince

function StyleHUD.bounds(scale, backpack)
    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local rowWidth = 95 + WIDTH
    scale = math.min(scale or 1, (width - 4) / rowWidth, (height - 4) / 40)
    local rowX = math.max(2, math.min(width / 2 - 45 * scale, width - rowWidth * scale - 2))
    local rowY = height - (width < 556 and 50 or 24) * scale
    if scale ~= 1 and backpack and rowX < backpack.x + backpack.width + 6 then
        local right = backpack.x + backpack.width + 6
        if right + rowWidth * scale + 2 <= width then
            rowX = right
        else
            rowY = math.min(rowY, backpack.y - 23 * scale - 4)
        end
    end
    rowY = math.max(12 * scale, rowY)
    return {
        x = math.floor(rowX + 95 * scale),
        y = math.floor(rowY - 5 * scale),
        width = WIDTH * scale,
        height = HEIGHT * scale,
        rowX = rowX,
        rowY = rowY,
        scale = scale,
    }
end

local function setup()
    if not fontChecked then
        local candidate, loaded = Font('font/samira_items_ru.fnt')
        if loaded then font = candidate end
        fontChecked = true
    end
    if palette then return end
    palette = {
        frame = KColor(0.56, 0.34, 0.36, 1),
        panel = KColor(0.067, 0.052, 0.10, 1),
        empty = KColor(0.33, 0.23, 0.25, 1),
        muted = {0.83, 0.76, 0.76},
    }
end

local function fill(x, y, width, height, color)
    local middle = y + height / 2
    Isaac.DrawLine(Vector(x, middle), Vector(x + width, middle), color, color, height)
end

local function center(text, x, y, scale, tint, hudScale)
    local r, g, b = table.unpack(tint)
    if font and font:GetStringWidthUTF8(text) > 0 then
        scale = scale * hudScale
        local width = font:GetStringWidthUTF8(text) * scale
        font:DrawStringScaledUTF8(text, x - width / 2, y, scale, scale, KColor(r, g, b, 1), 0, false)
    else
        local fallbackScale = math.min(1, scale) * hudScale
        local width = Isaac.GetTextWidth(text) * fallbackScale
        Isaac.RenderScaledText(text, x - width / 2, y, fallbackScale, fallbackScale, r, g, b, 1)
    end
end

local function renderReady(width, height, elapsed, scale)
    local opening = math.max(0, 1 - elapsed / 420) ^ 2
    local pulse = (1 + math.cos(elapsed * 2 * math.pi / 1300)) / 2
    local gold = KColor(1, 0.74 + 0.17 * pulse, 0.33, 1)
    local crimson = KColor(0.94, 0.20, 0.21, 0.86)
    -- Peripheral motion stays in the margins, away from the character and enemy shots.
    local mid = height * 0.5
    for _, side in ipairs({-1, 1}) do
        local edge = side == 1 and width or 0
        local tip = edge - side * (6 + 9 * opening + 1.5 * pulse)
        local spread = 18 + 10 * opening
        Isaac.DrawLine(Vector(edge, mid - spread), Vector(tip, mid), crimson, gold, 3)
        Isaac.DrawLine(Vector(tip, mid), Vector(edge, mid + spread), gold, crimson, 3)
    end
    local half = math.min(38 * scale, math.floor(width / 4))
    local x, y = math.floor(width / 2), math.floor((8 + 5 * opening) * scale)
    fill(x - half, y, half * 2, 17 * scale, palette.panel)
    fill(x - half, y + 16 * scale, half * 2, 2 * scale, gold)
    center(font and 'R ГОТОВА' or 'R READY', x, y + scale, 0.95, RANK_COLORS[7], scale)
end

function StyleHUD.render(_, status, externalStyleHud, bounds)
    if not status then
        currentRank, changedAt, readySince = nil, nil, nil
        return
    end
    local now = Isaac.GetTime()
    bounds = bounds or StyleHUD.bounds()
    local x, y, scale = bounds.x, bounds.y, bounds.scale
    setup()
    if status.ready then
        readySince = readySince or now
        renderReady(Isaac.GetScreenWidth(), Isaac.GetScreenHeight(), now - readySince, scale)
    else
        readySince = nil
    end
    -- The companion owns the lower rank panel, but the cast prompt belongs to the game.
    if externalStyleHud then return end

    local rank = math.floor(math.max(0, math.min(6, status.rank or 0)))
    if rank ~= currentRank then
        changedAt = currentRank ~= nil and now or nil
        currentRank = rank
    end
    local transition = changedAt and math.max(0, 1 - (now - changedAt) / TRANSITION_MS) or 0
    local strength = transition * transition
    local tint = RANK_COLORS[rank + 1]
    local color = KColor(tint[1], tint[2], tint[3], 1)
    fill(x, y, bounds.width, bounds.height, status.ready and color or palette.frame)
    fill(x + scale, y + scale, bounds.width - 2 * scale, bounds.height - 2 * scale, palette.panel)

    center(RANKS[rank + 1], x + 11 * scale, y + (1 - strength) * scale, 1.23 + strength * 0.18, tint, scale)
    local cooldown = status.cooldown or 0
    local remaining = status.remaining or 0
    if status.ready then
        center('R', x + 28 * scale, y + 2 * scale, 0.8, tint, scale)
    elseif cooldown > 0 then
        center(('R %d'):format(math.ceil(cooldown)), x + 28 * scale, y + 3 * scale, TIME_SCALE, palette.muted, scale)
    end
    if rank > 0 and remaining > 0 then
        center(tostring(math.ceil(remaining)), x + 28 * scale, y + 11 * scale, TIME_SCALE, palette.muted, scale)
    end
    for i = 1, 6 do
        fill(x + (3 + (i - 1) * 5.6) * scale, y + 22 * scale, 5 * scale, 3 * scale,
            i <= rank and color or palette.empty)
    end
end

return StyleHUD
