local Character = {}
local registeredType
local fallbackSprite

function Character.playerType()
    if registeredType == nil then
        local playerType = Isaac.GetPlayerTypeByName('Samira', false)
        if playerType >= 0 then registeredType = playerType end
    end
    return registeredType
end

function Character.is(player)
    local playerType = Character.playerType()
    return player ~= nil and playerType ~= nil and player:GetPlayerType() == playerType
end

function Character.player(game)
    if game:GetNumPlayers() ~= 1 then return nil end
    local player = Isaac.GetPlayer(0)
    if Character.is(player) then return player end
end

function Character.drawFallback(player, facing, offset, clock)
    if fallbackSprite == nil then
        local sprite, loaded = Sprite('gfx/samira/fallback.anm2', true)
        fallbackSprite = loaded and sprite or false
    end
    if not fallbackSprite then return false end

    local moving = player.Velocity:Length() > 0.6
    local direction = math.floor((90 - facing:GetAngleDegrees()) / 45 + 0.5) % 8
    local animation = (moving and 'Walk' or 'Idle') .. direction
    local frame = moving and math.floor(clock / 7.5) % 4 or 0

    fallbackSprite:SetFrame(animation, frame)
    fallbackSprite.Scale = player.SpriteScale or Vector(1, 1)
    fallbackSprite.Color = player:GetSprite().Color
    fallbackSprite:Render(Isaac.WorldToRenderPosition(player.Position) + offset)
    return true
end

return Character
