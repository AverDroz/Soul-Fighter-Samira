local ShopCrafting = {}
local Crafting = include('samira_crafting_ui')
local Description = include('samira_item_description')
local ItemIcons = include('samira_item_icons')
local InventoryHUD = include('samira_inventory_hud')

local font, colors
local open, down, page, selected, feedback = false, false, 1, nil, nil
local pageSize, panelWidth, panelHeight = 6, 326, 116

local function setup()
    if font then return true end
    if not Font or not KColor or not Isaac.DrawLine then return false end
    local candidate, loaded = Font('font/samira_items_ru.fnt')
    if not loaded then return false end
    font = candidate
    colors = {
        paper = KColor(.055, .071, .095, .97), row = KColor(.095, .12, .15, 1),
        hover = KColor(.14, .20, .24, 1), rim = KColor(.34, .32, .28, 1),
        gold = KColor(1, .81, .45, 1), white = KColor(1, .97, .91, 1),
        muted = KColor(.66, .70, .75, 1), ready = KColor(.63, .86, .77, 1),
    }
    return true
end

local function inside(pointer, rect)
    return pointer.X >= rect.x and pointer.X < rect.x + rect.width
        and pointer.Y >= rect.y and pointer.Y < rect.y + rect.height
end

local function fill(rect, tint)
    local mid = rect.y + rect.height / 2
    Isaac.DrawLine(Vector(rect.x, mid), Vector(rect.x + rect.width, mid), tint, tint, rect.height)
end

local function text(label, x, y, scale, width, color)
    local s = math.min(scale, width / math.max(1, font:GetStringWidthUTF8(label)))
    font:DrawStringScaledUTF8(label, x, y, s, s, color, 0, false)
end

local function button(rect, label, s, pointer, enabled)
    fill(rect, enabled and inside(pointer, rect) and colors.hover or colors.row)
    text(label, rect.x + 4 * s, rect.y + 2 * s, .70 * s, rect.width - 8 * s,
        enabled and colors.gold or colors.muted)
end

local function opener(backpack, avoid)
    local s = backpack.scale
    local width = 49 * s
    local y = backpack.y - 32 * s
    if avoid and backpack.x < avoid.x + avoid.width and backpack.x + width > avoid.x then
        y = math.min(y, avoid.y - 23 * s)
    end
    return {x = backpack.x, y = math.max(4, y), width = width, height = 13 * s}
end

local function rankedRecipes(owner, inventory)
    local coins = owner:GetNumCoins()
    local recipes = inventory.recipes(owner)
    for i, recipe in ipairs(recipes) do
        recipe.order = i
        recipe.owned = #recipe.row.components - #recipe.missing
        recipe.ready = #recipe.missing == 0 and coins >= recipe.combinePrice
    end
    table.sort(recipes, function(a, b)
        if a.ready ~= b.ready then return a.ready end
        if a.owned ~= b.owned then return a.owned > b.owned end
        return a.order < b.order
    end)
    return recipes, coins
end

function ShopCrafting.isOpen()
    return open
end

