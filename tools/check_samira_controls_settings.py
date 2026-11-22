"""Exercise the REPENTOGON menu, hotkey and per-slot save transitions."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
source = root / "samira_testroom/samira_controls_settings.lua"
if not source.exists():
    source = root / "src/samira-testroom/mod/samira_controls_settings.lua"
sys.path.insert(0, str(root / "work/python-deps"))
sys.path.insert(0, str(root.parent / "upstream/work/python-deps"))
from lupa.lua54 import LuaRuntime

lua = LuaRuntime()
lua.globals().source = source.read_text(encoding="utf-8")
lua.execute(r'''
local records, n = {}, 0
local function copy(x)
    if type(x) ~= 'table' then return x end
    local t={}; for k,v in pairs(x) do t[k]=copy(v) end; return t
end
package.loaded.json={
    encode=function(t) n=n+1; records[n]=copy(t); return tostring(n) end,
    decode=function(s) return copy(assert(records[tonumber(s)],'bad JSON')) end
}
local json=require('json')
ModCallbacks=setmetatable({}, {__index=function(_,k) return k end})
ImGuiElement={MenuItem=1,CollapsingHeader=4}; ImGuiData={Value=1}; ImGuiCallback={Render=10}; Keyboard={KEY_F9=9}
local saves, slot, active, paused, mode, inertia, held={},1,false,false,nil,nil,false
local speed, bagRender
local callbacks, ui, checkbox, done, windowVisible, overlay, writes
Game=function() return {IsPaused=function() return paused end} end
Isaac={IsInGame=function() return active end,DebugString=function() end}
Input={IsButtonPressed=function(k) assert(k==9); return held end}
local mod={
    LoadData=function() return saves[slot] end,
    HasData=function() return saves[slot]~=nil end,
    SaveData=function(_,s) saves[slot]=s; writes=writes+1 end,
    AddCallback=function(_,k,f) callbacks[k]=f end,
}
local function boot()
    callbacks,ui,checkbox,writes={}, {}, {}, 0
    overlay,windowVisible=false,false
    ImGui={
        CreateMenu=function(id,text) ui[id]=text end,
        AddElement=function(parent,id,kind,text) assert(ui[parent] and (kind==1 or kind==4)); ui[id]=text end,
        CreateWindow=function(id,text) ui[id]=text end,
        LinkWindowToElement=function(win,item) assert(ui[win] and ui[item]=='Управление') end,
        AddCheckbox=function(win,id,label,fn,val)
            assert(ui[win] and (label=='Attack-move (A)' or label=='Инерция Isaac'))
            ui[id]=val; checkbox[id]=fn
        end,
        AddCombobox=function(win,id,label,fn,options,index)
            assert(ui[win])
            if id == 'samiraWalkSpeed' then
                assert(label=='Скорость ходьбы' and table.concat(options,',')=='70%,85%,100%')
            else
                assert(id=='samiraHudScale' and label=='Масштаб HUD')
                assert(table.concat(options,',')=='75%,85%,100%,115%,130%,150%')
            end
            ui[id]=index; checkbox[id]=fn
        end,
        AddText=function(win,text,_,id) if id then assert(ui[win]); ui[id]=text end end,
        AddCallback=function(id,kind,fn) assert(id=='samiraBagStats' and kind==10);bagRender=fn end,
        UpdateText=function(id,text) assert(ui[id]);ui[id]=text end,
        AddButton=function(win,id,label,fn) assert(ui[win]); done=fn end,
        SetVisible=function(id,v) assert(ui[id]); windowVisible=v end,
        GetVisible=function(id) assert(ui[id]); return windowVisible end,
        IsVisible=function() return overlay end, Show=function() overlay=true end, Hide=function() overlay=false end,
        UpdateData=function(id,kind,v) assert(ui[id]~=nil and kind==1);ui[id]=v end,
        RemoveElement=function(id) ui[id]=nil end,
    }
    local cfg=assert(load(source))()
    cfg.init(mod,{setAttackMove=function(v) mode=v end,setInertia=function(v) inertia=v end,
        setWalkSpeed=function(v) speed=v end},function() return active end,function(p) return p and '6 слотов' or 'Нет забега' end)
    return cfg
end
local function key(down)
    held=down; callbacks.MC_POST_RENDER()
end
local function toggle(value,id)
    id=id or 'samiraAttackMove'
    ui[id]=value
    checkbox[id](value)
end
local cfg=boot()
assert(ui.samiraBag=='Рюкзак')
bagRender(); assert(ui.samiraBagStats=='Нет забега')
assert(ui.samiraControlsMenu=='Samira' and ui.samiraAttackMove and not ui.samiraInertia)
assert(ui.samiraWalkSpeed==1)
assert(ui.samiraHudScale==2 and cfg.hudScale()==1)
toggle(false); assert(writes==0 and ui.samiraAttackMove,'preview slot write')
toggle(5,'samiraHudScale'); assert(writes==0 and ui.samiraHudScale==2 and cfg.hudScale()==1)
active=true; callbacks.MC_POST_SAVESLOT_LOAD(nil,1,true,1); assert(mode==true and inertia==false)
bagRender(); assert(ui.samiraBagStats=='6 слотов')
assert(speed==85)
saves[1]=json.encode({version=3, seed=123, backpack={77}, otherField='keep'})
callbacks.MC_POST_GAME_STARTED(); assert(writes==0)
key(true); key(true); assert(overlay and windowVisible)
toggle(false); assert(mode==false and writes==1)
toggle(true,'samiraInertia'); assert(mode==false and inertia==true and writes==2)
toggle(0,'samiraWalkSpeed'); assert(speed==70 and inertia)
toggle(2,'samiraWalkSpeed'); assert(speed==100 and inertia and not mode)
toggle(5,'samiraHudScale'); assert(cfg.hudScale()==1.5 and writes==5)
local old=json.decode(saves[1]); assert(old.seed==123 and old.backpack[1]==77 and old.otherField=='keep')
assert(old.samiraHudScale==150)
key(false); key(true); assert(not overlay and not windowVisible)
local fresh={seed=456}; cfg.attachToSave(fresh); assert(fresh.samiraAttackMove==false and fresh.samiraInertia)
assert(fresh.samiraWalkSpeed==100)
assert(fresh.samiraHudScale==150)
saves[1]=json.encode(fresh)
cfg=boot(); assert(mode==false and inertia and ui.samiraInertia and ui.samiraAttackMove==false and writes==0)
assert(speed==100 and ui.samiraWalkSpeed==2)
assert(cfg.hudScale()==1.5 and ui.samiraHudScale==5)
slot=2; callbacks.MC_POST_SAVESLOT_LOAD(nil,2,true,2); assert(mode==true and ui.samiraAttackMove and not inertia)
saves[2]=json.encode({samiraAttackMove=false,samiraWalkSpeed=-3,samiraHudScale='150'})
callbacks.MC_POST_GAME_STARTED(); assert(not mode and not inertia,'invalid defaults for old slot')
assert(speed==85 and ui.samiraWalkSpeed==1)
assert(cfg.hudScale()==1 and ui.samiraHudScale==2)
slot=1; callbacks.MC_POST_SAVESLOT_LOAD(nil,1,true,1); assert(mode==false and inertia)
overlay=true; key(true); done(); assert(overlay and not windowVisible,'pre-existing overlay closed')
saves[1]='broken'; toggle(true); assert(saves[1]=='broken' and mode==false and not ui.samiraAttackMove)
toggle(0,'samiraHudScale'); assert(saves[1]=='broken' and cfg.hudScale()==1.5 and ui.samiraHudScale==5)
callbacks.MC_PRE_MOD_UNLOAD(nil,mod); assert(ui.samiraControlsMenu==nil and ui.samiraControlsWindow==nil)
''')
lua.globals().craft_source = source.with_name('samira_crafting_ui.lua').read_text(encoding='utf-8')
lua.execute(r'''
local piece = {riotId = 1036, name = 'Длинный меч'}
local second = {riotId = 1037, name = 'Кирка'}
local output = {riotId = 3133, name = 'Молот', components = {1036, 1036, 1037}}
local other = {riotId = 3078, name = 'Союз', components = {3133}}
function include(name)
    assert(name == 'samira_items_data')
    return {piece, second, output, other}
end
local text, inputs, options = {}, {}, {}
local owner, inShop, assembled = {GetNumCoins = function() return 9 end}, false, 0
RoomType = {ROOM_SHOP = 2}
Game = function() return {GetRoom = function()
    return {GetType = function() return inShop and RoomType.ROOM_SHOP or 0 end}
end} end
ImGuiData.Options = 2
ImGui = {
    AddElement = function() end,
    AddCombobox = function(_, key, _, run) inputs[key] = run end,
    AddButton = function(_, key, _, run) inputs[key] = run end,
    AddCallback = function(key, _, run) inputs[key] = run end,
    AddText = function() end,
    UpdateText = function(key, value) text[key] = value end,
    UpdateData = function(key, kind, value)
        if kind == ImGuiData.Options then options[key] = value end
    end,
}
local current = owner
assert(load(craft_source))().init('window', function() return current end, {
    recipes = function(p)
        if not p then return {} end
        return {{row = output, missing = assembled == 0 and {1036} or {}, combinePrice = 3},
            {row = other, missing = {3133}, combinePrice = 8}}
    end,
    craft = function(p, id)
        assert(p == owner and id == output.riotId)
        if not inShop then return false, 'room' end
        assembled = assembled + 1
        return true
    end,
})
inputs.samiraCraftInfo()
assert(#options.samiraCraftChoice == 2)
assert(text.samiraCraftInfo:find('2× Длинный меч', 1, true))
assert(text.samiraCraftInfo:find('Не хватает: Длинный меч', 1, true))
inputs.samiraCraftChoice(1)
inputs.samiraCraftInfo()
assert(text.samiraCraftInfo:find('Доплата: 8 мон.', 1, true))
inputs.samiraCraftChoice(0)
inputs.samiraCraftApply()
assert(assembled == 0 and text.samiraCraftFeedback == 'Собирать можно в магазине.')
inShop = true
inputs.samiraCraftApply()
inputs.samiraCraftInfo()
assert(assembled == 1 and text.samiraCraftInfo:find('Все компоненты в рюкзаке.', 1, true))
current = nil
inputs.samiraCraftInfo()
assert(#options.samiraCraftChoice == 1 and options.samiraCraftChoice[1] == 'Нет доступных рецептов')
''')
print("Passed settings, slot saves and the crafting menu.")
