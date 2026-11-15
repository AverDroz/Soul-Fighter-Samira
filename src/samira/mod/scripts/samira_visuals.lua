local V={};local sprites={};local images={};local sizes=include('scripts.samira_art_sizes');local G=include('scripts.samira_geometry')
local Q=include('scripts.samira_quads')
local rangeLine
local stroke
local function line(a,b,width,color)
    if not stroke then stroke=Sprite();stroke:Load('gfx/samira/pixel.anm2',true);stroke:SetFrame('Idle',0) end
    local delta=b-a;stroke.Scale=Vector(delta:Length(),width);stroke.Rotation=delta:GetAngleDegrees();stroke.Color=color;stroke:Render(a)
end
local function ring(center,radius,alpha,color)
    local previous
    for i=0,28 do
        local pos=Isaac.WorldToScreen(center+G.project(Vector(radius,0):Rotated(i*360/28)))
        if previous then line(previous,pos,1.6,Color(color[1],color[2],color[3],alpha)) end
        previous=pos
    end
end
local function outline(origin,face,shape,sweet,color)
    if not rangeLine then rangeLine=Sprite();rangeLine:Load('gfx/samira/pixel.anm2',true);rangeLine:SetFrame('Idle',0) end
    rangeLine.Color=color;local previous;local angle=face:GetAngleDegrees()
    for _,point in ipairs(G.outline(shape,sweet)) do
        local pos=Isaac.WorldToScreen(origin+G.project(Vector(point[1],point[2]):Rotated(angle)))
        if previous then
            local delta=pos-previous;rangeLine.Scale=Vector(delta:Length(),sweet and 1.3 or 1)
            rangeLine.Rotation=delta:GetAngleDegrees();rangeLine:Render(previous)
        end
        previous=pos
    end
end
local function ground(name,origin,face,width,length,forward,color)
    local size=sizes[name];local entry=images[name]
    if not entry then entry={image=Renderer.LoadImage('gfx/samira/combat/'..name..'.png'),source=SourceQuad.NewFromRectangle(Vector(size[3] or 0,size[4] or 0),size[1],size[2],false)};images[name]=entry end
    local side=Vector(face.Y,-face.X)
    local function corner(x,y)return Isaac.WorldToScreen(origin+G.project(side*x+face*(forward+y)))end
    local dest=Q.destination(corner(-width/2,-length/2),corner(width/2,-length/2),corner(-width/2,length/2),corner(width/2,length/2))
    -- Image.Render takes multiplicative tint from KColor, not ColorMod's RGB fields.
    entry.image:Render(entry.source,dest,KColor(color.R,color.G,color.B,color.A),Color.Default)
end
local function draw(name,pos,width,height,angle,color)
    local sp=sprites[name]
    if not sp then
        sp=Sprite();sp:Load('gfx/samira/combat/'..name..'.anm2',true);sp:SetFrame('Idle',0)
        -- These two original textures store brightness on an opaque black background.
        if name=='aatrox_base_r_fear_shock' or name=='aatrox_base_q_hit_burst' then sp:GetLayer(0):GetBlendMode():SetMode(BlendType.ADDITIVE) end
        sprites[name]=sp
    end
    local size=sizes[name];sp.Scale=Vector(width/size[1],height/size[2]);sp.Rotation=angle or 0;sp.Color=color or Color.Default;sp:Render(pos)
end
local function chain(a,b,alpha)
    local delta=b-a;local length=delta:Length();if length<1 then return end
    -- Tile the existing chain texture, instead of stretching one glowing core into a missile.
    local count=math.ceil(length/24)
    for i=1,count do
        local start=(i-1)/count;local finish=i/count
        draw('aatrox_base_w_chain_beam',a+delta*((start+finish)*.5),8,length/count+1,delta:GetAngleDegrees()-90,Color(1,.8,.7,alpha))
    end
