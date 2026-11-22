local HUD = {}
local abilities = {'q', 'w', 'e', 'r'}
local width, height = 174, 58
local iconSize, iconStep = 26, 33
local ready = {.95, .91, .80, 1}
local cooling = {.64, .68, .72, 1}
local recast = {.63, .90, 1, 1}
local gold = {.98, .78, .46, 1}
local muted = {.64, .75, .78, 1}
local ink = {.02, .029, .065, 1}
local icons, palette

function HUD.bounds(requestedScale, backpack)
    local screenWidth, screenHeight = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local scale = math.min(requestedScale, (screenWidth - 12) / width, (screenHeight - 10) / height)
    local x = (screenWidth - width * scale) / 2
    local bottom = screenHeight - 4
    if backpack then
        local right = backpack.x + backpack.width + 7
        if right + width * scale + 6 <= screenWidth then
            x = math.max(x, right)
        else
            bottom = backpack.y - 17 * backpack.scale - 3
            scale = math.min(scale, (bottom - 3) / height)
            x = screenWidth - width * scale - 6
        end
    end
    if scale <= 0 then return end
    return {x = math.floor(x), y = math.floor(bottom - height * scale),
        width = width * scale, height = height * scale, scale = scale}
end

local function line(x1, y1, x2, y2, tint, weight)
    Isaac.DrawLine(Vector(x1, y1), Vector(x2, y2), tint, tint, weight)
end

local function fill(x, y, w, h, tint)
    line(x, y + h / 2, x + w, y + h / 2, tint, h)
end

local function text(label, x, y, scale, tint)
    Isaac.RenderScaledText(label, x, y, scale, scale, table.unpack(tint))
end

local function centered(label, x, y, scale, tint, maxWidth)
    local w = Isaac.GetTextWidth(label)
    scale = math.min(scale, maxWidth / math.max(1, w))
    local left = x - w * scale / 2
    text(label, left + scale, y + scale, scale, ink)
    text(label, left, y, scale, tint)
end

local function outline(x, y, size, scale, remaining, tint)
    local a, b = x - scale, y - scale
    local c, d = x + size + scale, y + size + scale
    local corners = {Vector(a, b), Vector(c, b), Vector(c, d), Vector(a, d), Vector(a, b)}
    for edge = 1, 4 do
        local portion = math.max(0, math.min(1, remaining * 4 - edge + 1))
        if portion > 0 then
            local start = corners[edge]
            Isaac.DrawLine(start, start + (corners[edge + 1] - start) * portion, tint, tint, 1.5 * scale)
        end
    end
end

local function setup()
    if icons == nil then
        local sprite, loaded = Sprite('gfx/yone/ability_icons.anm2', true)
        icons = loaded and sprite or false
    end
    if not palette then
        palette = {
            edge = KColor(.49, .37, .24, 1), cap = KColor(.76, .57, .33, 1),
            body = KColor(.037, .059, .093, .97), rail = KColor(.044, .094, .125, .96),
            divider = KColor(.28, .37, .38, 1), seam = KColor(.15, .23, .28, 1),
            shade = KColor(.012, .018, .035, .70), key = KColor(.022, .034, .051, .92),
            wind = KColor(.60, .93, 1, 1), spirit = KColor(1, .38, .55, 1),
        }
    end
end

local function drawPlate(b)
    local x, y, s = b.x, b.y, b.scale
    -- Stepped corners and a single cool-toned rail under all four abilities.
    fill(x, y + 3 * s, b.width, b.height - 6 * s, palette.edge)
    fill(x + 4 * s, y, b.width - 8 * s, b.height, palette.edge)
    fill(x + s, y + 4 * s, b.width - 2 * s, b.height - 8 * s, palette.body)
    fill(x + 5 * s, y + s, b.width - 10 * s, b.height - 2 * s, palette.body)
    fill(x + 43 * s, y + 4 * s, b.width - 49 * s, 32 * s, palette.rail)
    line(x + 8 * s, y + 38 * s, x + b.width - 8 * s, y + 38 * s, palette.divider, s)
    line(x + 41 * s, y + 7 * s, x + 41 * s, y + 33 * s, palette.seam, s)
    line(x + 5 * s, y + .5 * s, x + 37 * s, y + .5 * s, palette.cap, s)
    line(x + b.width - 37 * s, y + .5 * s, x + b.width - 5 * s, y + .5 * s, palette.cap, s)
