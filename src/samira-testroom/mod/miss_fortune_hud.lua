local HUD = {}
local SharedHUD = include('yone_hud')
local abilities = {'q', 'w', 'e', 'r'}
local width, height, margin = 215, 39, 6
local inset, iconSize, iconStep = 99, 24, 28
local statsLayout = {
    {'damage', '%.2f'}, {'crit', '%.0f%%'},
    {'attacks', '%.2f'}, {'haste', '%g'},
    {'move', '%.2f'}, {'range', '%.0f'},
}
local warm, muted, light = {1, .83, .60, 1}, {.72, .75, .79, 1}, {1, .94, .84, 1}
local shadow = {.025, .033, .052, 1}
local icons, colors

function HUD.bounds(requestedScale, backpack)
    local sw, sh = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local scale = math.min(requestedScale or 1, (sw - 2 * margin) / width, (sh - 10) / height)
    local x, bottom = (sw - width * scale) / 2, sh - 4
    if backpack then
        local beside = backpack.x + backpack.width + 7
        if beside + width * scale + margin <= sw then
            x = math.max(x, beside)
        else
            local header = 17 * backpack.scale
            bottom = backpack.y - header - 3
            scale = math.min(scale, (bottom - 3) / height)
            x = sw - width * scale - margin
        end
    end
    if scale <= 0 then return end
    local w, h = width * scale, height * scale
    x = math.floor(x)
    local y = math.floor(bottom - h)
    return {x=x, y=y, width=w, height=h, left=x, top=y, right=x+w, bottom=y+h, scale=scale}
end

local function setUp()
    if icons == nil then
        local sprite, loaded = Sprite('gfx/mf/hud_icons.anm2', true)
        icons = loaded and sprite or false
    end
    if colors then return end
    colors = {
        shell=KColor(.18, .20, .24, 1), panel=KColor(.054, .082, .13, .98),
        keyBackground=KColor(.033, .06, .096, .98), cell=KColor(.13, .15, .21, 1),
        gold=KColor(.65, .49, .31, 1), bright=KColor(.87, .69, .44, 1),
        glyph=KColor(.80, .67, .47, 1), dim=KColor(.34, .36, .42, 1),
        shade=KColor(.034, .040, .068, .59),
    }
end

local function fill(x, y, w, h, color)
    if w <= 0 then return end
    Isaac.DrawLine(Vector(x, y + h / 2), Vector(x + w, y + h / 2), color, color, h)
end

local function label(value, x, y, size, color)
    Isaac.RenderScaledText(value, x, y, size, size, table.unpack(color))
end

local function center(value, x, y, size, color)
    local left = x - Isaac.GetTextWidth(value) * size / 2
    label(value, left + size, y + size, size, shadow)
    label(value, left, y, size, color)
end

local function art(name, x, y, size)
    if not icons then return end
    icons:SetFrame(name, 0)
    icons.Scale = Vector(size / 64, size / 64)
    icons:Render(Vector(x, y))
end

local function drawStats(x, y, s, stats)
    for i, stat in ipairs(statsLayout) do
        local value = stats and stats[stat[1]]
        if value ~= nil then
            if stat[1] == 'crit' then value = value * 100 end
            local col = x + (i - 1) % 2 * 27 * s
            local row = y + math.floor((i - 1) / 2) * 10 * s
            SharedHUD.drawStatGlyph(stat[1], col, row + .9 * s, .77 * s, colors.glyph)
            local text = stat[2]:format(value)
            local size = math.min(.88, 18 / math.max(1, Isaac.GetTextWidth(text))) * s
            label(text, col + 8 * s, row, size, light)
        end
    end
end

local function drawAbilities(b, combat, clock)
    local s, y = b.scale, b.y + 4 * b.scale
    local size = iconSize * s
    for i, key in ipairs(abilities) do
        local x = b.x + (inset + (i - 1) * iconStep) * s
        local remaining = (combat.ready[key] or 0) - clock
        local strut = key == 'w' and (combat.wUntil or clock) - clock or 0
        local border = remaining > 0 and strut <= 0 and colors.dim or colors.bright
        fill(x - s, y - s, size + 2 * s, size + 2 * s, border)
        fill(x, y, size, size, colors.cell)
        art(key:upper(), x, y, size)
        if remaining > 0 then
            fill(x, y, size, size, colors.shade)
            center(('%ds'):format(math.ceil(remaining / 30)), x + size / 2, y + 7 * s, 1.05 * s, light)
        end
        fill(x, y + size, size, 7 * s, colors.keyBackground)
        local caption = strut > 0 and ('W %.1fs'):format(math.ceil(strut / 3) / 10) or key:upper()
        local scale = math.min(.91, (iconSize - 2) / math.max(1, Isaac.GetTextWidth(caption))) * s
        center(caption, x + size / 2, y + size, scale, remaining > 0 and strut <= 0 and muted or warm)
    end
end

local function drawRune(x, y, s, rules, progress, clock)
    if not rules or not progress then return end
    local status = rules.runeStatus(progress, clock)
    if not status then return end
    local size = 14 * s
    local cooling = not status.limit and not status.active and status.remaining > 0
    fill(x - s, y - s, size + 2 * s, size + 2 * s, cooling and colors.dim or colors.gold)
    fill(x, y, size, size, colors.keyBackground)
    art(progress.rune, x, y, size)
    if cooling then fill(x, y, size, size, colors.shade) end
    local caption
    if status.limit then
        if status.stacks > 0 then caption = tostring(status.stacks) end
    elseif status.remaining > 0 then
        caption = ('%ds'):format(math.ceil(status.remaining / 30))
    end
    if caption then
        local maxWidth = size - 2 * s
        local scale = math.min(.77 * s, maxWidth / math.max(1, Isaac.GetTextWidth(caption)))
        local top = y + size - 7 * s
        if not cooling then fill(x, top, size, 7 * s, colors.shade) end
        center(caption, x + size / 2, cooling and y + 3 * s or top, scale, light)
    end
end

function HUD.render(b, combat, clock, stats, runeRules, runeProgress)
    if not b or not Isaac.DrawLine or not KColor then return end
    setUp()
    local x, y, s = b.x, b.y, b.scale
    fill(x + 2 * s, y, b.width - 4 * s, b.height, colors.shell)
    fill(x, y + 2 * s, b.width, b.height - 4 * s, colors.shell)
    fill(x + 2 * s, y + s, b.width - 4 * s, b.height - 2 * s, colors.panel)
    fill(x + 4 * s, y, b.width - 8 * s, s, colors.gold)
    art('Portrait', x + 3 * s, y + 1.5 * s, 36 * s)
    drawRune(x + 25 * s, y + 23 * s, s, runeRules, runeProgress, clock)
    drawStats(x + 42 * s, y + 6 * s, s, stats)
    drawAbilities(b, combat, clock)
end

return HUD
