local E={};local clips=include('scripts.samira_external_actions')
local presets={
 {intro='Joke'}, {intro='Taunt_Into',loop='Taunt_loop',ultIntro='ULT_Taunt_Into',ultLoop='ULT_Taunt_loop'},
 {intro='Dance_Windup',loop='Dance_Loop'}, {intro='Laugh'},
}
function E.start(s,name)
    if not clips[name] or s.cast or s.dash then return false end
    s.emote={intro=name,at=s.clock};s.goal=nil;s.target=nil;s.path=nil;s.exitIntent=nil
    return true
end
function E.update(s,enabled,cancel)
    local ctrl=Input.IsButtonPressed(Keyboard.KEY_LEFT_CONTROL,0) or Input.IsButtonPressed(Keyboard.KEY_RIGHT_CONTROL,0)
    s.emoteKeys=s.emoteKeys or {};local selected
    for i=1,5 do
        local down=ctrl and Input.IsButtonPressed(Keyboard['KEY_'..i],0)
        if down and not s.emoteKeys[i] then selected=i end
        s.emoteKeys[i]=down
    end
    if not enabled or cancel then s.emote=nil;return end
    if selected==5 then
        s.bannerVisible=not (s.bannerVisible~=false)
    elseif selected then
        local preset=presets[selected];local ult=(s.rUntil or 0)>s.clock
        if E.start(s,ult and preset.ultIntro or preset.intro) then
            s.emote.loop=ult and preset.ultLoop or preset.loop
        end
    end
    if s.emote and not s.emote.loop and (s.clock-s.emote.at)/30>=clips[s.emote.intro] then s.emote=nil end
end
function E.frame(s)
    local e=s.emote;if not e then return end
    local age=math.max(0,(s.clock-e.at)/30);local duration=clips[e.intro]
    if age<duration then return e.intro,age/duration,false end
    if e.loop then return e.loop,((age-duration)/clips[e.loop])%1,true end
    return e.intro,1,false
end
function E.has(name)return clips[name]~=nil end
function E.list()
    local names={};for name in pairs(clips) do names[#names+1]=name end
    table.sort(names);return table.concat(names,', ')
end
return E
