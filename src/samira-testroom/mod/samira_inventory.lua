local Inventory = {}
local catalog = include('samira_items_data')
local slotCount = 6
local droppedVarData = 0x53414D49

local game, getPlayer, items
local entriesByCollectible, entriesByRiot
local pending

local function storage()
    local state = items.getInventoryState()
    state.entries = state.entries or {}
    state.selected = state.selected or 1
    return state
end

local function managed(p)
    local active = getPlayer()
    return active and p and GetPtrHash(active) == GetPtrHash(p)
end

local function capacity(row)
    return math.floor((row.stats.health_red_hearts or 0) * 2 + .5)
end

local function nativeCount(p, row)
    return p:GetCollectibleNum(row.collectibleId, true)
end

local function usesRedContainers(p)
    return not p.GetHealthType or p:GetHealthType() == HealthType.RED
end

local function undoCapacity(p, amount)
    if amount > 0 then p:AddMaxHearts(-math.min(amount, p:GetMaxHearts()), false) end
end

local function addCapacity(p, amount)
    local limit = p.GetHeartLimit and p:GetHeartLimit() or 24
    local occupied = p:GetMaxHearts() + p:GetSoulHearts() + 2 * p:GetBoneHearts()
    local allowed = math.min(amount, math.max(0, limit - occupied))
    if allowed > 0 then p:AddMaxHearts(allowed, false) end
end

local function dropPedestal(p, collectibleId, touched)
    local position = game:GetRoom():FindFreePickupSpawnPosition(p.Position, 40, true)
    local ok, entity = pcall(Isaac.Spawn, EntityType.ENTITY_PICKUP, PickupVariant.PICKUP_COLLECTIBLE,
        collectibleId, position, Vector.Zero, nil)
    local pickup = ok and entity and entity:ToPickup()
    if not pickup then return end
    pickup.AutoUpdatePrice, pickup.Price, pickup.ShopItemId = false, 0, -1
    pickup.Touched, pickup.Wait = touched, 30
    if touched then pickup:SetVarData(droppedVarData) end
    return pickup
end

local function dropSlot(p, state, index)
    local key = tostring(index)
    local slot = state.entries[key]
    local row = slot and entriesByRiot[slot.riotId]
    if not row then return false end
    local count = nativeCount(p, row)
    if count <= 0 then return false end
    local pedestal = dropPedestal(p, row.collectibleId, true)
    if not pedestal then return false end

    local maxBefore = p:GetMaxHearts()
    p:RemoveCollectible(row.collectibleId)
    if nativeCount(p, row) >= count then
        pedestal:Remove()
        return false
    end
    local nativeRemoved = math.max(0, maxBefore - p:GetMaxHearts())
    undoCapacity(p, (slot.hearts or 0) - nativeRemoved)
    state.entries[key] = nil
    state.observedMax = p:GetMaxHearts()
    return true
end

local function place(p, state, row, hearts)
    local chosen
    for index = 1, slotCount do
        if not state.entries[tostring(index)] then
            chosen = index
            break
        end
    end
    if not chosen then
        chosen = state.selected
        if not dropSlot(p, state, chosen) then return end
    end
    local entry = {riotId = row.riotId, hearts = hearts}
    state.entries[tostring(chosen)] = entry
    return entry
end

local function reconcile(p)
    local state = storage()
    local counts = {}
    local legacyBudget = not state.initialized and usesRedContainers(p) and p:GetMaxHearts() or 0
    local externallyRemoved = math.max(0, (state.observedMax or p:GetMaxHearts()) - p:GetMaxHearts())
    for _, row in ipairs(catalog) do
        local entry = entriesByRiot[row.riotId]
        if entry then counts[row.riotId] = nativeCount(p, entry) end
    end
    -- Retain the leftmost copies in duplicate slots when native mechanics remove one.
    for index = 1, slotCount do
        local key = tostring(index)
        local slot = state.entries[key]
        if slot then
            local id = slot.riotId
            if (counts[id] or 0) > 0 then
                counts[id] = counts[id] - 1
            else
                local owed = slot.hearts or 0
                local alreadyRemoved = math.min(owed, externallyRemoved)
                externallyRemoved = externallyRemoved - alreadyRemoved
                undoCapacity(p, owed - alreadyRemoved)
                state.entries[key] = nil
            end
        end
    end
    -- Older saves have native item counts and no slot metadata.
    for _, row in ipairs(catalog) do
        local entry = entriesByRiot[row.riotId]
        if entry then
            for _ = 1, counts[row.riotId] do
                local hearts = math.min(legacyBudget, capacity(row))
                legacyBudget = legacyBudget - hearts
                if not place(p, state, entry, hearts) then break end
            end
        end
    end
    state.initialized = true
    state.observedMax = p:GetMaxHearts()
    return state
