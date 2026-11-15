local F={};local sprite;local G=include('scripts.samira_geometry')
function F.draw(p,s,offset)
    if not sprite then sprite=Sprite();sprite:Load('gfx/samira/fallback.anm2',true) end
    local walking=p.Velocity:Length()>.6
    local kind=p:IsDead() and 'Death' or s.cast and 'Attack' or walking and 'Walk' or 'Idle'
    local face=s.cast and s.cast.face or s.face
    local dir=math.floor((90-face:GetAngleDegrees())/45+.5)%8
    local frame=p:IsDead() and math.min(2,math.floor((s.presentation and s.presentation.age or 0)*2)) or s.cast and math.min(2,math.floor(s.cast.age/s.cast.duration*3))
        or math.floor((walking and (s.walkClock or 0) or s.clock)/8)%(walking and 4 or 2)
    sprite:SetFrame(kind..dir,frame);sprite.Scale=G.bodyScale(p)*.96
    sprite.Color=(s.hurtUntil or 0)>s.clock and Color(1,.18,.18,1,.3,0,0) or Color.Default
    sprite:Render(Isaac.WorldToRenderPosition(p.Position)+offset)
end
return F
