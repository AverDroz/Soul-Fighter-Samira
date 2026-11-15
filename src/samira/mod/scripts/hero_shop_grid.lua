-- Lua owns scroll positions, visible cells and click targets for any catalog size.
local G={top=34,bottom=309,columns=7,rowHeight=39}
function G.layout(catalog,offset)
    local groups={{},{},{}};local all,sections={},{}
    for _,item in ipairs(catalog) do if item.buyable then
        local group=#(item.components or {})==0 and 1 or item.price<50 and 2 or 3
        groups[group][#groups[group]+1]=item
    end end
    local y=36
    for group,items in ipairs(groups) do if #items>0 then
        sections[#sections+1]={group=group,y=y}
        for n,item in ipairs(items) do
            all[#all+1]={id=item.id,x=22+(n-1)%G.columns*40,y=y+14+math.floor((n-1)/G.columns)*G.rowHeight}
        end
        y=y+13+math.max(2,math.ceil(#items/G.columns))*G.rowHeight
    end end
    local last=all[#all];local maximum=math.max(0,(last and last.y+36 or G.bottom)-G.bottom)
    offset=math.max(0,math.min(maximum,tonumber(offset) or 0))
    local cells,visibleSections={},{}
    for _,cell in ipairs(all) do
        cell.y=cell.y-offset
        if cell.y-2>=G.top and cell.y+36<=G.bottom then cells[#cells+1]=cell end
    end
    for _,section in ipairs(sections) do
        section.y=section.y-offset
        if section.y>=G.top and section.y+10<=G.bottom then visibleSections[#visibleSections+1]=section end
    end
    return {cells=cells,sections=visibleSections,offset=offset,maximum=maximum,top=G.top,bottom=G.bottom,total=#all}
end
function G.scroll(catalog,offset,delta)
    local view=G.layout(catalog,offset)
    return math.max(0,math.min(view.maximum,view.offset-(tonumber(delta) or 0)*G.rowHeight))
end
return G
