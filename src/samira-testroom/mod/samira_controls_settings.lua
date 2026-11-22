local Settings = {}
local json = require('json')
local attackMove, inertia, walkSpeed, hudPercent = true, false, 85, 100
local speedOptions = {70, 85, 100}
local speedIndex = {[70] = 0, [85] = 1, [100] = 2}
local hudOptions = {75, 85, 100, 115, 130, 150}
local hudIndex, hudLabels = {}, {}
for index, percent in ipairs(hudOptions) do
    hudIndex[percent], hudLabels[index] = index - 1, percent .. '%'
end

-- These top-level preferences belong to the save slot, independently of the run seed.
function Settings.attachToSave(saved)
    saved.samiraAttackMove = attackMove
    saved.samiraInertia = inertia
    saved.samiraWalkSpeed = walkSpeed
    saved.samiraHudScale = hudPercent
end

function Settings.hudScale()
    return hudPercent / 100
end

function Settings.init(mod, combat, player, inventorySummary)
    local menu, item, window = 'samiraControlsMenu', 'samiraControlsItem', 'samiraControlsWindow'
    local ownsOverlay, keyHeld, slotReady = false, false, false
    local function readSave()
        if not mod:HasData() then return {} end
        local ok, saved = pcall(json.decode, mod:LoadData())
        if ok and type(saved) == 'table' then return saved end
    end
    local function loadSlot()
        slotReady = true
        local saved = readSave()
        attackMove = not saved or saved.samiraAttackMove ~= false
        inertia = saved ~= nil and saved.samiraInertia == true
        walkSpeed = saved and speedIndex[saved.samiraWalkSpeed] and saved.samiraWalkSpeed or 85
        hudPercent = saved and hudIndex[saved.samiraHudScale] and saved.samiraHudScale or 100
        combat.setAttackMove(attackMove)
        combat.setInertia(inertia)
        combat.setWalkSpeed(walkSpeed)
        ImGui.UpdateData('samiraAttackMove', ImGuiData.Value, attackMove)
        ImGui.UpdateData('samiraInertia', ImGuiData.Value, inertia)
        ImGui.UpdateData('samiraWalkSpeed', ImGuiData.Value, speedIndex[walkSpeed])
        ImGui.UpdateData('samiraHudScale', ImGuiData.Value, hudIndex[hudPercent])
    end
    local function writeSetting(key, value, previous)
        local saved = slotReady and readSave()
        if not saved then
            Isaac.DebugString('[Samira] Select a readable save slot to change settings.')
            ImGui.UpdateData(key, ImGuiData.Value, previous)
            return false
        end
        saved[key] = value
        mod:SaveData(json.encode(saved))
        return true
    end
    local function close()
        ImGui.SetVisible(window, false)
        if ownsOverlay then ImGui.Hide() end
        ownsOverlay = false
    end
    ImGui.CreateMenu(menu, 'Samira')
    ImGui.AddElement(menu, item, ImGuiElement.MenuItem, 'Управление')
    ImGui.CreateWindow(window, 'Samira — управление')
    ImGui.LinkWindowToElement(window, item)
    ImGui.AddCheckbox(window, 'samiraAttackMove', 'Attack-move (A)', function(value)
        if writeSetting('samiraAttackMove', value, attackMove) then
            attackMove = value
            combat.setAttackMove(value)
        end
    end, attackMove)
    ImGui.AddText(window, 'Вкл. — нажми A, чтобы идти к курсору и атаковать врагов.', true)
    ImGui.AddText(window, 'Выкл. — удерживай A, чтобы стрелять в сторону курсора.', true)
    ImGui.AddCheckbox(window, 'samiraInertia', 'Инерция Isaac', function(value)
        if writeSetting('samiraInertia', value, inertia) then
            inertia = value
            combat.setInertia(value)
        end
    end, inertia)
    ImGui.AddText(window, 'Разгон задаёт Isaac. Сними флажок для быстрого поворота и остановки по команде.', true)
    ImGui.AddCombobox(window, 'samiraWalkSpeed', 'Скорость ходьбы', function(index)
        local value = speedOptions[index + 1]
        if value and writeSetting('samiraWalkSpeed', value, speedIndex[walkSpeed]) then
            walkSpeed = value
            combat.setWalkSpeed(value)
        end
    end, {'70%', '85%', '100%'}, speedIndex[walkSpeed])
    ImGui.AddCombobox(window, 'samiraHudScale', 'Масштаб HUD', function(index)
        local value = hudOptions[index + 1]
        if value and writeSetting('samiraHudScale', value, hudIndex[hudPercent]) then
            hudPercent = value
        end
    end, hudLabels, hudIndex[hudPercent])
    ImGui.AddElement(window, 'samiraBag', ImGuiElement.CollapsingHeader, 'Рюкзак')
    ImGui.AddText('samiraBag', '', true, 'samiraBagStats')
    local previousSummary
    ImGui.AddCallback('samiraBagStats', ImGuiCallback.Render, function()
        local text = inventorySummary(player())
        if text ~= previousSummary then
            ImGui.UpdateText('samiraBagStats', text)
            previousSummary = text
        end
    end)
    ImGui.AddButton(window, 'samiraControlsClose', 'Готово', close)
    mod:AddCallback(ModCallbacks.MC_POST_SAVESLOT_LOAD, function(_, _, selected, rawSlot)
        if selected and rawSlot ~= 0 then loadSlot() else slotReady = false end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, loadSlot)
    if Isaac.IsInGame() then loadSlot() end
    mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
        if ownsOverlay and (not ImGui.IsVisible() or not ImGui.GetVisible(window)) then close() end
        local down = Input.IsButtonPressed(Keyboard.KEY_F9, 0)
        if down and not keyHeld then
            if ImGui.IsVisible() and ImGui.GetVisible(window) then
                close()
            elseif player() and not Game():IsPaused() then
                ownsOverlay = not ImGui.IsVisible()
                ImGui.Show()
                ImGui.SetVisible(window, true)
            end
        end
        keyHeld = down
    end)
    mod:AddCallback(ModCallbacks.MC_PRE_MOD_UNLOAD, function(_, unloading)
        if unloading ~= mod then return end
        close()
        ImGui.RemoveElement(menu)
        ImGui.RemoveElement(window)
    end)
end

return Settings
