"""Exercise Samira's style meter and ultimate gate in the actual Lua module."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
lua.globals().style_source = (
    ROOT / 'src/samira-testroom/mod/samira_style.lua'
).read_text(encoding='utf-8')

lua.execute(r'''
local Style = assert(load(style_source))()
local function hit(kind, frame)
    local context = {kind = kind}
    Style.hit(context, frame)
    return context
end
local function rank(expected, frame, label)
    local observed = Style.status(frame).rank
    assert(observed == expected, label .. ': expected ' .. expected .. ', got ' .. observed)
end

Style.reset()
for i = 1, 6 do
    hit(i % 2 == 1 and 'attack' or 'q', 10 * i)
    rank(i, 10 * i, 'alternating attacks/abilities')
    assert(Style.canCast(10 * i) == (i == 6))
end
assert(Style.status(60, 60).ready)
assert(not Style.status(60, 90).ready and Style.status(60, 90).cooldown == 1)
assert(Style.status(90, 90).ready and Style.status(90, 90).cooldown == 0)
hit('melee', 95)
rank(6, 95, 'rank is capped at S')

assert(Style.consume(100, 60))
rank(0, 100, 'casting consumes the meter')
assert(not Style.consume(100, 60))
hit('q', 159)
rank(0, 159, 'casting locks style for 60 frames')
hit('q', 160)
rank(1, 160, 'style unlocks on the first frame after the cast interval')

Style.reset()
hit('attack', 200)
hit('melee', 379)
rank(1, 379, 'ranged and melee autoattacks share their style kind')
local refreshed = Style.status(379)
assert(refreshed.remaining == 6 and refreshed.progress == 1 and not refreshed.ready)
rank(1, 558, 'repeated autoattack refreshed the six-second timer')
rank(0, 559, 'style expires at 180 frames')
assert(Style.status(559).remaining == 0 and Style.status(559).progress == 0)
hit('melee', 560)
rank(1, 560, 'expiry clears the last action kind')

Style.reset()
local sweep = hit('w', 600)
Style.hit(sweep, 601)
hit('e', 602)
Style.hit(sweep, 603)
sweep.stylePart = 2
Style.hit(sweep, 604)
Style.hit(sweep, 605)
rank(3, 605, 'each W sweep can count once, with E between')

Style.reset()
local beam = hit('q', 700)
Style.hit(beam, 701)
hit('attack', 702)
Style.hit(beam, 703)
rank(2, 703, 'an interleaved hit from the same beam gives no extra rank')
hit('melee', 704)
rank(2, 704, 'an old beam cannot make consecutive autoattacks alternate')

Style.reset()
hit('attack', 800)
local repeated = hit('melee', 801)
hit('q', 802)
Style.hit(repeated, 803)
rank(2, 803, 'a repeated multi-hit autoattack is decided on its first hit')

Style.reset()
hit('eq', 900)
hit('q', 901)
hit('qmelee', 902)
rank(1, 902, 'EQ and melee Q use the Q style kind')
hit('r', 903)
hit('item', 904)
Style.hit(nil, 905)
rank(1, 905, 'R hits and item effects do not add style')
assert(Style.status(905).remaining == 177 / 30)
assert(not Style.status(905, 0).ready and not Style.consume(905, 60))
Style.reset()
rank(0, 905, 'full reset clears style')
''')
print('Samira style ranks, action deduplication, expiry, resets and R gate passed.')
