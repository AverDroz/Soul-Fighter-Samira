-- Brief Q stagger plus render-only lift. Never write Position/SpriteOffset/physics height.
local K={DURATION=12,HEIGHT=24}
local clock,epoch=0,0
function K.tick()clock=clock+1 end
function K.clear()epoch=epoch+1 end
local function active(e)
    local data=e:GetData();local air=data.SamiraQStagger
    if not air then return end
    if air.epoch~=epoch or clock>=air.untilTick or not e:Exists() or e:IsDead() then
        data.SamiraQStagger=nil;return
    end
    return air
end
local function height(air)
    local t=math.max(0,math.min(1,(clock-air.started)/K.DURATION))
    local function smooth(v)return v*v*(3-2*v) end
    -- Ease up in the first quarter, settle back down for the remaining time.
    if t<.25 then return air.startHeight+(K.HEIGHT-air.startHeight)*smooth(t/.25) end
    return K.HEIGHT*(1-smooth((t-.25)/.75))
end
function K.preRender(e,offset)
    local air=active(e)
    if air then
        -- Retain returned userdata until native rendering consumes it.
        air.renderOffset=air.renderOffset or Vector(0,0)
        air.renderOffset.X=offset.X
        air.renderOffset.Y=offset.Y-height(air)
        return air.renderOffset
    end
end
function K.apply(e)
    if not e:Exists() or e:IsDead() then return end
    local air=active(e)
    if air then
        -- A later Q refreshes the remaining stop duration.
        air.startHeight=height(air);air.started=clock;air.untilTick=clock+K.DURATION
    else
        e:GetData().SamiraQStagger={epoch=epoch,untilTick=clock+K.DURATION,started=clock,startHeight=0}
    end
    e.Velocity=Vector.Zero
end
function K.preUpdate(e)
    if active(e) then e.Velocity=Vector.Zero;return true end
end
return K
