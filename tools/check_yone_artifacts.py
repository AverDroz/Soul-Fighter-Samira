"""Test Yone's bounded native collectible adaptations without a running game."""
from pathlib import Path
from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'src/samira-testroom/mod/yone_artifacts.lua'


def main():
    lua = LuaRuntime()
    lua.execute(r'''
CollectibleType = {COLLECTIBLE_20_20=1, COLLECTIBLE_INNER_EYE=2, COLLECTIBLE_MUTANT_SPIDER=3,
 COLLECTIBLE_MOMS_KNIFE=4, COLLECTIBLE_COMMON_COLD=5, COLLECTIBLE_FIRE_MIND=6,
 COLLECTIBLE_SPIDER_BITE=7, COLLECTIBLE_MOMS_CONTACTS=8}
function EntityRef(p) return p end
function Color(...) return {...} end
player = {TearRange=260, Damage=4, owned={}, rolls={}}
function player:HasCollectible(id) return self.owned[id] == true end
function player:GetCollectibleRNG(id)
 return {RandomFloat = function() self.rolls[id]=(self.rolls[id] or 0)+1; return 0 end}
end
enemy = {effects={}, boss=false}
function enemy:IsBoss() return self.boss end
function enemy:AddPoison(_,d,v) self.effects.poison={d,v} end
function enemy:AddBurn(_,d,v) self.effects.burn={d,v} end
function enemy:AddSlowing(_,d,v) self.effects.slow={d,v} end
function enemy:AddFreeze(_,d) self.effects.freeze=d end
''')
    lua.globals().artifacts = lua.execute(MODULE.read_text(encoding='utf-8'))
    lua.execute(r'''
local a=artifacts
local h={kind='attack', artifactHit=false}
assert(a.range(player)==1 and a.multiplier(player,h)==1)
player.TearRange=9999; assert(a.range(player)==1.35)
player.TearRange=-100; assert(a.range(player)==.85)
player.TearRange=nil; assert(a.range(player)==1)
player.owned[4]=true; assert(a.range(player)>1 and a.range(player)<=1.35)
player.owned[1]=true
assert(math.abs(a.multiplier(player,h)-1.4)<.0001)
player.owned[2]=true; player.owned[3]=true
assert(math.abs(a.multiplier(player,h)-1.75)<.0001)
for _, kind in ipairs({'w','r','e_return'}) do
 local x={kind=kind}; assert(a.multiplier(player,x)==1)
 a.onHit(player,x,enemy); assert(not x.artifactHit)
end
for id=5,8 do player.owned[id]=true end
a.onHit(player,h,enemy)
assert(h.artifactHit and a.multiplier(player,h)==1)
assert(enemy.effects.poison and enemy.effects.burn and enemy.effects.slow and enemy.effects.freeze)
assert(enemy.effects.poison[1] <= 60 and enemy.effects.poison[2] <= player.Damage)
assert(enemy.effects.burn[1] <= 60 and enemy.effects.burn[2] <= player.Damage)
for id=5,8 do assert(player.rolls[id]==1) end
a.onHit(player,h,enemy)
for id=5,8 do assert(player.rolls[id]==1) end
enemy.boss=true; enemy.effects={}
local bossHit={kind='q'}; a.onHit(player,bossHit,enemy)
assert(enemy.effects.freeze == nil and player.rolls[8] == 1)
assert(enemy.effects.poison and enemy.effects.burn and enemy.effects.slow)
for _, kind in ipairs({'attack','q','q3'}) do
 local x={kind=kind}; assert(a.multiplier(player,x)>1); a.onHit(player,x,enemy); assert(x.artifactHit)
end
-- Rolls outside the proc chance must not apply effects; owning no items must
-- not consume any RNG, and a consumed multi-target action cannot proc again.
enemy.boss=false; enemy.effects={}
function player:GetCollectibleRNG(id)
 return {RandomFloat = function() self.rolls[id]=(self.rolls[id] or 0)+1; return .99 end}
end
local failedRoll={kind='q'}; a.onHit(player,failedRoll,enemy)
assert(failedRoll.artifactHit and next(enemy.effects)==nil)
player.owned={}; player.rolls={}; enemy.effects={}
local noItems={kind='q3'}; a.onHit(player,noItems,enemy)
assert(noItems.artifactHit and next(player.rolls)==nil and next(enemy.effects)==nil)
assert(a.multiplier(player,{kind='attack'})==1)

''')
    print('PASS Yone collectible range, multi-shot, single-use statuses and boss freeze')


if __name__ == '__main__':
    main()
