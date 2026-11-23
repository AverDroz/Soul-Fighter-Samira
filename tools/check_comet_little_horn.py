"""Exercise the Little Horn reskin against Isaac sprite and callback doubles."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/python-deps"))
from lupa.lua54 import LuaRuntime


def main():
    lua = LuaRuntime()
    path = ROOT / "src/samira-testroom/mod/comet_little_horn.lua"
    lua.globals().source = path.read_text(encoding="utf-8")
    lua.execute(r"""
ModCallbacks = {
    MC_POST_NPC_INIT=27, MC_NPC_UPDATE=0,
    MC_POST_BOMB_INIT=57, MC_POST_BOMB_UPDATE=58,
    MC_POST_EFFECT_INIT=54, MC_POST_EFFECT_UPDATE=55,
}
local callbacks = {}
local mod = {}
function mod:AddCallback(id, callback, filter)
    local handlers = callbacks[id] or {}
    assert(handlers[filter] == nil)
    handlers[filter] = callback
    callbacks[id] = handlers
end
local function fire(name, entity)
    local filter = name:find('NPC') and entity.Type or entity.Variant
    local handler = callbacks[ModCallbacks['MC_' .. name]][filter]
    if handler then assert(handler(mod, entity) == nil, 'graphics callback returned a gameplay override') end
end

