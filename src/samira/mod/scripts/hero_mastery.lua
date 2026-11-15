-- Cosmetic only. One update per player; never changes movement, casts or stats.
-- Original live rig in Companion; 30-FPS atlas only when Companion is unavailable.
local M={DURATION=120,COOLDOWN=180}
local states=setmetatable({},{__mode='k'})
local sprite
function M.clear()
    for s,v in pairs(states) do s.masteryAt=nil;v.at=nil;v.ready=nil;v.armed=false end
end
function M.update(s,enabled,allowed,down)
    local v=states[s]
    if not v then v={held=false,armed=true};states[s]=v end
    local pressed=down and not v.held and v.armed
    v.held=down
    if not down then v.armed=true end
    if not enabled or not allowed then s.masteryAt=nil;v.at=nil;return false end
    if v.at and (s.clock<v.at or s.clock-v.at>=M.DURATION) then s.masteryAt=nil;v.at=nil end
    if pressed and s.clock>=(v.ready or 0) then
        v.at=s.clock;s.masteryAt=s.clock;v.ready=s.clock+M.COOLDOWN;return true
    end
    return false
end
function M.sound()
    local id=Isaac.GetSoundIdByName("Hero Mastery Level 7")
    if id and id>0 then SFXManager():Play(id,.8,0,false,1) end
end
function M.alpha(s)
    local v=states[s];if not v or not v.at then return 0 end
    local age=s.clock-v.at
    if age<0 or age>=M.DURATION then v.at=nil;return 0 end
    return math.min(1,(age+1)/6,(M.DURATION-age)/10)
end
function M.draw(s,position)
    local alpha=M.alpha(s);if alpha<=0 then return end
    if not sprite then sprite=Sprite();sprite:Load('gfx/hero_mastery/badge.anm2',true);sprite.Scale=Vector(.5,.5) end
    sprite:SetFrame('Play',math.min(M.DURATION-1,math.max(0,math.floor(s.clock-states[s].at))))
    sprite.Color=Color(1,1,1,alpha,0,0,0)
    sprite:Render(position,Vector.Zero,Vector.Zero)
end
return M
