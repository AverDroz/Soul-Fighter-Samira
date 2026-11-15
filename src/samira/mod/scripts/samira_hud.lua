local Health=include('scripts.samira_health')
local E=include('scripts.samira_equipment')
local P=include('scripts.samira_progression')
local Passive=include('scripts.samira_passive')
local nativeIcons=include('scripts.samira_native_icons')
local portrait=include('scripts.samira_portrait_layout')
local H={};local sprites={};local font
local function sprite(name)
    if not sprites[name] then local s=Sprite();s:Load('gfx/samira/hud/'..name..'.anm2',true);s:SetFrame(name=='heart_buffs' and 'RedHeartFull' or 'Idle',0);sprites[name]=s end
    return sprites[name]
end
function H.layout(w,h)
    return {left={x=6,y=math.floor(h)-51,w=154,h=47},right={x=math.floor(w)-122,y=math.floor(h)-36,w=122,h=36}}
end
function H.contains(pos,w,h)
    local l=H.layout(w,h)
    if pos.X>=l.left.x+10 and pos.X<=l.left.x+28 and pos.Y>=l.left.y-19 and pos.Y<=l.left.y-1 then return true end
    for _,r in ipairs({l.left,l.right}) do
        if pos.X>=r.x and pos.X<=r.x+r.w and pos.Y>=r.y and pos.Y<=r.y+r.h then return true end
    end
    return false
end
function H.upgradeAt(p,pos,w,h)
    local l=H.layout(w,h).left
    for i,key in ipairs({'q','w','e','r'}) do
        local x=l.x+49+(i-1)*27;local y=l.y-11
        if pos.X>=x and pos.X<=x+10 and pos.Y>=y and pos.Y<=y+9 and P.canUpgrade(p,key) then return key end
    end
end
function H.health(p)
    local h=Health.state(p)
    return h.hp,h.soul,math.max(1,Health.max(p)+h.soul)
end
function H.healthNumbers(p)
    local maximum=math.floor(Health.max(p)+.5)
    return math.min(maximum,math.ceil(Health.current(p))),maximum
