-- Engine-independent console parser. The hero adapter owns gameplay and saves.
local D={}
function D.new(api)
    assert(api.prefix and api.getPlayer and api.isHero and api.state)
    local function say(text) (api.print or Isaac.ConsoleOutput)(api.prefix..': '..text..'\n') end
    local function help()
        say('lollevel <1-'..(api.maxLevel or 18)..'> | lolcd [on/off] | lolmana [on/off] | lolgold <amount> | lolheal [amount] | lolrespec | lolresource <amount> | lolstatus | lolhelp')
    end
    return function(command,args)
        local aliases={lolhelp='help',lolgold='gold',lollevel='level',lolcd='0cd',lolmana='mana',lolheal='heal',lolrespec='respec',lolresource='resource',lolstatus='status'}
        if aliases[command] then
            local player=api.getPlayer()
            -- Other installed champions must neither mutate nor print for this command.
            if not player or not api.isHero(player) then return false end
            args=aliases[command]..' '..(args or '')
        elseif command~=api.prefix then return false end
        local words={};for word in (args or ''):gmatch('%S+') do words[#words+1]=word:lower() end
        local name=words[1]
        if not name or name=='help' then help();return true end
        if name~='level' and name~='0cd' and name~='mana' and name~='gold' and name~='heal' and name~='respec' and name~='status' and name~='resource' then return false end
        local p=api.getPlayer()
        if not p or not api.isHero(p) then say('Enter this hero first.');return true end
        if name=='heal' or name=='respec' or name=='status' or name=='resource' then
            local value=words[2] and words[2]:match('^%d+$') and tonumber(words[2])
            if #words>2 or words[2] and (not value or value>1000000) or (name=='respec' or name=='status') and #words~=1 or name=='resource' and not value then help();return true end
            if not api[name] then say('Command not implemented by this hero.');return true end
            say(name..' = '..tostring(api[name](p,value)))
            if api.save and name~='status' then api.save() end
            return true
        end
        if name=='0cd' or name=='mana' then
            if #words>2 or words[2] and words[2]~='on' and words[2]~='off' then help();return true end
            if name=='mana' and not api.supportsMana then say('This hero has no mana system.');return true end
            local key=name=='0cd' and 'noCD' or 'infiniteMana';local s=api.state(p)
            local enabled=words[2]=='on' or words[2]==nil and not s[key]
            s[key]=enabled
            if api.onFlag then api.onFlag(p,key,enabled) end
            say((name=='mana' and 'Infinite mana' or 'Zero cooldown')..(enabled and ' ON' or ' OFF'))
            return true -- Debug flags are session state, never written to saves.
        end
        local adding=name=='gold' and words[2]=='add';local number=words[adding and 3 or 2]
        local count=adding and 3 or 2
        local value=number and number:match('^%d+$') and tonumber(number)
        local limit=name=='level' and (api.maxLevel or 18) or (api.maxGold or 999)
        if #words~=count or not value or value>(limit) or value<(name=='level' and 1 or 0) then help();return true end
        local fn;if name=='level' then fn=api.setLevel else fn=api.gold end
        if not fn then say('Command not implemented by this hero.');return true end
        local result=fn(p,value,adding)
        if api.save then api.save() end
        say(name..' = '..tostring(result))
        return true
    end
end
return D
