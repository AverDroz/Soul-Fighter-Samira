local InventoryHUD = {}
local ItemIcons = include('samira_item_icons')
local Description = include('samira_item_description')

local SLOT_COUNT = 6
local SLOT_SIZE = 22
local SLOT_GAP = 3
local WIDTH = SLOT_COUNT * SLOT_SIZE + (SLOT_COUNT - 1) * SLOT_GAP
local TEXT_SCALE = 0.62
local LINE_HEIGHT = 11

local game, inventory
local font, colors
local tooltipLayouts = {}
local clickDown, dropDown = false, false

function InventoryHUD.init(ownerGame, items)
    game, inventory = ownerGame, items
    clickDown, dropDown = false, false
end

function InventoryHUD.bounds(player, scale)
    local offset = math.floor((Options.HUDOffset or 0) * 16 + 0.5)
    local trinkets = player and (player:GetTrinket(0) ~= 0 or player:GetTrinket(1) ~= 0)
    local x = (trinkets and 70 or 6) + offset
    local width, height = Isaac.GetScreenWidth(), math.floor(Isaac.GetScreenHeight())
    scale = math.min(scale or 1, (width - x - 4) / WIDTH, (height - 8) / SLOT_SIZE)
    return {
        x = x,
        y = height - SLOT_SIZE * scale - 4,
        width = WIDTH * scale,
        height = SLOT_SIZE * scale,
        scale = scale,
    }
end

local function mousePosition()
    -- Keep HUD hitboxes in render coordinates, including in a mirror room.
    local raw = Input.GetMousePosition(false)
    local span = Isaac.ScreenToWorld(Vector(10000, 10000)) - Isaac.ScreenToWorld(Vector.Zero)
    local scale = Isaac.WorldToScreenDistance(span) * 0.0001
    return Vector(raw.X * scale.X, raw.Y * scale.Y)
end

local function hoveredSlot(bounds)
    local cursor = mousePosition()
    local localX, localY = cursor.X - bounds.x, cursor.Y - bounds.y
    if localX < 0 or localX >= bounds.width or localY < 0 or localY >= bounds.height then return nil end
    local step = (SLOT_SIZE + SLOT_GAP) * bounds.scale
    if localX % step < bounds.height then return math.floor(localX / step) + 1 end
end

function InventoryHUD.input(player, actionable, scale)
    local click = Input.IsMouseBtnPressed(0)
    local drop = Input.IsButtonPressed(Keyboard.KEY_X, 0)
    local pressedClick, pressedDrop = click and not clickDown, drop and not dropDown
    clickDown, dropDown = click, drop
    if not player or actionable == false or game:IsPaused() then return end
    if pressedClick then
        local slot = hoveredSlot(InventoryHUD.bounds(player, scale))
        if slot then inventory.select(slot) end
    end
    if pressedDrop then inventory.drop(player, inventory.selected()) end
end

local function setupColors()
    if colors then return end
    colors = {
        paper = KColor(0.08, 0.075, 0.105, 0.96),
        rim = KColor(0.42, 0.36, 0.40, 1),
        hover = KColor(0.83, 0.72, 0.62, 1),
        selected = KColor(1, 0.81, 0.45, 1),
        white = KColor(1, 0.97, 0.91, 1),
        stats = KColor(0.72, 0.88, 0.84, 1),
        muted = KColor(0.79, 0.76, 0.83, 1),
    }
end

local function fill(x, y, width, height, color)
    local middle = y + height / 2
    Isaac.DrawLine(Vector(x, middle), Vector(x + width, middle), color, color, height)
end

local function draw(message, x, y, scale, color)
    font:DrawStringScaledUTF8(message, x, y, TEXT_SCALE * scale, TEXT_SCALE * scale, color, 0, false)
end

