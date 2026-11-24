local Crafting = {}
local catalog = include('samira_items_data')
local names = {}
local noRecipes = 'Нет доступных рецептов'
local failures = {
    player = 'Выбери Самиру или Ёнэ.',
    room = 'Собирать можно в магазине.',
    recipe = 'Рецепт недоступен.',
    coins = 'Не хватает монет.',
    ingredients = 'Не хватает компонентов.',
    native = 'Игра не подтвердила сборку.',
}
for _, row in ipairs(catalog) do names[row.riotId] = row.name end

function Crafting.describe(ids)
    local counts, order, text = {}, {}, {}
    for _, id in ipairs(ids) do
        if not counts[id] then order[#order + 1], counts[id] = id, 0 end
        counts[id] = counts[id] + 1
    end
    for _, id in ipairs(order) do
        local label = names[id] or tostring(id)
        text[#text + 1] = counts[id] > 1 and (counts[id] .. '× ' .. label) or label
    end
    return table.concat(text, ', ')
end

function Crafting.result(recipe, ok, reason)
    return ok and ('Собран предмет «' .. names[recipe] .. '».')
        or failures[reason] or 'Сборка недоступна.'
end

function Crafting.init(window, player, inventory)
    local menu, combo, info, feedback = 'samiraCrafting', 'samiraCraftChoice', 'samiraCraftInfo', 'samiraCraftFeedback'
    local recipes, selected, previousOptions, previousText = {}, nil, '', nil
    ImGui.AddElement(window, menu, ImGuiElement.CollapsingHeader, 'Сборка')
    ImGui.AddCombobox(menu, combo, 'Рецепт', function(index)
        local recipe = recipes[index + 1]
        selected = recipe and recipe.row.riotId
        ImGui.UpdateText(feedback, '')
    end, {noRecipes}, 0)
    ImGui.AddText(menu, '', true, info)
    ImGui.AddButton(menu, 'samiraCraftApply', 'Собрать', function()
        if not selected then return end
        local ok, reason = inventory.craft(player(), selected)
        ImGui.UpdateText(feedback, Crafting.result(selected, ok, reason))
    end)
    ImGui.AddText(menu, '', true, feedback)
    ImGui.AddCallback(combo, ImGuiCallback.Render, function()
        local owner = player()
        recipes = inventory.recipes(owner)
        local options, index = {}, 0
        for i, recipe in ipairs(recipes) do
            options[i] = recipe.row.name
            if recipe.row.riotId == selected then index = i end
        end
        if index == 0 and #recipes > 0 then index = 1 end
        local recipe = recipes[index]
        selected = recipe and recipe.row.riotId
        if #options == 0 then options[1] = noRecipes end
        local key = table.concat(options, '\n')
        if key ~= previousOptions then
            ImGui.UpdateData(combo, ImGuiData.ListValues, options)
            ImGui.UpdateData(combo, ImGuiData.Value, math.max(0, index - 1))
            previousOptions = key
        end

        local text = 'Выбери Самиру или Ёнэ.'
        if recipe then
            local requirements = 'Нужно: ' .. Crafting.describe(recipe.row.components)
            local cost = ('Доплата: %d мон. У тебя: %d.'):format(recipe.combinePrice, owner:GetNumCoins())
            local available = #recipe.missing == 0 and 'Все компоненты в рюкзаке.'
                or 'Не хватает: ' .. Crafting.describe(recipe.missing)
            local place = Game():GetRoom():GetType() == RoomType.ROOM_SHOP and '' or '\nСобирается в магазине.'
            text = requirements .. '\n' .. cost .. '\n' .. available .. place
        end
        if text ~= previousText then
            previousText = text
            ImGui.UpdateText(info, text)
        end
    end)
end

return Crafting
