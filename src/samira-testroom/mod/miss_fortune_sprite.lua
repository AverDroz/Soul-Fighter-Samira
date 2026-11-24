local Sprites = {}
local frames = include('miss_fortune_sprite_frames')
local durations = include('miss_fortune_sprite_times')
local prepared = {}
-- Skin69 discharge events verified in tools/build_miss_fortune_muzzle_tracks.py.
local releaseFrames = {attack=7, attack2=7, crit=7, q=6}
-- Horizontal barrel extension in the original 30-frame Spell4_Loop.
-- Right and left alternate. The last value is the next cycle's right shot.
local barrageShots = {8,12,18,22,28,32,38}
local loops = {
    idle=true, base_idle=true, run=true, strut_run_loop=true, r=true,
    joke_loop=true, taunt_loop=true, taunt_spam_loop=true, dance_loop=true, recall_loop=true, homeguard=true,
}

function Sprites.duration(clip)
    local seconds = durations[clip]
    return seconds and math.max(1, math.floor(30 * seconds + .5))
end

function Sprites.discharge(clip,frame,length)
    local release,seconds=releaseFrames[clip],durations[clip]
    if not length or not release or not seconds or 30*seconds<=release then return frame,length end
    -- Isaac has already fired. Align the first presented frame to the source
    -- discharge pose and use the existing playback window for its remaining frames.
    local lead=math.max(1,length-1)*release/(30*seconds-release)
    return frame+lead,length+lead
end

function Sprites.barrageFrame(wave,age,interval)
    if durations.r~=1 then return (wave-1)*interval+age end
    local cycle=(wave-1)//6
    local shot=(wave-1)%6+1
    local from,to=barrageShots[shot],barrageShots[shot+1]
    return 30*cycle+from+(to-from)*math.min(1,age/interval)
end

function Sprites.sample(clip, frame, length, expression)
    if not frames[clip] or not durations[clip] then return end
    if expression == 'joke' and durations.joke_in then
        local entry = Sprites.duration('joke_in')
        if frame < entry then clip, expression = 'joke_in', nil
        else frame = frame - entry end
    end
    local phase
    if expression then
        local intro = Sprites.duration(clip)
        local exit = expression == 'recall' and Sprites.duration('recall_out')
        local loop = clip .. '_loop'
        if exit and frame >= 240 - exit then
            clip = 'recall_out'
            phase = math.min(1, (frame - 240 + exit) / exit)
        elseif frame >= intro and loops[loop] and durations[loop] then
            clip = loop
            phase = ((frame - intro) / (durations[loop] * 30)) % 1
        else
            phase = math.min(1, frame / intro)
        end
    else
        local ticks = length and not loops[clip] and math.max(1, length - 1) or 30 * durations[clip]
        phase = loops[clip] and (frame % ticks) / ticks or math.min(1, frame / ticks)
    end
    local index = loops[clip] and math.floor(phase * frames[clip])
        or math.floor(phase * (frames[clip] - 1) + .5)
    return clip, math.min(frames[clip] - 1, math.max(0, index))
end

function Sprites.prepare(clip)
    if not frames[clip] or prepared[clip] ~= nil then return end
    local path = 'gfx/mf/action-' .. clip .. '.anm2'
    local ok, sprite, loaded = pcall(Sprite, path, true)
    prepared[clip] = ok and loaded and sprite or false
    if not prepared[clip] then Isaac.DebugString('[MF_NATIVE] Could not load ' .. path) end
end

function Sprites.drawPrepared(clip, frame, direction, position, scale, color)
    local sprite = prepared[clip]
    if not sprite then return false end
    sprite:SetFrame(clip .. direction, frame)
    sprite.Scale, sprite.Color = scale, color
    sprite:Render(position)
    return true
end

return Sprites