end

local function drawStats(b, stats, shield)
    local x, y, s = b.x, b.y, b.scale
    local crit = ('%d%%'):format(math.floor(stats.crit * 100 + .5))
    centered('CRIT', x + 22 * s, y + 8 * s, .94 * s, gold, 33 * s)
    centered(crit, x + 22 * s, y + 17 * s, 1.28 * s, stats.crit > 0 and gold or ready, 33 * s)
    if shield then centered('SHIELD', x + 22 * s, y + 29 * s, .78 * s, recast, 33 * s) end
    local entries = {
        {'DMG', ('%.2f'):format(stats.damage)}, {'ATK/s', ('%.2f'):format(stats.attacks)},
        {'MOVE', ('%.2f'):format(stats.move)}, {'HASTE', ('%g'):format(stats.haste)},
        {'RANGE', ('%.0f'):format(stats.range)},
    }
    for i, entry in ipairs(entries) do
        local left = x + (7 + (i - 1) * 32) * s
        if i > 1 then line(left, y + 41 * s, left, y + 54 * s, palette.seam, s) end
        centered(entry[1], left + 16 * s, y + 40 * s, .86 * s, muted, 29 * s)
        centered(entry[2], left + 16 * s, y + 48 * s, 1.01 * s, ready, 29 * s)
    end
end

function HUD.render(b, combat, clock, aiming, picture, stats, aimColors)
    if not b or not Isaac.DrawLine or not KColor then return end
    setup()
    drawPlate(b)
    drawStats(b, stats, picture.shield)
    local s = b.scale
    for i, key in ipairs(abilities) do
        local x, y, size = b.x + (45 + (i - 1) * iconStep) * s, b.y + 5 * s, iconSize * s
        local remaining = (combat.ready[key] or 0) - clock
        local spirit = key == 'e' and combat.spirit
        local q3 = key == 'q' and picture.qReady
        local tint = remaining > 0 and cooling or ready
        if spirit and clock >= spirit.recastAt then tint = recast end
        if icons then
            icons:SetFrame(q3 and 'Q3' or spirit and 'E2' or key:upper(), 0)
            icons.Scale, icons.Color = Vector(size / 64, size / 64), Color(1, 1, 1, 1)
            icons:Render(Vector(x, y))
        else
            centered(key:upper(), x + size / 2, y + 3 * s, 1.35 * s, tint, size)
        end
        if remaining > 0 and not spirit then fill(x, y, size, size, palette.shade) end
        if q3 then outline(x, y, size, s, picture.qRemaining, palette.wind) end
        if spirit then outline(x, y, size, s, picture.spirit.remaining, palette.spirit) end
        if aiming == key then
            local r, g, b = table.unpack(aimColors[key])
            line(x, y + 29 * s, x + size, y + 29 * s, KColor(r, g, b, 1), 1.5 * s)
        end
        fill(x + 2 * s, y + 21 * s, 9 * s, 9 * s, palette.key)
        centered(key:upper(), x + 6.5 * s, y + 21 * s, .94 * s, tint, 8 * s)
        local status
        if spirit then
            local ticks = math.max(0, spirit.untilFrame - clock)
            status = ticks == 0 and 'HOLD' or ('%.1fs'):format(ticks / 30)
        elseif remaining > 0 then
            status = ('%ds'):format(math.ceil(remaining / 30))
        end
        if status then centered(status, x + size / 2, y + 9 * s, 1.05 * s, spirit and recast or ready, size - 2 * s) end
    end
end

return HUD
