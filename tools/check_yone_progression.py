"""Exercise Yone's run progression and rune rules without an Isaac session."""

from pathlib import Path

from lupa.lua54 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/samira-testroom/mod/yone_progression.lua"


def main():
    lua = LuaRuntime()
    lua.globals().Progress = lua.execute(MODULE.read_text(encoding="utf-8"))
    lua.execute(r"""
local P = Progress
local function close(actual, expected)
    assert(math.abs(actual - expected) < .0001, ('expected %s but got %s'):format(expected, actual))
end

local p = P.restore()
assert(p.level == 1 and p.xp == 0 and p.rune == nil and P.points(p) == 0)
for _, key in ipairs({'q', 'w', 'e', 'r', 'q3', 'e_return'}) do
    assert(P.rank(p, key) == 1 and not P.upgrade(p, key))
    close(P.cooldown(p, key), 1)
    close(P.damage(p, key, 0), 1)
end
assert(P.required(1) == 60 and P.required(2) == 72)
assert(P.award(p, 59) == 0 and p.xp == 59)
assert(P.award(p, 1) == 1 and p.level == 2 and p.xp == 0 and P.points(p) == 1)
assert(not P.upgrade(p, 'r') and not P.upgrade(p, 'attack'))
assert(P.upgrade(p, 'q3') and P.rank(p, 'q') == 2 and not P.upgrade(p, 'q'))
close(P.cooldown(p, 'q3'), 1)
close(P.damage(p, 'q3', 0), 1.08)
assert(P.award(p, 72 + 84 + 1) == 2 and p.level == 4 and p.xp == 1)
assert(P.upgrade(p, 'q') and P.rank(p, 'q') == 3 and not P.upgrade(p, 'q'))
assert(P.upgrade(p, 'w') and not P.upgrade(p, 'r'))
close(P.cooldown(p, 'w'), .95)
assert(P.award(p, 96 + 108 - 1) == 2 and p.level == 6)
assert(P.upgrade(p, 'r') and not P.upgrade(p, 'r') and P.upgrade(p, 'e'))
close(P.damage(p, 'e_return', 0), 1.08)
close(P.cooldown(p, 'e'), .95)
assert(P.award(p, math.maxinteger) == 12 and p.level == 18 and p.xp == 0)
assert(P.award(p, 900) == 0 and P.points(p) == 9)
for _, key in ipairs({'q', 'w', 'e', 'r'}) do
    while P.upgrade(p, key) do end
    assert(P.rank(p, key) == (key == 'r' and 3 or 5))
end
assert(P.points(p) == 0)

local bad = P.restore({version = 1, level = 2, xp = math.huge, rune = 'random',
    ranks = {q = 900, w = 4, e = -math.huge, r = 3}})
assert(bad.level == 2 and bad.xp == 0 and bad.rune == nil)
assert(P.rank(bad, 'q') == 2 and P.rank(bad, 'w') == 1 and P.rank(bad, 'e') == 1 and P.rank(bad, 'r') == 1)
assert(P.restore({version = 2, level = 16}).level == 1)
assert(P.restore({level = 16}).level == 1)
assert(P.restore({version = 1, level = 5, xp = 999}).xp == P.required(5) - 1)
assert(P.restore({version = 1, level = 99, xp = 999}).xp == 0)

local selected = {}
for seed = -10, 50 do
    local left, right = P.restore(), P.restore()
    local ok, rune = P.choose(left, 'random', seed)
    assert(ok and rune == left.rune and rune ~= 'random')
    assert(P.choose(right, 'random', seed) and left.rune == right.rune)
    assert(not P.choose(left, 'conqueror', seed) and left.rune == rune)
    assert(P.restore(P.snapshot(left)).rune == rune)
    selected[rune] = true
end
assert(selected.conqueror and selected.lethal_tempo and selected.electrocute)
assert(not P.choose(P.restore(), 'unknown', 0))

local conqueror = P.restore()
assert(P.choose(conqueror, 'conqueror', 1))
P.onStrike(conqueror, 'invalid', 0)
close(P.damage(conqueror, 'attack', 0), 1)
for t = 1, 8 do P.onStrike(conqueror, 'attack', t) end
close(P.damage(conqueror, 'attack', 157), 1.10)
close(P.damage(conqueror, 'attack', 158), 1)
P.onStrike(conqueror, 'w', 158)
close(P.damage(conqueror, 'w', 158), 1.02)
local saved = P.snapshot(conqueror)
assert(saved.rune == conqueror.rune and saved.ranks ~= conqueror.ranks and saved.runeStacks == nil)
close(P.damage(saved, 'w', 158), 1)
P.resetRoom(conqueror)
close(P.damage(conqueror, 'w', 158), 1)

local tempo = P.restore()
assert(P.choose(tempo, 'lethal_tempo', 1))
for _, key in ipairs({'w', 'e_return', 'r'}) do P.onStrike(tempo, key, 1) end
close(P.attackSpeed(tempo, 1), 1)
for t = 2, 9 do P.onStrike(tempo, t % 2 == 0 and 'q3' or 'attack', t) end
close(P.attackSpeed(tempo, 128), 1.24)
close(P.attackSpeed(tempo, 129), 1)
P.onStrike(tempo, 'q', 129)
P.resetRoom(tempo)
close(P.attackSpeed(tempo, 129), 1)

local electro = P.restore()
assert(P.choose(electro, 'electrocute', 1))
assert(P.onStrike(electro, 'q', 0) == nil)
assert(P.onStrike(electro, 'q3', 4) == nil)
assert(P.onStrike(electro, 'attack', 5) == nil)
assert(P.onStrike(electro, 'r', 95) == nil)
assert(P.onStrike(electro, 'w', 96) == nil)
close(P.onStrike(electro, 'e_return', 97), .45)
P.resetRoom(electro)
for _, key in ipairs({'q', 'w', 'attack'}) do assert(P.onStrike(electro, key, 336) == nil) end
assert(P.onStrike(electro, 'q', 337) == nil and P.onStrike(electro, 'w', 338) == nil)
close(P.onStrike(electro, 'attack', 339), .45)
assert(P.snapshot(electro).electrocuteReady == nil)
local reloaded = P.restore(P.snapshot(electro, 400), 1000)
assert(reloaded.electrocuteReady == 1179 and reloaded.electrocuteHits == nil)
for _, key in ipairs({'q', 'w', 'r'}) do assert(P.onStrike(reloaded, key, 1178) == nil) end
assert(P.onStrike(reloaded, 'q', 1179) == nil and P.onStrike(reloaded, 'w', 1180) == nil)
close(P.onStrike(reloaded, 'r', 1181), .45)
""")
    print("Yone progression and rune simulation passed")


if __name__ == "__main__":
    main()
