local HUD = {}
local Progression = include('yone_progression')
local abilities = {'q', 'w', 'e', 'r'}
local width, height = 206, 39
local iconSize, iconStep, firstIcon = 26, 33, 76
local cellWidth, cellHeight = 32, 10
local ready = {.95, .91, .80, 1}
local cooling = {.64, .68, .72, 1}
local recast = {.63, .90, 1, 1}
local gold = {.98, .78, .46, 1}
local ink = {.02, .029, .065, 1}
local icons, palette

-- Each sequence is one pen stroke on an eight-by-eight grid.
local statCells = {
    {key = 'damage', label = 'Attack damage', format = '%.2f', strokes = {
        {2, 6, 6, 1, 8, 0, 7, 2, 3, 7}, {1, 5, 4, 8}, {2, 7, 1, 8},
    }},
    {key = 'crit', label = 'Critical strike chance', format = '%d%%', strokes = {
        {4, 0, 5, 3, 8, 4, 5, 5, 4, 8, 3, 5, 0, 4, 3, 3, 4, 0},
    }},
    {key = 'attacks', label = 'Attacks per second', format = '%.2f', strokes = {
        {0, 1, 3, 4, 0, 7}, {4, 1, 7, 4, 4, 7},
    }},
    {key = 'haste', label = 'Ability haste', format = '%g', strokes = {
        {2, 0, 6, 0, 8, 2, 8, 6, 6, 8, 2, 8, 0, 6, 0, 2, 2, 0}, {4, 2, 4, 4, 6, 5},
    }},
    {key = 'move', label = 'Movement speed', format = '%.2f', strokes = {
        {2, 0, 5, 0, 5, 4, 8, 6, 8, 8, 1, 8, 1, 5, 2, 4, 2, 0}, {1, 6, 4, 6},
    }},
    {key = 'range', label = 'Attack range', format = '%.0f', strokes = {
        {3, 1, 1, 1, 1, 3}, {5, 1, 7, 1, 7, 3},
        {7, 5, 7, 7, 5, 7}, {3, 7, 1, 7, 1, 5}, {3, 4, 5, 4}, {4, 3, 4, 5},
    }},
}
local shieldMark = {{1, 1, 7, 1, 7, 5, 4, 8, 1, 5, 1, 1}}

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
            stat = KColor(.74, .65, .49, 1), statCrit = KColor(.97, .78, .46, 1),
            hover = KColor(.10, .17, .20, 1), shield = KColor(.55, .87, 1, 1),
        }
    end
end

local function drawPlate(b)
    local x, y, s = b.x, b.y, b.scale
    -- Stepped corners and a single cool-toned rail behind all four abilities.
    fill(x, y + 3 * s, b.width, b.height - 6 * s, palette.edge)
    fill(x + 4 * s, y, b.width - 8 * s, b.height, palette.edge)
    fill(x + s, y + 4 * s, b.width - 2 * s, b.height - 8 * s, palette.body)
    fill(x + 5 * s, y + s, b.width - 10 * s, b.height - 2 * s, palette.body)
    fill(x + (firstIcon - 2) * s, y + 4 * s, b.width - (firstIcon + 2) * s, 32 * s, palette.rail)
    line(x + (firstIcon - 2) * s, y + 36 * s, x + b.width - 4 * s, y + 36 * s, palette.divider, s)
    line(x + 71 * s, y + 5 * s, x + 71 * s, y + 34 * s, palette.divider, s)
    line(x + 37 * s, y + 6 * s, x + 37 * s, y + 33 * s, palette.seam, s)
    line(x + 5 * s, y + .5 * s, x + 33 * s, y + .5 * s, palette.cap, s)
    line(x + b.width - 37 * s, y + .5 * s, x + b.width - 5 * s, y + .5 * s, palette.cap, s)
end

local function drawMark(strokes, x, y, s, tint)
    for _, stroke in ipairs(strokes) do
        for point = 1, #stroke - 2, 2 do
            line(x + stroke[point] * s, y + stroke[point + 1] * s,
                x + stroke[point + 2] * s, y + stroke[point + 3] * s, tint, 1.05 * s)
        end
    end
end

