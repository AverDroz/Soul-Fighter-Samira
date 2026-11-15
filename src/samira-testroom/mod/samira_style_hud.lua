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
local currentRank, changedAt

function StyleHUD.bounds()
    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    return {
        x = math.floor(width / 2 + 50),
        y = math.floor(height - (width < 556 and 50 or 24) - 5),
        width = WIDTH,
        height = HEIGHT,
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

local function center(text, x, y, scale, tint)
    local r, g, b = table.unpack(tint)
    if font and font:GetStringWidthUTF8(text) > 0 then
        local width = font:GetStringWidthUTF8(text) * scale
        font:DrawStringScaledUTF8(text, x - width / 2, y, scale, scale, KColor(r, g, b, 1), 0, false)
    else
        local fallbackScale = math.min(1, scale)
        local width = Isaac.GetTextWidth(text) * fallbackScale
        Isaac.RenderScaledText(text, x - width / 2, y, fallbackScale, fallbackScale, r, g, b, 1)
    end
end

local function readyEdges(width, height, now)
    local pulse = 1 + 0.15 * math.sin(now * 0.005)
    for _, band in ipairs({{14, 0.04}, {8, 0.08}, {3, 0.125}}) do
        local thickness = band[1]
        local edge = thickness / 2
        local orange = KColor(1, 0.40, 0.12, pulse * band[2])
        local red = KColor(0.98, 0.17, 0.09, pulse * band[2])
        Isaac.DrawLine(Vector(0, edge), Vector(width, edge), orange, red, thickness)
        Isaac.DrawLine(Vector(0, height - edge), Vector(width, height - edge), red, orange, thickness)
        Isaac.DrawLine(Vector(edge, 0), Vector(edge, height), orange, red, thickness)
        Isaac.DrawLine(Vector(width - edge, 0), Vector(width - edge, height), red, orange, thickness)
    end
end

function StyleHUD.render(_, status, externalStyleHud)
    if not status then
        currentRank, changedAt = nil, nil
        return
    end
    if externalStyleHud then return end
    local now = Isaac.GetTime()
    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    if status.ready then readyEdges(width, height, now) end
    setup()

    local rank = math.floor(math.max(0, math.min(6, status.rank or 0)))
    if rank ~= currentRank then
        changedAt = currentRank ~= nil and now or nil
        currentRank = rank
    end
    local transition = changedAt and math.max(0, 1 - (now - changedAt) / TRANSITION_MS) or 0
    local strength = transition * transition
    local tint = RANK_COLORS[rank + 1]
    local color = KColor(tint[1], tint[2], tint[3], 1)
    local bounds = StyleHUD.bounds()
    local x, y = bounds.x, bounds.y
    fill(x, y, WIDTH, HEIGHT, status.ready and color or palette.frame)
    fill(x + 1, y + 1, WIDTH - 2, HEIGHT - 2, palette.panel)

    center(RANKS[rank + 1], x + 11, y + 1 - strength, 1.23 + strength * 0.18, tint)
    local cooldown = status.cooldown or 0
    local remaining = status.remaining or 0
    if status.ready then
        center('R', x + 28, y + 2, 0.8, tint)
    elseif cooldown > 0 then
        center(('R %d'):format(math.ceil(cooldown)), x + 28, y + 3, TIME_SCALE, palette.muted)
    end
    if rank > 0 and remaining > 0 then
        center(tostring(math.ceil(remaining)), x + 28, y + 11, TIME_SCALE, palette.muted)
    end
    for i = 1, 6 do
        fill(x + 3 + (i - 1) * 5.6, y + 22, 5, 3, i <= rank and color or palette.empty)
    end
end

return StyleHUD
