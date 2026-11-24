"""Exercise Yone's expression and mastery input without starting Isaac."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work/python-deps"))

from lupa import LuaRuntime


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    source = ROOT / "src/samira-testroom/mod/yone_emotes.lua"
    emotes = lua.execute(source.read_text(encoding="utf-8"))
    lua.globals().Emotes = emotes
    lua.execute("""
        local function tick(state, frame, number, ctrl, interrupted, disabled)
            local keys = {ctrl = ctrl, disabled = disabled}
            if number then keys[number] = true end
            Emotes.update(state, frame, keys, interrupted)
        end

        local state = Emotes.new()
        tick(state, 10, 1, true)
        local action, age = Emotes.action(state, 10)
        assert(action == 'joke' and age == 0)
        tick(state, 11, 1, true)
        _, age = Emotes.action(state, 11)
        assert(age == 1, 'Holding the chord restarted the expression')
        assert(Emotes.action(state, 274) == 'joke')
        assert(Emotes.action(state, 275) == nil)
        tick(state, 277, 1, true)
        assert(Emotes.action(state, 277) == nil, 'Holding restarted an expired expression')
        tick(state, 278, 2, true)
        assert(Emotes.action(state, 278) == 'taunt')
        assert(Emotes.action(state, 401) == 'taunt')
        assert(Emotes.action(state, 402) == nil)
        tick(state, 279, 3, true)
        action, age = Emotes.action(state, 376)
        assert(action == 'dance' and age == 97, 'Dance time must advance beyond the intro')
        tick(state, 377, 3, true, true)
        assert(Emotes.action(state, 377) == nil)
        tick(state, 378, 3, true)
        assert(Emotes.action(state, 378) == nil, 'Interrupting must not rearm a held chord')

        local finite = Emotes.new({{action='recall', duration=3, toggle=true}})
        tick(finite, 0, 1, true)
        tick(finite, 1, nil, false)
        tick(finite, 3, 1, true)
        action, age = Emotes.action(finite, 3)
        assert(action == 'recall' and age == 0, 'A finished toggle must restart on the first new press')

        state = Emotes.new()
        tick(state, 162, 4, true)
        assert(Emotes.action(state, 162) == 'laugh' and Emotes.blocksPocket(state))
        assert(Emotes.action(state, 215) == nil)
        tick(state, 163, 4, false)
        assert(Emotes.blocksPocket(state), 'Releasing Ctrl first leaked the pocket action')
        tick(state, 164, nil, false)
        tick(state, 165, 4, false)
        assert(not Emotes.blocksPocket(state), 'Clean 4 must still reach the pocket action')
        tick(state, 166, 4, true)
        tick(state, 167, nil, true)
        tick(state, 168, nil, false)
        tick(state, 169, 4, false)
        assert(not Emotes.blocksPocket(state), 'Releasing 4 first locked out the next clean 4')

        state = Emotes.new()
        tick(state, 200, 5, true)
        assert(Emotes.action(state, 200) == nil and Emotes.mastery(state, 200) == nil)
        tick(state, 201, 6, true, true)
        assert(Emotes.mastery(state, 201) == 0, 'Mastery must be independent of combat interruption')
        assert(Emotes.mastery(state, 261) == 0.5)
        assert(Emotes.mastery(state, 321) == nil)
        tick(state, 202, 3, true)
        assert(Emotes.action(state, 202) == 'dance' and Emotes.mastery(state, 202) ~= nil)
        Emotes.cancel(state, false)
        assert(Emotes.action(state, 203) == nil and Emotes.mastery(state, 203) ~= nil)
        Emotes.cancel(state, true)
        assert(Emotes.mastery(state, 204) == nil)
        tick(state, 205, 6, true)
        assert(Emotes.mastery(state, 205) == nil, 'Clearing the badge must not reset cooldown')
        tick(state, 381, 6, true)
        assert(Emotes.mastery(state, 381) == nil, 'Holding mastery through cooldown retriggered it')
        tick(state, 382, nil, true)
        tick(state, 383, 6, true)
        assert(Emotes.mastery(state, 383) == 0)

        local other = Emotes.new()
        tick(other, 383, nil, false)
        assert(Emotes.mastery(other, 383) == nil, 'Mastery crossed player states')
        tick(other, 390, 1, true, false, true)
        tick(other, 390, 1, true)
        assert(Emotes.action(other, 390) == nil, 'A chord held through pause activated on resume')
        tick(other, 391, 6, true, false, true)
        tick(other, 391, 6, true)
        assert(Emotes.mastery(other, 391) == nil, 'A mastery chord held through pause activated on resume')
        tick(other, 392, nil, true)
        tick(other, 393, 6, true)
        assert(Emotes.mastery(other, 393) == 0)
        tick(other, 403, nil, true)
        tick(other, 203, nil, true)
        assert(Emotes.mastery(other, 203) == nil, 'A rewind retained the old badge')
        tick(other, 372, 6, true)
        assert(Emotes.mastery(other, 372) == nil, 'A rewind cleared the remaining cooldown')
        tick(other, 373, nil, true)
        tick(other, 374, 6, true)
        assert(Emotes.mastery(other, 374) == 0, 'Cooldown used the pre-rewind clock')
    """)
    print("Yone emote edges, animation timing, pocket routing, and mastery passed")


if __name__ == "__main__":
    main()