local function tooltip(item, bounds, dropHintVisible, full, avoid)
    local layout = tooltipLayouts[item]
    if not layout then
        local width = (WIDTH - 12) / TEXT_SCALE
        local title = Description.wrap(font, item.name, width)
        local stats, body = Description.lines(font, item, width)
        layout = {
            height = (#title + #stats + #body) * LINE_HEIGHT + 9,
            compactHeight = (#title + #stats) * LINE_HEIGHT + 9,
            groups = {{title, colors.selected}, {stats, colors.stats}, {body, colors.white}},
        }
        tooltipLayouts[item] = layout
    end
    local baseHeight = full and layout.height or layout.compactHeight
    local bottom = bounds.y - (dropHintVisible and 21 or 5) * bounds.scale
    if avoid and bounds.x + bounds.width > avoid.x and bounds.x < avoid.x + avoid.width
        and bottom > avoid.y then
        bottom = avoid.y - 3
    end
    local scale = math.min(bounds.scale, math.max(0, bottom - 2) / baseHeight)
    if scale <= 0 then return end
    local height = baseHeight * scale
    local y = bottom - height
    fill(bounds.x, y, bounds.width, height, colors.paper)
    y = y + 4 * scale
    for index = 1, full and 3 or 2 do
        local group = layout.groups[index]
        for _, line in ipairs(group[1]) do
            draw(line, bounds.x + 6 * scale, y, scale, group[2])
            y = y + LINE_HEIGHT * scale
        end
    end
end

function InventoryHUD.statsSummary(player)
    if not player then return 'Доступно в забеге за Самиру.' end
    local slots, totals, rows = inventory.slots(player), {}, {}
    for index = 1, SLOT_COUNT do
        local item = slots[index]
        if item then
            for key, value in pairs(item.stats) do
                totals[key] = (totals[key] or 0) + value
            end
            local stats = Description.statText(item.stats)
            rows[index] = ('%d. %s'):format(index, item.name)
            if stats ~= '' then rows[index] = rows[index] .. '\n' .. stats end
        else
            rows[index] = ('%d. Пусто'):format(index)
        end
    end
    local total = Description.statText(totals)
    return 'Постоянные бонусы шести слотов до лимитов\n' .. (total ~= '' and total or 'Нет бонусов')
        .. '\n\n' .. table.concat(rows, '\n\n')
end

function InventoryHUD.render(player, requestedScale, avoid)
    setupColors()
    local bounds = InventoryHUD.bounds(player, requestedScale)
    local scale, size = bounds.scale, bounds.height
    local slots, selected = inventory.slots(player), inventory.selected()
    local hover = hoveredSlot(bounds)
    for i = 1, SLOT_COUNT do
        local x = bounds.x + (i - 1) * (SLOT_SIZE + SLOT_GAP) * scale
        local border = i == selected and colors.selected or i == hover and colors.hover or colors.rim
        fill(x, bounds.y, size, size, border)
        fill(x + scale, bounds.y + scale, size - 2 * scale, size - 2 * scale, colors.paper)
        if slots[i] then
            ItemIcons.render(slots[i].icon, Vector(x + size / 2, bounds.y + size / 2), 0.55 * scale)
        end
    end

    if not font then
        local candidate, loaded = Font('font/samira_items_ru.fnt')
        if loaded then font = candidate end
    end
    if not font then return end
    local dropHintVisible = slots[selected] ~= nil
    if hover and slots[hover] then
        tooltip(slots[hover], bounds, dropHintVisible, true, avoid)
    elseif dropHintVisible then
        tooltip(slots[selected], bounds, true, false, avoid)
    end
    if dropHintVisible then
        local hint = 'X · выбросить выбранное'
        local width = (math.ceil(font:GetStringWidthUTF8(hint) * TEXT_SCALE) + 12) * scale
        local x = bounds.x
        fill(x, bounds.y - 17 * scale, width, 14 * scale, colors.paper)
        draw(hint, x + 6 * scale, bounds.y - 16 * scale, scale, colors.muted)
    end
end

return InventoryHUD
