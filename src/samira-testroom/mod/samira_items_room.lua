local RoomItems = {}
local catalog = include('samira_items_data')
local ItemIcons = include('samira_item_icons')
local Description = include('samira_item_description')

local PAGE_SIZE = 12
local CARDS_PER_PAGE = 3
local SHOP_BONUS_COUNT = 4
local pickupType = EntityType.ENTITY_PICKUP
local collectibleVariant = PickupVariant.PICKUP_COLLECTIBLE

local game, getPlayer, runtime
local byCollectible, byRiotId, entries
local font, colors
local pageOverride, pageKeyDown, cardsHidden
local checkedRoom
local eidHidden = {}
local cardLayouts = {}

local function log(message)
    Isaac.ConsoleOutput(message .. '\n')
end

local function loadCatalog()
    if entries then return end
    byCollectible, byRiotId, entries = {}, {}, {}
    for _, item in ipairs(catalog) do
        local id = Isaac.GetItemIdByName(item.collectibleName)
        if id > 0 and not byCollectible[id] then
            local entry = {item = item, id = id}
            entries[#entries + 1] = entry
            byCollectible[id], byRiotId[item.riotId] = entry, entry
        else
            Isaac.DebugString('[Samira] Could not resolve ' .. item.collectibleName)
        end
    end
end

local function roomKey()
    local level = game:GetLevel()
    return tostring(level:GetCurrentRoomDesc().ListIndex)
end

local function roomState()
    return runtime.getRoomState('shop:' .. roomKey())
end

local function placement(room, player, ignore, count, nearPlayer)
    local blocked, doors, nodes, positions = {}, {}, {}, {}
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if not ignore[entity.Index] and entity.Type ~= EntityType.ENTITY_PLAYER
            and entity.Type ~= EntityType.ENTITY_EFFECT then
            blocked[#blocked + 1] = entity.Position
        end
    end
    for slot = 0, 7 do
        local door = room:GetDoor(slot)
        if door then doors[#doors + 1] = door.Position end
    end

    local center = room:GetCenterPos()
    local targets = {}
    for _, y in ipairs({-80, 0, 80}) do
        for _, x in ipairs({-160, -80, 80, 160}) do
            targets[#targets + 1] = center + Vector(x, y)
        end
    end
    for index = 0, room:GetGridSize() - 1 do
        local pos = room:GetGridPosition(index)
        if room:IsPositionInRoom(pos, 20) and room:GetGridCollision(index) == GridCollisionClass.COLLISION_NONE
            and not room:GetGridEntity(index) and pos:Distance(player.Position) >= (nearPlayer and 40 or 24) then
            local clear = true
            for _, door in ipairs(doors) do
                if pos:Distance(door) < 78 then clear = false break end
            end
            for _, occupied in ipairs(blocked) do
                if pos:Distance(occupied) < 32 then clear = false break end
            end
            if clear then
                local score = pos:Distance(player.Position)
                if not nearPlayer then
                    score = math.huge
                    for _, target in ipairs(targets) do
                        score = math.min(score, pos:Distance(target))
                    end
                end
                nodes[#nodes + 1] = {pos = pos, score = score, index = index}
            end
        end
    end
    table.sort(nodes, function(a, b)
        if a.score == b.score then return a.index < b.index end
        return a.score < b.score
    end)
    for _, minimum in ipairs({64, 40}) do
        for _, node in ipairs(nodes) do
            local clear = true
            for _, pos in ipairs(positions) do
                if node.pos:Distance(pos) < minimum then clear = false break end
            end
            if clear then
                positions[#positions + 1] = node.pos
                if #positions == count then return positions end
            end
        end
    end
    return positions
end

local function shopInventory(seed, player)
    local pool = {}
    for _, entry in ipairs(entries) do
        if not runtime.shopEligible or runtime.shopEligible(player, entry.item.riotId) then
            pool[#pool + 1] = entry
        end
    end
    if #pool < SHOP_BONUS_COUNT then return nil end
    local rng = RNG()
    rng:SetSeed(math.max(1, seed), 35)
    local selected = {}
    for i = 1, SHOP_BONUS_COUNT do
        selected[i] = table.remove(pool, rng:RandomInt(#pool) + 1)
    end
    return selected
end

local function shopSlots(count, ignored)
    local taken, slots = {}, {}
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        local pickup = entity:ToPickup()
        if pickup and not ignored[pickup.Index] and pickup:IsShopItem() then
            taken[pickup.ShopItemId] = true
        end
    end
    -- The native shop allocates slots 0 through 7, including restocked offers.
    local slot = 8
    for i = 1, count do
        while taken[slot] do slot = slot + 1 end
        slots[i], slot = slot, slot + 1
    end
    return slots
end

local function spawn(entriesToSpawn, positions, slots)
    local spawned = {}
    for slot, entry in ipairs(entriesToSpawn) do
        local entity = Isaac.Spawn(pickupType, collectibleVariant, entry.id, positions[slot], Vector.Zero, nil)
        local pickup = entity:ToPickup()
        if not pickup or pickup.SubType ~= entry.id then
            entity:Remove()
            for _, partial in ipairs(spawned) do partial:Remove() end
            return nil
        end
        if slots then pickup:MakeShopItem(slots[slot]) end
        pickup.ShopItemId = slots and slots[slot] or -1
        pickup.AutoUpdatePrice = false
        pickup.Price = slots and entry.item.price or 0
        spawned[#spawned + 1] = pickup
    end
    return spawned
end

local function placePedestals(player, selected, previous, ignored, priced)
    if not selected then return nil end
    local positions = placement(game:GetRoom(), player, ignored, #selected, #selected == 1)
    if #positions < #selected then return nil end
    local spawned = spawn(selected, positions, priced and shopSlots(#selected, ignored))
    if not spawned then return nil end
    for _, pickup in ipairs(previous) do pickup:Remove() end
    local ids = {}
    for _, pickup in ipairs(spawned) do ids[tostring(pickup.InitSeed)] = pickup.SubType end
    return ids
end

local function updateShop()
    local player = getPlayer()
    if not player then return end
    local room = game:GetRoom()
    if room:GetType() ~= RoomType.ROOM_SHOP or not room:IsClear() or game:IsGreedMode() then return end
    local key = roomKey()
    if checkedRoom == key then return end
    checkedRoom = key
    loadCatalog()
    local state = roomState()
    if state.stocked then
        for _, entity in ipairs(Isaac.FindByType(pickupType, collectibleVariant, -1, false, false)) do
            local pickup = entity:ToPickup()
            local entry = byCollectible[pickup.SubType]
            if entry and state.stocked[tostring(pickup.InitSeed)] == pickup.SubType then
                pickup.AutoUpdatePrice = false
                pickup.Price = entry.item.price
            end
        end
        return
    end
    if not room:IsFirstVisit() then return end
    state.stocked = placePedestals(player, shopInventory(room:GetSpawnSeed(), player), {}, {}, true)
    if not state.stocked then
        Isaac.DebugString('[Samira] Could not place the four bonus offers in this shop.')
    end
end

local function debugPedestals(player, selected, priced)
    local state = roomState()
    local previous, ignored = {}, {}
    for _, entity in ipairs(Isaac.FindByType(pickupType, collectibleVariant, -1, false, false)) do
        local pickup = entity:ToPickup()
        if state.debug and state.debug[tostring(pickup.InitSeed)] == pickup.SubType then
            previous[#previous + 1] = pickup
            ignored[pickup.Index] = true
        end
    end
    local spawned = placePedestals(player, selected, previous, ignored, priced)
    if not spawned then return false end
    state.debug = spawned
    pageOverride, cardsHidden = nil, nil
    return true
end

local yoneCommands = {yoneitems = 'samiraitems', yoneitem = 'samiraitem', yoneshop = 'samirashop'}

local function execute(_, command, args)
    local displayName = command
    command = yoneCommands[command] or command
    if command ~= 'samiraitems' and command ~= 'samiraitem' and command ~= 'samirashop' then return end
    local player = getPlayer()
    if not player then log('Select Samira or Yone, or enable their test mode in a single-player run.') return end
    local arg = (args or ''):match('^%s*(.-)%s*$')
    loadCatalog()
    local selected, priced
    if command == 'samiraitems' then
        local page = arg == '' and 1 or tonumber(arg)
        local pages = math.ceil(#entries / PAGE_SIZE)
        if not page or page % 1 ~= 0 or page < 1 or page > pages then
            log('Usage: ' .. displayName .. ' [1-' .. pages .. ']') return
        end
        selected = {}
        for i = (page - 1) * PAGE_SIZE + 1, math.min(page * PAGE_SIZE, #entries) do
            selected[#selected + 1] = entries[i]
        end
    elseif command == 'samiraitem' then
        local entry = byRiotId[tonumber(arg)]
        if not entry then log('Usage: ' .. displayName .. ' <Riot item ID>') return end
        selected = {entry}
    else
        if arg ~= '' then log('Usage: ' .. displayName) return end
        priced = true
        selected = shopInventory(game:GetRoom():GetSpawnSeed(), player)
    end
    if debugPedestals(player, selected, priced) then
        log(('Spawned %d Samira %s. F4 cycles the descriptions.'):format(#selected, priced and 'offers' or 'pedestals'))
    else
        log('The room has too little free floor for the full selection, or its collectibles failed to load.')
    end
end

local function loadFont()
    if font then return true end
    local candidate, loaded = Font('font/samira_items_ru.fnt')
    if not loaded then return false end
    font = candidate
    colors = {
        paper = KColor(0.08, 0.075, 0.105, 0.95),
        gold = KColor(1, 0.81, 0.45, 1),
        white = KColor(1, 0.97, 0.91, 1),
        stats = KColor(0.72, 0.88, 0.84, 1),
        muted = KColor(0.79, 0.76, 0.83, 1),
        shadow = KColor(0, 0, 0, 0.95),
    }
    return true
end

local function draw(text, x, y, scale, color)
    font:DrawStringScaledUTF8(text, x, y, scale, scale, color, 0, false)
end

local function background(x, y, width, height)
    local start = Vector(x, y + height / 2)
    local finish = Vector(x + width, start.Y)
    Isaac.DrawLine(start, finish, colors.paper, colors.paper, math.ceil(height))
end

local function drawHint(text, x, y, scale)
    background(x, y, math.ceil(font:GetStringWidthUTF8(text) * scale) + 18, 15)
    draw(text, x + 9, y + 1, scale, colors.muted)
end

local function updateEid(pickups, visible)
    if not EID then return end
    local hidden = {}
    for _, entity in ipairs(pickups) do
        local pickup = entity:ToPickup()
        local seed = pickup.InitSeed
        local previouslyHidden = eidHidden[pickup.Index] == seed
        local data = pickup:GetData()
        if visible[pickup.Index] and (previouslyHidden or not data.EID_Hide) then
            data.EID_Hide = true
            hidden[pickup.Index] = seed
        elseif previouslyHidden then
            data.EID_Hide = nil
        end
    end
    eidHidden = hidden
end

local function layoutPages(available, width, maxHeight, scale)
    local maxWidth = (width - 24) / scale
    local titleWidth = maxWidth - 16 / scale - font:GetStringWidthUTF8('3. ')
    local lineHeight = 17 * scale
    local pages, cards, used = {}, {}, 15
    for _, option in ipairs(available) do
        local item, price = option.entry.item, option.pickup.Price
        local key = table.concat({item.riotId, price, width, scale}, ':')
        local layout = cardLayouts[key]
        if not layout then
            local title = item.name
            if price > 0 then title = title .. ' · ' .. price .. ' мон.' end
            local titleLines = Description.wrap(font, title, titleWidth)
            local stats, body = Description.lines(font, item, maxWidth)
            layout = {
                title = titleLines, stats = stats, body = body,
                height = (#titleLines + #stats + #body) * lineHeight + 8,
            }
            cardLayouts[key] = layout
        end
        local height = layout.height
        if height + 17 > maxHeight then return nil end
        if #cards == CARDS_PER_PAGE or used + height + 2 > maxHeight then
            pages[#pages + 1], cards, used = cards, {}, 15
        end
        cards[#cards + 1] = {option = option, layout = layout}
        used = used + height + 2
    end
    pages[#pages + 1] = cards
    return pages
end

function RoomItems.render(player, inventoryBounds, styleBounds)
    loadCatalog()
    local room = game:GetRoom()
    local shop = room:GetType() == RoomType.ROOM_SHOP
    local blind = (game:GetLevel():GetCurses() & LevelCurse.CURSE_OF_BLIND) ~= 0
    local available, visible = {}, {}
    local pickups = Isaac.FindByType(pickupType, collectibleVariant, -1, false, false)
    if not blind then
        for _, entity in ipairs(pickups) do
            local pickup = entity:ToPickup()
            local entry = byCollectible[pickup.SubType]
            local distance = player.Position:Distance(pickup.Position)
            if entry and pickup.Visible and not pickup:IsBlind() and (shop or distance < 230) then
                available[#available + 1] = {entry = entry, pickup = pickup, distance = distance}
                visible[pickup.Index] = true
            end
        end
    end
    local canDraw = #available > 0 and loadFont()
    local pressed = Input.IsButtonPressed(Keyboard.KEY_F4, 0)
    local nextPage = pressed and not pageKeyDown
    pageKeyDown = pressed
    updateEid(pickups, canDraw and visible or {})
    if not canDraw then pageOverride = nil return end

    local width, height = Isaac.GetScreenWidth(), Isaac.GetScreenHeight()
    local rightEdge = width - 10
    local leftEdge = inventoryBounds and inventoryBounds.x + inventoryBounds.width + 9 or 10
    local panelWidth = math.floor(math.min(245, width * 0.49, rightEdge - leftEdge))
    local y, maxBottom = 62, height - 20
    if styleBounds then
        local leftOfStyle = styleBounds.x - 7
        if leftOfStyle - leftEdge >= math.min(195, panelWidth) then
            rightEdge = leftOfStyle
            panelWidth = math.min(panelWidth, rightEdge - leftEdge)
        else
            maxBottom = math.min(maxBottom, styleBounds.y - 6)
        end
    end
    local panelX = rightEdge - panelWidth
    table.sort(available, function(a, b)
        if a.distance == b.distance then return a.pickup.InitSeed < b.pickup.InitSeed end
        return a.distance < b.distance
    end)

    local scale = 0.68
    local pages = layoutPages(available, panelWidth, maxBottom - y, scale)
    while not pages and scale > 0.52 do
        scale = scale - 0.04
        pages = layoutPages(available, panelWidth, maxBottom - y, scale)
    end
    if not pages then return end
    if nextPage then
        if cardsHidden then
            cardsHidden = nil
        elseif (pageOverride or 0) + 1 >= #pages then
            pageOverride, cardsHidden = nil, true
        else
            pageOverride = (pageOverride or 0) + 1
        end
    end
    if pageOverride and pageOverride >= #pages then pageOverride = nil end
    if cardsHidden then
        local hint = 'F4 · описания'
        drawHint(hint, rightEdge - math.ceil(font:GetStringWidthUTF8(hint) * scale) - 18, y, scale)
        return
    end
    local page = pageOverride or 0
    local cards, lineHeight = pages[page + 1], 17 * scale
    local panelBottom = y + 15
    for _, card in ipairs(cards) do panelBottom = panelBottom + card.layout.height + 2 end
    local markerScale = 0.8
    for index, card in ipairs(cards) do
        local pickup = card.option.pickup
        local screen = Isaac.WorldToScreen(pickup.Position)
        if room:IsMirrorWorld() then screen.X = width - screen.X end
        local marker = tostring(index)
        local markerWidth = font:GetStringWidthUTF8(marker) * markerScale
        local markerX, markerY = screen.X - markerWidth / 2, screen.Y - 32
        if markerX + markerWidth < panelX or markerX > rightEdge
            or markerY + 17 * markerScale < y or markerY > panelBottom then
            draw(marker, markerX + 0.7, markerY + 1, markerScale, colors.shadow)
            draw(marker, markerX, markerY, markerScale, colors.gold)
        end
    end

    for number, card in ipairs(cards) do
        local layout = card.layout
        background(panelX, y, panelWidth, layout.height)
        ItemIcons.render(card.option.entry.item.icon, Vector(panelX + 14, y + 11), 0.5)
        y = y + 3
        for groupIndex, group in ipairs({{layout.title, colors.gold, 25}, {layout.stats, colors.stats, 9}, {layout.body, colors.white, 9}}) do
            for lineIndex, line in ipairs(group[1]) do
                if groupIndex == 1 and lineIndex == 1 then line = number .. '. ' .. line end
                draw(line, panelX + group[3], y, scale, group[2])
                y = y + lineHeight
            end
        end
        y = y + 7
    end
    local hint = #pages > 1 and ('F4 · %d/%d'):format(page + 1, #pages) or 'F4'
    if page + 1 == #pages then hint = hint .. ' · скрыть' end
    drawHint(hint, panelX, y, scale)
end

function RoomItems.init(mod, ownerGame, playerProvider, itemRuntime)
    game, getPlayer = ownerGame, playerProvider
    runtime = itemRuntime or include('samira_items')
    mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, execute)
    mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
        updateShop()
        if next(eidHidden) and not getPlayer() then
            updateEid(Isaac.FindByType(pickupType, collectibleVariant, -1, false, false), {})
        end
    end)
    mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
        eidHidden = {}
        checkedRoom, pageOverride, pageKeyDown, cardsHidden = nil, nil, nil, nil
    end)
    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
        eidHidden = {}
        checkedRoom, pageOverride, pageKeyDown, cardsHidden = nil, nil, nil, nil
    end)
    Console.RegisterCommand('samiraitems', 'Spawn a page of Samira collectibles', 'samiraitems [1-4]', false, AutocompleteType.NONE)
    Console.RegisterCommand('samiraitem', 'Spawn a Samira collectible', 'samiraitem <Riot item ID>', false, AutocompleteType.NONE)
    Console.RegisterCommand('samirashop', 'Spawn a paid Samira test assortment', 'samirashop', false, AutocompleteType.NONE)
    Console.RegisterCommand('yoneitems', 'Spawn a page of League collectibles', 'yoneitems [1-4]', false, AutocompleteType.NONE)
    Console.RegisterCommand('yoneitem', 'Spawn a League collectible for a test', 'yoneitem <Riot item ID>', false, AutocompleteType.NONE)
    Console.RegisterCommand('yoneshop', 'Spawn a paid Yone test assortment', 'yoneshop', false, AutocompleteType.NONE)
end

return RoomItems