end

function Inventory.slots(p)
    if not p then return {} end
    local state = storage()
    local result = {}
    for index = 1, slotCount do
        local slot = state.entries[tostring(index)]
        if slot then result[index] = entriesByRiot[slot.riotId] end
    end
    return result
end

function Inventory.selected()
    return storage().selected
end

function Inventory.select(index)
    if type(index) ~= 'number' or index % 1 ~= 0 or index < 1 or index > slotCount then return false end
    storage().selected = index
    return true
end

function Inventory.drop(p, index)
    if not managed(p) then return false end
    local state = reconcile(p)
    return dropSlot(p, state, index or state.selected)
end

function Inventory.update(p)
    if not managed(p) then return end
    local state = reconcile(p)
    if not state.returnPickups then return end
    local retained = {}
    for _, owed in ipairs(state.returnPickups) do
        local row = entriesByRiot[owed.riotId]
        if row and not dropPedestal(p, row.collectibleId, owed.touched) then
            retained[#retained + 1] = owed
        end
    end
    state.returnPickups = #retained > 0 and retained or nil
end

local function beforeAdd(_, id, charge, firstTime, slot, varData, p)
    local row = entriesByCollectible[id]
    if not row or not managed(p) then return end
    reconcile(p)
    pending = {
        p = GetPtrHash(p), id = id, count = nativeCount(p, row),
        max = p:GetMaxHearts(), red = p:GetHearts(),
        dropped = varData == droppedVarData or not firstTime,
    }
    if firstTime and varData == droppedVarData then
        return {id, charge, false, slot, varData}
    end
end

local function afterAdd(_, id, _, _, _, _, p)
    local row = entriesByCollectible[id]
    if not row or not managed(p) then return end
    local acquisition = pending
    pending = nil
    if not acquisition or acquisition.id ~= id or acquisition.p ~= GetPtrHash(p) then
        reconcile(p)
        return
    end
    if nativeCount(p, row) <= acquisition.count then return end
    local state = storage()
    local normalHealth = usesRedContainers(p)
    local granted = normalHealth and math.min(capacity(row), math.max(0, p:GetMaxHearts() - acquisition.max)) or 0
    local entry = place(p, state, row, granted)
    if not entry then
        local before = p:GetMaxHearts()
        p:RemoveCollectible(row.collectibleId)
        if nativeCount(p, row) == acquisition.count then
            undoCapacity(p, granted - math.max(0, before - p:GetMaxHearts()))
            if normalHealth then
                p:AddHearts(math.min(p:GetEffectiveMaxHearts(), acquisition.red) - p:GetHearts())
            end
            state.observedMax = p:GetMaxHearts()
            state.returnPickups = state.returnPickups or {}
            local queue = state.returnPickups
            queue[#queue + 1] = {riotId = row.riotId, touched = acquisition.dropped}
        end
        return
    end
    if not normalHealth then return end

    local retainedRed = math.min(acquisition.red, math.max(0, p:GetEffectiveMaxHearts() - granted))
    if granted < capacity(row) then
        local before = p:GetMaxHearts()
        addCapacity(p, capacity(row) - granted)
        granted = granted + math.max(0, p:GetMaxHearts() - before)
        entry.hearts = granted
    end
    local targetRed = math.min(p:GetEffectiveMaxHearts(), retainedRed + (acquisition.dropped and 0 or granted))
    if p:GetHearts() ~= targetRed then p:AddHearts(targetRed - p:GetHearts()) end
    state.observedMax = p:GetMaxHearts()
end

function Inventory.init(mod, currentGame, playerProvider, itemModule)
    game, getPlayer, items = currentGame, playerProvider, itemModule
    entriesByCollectible, entriesByRiot = {}, {}
    for _, row in ipairs(catalog) do
        local id = Isaac.GetItemIdByName(row.collectibleName)
        if id and id > 0 then
            local entry = {}
            for key, value in pairs(row) do entry[key] = value end
            entry.collectibleId = id
            entriesByCollectible[id], entriesByRiot[row.riotId] = entry, entry
        end
    end
    mod:AddCallback(ModCallbacks.MC_PRE_ADD_COLLECTIBLE, beforeAdd)
    mod:AddCallback(ModCallbacks.MC_POST_ADD_COLLECTIBLE, afterAdd)
    mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function() pending = nil end)
end

return Inventory
