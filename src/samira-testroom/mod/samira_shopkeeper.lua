local Shopkeeper = {}
local Navigation = include('samira_navigation')
local browser, game, owner, available
local keeper, icon
local anchor, roomSeed
local heldRight, heldLeft, captured = false, false, false
local modelScale = .72

local function screen(room, point)
    local result = Isaac.WorldToScreen(point)
    if room:IsMirrorWorld() then result.X = Isaac.GetScreenWidth() - result.X end
    return result
end

local function shopRoom()
    if not Isaac.IsInGame() then return end
    local room = game:GetRoom()
    if room:GetType() == RoomType.ROOM_SHOP and room:IsClear() then return room end
end

local function reservePositions(room, player)
    local occupied = {player.Position}
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_PICKUP or entity.Type == EntityType.ENTITY_SHOPKEEPER then
            occupied[#occupied + 1] = entity.Position
        end
    end
    for slot = 0, 7 do
        local door = room:GetDoor(slot)
        if door then occupied[#occupied + 1] = door.Position end
    end
    return occupied
end

local function availableSpace(point, occupied)
    for _, position in ipairs(occupied) do
        if point:Distance(position) < 35 then return false end
    end
    return true
end

local function chooseAnchor(room, player)
    local center, top = room:GetCenterPos(), room:GetTopLeftPos()
    local goal = Vector(center.X, top.Y + 44)
    local occupied = reservePositions(room, player)
    local found, minimum
    for i = 0, room:GetGridSize() - 1 do
        local point = room:GetGridPosition(i)
        if room:IsPositionInRoom(point, 27) and room:GetGridCollision(i) == GridCollisionClass.COLLISION_NONE
            and not room:GetGridEntity(i) and availableSpace(point, occupied) then
            local distance = point:Distance(goal)
            if minimum == nil or distance < minimum then found, minimum = point, distance end
        end
    end
    return found or room:GetClampedPosition(goal, 24)
end

local function sprite(path, animation, scale)
    local value, loaded = Sprite(path, true)
    if not loaded then return false end
    value.Scale = Vector(scale, scale)
    value:Play(animation, true)
    return value
end

local function hit(pointer, position)
    return math.abs(pointer.X - position.X) <= 36
        and pointer.Y >= position.Y - 63 and pointer.Y <= position.Y + 6
end

local function resetRoom()
    if browser and browser.isOpen() then browser.close() end
    anchor, roomSeed, keeper = nil, nil, nil
end

local function place(room, player)
    if roomSeed ~= room:GetSpawnSeed() then resetRoom() end
    if anchor then return end
    roomSeed = room:GetSpawnSeed()
    anchor = chooseAnchor(room, player)
    local side = roomSeed % 2 == 0 and 'south' or 'north'
    keeper = sprite('gfx/league_shop/shopkeeper_' .. side .. '.anm2', 'Idle', modelScale)
    if icon == nil then icon = sprite('gfx/league_shop/shop_ui.anm2', 'Shop', .7) end
end

local function sampleInput()
    local right, left = Input.IsMouseBtnPressed(1), Input.IsMouseBtnPressed(0)
    local rightClick, leftClick = right and not heldRight, left and not heldLeft
    heldRight, heldLeft = right, left
    if not right and not left then captured = false end
    if not rightClick and not leftClick then return end

    local room, player = shopRoom(), owner()
    if not room or not player or not available(player) then return end
    place(room, player)

    local pointer = screen(room, Navigation.worldCursor(room))
    if browser.isOpen() then
        captured = true
        browser.onMousePressed(pointer, rightClick and 1 or 0)
    elseif rightClick and anchor and roomSeed == room:GetSpawnSeed() and hit(pointer, screen(room, anchor)) then
        captured = browser.open(player) == true
    end
end

function Shopkeeper.isBlocking()
    if not browser then return false end
    -- Isaac can ask for a movement action before MC_POST_UPDATE. Let the
    -- merchant claim the current edge before any gameplay caller reads it.
    sampleInput()
    return browser.isOpen() or captured
end

local function update()
    sampleInput()
    local room, player = shopRoom(), owner()
    if not room or not player or not available(player) then
        if browser.isOpen() then browser.close() end
        return
    end
    if keeper then keeper:Update() end
end

function Shopkeeper.render()
    local room, player = shopRoom(), owner()
    if not room or not player or not available(player) then return end
    place(room, player)
    local position = screen(room, anchor)
    local pointer = screen(room, Navigation.worldCursor(room))
    if keeper then keeper:Render(position)
    else Isaac.RenderText('Merchant', position.X - 18, position.Y - 18, 1, .82, .47, 1) end
    if browser.isOpen() then browser.render(pointer)
    elseif hit(pointer, position) then
        if icon then icon:Render(position + Vector(-34, -60)) end
        Isaac.RenderText('RMB - Recipes', position.X - 22, position.Y - 64, 1, .85, .5, 1)
    end
end

function Shopkeeper.init(mod, currentGame, player, canInteract, panel)
    game, owner, available, browser = currentGame, player, canInteract, panel
    mod:AddPriorityCallback(ModCallbacks.MC_POST_UPDATE, CallbackPriority.EARLY, update)
    mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, resetRoom)
    mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, resetRoom)
end

return Shopkeeper
