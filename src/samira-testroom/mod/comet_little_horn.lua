local CometLittleHorn = {}

local LITTLE_HORN, PITFALL, BOMB, EFFECT = 404, 291, 4, 1000
local LITTLE_HORN_BOSS_ID, DARK_SMOKE = 60, 88
local TEXTURES = 'gfx/comet_little_horn/'

local darkSmokeColors = {['effect_088_darksmoke_black.png'] = true, ['effect_088_darksmoke_orange.png'] = true}
local BOSS = {
    ['404.000_littlehorn.anm2'] = {texture = 'boss.png', layers = 3,
        nativeColors = {['littlehorn_black.png'] = true, ['littlehorn_orange.png'] = true}},
    ['404.000_littlehorn_orange.anm2'] = {texture = 'boss_orange.png', layers = 6},
}
local BUBBLE = {['404.001_darkball.anm2'] = {texture = 'bubble.png', layers = 1, nativeColors = darkSmokeColors}}
local PORTAL = {['291.000_pitfall.anm2'] = {texture = 'portal.png', layers = 2}}
local bombAtlas = {texture = 'bomb.png', layers = 3, nativeSheet = 'pickup_016_bomb.png'}
local BOMBS = {['004.003_troll bomb.anm2'] = bombAtlas, ['004.004_megatroll bomb.anm2'] = bombAtlas}
local TRAIL = {['1000.088_darksmoke.anm2'] = {texture = 'trail.png', layers = 1, nativeColors = darkSmokeColors}}

local function filename(path)
    local name = (path or ''):match('[^/\\]+$')
    return name and name:lower() or ''
end

local function applyTexture(entity, skins)
    local sprite = entity:GetSprite()
    local skin = skins[filename(sprite:GetFilename())]
    if not skin then return end

    local changed = false
    for id = 0, skin.layers - 1 do
        local layer = sprite:GetLayer(id)
        if layer then
            local current = filename(layer:GetSpritesheetPath())
            local native = filename(layer:GetDefaultSpritesheetPath())
            local isNative = current == native or skin.nativeColors and skin.nativeColors[current]
            if current ~= '' and isNative and current ~= skin.texture
                and (not skin.nativeSheet or native == skin.nativeSheet) then
                if sprite:ReplaceSpritesheet(id, TEXTURES .. skin.texture) then changed = true end
            end
        end
    end
    if changed then sprite:LoadGraphics() end
end

local function owner(entity)
    local spawner = entity.SpawnerEntity
    if spawner then return spawner.Type, spawner.Variant, spawner end

    local parent = entity.Parent
    local kind, variant = entity.SpawnerType or 0, entity.SpawnerVariant or 0
    if kind ~= 0 then
        if parent and parent.Type == kind and parent.Variant == variant then return kind, variant, parent end
        return kind, variant
    end
    if parent then return parent.Type, parent.Variant, parent end
end

local function isLittleHorn(kind, variant)
    return kind == LITTLE_HORN and variant == 0
end

function CometLittleHorn.init(mod, game)
    if not ModCallbacks or not ModCallbacks.MC_POST_NPC_INIT or not ModCallbacks.MC_NPC_UPDATE then return end

    local function npcSkin(npc, afterUpdate)
        if npc.Type == LITTLE_HORN then
            if npc.Variant == 0 then applyTexture(npc, BOSS) end
            if npc.Variant == 1 then applyTexture(npc, BUBBLE) end
        elseif npc.Type == PITFALL and npc.Variant >= 0 and npc.Variant <= 2 then
            local kind, variant = owner(npc)
            if isLittleHorn(kind, variant) or (kind == nil and afterUpdate and game:GetRoom():GetBossID() == LITTLE_HORN_BOSS_ID) then
                applyTexture(npc, PORTAL)
            end
        end
    end

    local function bombSkin(bomb)
        if bomb.Type ~= BOMB or (bomb.Variant ~= 3 and bomb.Variant ~= 4) then return end
        local kind, variant, source = owner(bomb)
        -- The bomb may come from a portal. Trace that portal's explicit owner.
        if kind == PITFALL and source then kind, variant = owner(source) end
        if isLittleHorn(kind, variant) then applyTexture(bomb, BOMBS) end
    end

    local function trailSkin(_, effect)
        if effect.Type ~= EFFECT or effect.Variant ~= DARK_SMOKE then return end
        local kind, variant = owner(effect)
        if kind == LITTLE_HORN and variant == 1 then applyTexture(effect, TRAIL) end
    end

    -- Updates can supply a late owner or a native sprite loaded after init.
    for _, kind in ipairs({LITTLE_HORN, PITFALL}) do
        mod:AddCallback(ModCallbacks.MC_POST_NPC_INIT, function(_, npc) npcSkin(npc, false) end, kind)
        mod:AddCallback(ModCallbacks.MC_NPC_UPDATE, function(_, npc) npcSkin(npc, true) end, kind)
    end
    if ModCallbacks.MC_POST_BOMB_INIT and ModCallbacks.MC_POST_BOMB_UPDATE then
        for variant = 3, 4 do
            mod:AddCallback(ModCallbacks.MC_POST_BOMB_INIT, function(_, bomb) bombSkin(bomb) end, variant)
            mod:AddCallback(ModCallbacks.MC_POST_BOMB_UPDATE, function(_, bomb) bombSkin(bomb) end, variant)
        end
    end
    if ModCallbacks.MC_POST_EFFECT_INIT and ModCallbacks.MC_POST_EFFECT_UPDATE then
        mod:AddCallback(ModCallbacks.MC_POST_EFFECT_INIT, trailSkin, DARK_SMOKE)
        mod:AddCallback(ModCallbacks.MC_POST_EFFECT_UPDATE, trailSkin, DARK_SMOKE)
    end
end

return CometLittleHorn