end
function V.impact(fx,shape)
    local age=fx.age;local alpha=math.max(0,1-age/19)
    local distance=shape.kind=='circle' and shape.cx or shape.far
    local width=fx.stage and (shape.radius or shape.width)*2 or 38
    local center=fx.origin+G.project(fx.face*distance)
    if age<7 then
        draw('aatrox_base_q_hit_burst',Isaac.WorldToScreen(center),width*(.8+age*.07),30+age*4,fx.face:GetAngleDegrees()-90,Color(1,.38,.08,1-age/7))
    end
    if not fx.stage then return end
    -- Ground fractures persist after the bright contact flash, without leaving the aiming overlay.
    local side=Vector(-fx.face.Y,fx.face.X)
    if fx.stage==3 then
        if age<10 then ring(center,shape.radius*(.55+age*.045),.7*(1-age/10),{1,.26,.045}) end
        for i=0,7 do
            local direction=Vector(1,0):Rotated(i*45)
            local a=center+G.project(direction*shape.inner*.3)
            local b=center+G.project(direction*shape.radius*.85)
            line(Isaac.WorldToScreen(a),Isaac.WorldToScreen(b),1.3,Color(.35,.035,.01,alpha*.8))
        end
    else
        local previous
        for i=0,8 do
            local u=i/8
            local point=fx.stage==1 and (fx.face*(shape.near+(shape.far-shape.near)*u)+side*(math.sin(i*2.3)*5))
                or (fx.face*(shape.far-10*math.abs(2*u-1))+side*((2*u-1)*shape.width))
            local pos=Isaac.WorldToScreen(fx.origin+G.project(point))
            if previous then line(previous,pos,2,Color(.38,.035,.012,alpha)) end
            previous=pos
        end
    end
    if age<11 then
        for i=1,fx.stage==3 and 10 or 6 do
            local dir=Vector(1,0):Rotated(i*137.5+fx.face:GetAngleDegrees())
            local start=center+G.project(side*(math.sin(i*3.1)*width*.35))
            local pos=Isaac.WorldToScreen(start+G.project(dir*age*(1.1+i%3*.4)))-Vector(0,math.sin(age/11*math.pi)*(7+i%3*3))
            line(pos,pos-dir*(2+alpha*3),1.2,Color(1,.42,.1,1-age/11))
        end
    end
end
function V.indicator(origin,face,shape,stage,alpha,cast,progress,mode)
    if mode=='off' then return end
    progress=progress or 0
    local forward,width,height
    if shape.kind=='circle' then forward=shape.cx;width=shape.radius*2;height=width
    else forward=(shape.near+shape.far)/2;width=shape.width*2;height=shape.far-shape.near end
    ground('aatrox_base_q_indicator_0'..stage,origin,face,width,height,forward,
        cast and Color(.7+progress*.3,.12+progress*.16,.025,alpha*(.5+progress*.5)) or Color(.1,.75,1,alpha))
    if cast and stage<3 then
        ground('aatrox_base_q_indicator_sweetspot_0'..stage,origin,face,shape.width*2,shape.far-shape.sweet,(shape.far+shape.sweet)/2,Color(1,.42+progress*.3,.14,alpha*(.3+progress*.7)))
    end
    if mode~='debug' then return end
    -- Optional debug geometry follows the authoritative hit area.
    outline(origin,face,shape,false,cast and Color(1,.4,.1,alpha) or Color(.1,.75,1,alpha))
    outline(origin,face,shape,true,cast and Color(1,.75,.4,alpha) or Color(.4,.9,1,alpha*.8))
