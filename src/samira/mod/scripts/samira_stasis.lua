-- Stasis stops the actor, not the simulation. Call before processing new commands.
local S={}
function S.active(p,g)return not p:IsDead() and (g.stasis or 0)>(g.time or 0) end
function S.clear(p)
    local data=p:GetData();local held=data.SamiraStasis
    if not held then return end
    if p.EntityCollisionClass==EntityCollisionClass.ENTCOLL_NONE then p.EntityCollisionClass=held.collision end
    if held.noTarget then p:ClearEntityFlags(EntityFlag.FLAG_NO_TARGET) end
    data.SamiraStasis=nil
end
function S.update(p,g)
    if not S.active(p,g) then S.clear(p);return false end
    local data=p:GetData();local held=data.SamiraStasis
    if not held then
        held={collision=p.EntityCollisionClass,noTarget=not p:HasEntityFlags(EntityFlag.FLAG_NO_TARGET)}
        data.SamiraStasis=held
        p:AddEntityFlags(EntityFlag.FLAG_NO_TARGET)
    end
    p.EntityCollisionClass=EntityCollisionClass.ENTCOLL_NONE
    p.Velocity=Vector.Zero;p.FireDelay=math.max(p.FireDelay or 0,3)
    return true
end
return S
