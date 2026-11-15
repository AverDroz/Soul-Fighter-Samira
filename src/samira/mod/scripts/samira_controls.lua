-- Input ownership stays inside Isaac; the renderer only receives cursor/key labels.
local C={};local window='SamiraControls';local menuPlayer
local defaults={mouse={q='Q',w='W',e='E',r='R',attack='A',stop='S'},wasd={q='Q',w='E',e='R',r='C',attack='T',stop='V'}}
local pad={q=8,w=9,e=11,r=12,attack=4,stop=5,item=6,pocket=7,shop=14}
local function keyboardCtrl()
    return Input.IsButtonPressed(Keyboard.KEY_LEFT_CONTROL,0) or Input.IsButtonPressed(Keyboard.KEY_RIGHT_CONTROL,0)
end
function C.reserved(code,mode)
    for _,name in ipairs({'ESCAPE','F10','F','P','SPACE','G','TAB','LEFT_CONTROL','RIGHT_CONTROL','1','2','3','4','5','6','7'}) do
        if code==Keyboard['KEY_'..name] then return true end
    end
    return mode=='wasd' and (code==Keyboard.KEY_W or code==Keyboard.KEY_A or code==Keyboard.KEY_S or code==Keyboard.KEY_D)
end
function C.language()return tostring(Options.Language or 'en'):lower():find('zh',1,true) and 'zh' or 'en' end
function C.text(zh,en)return C.language()=='zh' and zh or en end
function C.state(p)
    local d=p:GetData();if not d.SamiraControls then d.SamiraControls={mode='mouse',bindings={}} end
    return d.SamiraControls
end
function C.restore(p,data)
    p:GetData().SamiraControls={mode=type(data)=='table' and data.mode=='wasd' and 'wasd' or 'mouse',bindings={}}
    if type(data)=='table' and type(data.bindings)=='table' then
        for key in pairs(defaults.mouse) do local v=data.bindings[key];if type(v)=='number' and v>=0 and v<400 then C.state(p).bindings[key]=v end end
    end
end
function C.key(p,key)
    local binding=C.state(p).bindings[key]
    if C.reserved(binding,C.state(p).mode) then binding=nil end
    return binding or Keyboard['KEY_'..defaults[C.state(p).mode][key]]
end
function C.label(p,key)
    if (p.ControllerIndex or 0)>0 then return ({q='LB',w='LT',e='RB',r='RT'})[key] or key end
    local code=C.key(p,key);for name,value in pairs(Keyboard) do if value==code then return name:gsub('KEY_','') end end
    return defaults[C.state(p).mode][key]
end
function C.down(p,key)
    if (p.ControllerIndex or 0)>0 then return Input.IsButtonPressed(pad[key],p.ControllerIndex) end
    return Input.IsButtonPressed(C.key(p,key),0)
end
function C.edge(p,s,key)
    s.controlHeld=s.controlHeld or {};local down=C.down(p,key);local edge=down and not s.controlHeld[key];s.controlHeld[key]=down;return edge
end
function C.raw(p,s,action)
    s.readingControls=true;local value=Input.GetActionValue(action,p.ControllerIndex);s.readingControls=nil;return value
end
function C.movement(p,s)
    local v=Vector.Zero
    if (p.ControllerIndex or 0)>0 then
        v=Vector(C.raw(p,s,ButtonAction.ACTION_RIGHT)-C.raw(p,s,ButtonAction.ACTION_LEFT),C.raw(p,s,ButtonAction.ACTION_DOWN)-C.raw(p,s,ButtonAction.ACTION_UP))
    elseif C.state(p).mode=='wasd' then
        local function n(k)return Input.IsButtonPressed(Keyboard['KEY_'..k],0) and 1 or 0 end
        v=Vector(n('D')-n('A'),n('S')-n('W'))
    end
    local length=v:Length();if length<.18 then return Vector.Zero end
    return length>1 and v:Normalized() or v
end
function C.aim(p,s,mouse)
    if (p.ControllerIndex or 0)==0 then return mouse end
    local v=Vector(C.raw(p,s,ButtonAction.ACTION_SHOOTRIGHT)-C.raw(p,s,ButtonAction.ACTION_SHOOTLEFT),C.raw(p,s,ButtonAction.ACTION_SHOOTDOWN)-C.raw(p,s,ButtonAction.ACTION_SHOOTUP))
    if v:Length()>.2 then s.padFace=v:Normalized() end
    return p.Position+(s.padFace or s.face)*180
end
function C.upgrade(p)
    if (p.ControllerIndex or 0)>0 then return Input.IsButtonPressed(10,p.ControllerIndex) end
    return keyboardCtrl()
end
-- Keep drop/swap in the engine (Schoolbag, extra pockets and trinket rules).
-- A short Ctrl tap is submitted on release; a hold starts after a 0.2s chord
-- window. Once a modifier chord is used, suppress drop until Ctrl is released.
function C.pollDrop(p,s,disabled)
    local frame=s.inputFrame or 0;local controller=(p.ControllerIndex or 0)>0
    local held=controller and Input.IsButtonPressed(10,p.ControllerIndex) and Input.IsButtonPressed(7,p.ControllerIndex)
    if not controller then held=keyboardCtrl() end
    local chord=false
    if held then
        for _,key in ipairs({'q','w','e','r'}) do if C.down(p,key) then chord=true end end
        if not controller then for i=1,6 do if Input.IsButtonPressed(Keyboard['KEY_'..i],0) then chord=true end end end
    end
    local d=s.nativeDrop or {held=false,active=false};s.nativeDrop=d
    if held and not d.held then d.start=frame;d.cancelled=false;d.sent=false;d.pulse=nil end
    if disabled or chord then d.cancelled=true;d.pulse=nil end
    if not held and d.held and not d.cancelled and not d.sent then d.pulse=frame end
    local down=not disabled and not d.cancelled and ((held and (controller or frame-d.start>=6)) or d.pulse==frame)
    if down and not d.active then d.edge=frame end
    if down then d.sent=true end
    d.held=held;d.active=down
    return down,d.edge==frame and down
