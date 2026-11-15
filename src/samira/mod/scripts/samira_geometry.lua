-- Shared by damage tests and indicator outlines. All dimensions are world units.
local G={};local Health=include('scripts.samira_health')
G.baseSpeed=2.45*1.05*1.10
function G.movementSpeed(speed)
    -- Reduce the total positive bonus once, after item and ability multipliers.
    return speed>G.baseSpeed and G.baseSpeed+(speed-G.baseSpeed)*.5 or speed
end
G.groundScale=.98
-- One distance conversion for all three abilities; Y compression is projection only.
G.units=.28
G.dashRange=330*G.units -- 10% longer E; keep the full dash at twelve ticks.
G.dashMin=75*G.units
G.dashTerrainRange=500*G.units
G.dashStep=880*G.units/30
G.qImpact=18 -- 0.6 seconds at Isaac's 30 Hz simulation rate.
G.qDuration=24
G.qRecast=30
-- Contact poses measured from the existing source clips; normal Q2 uses a different clip.
local contacts={Q1=.60,Q2=.82,Q3=.53,RQ1=.60,RQ2=.56,RQ3=.53}
function G.castPhase(kind,cast,alpha,contactOverride)
    local age=math.min(cast.duration,cast.age+(alpha or 0));local contact=contactOverride or contacts[kind]
    if not contact then return age/cast.duration end
    if age<=cast.impact then return contact*age/cast.impact end
    return contact+(1-contact)*(age-cast.impact)/(cast.duration-cast.impact)
end
function G.project(v)return Vector(v.X,v.Y*G.groundScale)end
function G.unproject(v)return Vector(v.X,v.Y/G.groundScale)end
function G.bodyScale(p)
    local scale=p.SpriteScale or Vector(1,1)
    local multiplier=1;local gear=p:GetData().SamiraGear
    for _,slot in ipairs(gear and gear.slots or {}) do
        if slot.id==3084 then
            -- Original Heartsteel: +3% size per 1000 maximum health, capped at 30%.
            -- Derive it from ownership/current HP so sale and rewind cannot leave
            -- a permanent SpriteScale mutation or compound it every frame.
            multiplier=1+math.min(.30,Health.max(p)/1000*.03);break
        end
    end
    return Vector(math.max(.05,scale.X)*multiplier,math.max(.05,scale.Y)*multiplier)
end
function G.qCount(p)
    if not p.GetMultiShotParams then return 1 end
    return math.max(1,math.floor(p:GetMultiShotParams(WeaponType.WEAPON_TEARS):GetNumTears()))
end
function G.qFaces(face,count)
    local faces={};local step=math.min(12,120/math.max(1,count-1))
    for i=1,count do faces[i]=face:Rotated((i-(count+1)/2)*step) end
    return faces
end
function G.stats(damage,delay,range,luck,speed)
    return {damage=math.max(1,damage)*1.8,interval=math.max(10,math.floor((delay+1)*4.2)),
        reach=math.max(44,math.min(90,56+(range-260)*.10)),
        scale=math.max(.8,math.min(1.5,1+(range-260)/900)),
        crit=math.max(0,math.min(.6,luck*.04)),speed=math.max(1.2,math.min(4,speed*G.baseSpeed))}
end
-- Client W area is authored around a 540-unit ground marker. Keep the
-- displayed trapezoid and the escape test on the same shared dimensions.
function G.wShape()
    return {kind='wedge',near=-140,far=140,narrow=80,width=140,sweet=140}
end
function G.shape(stage,scale)
    scale=scale or 1
    local u=G.units*scale
    if stage==1 then return {kind='box',near=0,far=650*u,width=90*u,sweet=480*u} end
    if stage==2 then return {kind='wedge',near=-100*u,far=525*u,narrow=150*u,width=250*u,sweet=375*u} end
    return {kind='circle',cx=200*u,radius=300*u,inner=180*u}
end
function G.hit(s,x,y,r)
    r=r or 0
    if s.kind=='circle' then local d=((x-s.cx)^2+y*y)^.5;return d<=s.radius+r,d<=s.inner end
    if x<s.near-r or x>s.far+r then return false,false end
    local w=s.width
    if s.kind=='wedge' then w=s.narrow+(s.width-s.narrow)*math.max(0,math.min(1,(x-s.near)/(s.far-s.near))) end
    return math.abs(y)<=w+r,x>=s.sweet and math.abs(y)<=w
end
-- 100-degree sector against a circular target; no wall/rock raycast.
function G.basicHit(x,y,r,reach)
    r=math.max(0,r or 0)
    local distance=math.sqrt(x*x+y*y)
    if distance<=r then return true end
    local angle=math.abs(math.atan(y,x));local half=math.rad(50)
    if angle<=half then return distance<=reach+r end
    -- Closest point on the sector's radial edge also handles the far corner.
    local along=math.max(0,math.min(reach,distance*math.cos(angle-half)))
    local dx=x-along*math.cos(half);local dy=math.abs(y)-along*math.sin(half)
    return dx*dx+dy*dy<=r*r
end
-- Return the first contact distance, or nil when outside the attack shape.
function G.basicContact(x,y,r,reach,thrust)
    r=math.max(0,r or 0)
    if not thrust then
        if G.basicHit(x,y,r,reach) then return math.max(0,math.sqrt(x*x+y*y)-r) end
        return nil
    end
    -- A 24-world-unit wide forward rectangle, with circular NPC collision.
    local side=math.max(0,math.abs(y)-12)
    if side>r then return nil end
    local edge=math.sqrt(math.max(0,r*r-side*side))
    if x+edge<0 or x-edge>reach then return nil end
    return math.max(0,x-edge)
end
function G.outline(s,sweet)
    local points={}
    if s.kind=='circle' then
        local radius=sweet and s.inner or s.radius
        for i=0,40 do local a=i*math.pi/20;points[#points+1]={s.cx+math.cos(a)*radius,math.sin(a)*radius} end
    else
        local near=sweet and s.sweet or s.near;local width=s.width
        local narrow=s.kind=='wedge' and s.narrow+(s.width-s.narrow)*(near-s.near)/(s.far-s.near) or width
        points={{near,-narrow},{s.far,-width},{s.far,width},{near,narrow},{near,-narrow}}
    end
    return points
end
return G
