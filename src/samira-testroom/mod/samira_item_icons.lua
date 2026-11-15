local ItemIcons = {}
local sprites = {}

function ItemIcons.render(path, position, scale)
    local sprite = sprites[path]
    if not sprite then
        local candidate, loaded = Sprite('gfx/items/collectibles/samira_hud_icon.anm2', false)
        if not loaded then return end
        candidate:ReplaceSpritesheet(0, path, true)
        candidate:SetFrame('Idle', 0)
        sprites[path], sprite = candidate, candidate
    end
    sprite.Scale = Vector(scale, scale)
    sprite:Render(position)
end

return ItemIcons
