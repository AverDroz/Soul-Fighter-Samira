-- Native enemy silhouette render and authoritative coin synchronization.
local E=include('scripts.samira_equipment')
local I={}
function I.same(a,b)
    if not a or not b then return false end
    return a==b or GetPtrHash and GetPtrHash(a)==GetPtrHash(b) or false
end
function I.hover(entities,aim,enemy)
    local selected,best=nil,1
    for _,e in ipairs(entities) do if enemy(e) then
        local radius=math.max(12,e.Size+6);local d=aim-(e.Position+Vector(0,-radius*.55))
        local foot=aim-e.Position
        local distance=math.min((d.X/radius)^2+(d.Y/(radius*1.4))^2,(foot.X^2+foot.Y^2)/(radius*.8)^2)
        if distance<best then selected=e;best=distance end
    end end
    return selected
end
function I.outline(npc,offset)
    local sp=npc:GetSprite();local original=sp.Color
    local pos=Isaac.WorldToRenderPosition(npc.Position)+offset+(npc.SpriteOffset or Vector.Zero)
    sp.Color=Color(0,0,0,1,1,.12,.05)
    for _,d in ipairs({Vector(-1.5,0),Vector(1.5,0),Vector(0,-1.5),Vector(0,1.5),Vector(-1,-1),Vector(1,1),Vector(-1,1),Vector(1,-1)}) do sp:Render(pos+d) end
    sp.Color=original
end
function I.coinBefore(coin,p) E.syncCoins(p) end
function I.coinAfter(coin,p) E.syncCoins(p) end
return I