end
function H.draw(p,s,st)
    if not font then font=Font();font:Load('font/luaminioutlined.fnt') end
    for _,f in ipairs(s.goldFX or {}) do
        local age=s.clock-f.at
        if age>=0 and age<42 then
            local pos=Isaac.WorldToScreen(f.position);local label='+'..f.amount;local lane=f.lane or 0
            font:DrawStringScaledUTF8(label,pos.X-font:GetStringWidthUTF8(label)/2+({0,-12,12,0})[lane%4+1],pos.Y-22-age*.7-lane*9,1,1,KColor(1,.82,.24,math.min(1,(42-age)/12)))
        end
    end
    local l=H.layout(Isaac.GetScreenWidth(),Isaac.GetScreenHeight())
    local gold=Color(.55,.43,.23,1);local dark=Color(.025,.045,.055,.92)
    local function rect(x,y,w,h,color)
        if w<=0 or h<=0 then return end
        local sp=sprite('pixel');sp.Color=color;sp.Scale=Vector(w,h);sp:Render(Vector(x,y))
    end
    local function panel(x,y,w,h)
        rect(x,y,w,h,gold);rect(x+1,y+1,w-2,h-2,dark)
    end
    local function icon(name,x,y,size,sourceSize)
        local sp=sprite(name);sp.Color=Color.Default;sp.Scale=Vector(size/sourceSize,size/sourceSize);sp:Render(Vector(x,y))
    end
    local function text(str,x,y,color)
        font:DrawStringScaledUTF8(str,math.floor(x),math.floor(y),1,1,color or KColor(.94,.89,.75,1))
    end
    local x,y=l.left.x,l.left.y
    panel(x+38,y,116,47)
    local k=38/portrait.frame[3];local a=portrait.arc
    icon('experience_background',x+a[1]*k,y+3+a[2]*k,a[3]*k,48)
    local progress=P.state(p);local xp=progress.level==18 and 1 or progress.xp/P.required(progress.level)
    local arc=sprite('experience_arc');arc:SetFrame('Idle',math.floor(math.max(0,math.min(1,xp))*100+.5))
    arc.Color=Color.Default;arc.Scale=Vector(k,k);arc:Render(Vector(x+a[1]*k,y+3+a[2]*k))
    local pr=portrait.portrait
    icon('portrait_round',x+pr[1]*k,y+3+pr[2]*k,pr[3]*k,128)
    icon('portrait_frame',x,y+3,38,portrait.frame[3])
    local level=tostring(progress.level)
    local lr=portrait.level
    font:DrawStringScaledUTF8(level,x+(lr[1]+lr[3]/2)*k-font:GetStringWidthUTF8(level)*.3,y+3+(lr[2]+lr[4]/2)*k-3,.6,.6,KColor(1,.91,.64,1))
    panel(x+10,y-19,18,18);icon('passive',x+11,y-18,16,64)
    local passiveCD=Passive.remaining(p)
    if passiveCD>0 then
        rect(x+11,y-18,16,16*passiveCD/Passive.total(p),Color(0,0,0,.7))
        text(tostring(math.ceil(passiveCD/30)),x+14,y-16,KColor(1,1,1,1))
    end
    local buffX=x+42;local canUpgrade=false
    for _,key in ipairs({'q','w','e','r'}) do canUpgrade=canUpgrade or P.canUpgrade(p,key) end
    local buffY=y-(canUpgrade and 25 or 13)
    for _,entry in ipairs({{'WhiteHeartHalf','GetEternalHearts'},{'GoldHeartOverlay','GetGoldenHearts'},{'BoneHeartEmpty','GetBoneHearts'},{'RottenHeartFull','GetRottenHearts'},{'BrokenHeart','GetBrokenHearts'}}) do
        local count=p[entry[2]] and p[entry[2]](p) or 0
        if count>0 then
            panel(buffX-1,buffY-1,12,12)
            local sp=sprite('heart_buffs');sp:SetFrame(entry[1],0);sp.Scale=Vector(.5,.5);sp.Color=Color.Default;sp:Render(Vector(buffX,buffY))
            if count>1 then text(tostring(count),buffX+7,buffY+4) end
            buffX=buffX+13
        end
    end
    for i,name in ipairs({'q','w','e','r'}) do
        local ix=x+42+(i-1)*27;local iy=y+4
        panel(ix-1,iy-1,26,26);icon(name,ix,iy,24,64)
        local rank=P.rank(p,name)
        local cd=math.max(0,(s[name..'Ready'] or 0)-s.clock)/30
        if rank==0 then
            rect(ix,iy,24,24,Color(0,0,0,.72))
        elseif name=='r' and (s.rUntil or 0)>s.clock then
            rect(ix,iy+22,math.floor(24*math.min(1,(s.rUntil-s.clock)/300)),2,Color(.95,.15,.08,1))
        elseif cd>0 then
            local total=name=='q' and s.chainUntil and 1 or E.cooldown(p,P.cooldown(p,name),name=='r')/30
            rect(ix,iy,24,math.ceil(24*math.min(1,cd/total)),Color(0,0,0,.7))
            local label=tostring(math.ceil(cd));text(label,ix+12-#label*2,iy+4,KColor(1,1,1,1))
        end
        text(name:upper(),ix+10,y+23)
        local maximum=name=='r' and 3 or 5
        for n=1,maximum do rect(ix+2+(5-maximum)*2+(n-1)*4,y+30,3,2,n<=rank and gold or Color(.12,.14,.14,1)) end
        if P.canUpgrade(p,name) then panel(ix+7,y-11,10,9);text('+',ix+9,y-13,KColor(1,.86,.42,1)) end
    end
    local red,soul,cap=H.health(p);local width=105
    rect(x+42,y+35,width,8,Color(.08,.1,.1,1))
    local redWidth=math.floor(width*red/cap);local soulWidth=math.floor(width*soul/cap)
    rect(x+42,y+35,redWidth,8,Color(.12,.78,.25,1))
    rect(x+42+redWidth,y+35,soulWidth,8,Color(.9,.94,.96,1))
    local current,maximum=H.healthNumbers(p);local label=current..' / '..maximum
    font:DrawStringScaledUTF8(label,math.floor(x+42+(width-#label*4.5)/2),y+34,.75,.75,KColor(1,1,1,1))
    x,y=l.right.x+46,l.right.y;panel(x,y,76,36)
    local gear=E.state(p)
    for i,key in ipairs(E.keys) do
        local ix=x+4+(i-1)%3*17;local iy=y+3+math.floor((i-1)/3)*17
        panel(ix,iy,16,16);local slot=gear.slots[i]
        if slot.id<0 and nativeIcons[-slot.id] then
            local sp=sprite('native_items');sp:SetFrame('Idle',nativeIcons[-slot.id]);sp.Scale=Vector(14/32,14/32);sp.Color=Color.Default;sp:Render(Vector(ix+1,iy+1))
        elseif E.items[slot.id] then icon('item_'..slot.id,ix+1,iy+1,14,E.items[slot.id].iconSize or 64) end
        text(tostring(key),ix+1,iy-2,KColor(.85,.82,.68,1))
        if slot.ready>gear.time then text(tostring(math.ceil((slot.ready-gear.time)/30)),ix+4,iy+4) end
    end
    panel(x+55,y+3,18,16);panel(x+55,y+20,18,15)
    text('4',x+59,y+3)
    local bomb=sprites.nativeBomb
    if not bomb then bomb=Sprite();bomb:Load('gfx/ui/hudpickups.anm2',true);sprites.nativeBomb=bomb end
    bomb:SetFrame('Idle',2);bomb.Scale=Vector(11/16,11/16);bomb.Color=Color.Default;bomb:Render(Vector(x+60,y+22))
    text('G',x+59,y+19);panel(x-46,y+24,46,12);text('$ '..gear.gold,x-41,y+24,KColor(1,.82,.3,1))
end
function H.overhead(p,s,progress)
    if p:IsDead() then return end
    if not font then font=Font();font:Load('font/luaminioutlined.fnt') end
    local position=Isaac.WorldToScreen(p.Position)
    local x=math.floor(math.max(13,math.min(Isaac.GetScreenWidth()-46,position.X-19)))
    local y=math.floor(math.max(15,position.Y-((s.rUntil or 0)>s.clock and 78 or 68)))
    local function rect(rx,ry,w,h,color)
        if w<=0 then return end
        local sp=sprite('pixel');sp.Color=color;sp.Scale=Vector(w,h);sp:Render(Vector(rx,ry))
    end
    local red,soul,cap=H.health(p);local current,maximum=H.healthNumbers(p)
    local ratio=(red+soul)/cap;local width=42
    local lag=s.healthLag
    if not lag then lag={value=ratio,from=ratio,at=s.clock};s.healthLag=lag end
    if lag.value~=ratio then lag.from=ratio<lag.value and lag.value or ratio;lag.value=ratio;lag.at=s.clock end
    local trailing=ratio+(lag.from-ratio)*(1-math.min(1,math.max(0,(s.clock-lag.at-4)/15)))
    rect(x-11,y-2,56,12,Color(.015,.02,.025,1))
    rect(x-10,y-1,9,10,Color(.13,.17,.19,1))
    rect(x,y-1,44,9,Color(.35,.37,.31,1));rect(x+1,y,42,7,Color(.06,.075,.06,1))
    rect(x+1,y,math.floor(width*trailing),7,Color(.85,.62,.13,1))
    local rw=math.floor(width*red/cap)
    rect(x+1,y,rw,7,Color(.13,.68,.21,1));rect(x+1,y,rw,2,Color(.42,.91,.36,1))
    rect(x+1+rw,y,math.floor(width*soul/cap),7,Color(.9,.94,.96,1))
    -- Hundred-HP subdivisions remain readable as native heart capacity grows.
    for hp=100,maximum-1,100 do
        local tx=x+1+math.floor(width*hp/maximum)
        rect(tx,y,1,hp%1000==0 and 7 or 3,Color(.015,.06,.025,.8))
    end
    rect(x+1,y+8,42,1,Color(.1,.15,.19,1))
    local nextXP=P.required(progress.level)
    rect(x+1,y+8,math.floor(42*(progress.level==18 and 1 or progress.xp/nextXP)),1,Color(.25,.7,.9,1))
    local level=tostring(progress.level)
    font:DrawStringScaledUTF8(level,math.floor(x-5.5-font:GetStringWidthUTF8(level)*.35),y-1,.7,.7,KColor(1,.93,.7,1))
    local label=current..'/'..maximum
    font:DrawStringScaledUTF8(label,math.floor(x+22-font:GetStringWidthUTF8(label)*.3),y,.6,.6,KColor(.92,.96,.9,1))
end
return H
