-- Opt-in real mesh experiment: two skeletal clips, continuous yaw and a local-pose blend.
-- Skills and ultimate still use the proven sprite path; gameplay remains entirely 2D.
local P={enabled=false};local Rig=include('scripts.samira_skeleton')
local Q=include('scripts.samira_quads');local G=include('scripts.samira_geometry')
local data,images,sources,surface,sourceRect;local lastTime,lastPaint,yaw,blend,idleTime,walkTime
local frames,total,slow=0,0,0
local step='idle'
local function log(s)Isaac.DebugString('[Samira renderer] '..s);Isaac.ConsoleOutput(s..'\n')end
local function resetClock()lastTime=nil;lastPaint=nil;yaw=nil;blend=0;idleTime=0;walkTime=0 end
function P.toggle(on)
    if on and (not Renderer or not Renderer.CreateImage or not Renderer.RenderToImage or not Renderer.LoadImage or not SourceQuad or not DestinationQuad) then
        log('Renderer API unavailable; keeping sprites.');P.enabled=false;return
    end
    P.enabled=on;frames=0;total=0;slow=0;resetClock()
    log(on and 'Skeletal probe ON: live bones, idle/walk blending and continuous turning. Skills use sprites. samira render off to restore all sprites.' or 'Skeletal probe OFF; sprites restored.')
end
local function initialize()
    if surface then return end
    step='load skeleton';data=Rig.data();images={};sources={}
    step='load materials';for i=1,3 do images[i]=Renderer.LoadImage('gfx/samira/probe/material'..i..'.png') end
    step='validate skeleton arrays'
    assert(type(data)=='table' and type(data.vertices)=='table' and type(data.faces)=='table','missing skeleton vertices/faces')
    log('Mesh data: '..#data.vertices..' vertices; '..#data.faces..' faces')
    for i,f in ipairs(data.faces) do
        step='read triangle '..i
        local a,b,c=data.vertices[f[1]],data.vertices[f[2]],data.vertices[f[3]]
        assert(a and b and c,'invalid vertex indices in face '..i)
        if i==1 then
            step='source factory';local q=SourceQuad.NewFromRectangle(Vector.Zero,1,1,true)
            step='source SetTopLeft';q:SetTopLeft(Vector(a[4],a[5]))
            step='source SetTopRight';q:SetTopRight(Vector(b[4],b[5]))
            step='source SetBottomLeft';q:SetBottomLeft(Vector(c[4],c[5]))
            step='source SetBottomRight';q:SetBottomRight(Vector(c[4],c[5]))
            sources[i]=q
            log('First source quad and all corner setters OK')
        else
            step='source quad '..i;sources[i]=Q.source(Vector(a[4],a[5]),Vector(b[4],b[5]),Vector(c[4],c[5]),Vector(c[4],c[5]))
        end
    end
    step='create surface';surface=Renderer.CreateImage(512,512,'Samira live skeleton probe')
    step='create surface rectangle';sourceRect=SourceQuad.NewFromRectangle(Vector.Zero,512,512,false)
end
local function draw(p,s,offset)
    if s.cast or s.dash or (s.rUntil or 0)>s.clock then lastTime=nil;lastPaint=nil;return false end
    initialize()
    step='animation clock';local now=Isaac.GetTime()/1000;local paused=Game():IsPaused()
    local dt=paused and 0 or math.min(.1,math.max(0,now-(lastTime or now)));lastTime=now
    local speed=p.Velocity:Length();local walking=speed>.15
    local face=walking and p.Velocity or s.face
    local targetYaw=math.rad(90-math.deg(math.atan(face.Y/G.groundScale,face.X)))
    if not yaw then yaw=targetYaw end
    local difference=(targetYaw-yaw+math.pi)%(2*math.pi)-math.pi
    yaw=yaw+difference*(1-math.exp(-dt/0.10))
    local target=walking and 1 or 0;blend=blend+math.max(-dt/.18,math.min(dt/.18,target-blend))
    idleTime=idleTime+dt;walkTime=walkTime+dt*math.min(2,speed/2.3)
    if not lastPaint or not paused and now-lastPaint>=1/30-.001 then
        local start=Isaac.GetTime();local cs,sn=math.cos(yaw),math.sin(yaw)
        local ce,se=math.cos(math.rad(35)),math.sin(math.rad(35));local vertices={};local ordered={}
        step='skin vertices';local pose=Rig.vertices(idleTime,walkTime,blend)
        for i,v in ipairs(pose) do
            local x=v[1]*cs+v[3]*sn;local z=-v[1]*sn+v[3]*cs
            vertices[i]={x=256+x*92.16,y=371-(v[2]*ce-z*se)*92.16,depth=v[2]*se+z*ce}
        end
        -- All three source GLB materials are single-sided. Y-down projection reverses
        -- their CCW winding; discard back faces before sorting or crossing the Lua/C API.
        for i,f in ipairs(data.faces) do
            local a,b,c=vertices[f[1]],vertices[f[2]],vertices[f[3]]
            if (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)<-.0001 then
                ordered[#ordered+1]={index=i,depth=(a.depth+b.depth+c.depth)/3}
                for _,v in ipairs({a,b,c}) do if not v.pos then v.pos=Vector(v.x,v.y) end end
            end
        end
        table.sort(ordered,function(a,b)if a.depth==b.depth then return a.index<b.index end;return a.depth<b.depth end)
        step='render to surface';Renderer.RenderToImage(surface,function(controller)
            step='clear surface';controller:Clear();local white=KColor(1,1,1,1)
            step='draw textured triangles'
            for _,entry in ipairs(ordered) do
                local f=data.faces[entry.index];local a,b,c=vertices[f[1]].pos,vertices[f[2]].pos,vertices[f[3]].pos
                images[f[4]]:Render(sources[entry.index],DestinationQuad(a,b,c,c),white,Color.Default)
            end
        end)
        lastPaint=now;frames=frames+1;local ms=Isaac.GetTime()-start;total=total+ms;slow=ms>30 and slow+1 or 0
        if frames<=5 or frames%60==0 then log(string.format('skeletal updates=%d; CPU avg=%.2fms; latest=%.2fms; blend=%.2f; visible=%d/%d; GPU excluded',frames,total/frames,ms,blend,#ordered,#data.faces)) end
        if slow>=5 then P.toggle(false);log('Five slow updates: restored sprites.');return false end
    end
    step='draw surface';local origin=Isaac.WorldToRenderPosition(p.Position)+offset-Vector(64,92.75)
    surface:Render(sourceRect,DestinationQuad.NewFromRectangle(origin,128,128),KColor(1,1,1,1),Color.Default);return true
end
function P.draw(p,s,offset)
    if not P.enabled then return false end
    local ok,result=xpcall(function()return draw(p,s,offset)end,function(err)
        local message='['..step..'] '..tostring(err)
        return debug and debug.traceback and debug.traceback(message,2) or message
    end)
    if not ok then P.enabled=false;surface=nil;resetClock();log('Skeletal probe disabled: '..tostring(result));return false end
    return result
end
return P