function ShopCrafting.render(owner, backpack, avoid, inventory)
    local mouse = Input.IsMouseBtnPressed(0)
    local clicked = mouse and not down
    down = mouse
    if not owner or not setup() then
        open, page, selected, feedback = false, 1, nil, nil
        return
    end

    local pointer = InventoryHUD.mousePosition()
    local toggle = opener(backpack, avoid)
    if clicked and inside(pointer, toggle) then
        open = not open
        clicked = false
        if open then page, selected, feedback = 1, nil, nil end
    end
    button(toggle, open and 'Закрыть' or 'Сборка', backpack.scale, pointer, true)
    if not open then return end

    local screenWidth, screenHeight = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local top, bottom = 5, toggle.y - 4
    if bottom - top < screenHeight * .4 then
        top, bottom = toggle.y + toggle.height + 3, backpack.y - 3
    end
    local s = math.min(backpack.scale, (screenWidth - 12) / panelWidth, (bottom - top) / panelHeight)
    if s <= 0 then return end
    local x, y = (screenWidth - panelWidth * s) / 2, bottom - panelHeight * s
    local function rect(left, top, width, height)
        return {x = x + left * s, y = y + top * s, width = width * s, height = height * s}
    end
    local function label(value, left, top, width, color)
        text(value, x + left * s, y + top * s, .73 * s, width * s, color or colors.white)
    end

    local recipes, coins = rankedRecipes(owner, inventory)
    local pages = math.max(1, math.ceil(#recipes / pageSize))
    page = math.min(page, pages)
    local back, nextPage, close = rect(7, 96, 19, 14), rect(83, 96, 19, 14), rect(300, 5, 19, 13)
    if clicked and inside(pointer, close) then open = false; return end
    if clicked and inside(pointer, back) and page > 1 then
        page, selected, feedback = page - 1, nil, nil
    elseif clicked and inside(pointer, nextPage) and page < pages then
        page, selected, feedback = page + 1, nil, nil
    end

    fill(rect(0, 0, panelWidth, panelHeight), colors.rim)
    fill(rect(1, 1, panelWidth - 2, panelHeight - 2), colors.paper)
    label('Рецепты', 8, 5, 113, colors.gold)
    button(close, 'X', s, pointer, true)
    local visible, active = {}, nil
    local first = (page - 1) * pageSize
    for i = 1, pageSize do
        local recipe = recipes[first + i]
        if not recipe then break end
        local row = rect(7, 20 + (i - 1) * 12, 124, 11)
        visible[i] = {recipe = recipe, row = row}
        if clicked and inside(pointer, row) then selected, feedback = recipe.row.riotId, nil end
        if recipe.row.riotId == selected then active = recipe end
    end
    active = active or (visible[1] and visible[1].recipe)
    selected = active and active.row.riotId
    for _, entry in ipairs(visible) do
        local recipe, row = entry.recipe, entry.row
        fill(row, (recipe == active or inside(pointer, row)) and colors.hover or colors.row)
        text(recipe.row.name, row.x + 4 * s, row.y + s, .70 * s, row.width - 8 * s,
            recipe.ready and colors.ready or colors.white)
    end
    button(back, '<', s, pointer, page > 1)
    button(nextPage, '>', s, pointer, page < pages)
    label(('%d / %d'):format(page, pages), 32, 98, 46, colors.muted)
    if not active then label('Нет доступных рецептов', 140, 20, 175); return end

    local icon = rect(139, 20, 15, 15)
    ItemIcons.render(active.row.icon, Vector(icon.x + icon.width / 2, icon.y + icon.height / 2), .42 * s)
    label(active.row.name, 159, 21, 154, colors.gold)
    local detailY = 35
    for _, line in ipairs(Description.wrap(font, 'Нужно: ' .. Crafting.describe(active.row.components), 220)) do
        label(line, 140, detailY, 177)
        detailY = detailY + 8
    end
    local missing = #active.missing > 0 and 'Не хватает: ' .. Crafting.describe(active.missing) or 'Все детали в рюкзаке'
    for _, line in ipairs(Description.wrap(font, missing, 220)) do
        label(line, 140, detailY, 177, #active.missing == 0 and colors.ready or colors.muted)
        detailY = detailY + 8
    end
    label(('Доплата: %d мон. · Есть: %d'):format(active.combinePrice, coins), 140, 82, 177, colors.gold)
    local craft = rect(140, 95, 52, 15)
    button(craft, 'Собрать', s, pointer, active.ready)
    if clicked and active.ready and inside(pointer, craft) then
        local ok, reason = inventory.craft(owner, active.row.riotId)
        feedback = Crafting.result(active.row.riotId, ok, reason)
    end
    if feedback then label(feedback, 199, 98, 118, colors.ready) end
end

return ShopCrafting
