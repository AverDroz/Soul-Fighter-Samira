-- Native transition/item bookkeeping may run invisibly; it never selects the body animation.
local P={}
local cosmetic={Hit=true,Happy=true,Sad=true,Pickup=true,PickupWalkDown=true,PickupWalkUp=true,PickupWalkLeft=true,PickupWalkRight=true,UseItem=true,LiftItem=true}
function P.cosmetic(player)
    local animation=player:GetSprite():GetAnimation() or ''
    return cosmetic[animation] or animation:find('Pickup',1,true)~=nil or animation:find('UseItem',1,true)~=nil
end
function P.canAct(player)
    if player:IsDead() then return false end
    -- Taking damage and holding an item must not stop an already running skill clock.
    return P.cosmetic(player) or player.ControlsEnabled and player:IsExtraAnimationFinished()
end
function P.update(player,s)
    if not player:IsDead() and player:GetSprite():GetAnimation()=='Hit' then
        s.hurtUntil=math.max(s.hurtUntil or 0,s.clock+4)
    end
end
function P.state(player,s,paused)
    if not player:IsDead() then s.presentation=nil;return nil end
    local key='Death'
    local now=Isaac.GetTime();local state=s.presentation
    if not state or state.key~=key then state={key=key,age=0,last=now};s.presentation=state end
    if not paused then state.age=state.age+math.max(0,math.min(.1,(now-state.last)/1000)) end
    state.last=now;state.kind='Death'
    return state
end
return P