end
function C.nativeItem(p,s,action,disabled)
    local controller=(p.ControllerIndex or 0)>0
    local bomb=action==ButtonAction.ACTION_BOMB
    local key=bomb and Keyboard.KEY_G or action==ButtonAction.ACTION_ITEM and Keyboard.KEY_SPACE or Keyboard.KEY_4
    local modifier=controller and Input.IsButtonPressed(10,p.ControllerIndex) or not controller and keyboardCtrl()
    local owner=action
    if controller then
        key=(bomb or action==ButtonAction.ACTION_ITEM) and 6 or 7
        if key==6 then owner=modifier and ButtonAction.ACTION_BOMB or ButtonAction.ACTION_ITEM
        elseif modifier then owner=false end
    elseif modifier then owner=false end
    local index=controller and p.ControllerIndex or 0
    local held=Input.IsButtonPressed(key,index)
    s.nativeItems=s.nativeItems or {};local route=s.nativeItems[key] or {};s.nativeItems[key]=route
    if held and not route.held then route.owner=owner;route.modifier=modifier end
    -- Releasing a modifier must not turn an emote into a card use, or a bomb
    -- chord into active-item use. Require the physical button to be released.
    if disabled or modifier~=route.modifier then route.owner=false end
    route.held=held
    local down=held and route.owner==action
    return down,down and Input.IsButtonTriggered(key,index)
end
function C.open(p,save)
    if not ImGui then return end
    if ImGui.ElementExists(window) then ImGui.RemoveWindow(window) end
    menuPlayer=p;local config=C.state(p)
    if p:GetData().Samira then p:GetData().Samira.shopOpen=false end
    ImGui.CreateWindow(window,C.text('Samira设置','Samira settings'))
    ImGui.AddCombobox(window,'aatrox_movement',C.text('移动方式','Movement'),function(index)
        config.mode=index==1 and 'wasd' or 'mouse';config.bindings={};save();C.rebuild=true
    end,{C.text('右键移动','Right-click movement'),'WASD'},config.mode=='wasd' and 1 or 0)
    ImGui.AddText(window,C.text('点击下面的按键可重新绑定。按住 A（WASD 模式为 T）朝鼠标方向单目标普攻：普通攻击为100°扇形，被动为矩形刺击。','Click a key to rebind. Hold A (T in WASD mode) for a single-target attack toward the cursor: a 100-degree cone, or a rectangular passive thrust.'),true)
    for _,key in ipairs({'q','w','e','r','attack','stop'}) do
        local label=({attack=C.text('扇形普攻','Cone attack'),stop=C.text('停止','Stop')})[key] or key:upper()
        ImGui.AddInputKeyboard(window,'aatrox_key_'..key,label,function(code)
            if C.reserved(code,config.mode) then C.rebuild=true;return end
            for other in pairs(defaults.mouse) do if other~=key and C.key(p,other)==code then C.rebuild=true;return end end
            config.bindings[key]=code;save()
        end,C.key(p,key))
    end
    ImGui.AddText(window,C.text('Ctrl 短按松开：切换；长按：丢弃。Ctrl+技能加点，Ctrl+1～5 表情。手柄：左摇杆移动，右摇杆瞄准；LB/LT/RB/RT 为 Q/W/E/R；A 普攻，B 停止；X 主动，Y 卡牌；L3+X 炸弹，L3+Y 短按切换／长按丢弃；Back 商店。L3+技能加点。十字键选装备，R3 使用。','Tap/release Ctrl to swap; hold to drop. Ctrl + skill upgrades; Ctrl + 1–5 emotes. Controller: sticks move/aim; LB/LT/RB/RT = Q/W/E/R; A attack, B stop; X active, Y pocket; L3+X bomb, L3+Y tap to swap/hold to drop; Back shop; L3 + skill upgrades; D-pad selects equipment, R3 uses it.'),true)
    ImGui.AddButton(window,'aatrox_settings_close',C.text('完成','Done'),function()C.close()end)
    ImGui.SetWindowSize(window,540,440);ImGui.SetVisible(window,true);ImGui.Show()
end
function C.close()
    if ImGui and ImGui.ElementExists(window) and ImGui.GetVisible(window) then ImGui.SetVisible(window,false);ImGui.Hide() end
    if menuPlayer and menuPlayer:GetData().Samira then menuPlayer:GetData().Samira.configOpen=false end
    menuPlayer=nil
end
function C.menu(p,s,save)
    local held=Input.IsButtonPressed(Keyboard.KEY_F10,0) or (p.ControllerIndex or 0)>0 and Input.IsButtonPressed(10,p.ControllerIndex) and Input.IsButtonPressed(14,p.ControllerIndex)
    local trigger=held and not s.configKey;s.configKey=held
    if trigger then if s.configOpen then C.close() else C.open(p,save) end end
    if C.rebuild then C.rebuild=nil;C.open(p,save) end
    s.configOpen=ImGui and ImGui.ElementExists(window) and ImGui.GetVisible(window) and ImGui.IsVisible() or false
end
return C
