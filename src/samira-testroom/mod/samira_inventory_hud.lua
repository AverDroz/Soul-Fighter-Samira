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

function InventoryHUD.bounds(player)
    local offset = math.floor((Options.HUDOffset or 0) * 16 + 0.5)
    local trinkets = player and (player:GetTrinket(0) ~= 0 or player:GetTrinket(1) ~= 0)
    return {
        x = (trinkets and 70 or 6) + offset,
        y = math.floor(Isaac.GetScreenHeight()) - SLOT_SIZE - 4,
        width = WIDTH,
        height = SLOT_SIZE,
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
    local step = SLOT_SIZE + SLOT_GAP
    if localX % step < SLOT_SIZE then return math.floor(localX / step) + 1 end
end

function InventoryHUD.input(player, actionable)
    local click = Input.IsMouseBtnPressed(0)
    local drop = Input.IsButtonPressed(Keyboard.KEY_X, 0)
    local pressedClick, pressedDrop = click and not clickDown, drop and not dropDown
    clickDown, dropDown = click, drop
    if not player or actionable == false or game:IsPaused() then return end
    if pressedClick then
        local slot = hoveredSlot(InventoryHUD.bounds(player))
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

local function draw(message, x, y, color)
    font:DrawStringScaledUTF8(message, x, y, TEXT_SCALE, TEXT_SCALE, color, 0, false)
end

local function tooltip(item, bounds, dropHintVisible, full)
    local layout = tooltipLayouts[item]
    if not layout then
        local width = (bounds.width - 12) / TEXT_SCALE
        local title = Description.wrap(font, item.name, width)
        local stats, body = Description.lines(font, item, width)
        layout = {
            height = (#title + #stats + #body) * LINE_HEIGHT + 9,
            compactHeight = (#title + #stats) * LINE_HEIGHT + 9,
            groups = {{title, colors.selected}, {stats, colors.stats}, {body, colors.white}},
        }
        tooltipLayouts[item] = layout
    end
    local height = full and layout.height or layout.compactHeight
    local y = bounds.y - height - 5 - (dropHintVisible and 16 or 0)
    fill(bounds.x, y, bounds.width, height, colors.paper)
    y = y + 4
    for index = 1, full and 3 or 2 do
        local group = layout.groups[index]
        for _, line in ipairs(group[1]) do
            draw(line, bounds.x + 6, y, group[2])
            y = y + LINE_HEIGHT
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

function InventoryHUD.render(player)
    setupColors()
    local bounds = InventoryHUD.bounds(player)
    local slots, selected = inventory.slots(player), inventory.selected()
    local hover = hoveredSlot(bounds)
    for i = 1, SLOT_COUNT do
        local x = bounds.x + (i - 1) * (SLOT_SIZE + SLOT_GAP)
        local border = i == selected and colors.selected or i == hover and colors.hover or colors.rim
        fill(x, bounds.y, SLOT_SIZE, SLOT_SIZE, border)
        fill(x + 1, bounds.y + 1, SLOT_SIZE - 2, SLOT_SIZE - 2, colors.paper)
        if slots[i] then
            ItemIcons.render(slots[i].icon, Vector(x + SLOT_SIZE / 2, bounds.y + SLOT_SIZE / 2), 0.55)
        end
    end

    if not font then
        local candidate, loaded = Font('font/samira_items_ru.fnt')
        if loaded then font = candidate end
    end
    if not font then return end
    local dropHintVisible = slots[selected] ~= nil
    if hover and slots[hover] then
        tooltip(slots[hover], bounds, dropHintVisible, true)
    elseif dropHintVisible then
        tooltip(slots[selected], bounds, true, false)
    end
    if dropHintVisible then
        local hint = 'X · выбросить выбранное'
        local width = math.ceil(font:GetStringWidthUTF8(hint) * TEXT_SCALE) + 12
        local x = bounds.x
        fill(x, bounds.y - 17, width, 14, colors.paper)
        draw(hint, x + 6, bounds.y - 16, colors.muted)
    end
end

return InventoryHUD