local function mousePosition()
    -- Like the backpack, the stat hitboxes stay fixed in mirrored rooms.
    local raw = Input.GetMousePosition(false)
    local span = Isaac.ScreenToWorld(Vector(10000, 10000)) - Isaac.ScreenToWorld(Vector.Zero)
    local scale = Isaac.WorldToScreenDistance(span) * .0001
    return Vector(raw.X * scale.X, raw.Y * scale.Y)
end

local function contains(pointer, x, y, w, h)
    return pointer.X >= x and pointer.X < x + w and pointer.Y >= y and pointer.Y < y + h
end

local function drawStats(b, stats, pointer)
    local s = b.scale
    local label, anchor
    for i, cell in ipairs(statCells) do
        local x = b.x + (5 + (i - 1) % 2 * (cellWidth + 1)) * s
        local y = b.y + (4.5 + math.floor((i - 1) / 2) * cellHeight) * s
        if contains(pointer, x, y, cellWidth * s, cellHeight * s) then
            fill(x, y, cellWidth * s, cellHeight * s, palette.hover)
            label, anchor = cell.label, x
        end
        local value = stats[cell.key]
        local activeCrit = cell.key == 'crit' and value > 0
        if cell.key == 'crit' then value = math.floor(value * 100 + .5) end
        drawMark(cell.strokes, x + 1.5 * s, y + s, s, activeCrit and palette.statCrit or palette.stat)
        local formatted = cell.format:format(value)
        local textWidth = Isaac.GetTextWidth(formatted)
        local scale = math.min(.9 * s, 20 * s / math.max(1, textWidth))
        local left = x + (cellWidth - 2) * s - textWidth * scale
        text(formatted, left + .7 * s, y + 1.8 * s, scale, ink)
        text(formatted, left, y + 1.1 * s, scale, activeCrit and gold or ready)
    end
    return label, anchor
end

local function drawTooltip(b, label, anchor)
    local available = b.y - 4
    if not label or available <= 0 then return end
    local s = math.min(b.scale, available / 17)
    local textWidth = Isaac.GetTextWidth(label)
    local maxWidth = Isaac.GetScreenWidth() - 6
    local textScale = math.min(.86 * s, (maxWidth - 12 * s) / math.max(1, textWidth))
    local w, h = textWidth * textScale + 12 * s, 13 * s
    local x = math.max(3, math.min(anchor, Isaac.GetScreenWidth() - w - 3))
    local y = b.y - h - 4 * s
    fill(x, y, w, h, palette.edge)
    fill(x + s, y + s, w - 2 * s, h - 2 * s, palette.body)
    text(label, x + 6 * s, y + 2 * s, textScale, ready)
end