end
function V.hit(s,pos,strong)
    s.hitFX=s.hitFX or {}
    if #s.hitFX>=16 then table.remove(s.hitFX,1) end
    s.hitFX[#s.hitFX+1]={position=Vector(pos.X,pos.Y),at=s.clock,strong=strong}
end
function V.update(s)
    for i=#(s.hitFX or {}),1,-1 do if s.clock-s.hitFX[i].at>=60 then table.remove(s.hitFX,i) end end
end
function V.hits(s)
    for _,fx in ipairs(s.hitFX or {}) do
        local age=s.clock-fx.at;local alpha=math.max(0,1-age/12)
        local center=Isaac.WorldToScreen(fx.position)-Vector(0,12)
        local size=fx.strong and 42 or 25
        draw('aatrox_base_q_hit_burst',center,size*(1+age*.03),size*.7,-35,Color(1,.3,.065,alpha))
        if age<3 then line(center-Vector(7,10),center+Vector(7,10),fx.strong and 3 or 1.5,Color(1,.8,.46,1-age/3)) end
        for i=1,fx.strong and 8 or 4 do
            local direction=Vector(1,0):Rotated(i*137.5)
            local tip=center+direction*(5+age*(fx.strong and 2.5 or 1.5))-Vector(0,age*.5)
            line(tip,tip-direction*(2+alpha*4),1,Color(1,.28+i%2*.3,.08,alpha))
        end
    end
end
function V.abilities(p,s)
    if s.wBolt then
        local bolt=s.wBolt;local a=Isaac.WorldToScreen(bolt.origin);local b=Isaac.WorldToScreen(bolt.position)
        chain(a,b,1)
        draw('aatrox_base_w_mis_core',b,9,9,0,Color(1,.65,.35,.9))
    end
    local c=s.wChain
    if c and c.target:Exists() then
        local a=Isaac.WorldToScreen(c.anchor-G.project(c.face*12));local b=Isaac.WorldToScreen(c.target.Position)-Vector(0,12)
        if s.indicators~='off' then local shape=G.wShape();ground('aatrox_base_w_indicator',c.anchor,c.face,shape.width*2,shape.far-shape.near,0,Color(1,.2,.1,.9)) end
        chain(a,b,c.pulled and 1 or .85)
    end
    local rAge=s.rStartedAt and s.clock-s.rStartedAt
    if rAge and rAge<24 then
        local n=rAge/24;draw('aatrox_base_r_fear_shock',Isaac.WorldToScreen(p.Position),80+n*180,(80+n*180)*G.groundScale,0,Color(1,.075,.025,1-n))
        for i=1,10 do
            local angle=i*36;local groundPos=p.Position+G.project(Vector(18+n*38,0):Rotated(angle))
            local pos=Isaac.WorldToScreen(groundPos)-Vector(0,n*48)
            line(pos,pos+Vector(0,5+n*9),1.8,Color(1,.12,.025,(1-n)*.8))
        end
    end
    if (s.rUntil or 0)>s.clock and rAge and rAge>=0 and rAge<45 then
        local opacity=.10+.035*math.sin(s.clock*.16)
        draw('aatrox_base_r_fear_shock',Isaac.WorldToScreen(p.Position),65,54,0,Color(1,.07,.015,opacity))
    end
end
function V.screen(s)
    if not s.rStartedAt or (s.rUntil or 0)<=s.clock then return end
    local age=s.clock-s.rStartedAt
    local strength=(.055+.18*math.exp(-age/15))*math.min(1,age/3)*math.min(1,(s.rUntil-s.clock)/24)
    local w,h=Isaac.GetScreenWidth(),Isaac.GetScreenHeight()
    -- Soft peripheral tint; the center and HUD stay readable. No hit-stop or gameplay timer changes.
    for i=0,15 do
        local alpha=strength*(1-i/16)^2;local color=Color(.65,.015,.005,alpha)
        local vy=h*.16/16;local vx=w*.12/16
        line(Vector(0,(i+.5)*vy),Vector(w,(i+.5)*vy),vy+1,color)
        line(Vector(0,h-(i+.5)*vy),Vector(w,h-(i+.5)*vy),vy+1,color)
        line(Vector((i+.5)*vx,0),Vector((i+.5)*vx,h),vx+1,color)
        line(Vector(w-(i+.5)*vx,0),Vector(w-(i+.5)*vx,h),vx+1,color)
    end
end
local marker
function V.click(s)
    local click=s.click;if not click then return end
    local age=s.clock-click.at;if age>=28 then s.click=nil;return end
    if not marker then marker=Sprite();marker:Load('gfx/samira/pixel.anm2',true);marker:SetFrame('Idle',0) end
    local alpha=math.min(1,(28-age)/10);local radius=4+12*(1-math.min(1,age/20))^2
    marker.Color=click.enemy and Color(1,.22,.12,alpha) or Color(.2,1,.45,alpha)
    local function segment(a,b)
        a=Isaac.WorldToScreen(click.position+G.project(a));b=Isaac.WorldToScreen(click.position+G.project(b))
        local d=b-a;marker.Scale=Vector(d:Length(),1.5);marker.Rotation=d:GetAngleDegrees();marker:Render(a)
    end
    for angle=45,315,90 do
        local tip=Vector(radius,0):Rotated(angle)
        segment(tip,Vector(radius+5,-4):Rotated(angle));segment(tip,Vector(radius+5,4):Rotated(angle))
    end
end
function V.cursor(pos,enemy)
    -- Cursor atlases are square; keep the transparent margin and authored ratio.
    local name=enemy and 'hoverenemy' or 'hand1';local size=sizes[name]
    draw(name,pos,17,17*size[2]/size[1],0,Color.Default)
end
return V
