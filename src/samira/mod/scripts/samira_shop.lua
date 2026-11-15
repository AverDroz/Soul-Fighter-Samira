-- Shop input, inventory transactions and modal input capture.
local E=include('scripts.samira_equipment')
local Audio=include('scripts.samira_audio')
local Grid=include('scripts.hero_shop_grid')
local S={catalog=include('scripts.samira_shop_catalog')}
S.filters={'推荐','全部','攻击','法术','防御','移动','消耗'}
local recommended={[1055]=true,[1001]=true,[1036]=true,[1028]=true,[1042]=true,[3071]=true,[2501]=true,[6333]=true,[6610]=true,[3161]=true}
function S.layout(w,h)
    local scale=math.min(1,(w-24)/540,(h-24)/370)
    return {x=(w-540*scale)/2,y=(h-370*scale)/2,w=540*scale,h=370*scale,scale=scale}
end
function S.items(filter)
    local out={}
    for i,item in ipairs(S.catalog) do
        if item.buyable then out[#out+1]=item.id end
    end
    return out
end
function S.upgrades(id)
    local out={}
    for _,item in ipairs(S.catalog) do if item.buyable then
        for _,child in ipairs(item.components) do if child==id then out[#out+1]=item.id;break end end
    end end
    return out
end
function S.grid(offset)return Grid.layout(S.catalog,offset).cells end
function S.selected(s)
    if s.shopSelected and E.items[s.shopSelected] then return s.shopSelected end
    for _,item in ipairs(S.catalog) do if item.buyable then return item.id end end
    return 0
end
function S.wheel(s,mouse,w,h,player,delta)
    if not s.shopOpen or delta==0 then return end
    local l=S.layout(w,h);local x,y=(mouse.X-l.x)/l.scale,(mouse.Y-l.y)/l.scale
    if x>=16 and x<316 and y>=Grid.top and y<Grid.bottom then
        s.shopScroll=Grid.scroll(S.catalog,s.shopScroll,delta)
    elseif x>=330 and x<523 and y>=30 and y<72 then
        local maximum=math.max(0,#S.upgrades(S.selected(s))-6)
        s.shopUpgradeScroll=math.max(0,math.min(maximum,(s.shopUpgradeScroll or 0)-delta))
    end
end
function S.tree(id,offset)
    local out={};local upgrades=S.upgrades(id)
    offset=math.max(0,math.min(math.max(0,#upgrades-6),offset or 0));local count=math.min(6,#upgrades)
    for i=1,count do out[#out+1]={id=upgrades[offset+i],x=424+(i-(count+1)/2)*27-10,y=40,size=20} end
    out[#out+1]={id=id,x=408,y=77,size=32,selected=true}
    local children=E.items[id] and E.items[id].components or {}
    for i,child in ipairs(children) do out[#out+1]={id=child,x=424+(i-(#children+1)/2)*math.min(58,160/math.max(1,#children-1))-12,y=134,size=24,component=true} end
    return out
end
local function inside(p,x,y,w,h)return p.X>=x and p.Y>=y and p.X<x+w and p.Y<y+h end
function S.update(s,mouse,w,h,available,player,room)
    local wasOpen=s.shopOpen
    local pad=player and (player.ControllerIndex or 0)>0
    local p=pad and Input.IsButtonPressed(14,player.ControllerIndex) and not Input.IsButtonPressed(10,player.ControllerIndex) or not pad and Input.IsButtonPressed(Keyboard.KEY_P,0)
    local escape=Input.IsButtonPressed(Keyboard.KEY_ESCAPE,0) or pad and Input.IsButtonPressed(5,player.ControllerIndex)
    local click=pad and Input.IsButtonPressed(4,player.ControllerIndex) or not pad and Input.IsMouseBtnPressed(0)
    s.shopEscape=escape and (s.shopOpen or s.shopEscape) or false
    s.shopAllowed=available==true
    if player then
        if not room or not room:IsClear() then E.clearUndo(player) else E.canUndo(player) end
    end
    if not available then S.close(s);s.shopKey=p;s.shopClick=click;return false end
    if p and not s.shopKey then s.shopOpen=not s.shopOpen end
    s.shopKey=p
    if escape then s.shopOpen=false end
    if click and not s.shopClick then
        if s.shopOpen then Audio.play('ui_click',false,.55) end
        if not s.shopOpen then
            if inside(mouse,w-122,h-12,46,12) then s.shopOpen=true end
        else
            local l=S.layout(w,h);local pos=Vector((mouse.X-l.x)/l.scale,(mouse.Y-l.y)/l.scale)
            if inside(pos,514,9,16,16) then s.shopOpen=false end
            if inside(pos,306,Grid.top,10,Grid.bottom-Grid.top) then
                local view=Grid.layout(S.catalog,s.shopScroll);s.shopScroll=view.maximum*math.max(0,math.min(1,(pos.Y-Grid.top)/(Grid.bottom-Grid.top)))
            end
            local tree=S.tree(S.selected(s),s.shopUpgradeScroll)
            for _,node in ipairs(tree) do
                if inside(pos,node.x,node.y,node.size,node.size) then s.shopSelected=node.id;s.shopSelling=nil;s.shopDetailPage=0;s.shopUpgradeScroll=0;break end
            end
            for _,cell in ipairs(S.grid(s.shopScroll)) do
                if inside(pos,cell.x-2,cell.y-2,32,38) then s.shopSelected=cell.id;s.shopSelling=nil;s.shopDetailPage=0;s.shopUpgradeScroll=0;break end
            end
            if inside(pos,485,307,16,14) then s.shopDetailPage=math.max(0,(s.shopDetailPage or 0)-1) end
            if inside(pos,504,307,16,14) then s.shopDetailPage=(s.shopDetailPage or 0)+1 end
            local allowed=room and room.IsClear and room:IsClear()
            for i=1,6 do
                if inside(pos,18+(i-1)*25,334,23,23) and E.state(player).slots[i].id~=0 then
                    s.shopSelling=i;s.shopSelected=E.state(player).slots[i].id;s.shopDetailPage=0
                end
            end
            if inside(pos,400,334,120,24) then s.shopChanged,s.shopMessage=E.buy(player,S.selected(s),allowed);s.shopMessageAt=s.clock;Audio.play(s.shopChanged and 'ui_buy' or 'ui_error',false,.65) end
            if inside(pos,236,334,68,24) then s.shopChanged,s.shopMessage=E.sell(player,s.shopSelling,allowed);s.shopMessageAt=s.clock;s.shopSelling=nil;Audio.play(s.shopChanged and 'ui_sell' or 'ui_error',false,.65) end
            if inside(pos,313,334,78,24) then s.shopChanged,s.shopMessage=E.undo(player,allowed);s.shopMessageAt=s.clock;s.shopSelling=nil;Audio.play(s.shopChanged and 'ui_buy' or 'ui_error',false,.65) end
        end
    end
    s.shopClick=click
    if (not not wasOpen)~=(not not s.shopOpen) then Audio.play(s.shopOpen and 'ui_open' or 'ui_close',false,.65) end
    if s.shopOpen then s.goal=nil;s.target=nil;s.path=nil;s.exitIntent=nil;s.emote=nil end
    return s.shopOpen
end
function S.close(s)s.shopOpen=false;s.shopEscape=false end
function S.payload(s,w,h,player,room)
    if not s.shopOpen then return end
    local items=S.items(s.shopFilter or 1)
    local selected=S.selected(s);local quote,reason=E.quote(player,selected)
    local view=Grid.layout(S.catalog,s.shopScroll);s.shopScroll=view.offset
    local allowed=room and room.IsClear and room:IsClear()
    if not allowed then reason='战斗中无法交易' elseif quote and quote.cost>E.state(player).gold then reason='金币不足' end
    return {open=true,layout=S.layout(w,h),selected=selected,items=items,cells=view.cells,sections=view.sections,scroll={offset=view.offset,maximum=view.maximum,top=view.top,bottom=view.bottom,total=view.total},tree=S.tree(selected,s.shopUpgradeScroll),upgradeTotal=#S.upgrades(selected),upgradeOffset=math.min(math.max(0,#S.upgrades(selected)-6),s.shopUpgradeScroll or 0),canUndo=allowed and E.canUndo(player),
        credit=quote and quote.credit or 0,cost=quote and quote.cost or E.items[selected] and E.items[selected].price or 0,canBuy=allowed and quote~=nil and reason==nil,canSell=allowed and s.shopSelling~=nil,selling=s.shopSelling,
        reason=reason,detailPage=s.shopDetailPage or 0,message=s.shopMessageAt and s.clock-s.shopMessageAt<90 and s.shopMessage or nil}
end
return S