local function wrap(label, maxWidth)
    local lines, row = {}, ''
    for word in label:gmatch('%S+') do
        local nextRow = row == '' and word or row .. ' ' .. word
        if row ~= '' and Isaac.GetTextWidth(nextRow) > maxWidth then
            lines[#lines + 1] = row
            row = word
        else
            row = nextRow
        end
    end
    if row ~= '' then lines[#lines + 1] = row end
    return lines
end

local function panel(x, y, w, h, s, edge, body)
    fill(x, y, w, h, edge)
    fill(x + s, y + s, w - 2 * s, h - 2 * s, body)
end

function HUD.renderRunePicker(choices, selectedIndex, hudScale)
    if #choices == 0 or not Isaac.DrawLine or not KColor then return end
    local cardWidth, gutter, padding, descriptionScale = 90, 4, 8, .78
    local descriptions, maxLines = {}, 0
    for i, choice in ipairs(choices) do
        local lines = wrap(choice.description, (cardWidth - 10) / descriptionScale)
        descriptions[i] = lines
        maxLines = math.max(maxLines, #lines)
    end
    local cardHeight = 24 + 10 * maxLines
    local width = 2 * padding + #choices * cardWidth + (#choices - 1) * gutter
    local height = cardHeight + 44
    local screenWidth, screenHeight = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local s = math.min(hudScale or 1, (screenWidth - 16) / width, (screenHeight - 16) / height)
    if s <= 0 then return end
    setup()
    local x, y = (screenWidth - width * s) / 2, (screenHeight - height * s) / 2
    local center = screenWidth / 2
    panel(x, y, width * s, height * s, s, palette.edge, palette.body)
    centered('Choose a keystone', center, y + 7 * s, 1.23 * s, gold, (width - 16) * s)

    local cardY = y + 24 * s
    for i, choice in ipairs(choices) do
        local cardX = x + (padding + (i - 1) * (cardWidth + gutter)) * s
        local cardCenter = cardX + cardWidth * s / 2
        local selected = i == selectedIndex
        panel(cardX, cardY, cardWidth * s, cardHeight * s, s,
            selected and palette.cap or palette.seam, selected and palette.hover or palette.rail)
        centered(choice.name, cardCenter, cardY + 5 * s, s,
            selected and gold or ready, (cardWidth - 10) * s)
        for row, label in ipairs(descriptions[i]) do
            centered(label, cardCenter, cardY + (17 + (row - 1) * 10) * s,
                descriptionScale * s, selected and ready or cooling, (cardWidth - 10) * s)
        end
    end
    centered('Left / Right to select   Enter to confirm', center, y + (height - 14) * s,
        .86 * s, ready, (width - 16) * s)
end

function HUD.renderProgress(b, progress)
    if not b or not progress or not Isaac.DrawLine or not KColor then return end
    local x, s = b.x, b.scale
    -- Tooltips occupy up to 17 scaled units immediately above the combat HUD.
    local y = b.y - 43 * s
    if y < 3 then return end
    setup()
    local runeName
    for _, choice in ipairs(Progression.choices) do
        if choice.id == progress.rune then runeName = choice.name; break end
    end
    local atMax = progress.level == Progression.MAX_LEVEL
    local required = Progression.required(progress.level)
    local fraction = atMax and 1 or math.min(1, math.max(0, progress.xp / required))
    local level = ('LVL %d'):format(progress.level)
    local points = Progression.points(progress)
    local ranks = {}
    for _, key in ipairs(abilities) do
        ranks[#ranks + 1] = key:upper() .. Progression.rank(progress, key)
    end

    panel(x, y, b.width, 24 * s, s, palette.edge, palette.body)
    centered(level .. (atMax and '  MAX' or ('  %d/%d XP'):format(progress.xp, required)),
        x + 51 * s, y + 2 * s, .85 * s, gold, 93 * s)
    if runeName then centered(runeName, x + 153 * s, y + 2 * s, .85 * s, ready, 93 * s) end
    fill(x + 5 * s, y + 11 * s, b.width - 10 * s, 2 * s, palette.divider)
    if fraction > 0 then fill(x + 5 * s, y + 11 * s, (b.width - 10 * s) * fraction, 2 * s, palette.wind) end
    if points > 0 then
        centered(('Alt+Q/W/E/R: %d pt'):format(points), x + 51 * s, y + 14 * s, .77 * s, gold, 93 * s)
    end
    centered(table.concat(ranks, '  '), x + (points > 0 and 153 or 103) * s,
        y + 14 * s, .77 * s, cooling, 93 * s)
end

function HUD.render(b, combat, clock, aiming, picture, stats, aimColors)
    if not b or not Isaac.DrawLine or not KColor then return end
    setup()
    local pointer = mousePosition()
    drawPlate(b)
    local tooltip, anchor = drawStats(b, stats, pointer)
    local s = b.scale
    for i, key in ipairs(abilities) do
        local x, y, size = b.x + (firstIcon + (i - 1) * iconStep) * s, b.y + 5 * s, iconSize * s
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
        if key == 'w' and picture.shield then
            local badgeX, badgeY = x + 17 * s, y + 21 * s
            fill(badgeX, badgeY, 9 * s, 9 * s, palette.key)
            drawMark(shieldMark, badgeX + .5 * s, badgeY + .5 * s, s, palette.shield)
            if contains(pointer, badgeX, badgeY, 9 * s, 9 * s) then tooltip, anchor = 'W shield active', badgeX end
        end
        local status
        if spirit then
            local ticks = math.max(0, spirit.untilFrame - clock)
            status = ticks == 0 and 'HOLD' or ('%.1fs'):format(ticks / 30)
        elseif remaining > 0 then
            status = ('%ds'):format(math.ceil(remaining / 30))
        end
        if status then centered(status, x + size / 2, y + 9 * s, 1.05 * s, spirit and recast or ready, size - 2 * s) end
    end
    drawTooltip(b, tooltip, anchor)
end

return HUD