local folder = 'gfx/comet_little_horn/'
local bossFile, ballFile = 'GFX\\404.000_Littlehorn.anm2', 'gfx/404.001_DarkBall.anm2'
local orangeFile = 'gfx/404.000_Littlehorn_Orange.anm2'
local pitFile, trailFile = 'gfx/291.000_Pitfall.anm2', 'gfx/1000.088_DarkSmoke.anm2'
local trollFile, megaFile = 'gfx/004.003_Troll Bomb.anm2', 'gfx/004.004_Megatroll Bomb.anm2'
local bossTexture = 'Bosses/Afterbirth/Littlehorn.png'
local orangeTexture = 'Bosses/Afterbirth/Littlehorn_Orange.png'
local pitTexture = 'Monsters/Afterbirth/291.000_Pitfall.png'
local ballTexture = 'Effects/Effect_088_DarkSmoke.png'
local bombTexture = 'Items/Pick Ups/Pickup_016_Bomb.png'
local function spawn(kind, variant, filename, native, layers)
    local sprite = {filename=filename, native=native, current={}, pending={}, swaps=0, loads=0, frame=7, animation='Idle'}
    for id=0,layers-1 do sprite.current[id] = 'gfx/' .. native end
    function sprite:GetFilename() return self.filename end
    function sprite:GetLayer(id)
        if not self.current[id] then return end
        return {
            GetSpritesheetPath=function() return self.current[id] end,
            GetDefaultSpritesheetPath=function() return self.layerNative and self.layerNative[id] or self.native end,
        }
    end
    function sprite:ReplaceSpritesheet(id, path)
        assert(self.current[id] and path:sub(1, #folder) == folder)
        if self.failNextSwap then self.failNextSwap = nil; return false end
        self.swaps = self.swaps + 1
        self.pending[id] = path
        return true
    end
    function sprite:LoadGraphics()
        assert(next(self.pending))
        self.loads = self.loads + 1
        for id, path in pairs(self.pending) do self.current[id] = path end
        self.pending = {}
    end
    local entity = {Type=kind, Variant=variant, SpawnerType=0, State=8, HitPoints=120, Sprite=sprite}
    function entity:GetSprite() return self.Sprite end
    return entity
end
local function assertSkin(entity, texture, swaps, loads)
    local sprite = entity.Sprite
    assert(sprite.swaps == swaps and sprite.loads == loads, 'unexpected sprite swap or reload count')
    if texture then
        for _, path in pairs(sprite.current) do assert(path == folder .. texture) end
    end
    assert(entity.State == 8 and entity.HitPoints == 120 and sprite.frame == 7 and sprite.animation == 'Idle')
end
local roomBoss = 0
local room = {GetBossID=function() return roomBoss end}
local game = {GetRoom=function() return room end}
local module = assert(load(source, '@comet_little_horn.lua'))()
module.init(mod, game)

local boss = spawn(404, 0, bossFile, bossTexture, 3)
fire('POST_NPC_INIT', boss)
fire('NPC_UPDATE', boss)
fire('NPC_UPDATE', boss)
assertSkin(boss, 'boss.png', 3, 1)

-- Native phase changes can recreate the entire spritesheet after init.
boss.Sprite.filename = orangeFile
boss.Sprite.native = orangeTexture
for id=0,5 do boss.Sprite.current[id] = 'gfx/' .. orangeTexture end
fire('NPC_UPDATE', boss)
fire('NPC_UPDATE', boss)
assertSkin(boss, 'boss_orange.png', 9, 2)

local regularRecolor = spawn(404, 0, bossFile, bossTexture, 3)
for id=0,2 do regularRecolor.Sprite.current[id] = 'gfx/' .. orangeTexture end
fire('POST_NPC_INIT', regularRecolor)
assertSkin(regularRecolor, 'boss.png', 3, 1)
local blackBoss = spawn(404, 0, bossFile, bossTexture, 3)
for id=0,2 do blackBoss.Sprite.current[id] = 'gfx/Bosses/Afterbirth/Littlehorn_Black.png' end
fire('POST_NPC_INIT', blackBoss)
assertSkin(blackBoss, 'boss.png', 3, 1)

local bubble = spawn(404, 1, nil, ballTexture, 1)
fire('POST_NPC_INIT', bubble)
assertSkin(bubble, nil, 0, 0)
bubble.Sprite.filename = ballFile
bubble.Sprite.failNextSwap = true
fire('NPC_UPDATE', bubble)
assertSkin(bubble, nil, 0, 0)
fire('NPC_UPDATE', bubble)
assertSkin(bubble, 'bubble.png', 1, 1)
for _, suffix in ipairs({'Orange', 'Black'}) do
    bubble.Sprite.current[0] = 'gfx/Effects/Effect_088_DarkSmoke_' .. suffix .. '.png'
    fire('NPC_UPDATE', bubble)
    assert(bubble.Sprite.current[0] == folder .. 'bubble.png')
end

local unknownVariant = spawn(404, 9, bossFile, bossTexture, 3)
fire('POST_NPC_INIT', unknownVariant)
assertSkin(unknownVariant, nil, 0, 0)
local otherAnimation = spawn(404, 0, 'gfx/another_boss.anm2', bossTexture, 3)
fire('POST_NPC_INIT', otherAnimation)
assertSkin(otherAnimation, nil, 0, 0)
local otherTexture = spawn(404, 0, bossFile, bossTexture, 3)
for id=0,2 do otherTexture.Sprite.current[id] = 'gfx/other_mod/other.png' end
fire('POST_NPC_INIT', otherTexture)
assertSkin(otherTexture, nil, 0, 0)

local spawnerPortal = spawn(291, 0, pitFile, pitTexture, 2)
spawnerPortal.SpawnerEntity = boss
fire('POST_NPC_INIT', spawnerPortal)
assertSkin(spawnerPortal, 'portal.png', 2, 1)
local durablePortal = spawn(291, 1, pitFile, pitTexture, 2)
durablePortal.SpawnerType, durablePortal.SpawnerVariant = 404, 0
fire('POST_NPC_INIT', durablePortal)
assertSkin(durablePortal, 'portal.png', 2, 1)
local parentPortal = spawn(291, 2, pitFile, pitTexture, 2)
fire('POST_NPC_INIT', parentPortal)
assertSkin(parentPortal, nil, 0, 0)
parentPortal.Parent = boss
fire('NPC_UPDATE', parentPortal)
assertSkin(parentPortal, 'portal.png', 2, 1)

local unownedPortal = spawn(291, 0, pitFile, pitTexture, 2)
fire('POST_NPC_INIT', unownedPortal)
fire('NPC_UPDATE', unownedPortal)
assertSkin(unownedPortal, nil, 0, 0)
roomBoss = 60
fire('NPC_UPDATE', unownedPortal)
assertSkin(unownedPortal, 'portal.png', 2, 1)
local generator = {Type=400, Variant=0}
for _, ownership in ipairs({'SpawnerEntity', 'SpawnerType', 'Parent'}) do
    local portal = spawn(291, 0, pitFile, pitTexture, 2)
    portal[ownership] = ownership == 'SpawnerType' and generator.Type or generator
    fire('POST_NPC_INIT', portal)
    fire('NPC_UPDATE', portal)
    assertSkin(portal, nil, 0, 0)
end

local troll = spawn(4, 3, trollFile, bombTexture, 2)
troll.SpawnerEntity = boss
fire('POST_BOMB_INIT', troll)
fire('POST_BOMB_UPDATE', troll)
assertSkin(troll, 'bomb.png', 2, 1)
local sparkBomb = spawn(4, 3, trollFile, bombTexture, 3)
local sparks = 'Effects/Bomb_Spark.png'
sparkBomb.Sprite.layerNative = {[1] = sparks}
sparkBomb.Sprite.current[1] = 'gfx/' .. sparks
sparkBomb.SpawnerEntity = boss
fire('POST_BOMB_INIT', sparkBomb)
assert(sparkBomb.Sprite.current[0] == folder .. 'bomb.png' and sparkBomb.Sprite.current[2] == folder .. 'bomb.png')
assert(sparkBomb.Sprite.current[1] == 'gfx/' .. sparks and sparkBomb.Sprite.swaps == 2
    and sparkBomb.Sprite.loads == 1, 'current bomb layout replaced sparks instead of Hole')
local mega = spawn(4, 4, megaFile, bombTexture, 2)
fire('POST_BOMB_INIT', mega)
assertSkin(mega, nil, 0, 0)
mega.SpawnerEntity = durablePortal
fire('POST_BOMB_UPDATE', mega)
assertSkin(mega, 'bomb.png', 2, 1)
local unownedBomb = spawn(4, 3, trollFile, bombTexture, 2)
unownedBomb.SpawnerEntity = unownedPortal
fire('POST_BOMB_INIT', unownedBomb)
fire('POST_BOMB_UPDATE', unownedBomb)
assertSkin(unownedBomb, nil, 0, 0)
local playerBomb = spawn(4, 4, megaFile, bombTexture, 2)
playerBomb.SpawnerType = 1
fire('POST_BOMB_INIT', playerBomb)
assertSkin(playerBomb, nil, 0, 0)

local trail = spawn(1000, 88, trailFile, ballTexture, 1)
trail.SpawnerEntity = bubble
fire('POST_EFFECT_INIT', trail)
fire('POST_EFFECT_UPDATE', trail)
assertSkin(trail, 'trail.png', 1, 1)
local unownedTrail = spawn(1000, 88, trailFile, ballTexture, 1)
unownedTrail.SpawnerEntity = boss
fire('POST_EFFECT_INIT', unownedTrail)
fire('POST_EFFECT_UPDATE', unownedTrail)
assertSkin(unownedTrail, nil, 0, 0)

ModCallbacks = {}
module.init({AddCallback=function() error('registered an absent callback') end}, game)
""")
    print("Little Horn: sprite layers, ownership, phase retries, and callback isolation passed")


if __name__ == "__main__":
    main()
