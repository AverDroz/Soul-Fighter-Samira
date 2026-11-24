local Special = {}
local Effects = include('miss_fortune_effects')
local Sprites = include('miss_fortune_sprite')

local mountFrames, rideFrames = 24, 50
local normalDismount = Sprites.duration('homeguard_out_run') and 'homeguard_out_run' or 'homeguard_out'
local homeguardSounds = {
    {0, 'Homeguard Start', .5},
    {5, 'Homeguard Gun', .48},
    {9, 'Homeguard Onboard', .44},
    {mountFrames, 'Homeguard Loop', .38, true},
}
local killWindow = 90
local pentaIntro = Sprites.duration('pentakill') or 0
local pentaBonus = Sprites.duration('pentakill_bonus') or 0
local effectsSprite

function Special.new(onNewFloor)
    return {homeguardReady=onNewFloor, killTimes={}}
end

local function stopHomeguardSounds(ride)
    for _, sound in ipairs(ride.sounds) do Effects.stopSound(sound) end
    ride.sounds={}
end

local function stopHomeguard(s)
    if s.ride then stopHomeguardSounds(s.ride) end
    s.ride=nil
end

function Special.reset(s)
    stopHomeguard(s)
    s.killTimes, s.pentakill={}, nil
end

function Special.takedown(s, clock)
    local kills=s.killTimes
    while kills[1] and clock-kills[1]>killWindow do table.remove(kills,1) end
    kills[#kills+1]=clock
    if #kills==5 then
        s.killTimes={}
        if pentaIntro>0 then s.pentakill={queuedAt=clock} end
    end
end

local function dismount(ride, clock, clip)
    stopHomeguardSounds(ride)
    ride.exit,ride.exitClip,ride.exitFrames=clock,clip,(Sprites.duration(clip) or 11)+1
    if clip~='idle_in' then
        local sound=Effects.playSound('Homeguard Exit',.43)
        if sound then ride.sounds[1]=sound end
    end
end

local function updateHomeguard(s, clock, game, allowed, moving, busy, strutting)
    if not s.homeguardReady and not s.ride then return end
    if not allowed then stopHomeguard(s); return end
    local level=game:GetLevel()
    if level:GetCurrentRoomIndex()~=level:GetStartingRoomIndex() or not game:GetRoom():IsClear() or busy then
        s.homeguardReady=false
        stopHomeguard(s)
        return
    end
    if s.homeguardReady and moving then
        s.homeguardReady=false
        s.ride={start=clock, nextSound=1, sounds={}}
    end
    local ride=s.ride
    if not ride then return end
    if ride.exit then
        if clock>=ride.exit+ride.exitFrames or moving and ride.exitClip=='idle_in' then
            stopHomeguard(s)
        elseif not moving and ride.exitClip~='idle_in' then
            dismount(ride,clock,'idle_in')
        end
        return
    end
    local elapsed=clock-ride.start
    -- Skin69 uses distinct blend edges to idle01, Run, and Run2.
    if not moving then
        dismount(ride,clock,'idle_in')
        return
    end
    if elapsed>=mountFrames+rideFrames then
        dismount(ride,clock,strutting and 'homeguard_out' or normalDismount)
        return
    end
    local cue=homeguardSounds[ride.nextSound]
    while cue and elapsed>=cue[1] do
        local sound=Effects.playSound(cue[2],cue[3],cue[4])
        if sound then ride.sounds[#ride.sounds+1]=sound end
        ride.nextSound=ride.nextSound+1
        cue=homeguardSounds[ride.nextSound]
    end
end

function Special.update(s, clock, game, allowed, moving, busy, strutting)
    updateHomeguard(s,clock,game,allowed,moving,busy,strutting)
    local penta=s.pentakill
    if not penta then return end
    if penta.start then
        if not allowed or moving or busy or clock>=penta.start+pentaIntro+pentaBonus then s.pentakill=nil end
    elseif clock-penta.queuedAt>killWindow then
        s.pentakill=nil
    elseif allowed and not moving and not busy and not s.ride then
        penta.start=clock
    end
end

function Special.pose(s, clock)
    local ride=s.ride
    if ride and ride.exit then return ride.exitClip,clock-ride.exit,false,ride.exitFrames,ride.exit end
    if ride then
        local movingAt=ride.start+mountFrames
        if clock<movingAt then return 'homeguard_in',clock-ride.start,false,mountFrames,ride.start end
        return 'homeguard',clock-movingAt,true,nil,movingAt
    end
    local penta=s.pentakill
    if penta and penta.start then
        local bonusAt=penta.start+pentaIntro
        if clock<bonusAt then return 'pentakill',clock-penta.start,false,nil,penta.start end
        return 'pentakill_bonus',clock-bonusAt,false,nil,bonusAt
    end
end

local function drawEffect(clip, position, rotation, width, height, tint)
    if effectsSprite==nil and Sprite then
        local sprite, loaded=Sprite('gfx/mf/special_effects.anm2',true)
        effectsSprite=loaded and sprite or false
    end
    if not effectsSprite then return end
    effectsSprite:SetFrame(clip,0)
    effectsSprite.Rotation=rotation
    effectsSprite.Scale=Vector(width,height)
    effectsSprite.Color=tint
    effectsSprite:Render(position)
end

function Special.render(s, clock, player, project)
    local ride=s.ride
    local penta=s.pentakill
    if ride and not ride.exit and clock-ride.start>=10 then
        local center=project(player.Position)
        local behind=project(player.Position-player.Velocity*5)
        local angle=(center-behind):GetAngleDegrees()
        drawEffect('HomeguardTrail',behind+Vector(0,3),angle,.19,.25,Color(1,.77,.45,.64))
        drawEffect('HomeguardGlow',center+Vector(0,3),0,.23,.15,Color(1,.83,.58,.54))
    elseif penta and penta.start then
        local age=clock-penta.start-pentaIntro
        if age>=0 and age<60 then
            local alpha=math.min(1,(age+2)/7,(60-age)/13)
            local scale=.30+.10*math.min(1,age/20)
            drawEffect('PentakillSignature',project(player.Position)-Vector(0,5),0,scale,scale*.6,
                Color(1,.76,.40,.80*alpha))
        end
    end
end

return Special
