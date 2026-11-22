local Debug = {}
local castList = 'attack|q|q3|w|e|r'
local animationList = 'idle|run|attack|attack2|q|q3|w|e|e_return|r|joke|taunt|dance|laugh|mastery'

local function choices(list)
    local result = {}
    for word in list:gmatch('[^|]+') do result[word] = true end
    return result
end

local casts, animations = choices(castList), choices(animationList)
local commands = {
    {'yonetest', 'Enable or rebind Yone for this run', 'yonetest [off]'},
    {'yoneanim', 'Preview a Yone animation or emote', 'yoneanim ' .. animationList},
    {'yonecast', 'Test a real cast toward the cursor', 'yonecast ' .. castList},
    {'yoneq3', 'Prepare both stacks of Mortal Steel', 'yoneq3'},
    {'yonereset', 'Reset Yone ability cooldowns', 'yonereset'},
    {'yonemastery', 'Preview the mastery emote', 'yonemastery'},
    {'yonestatus', 'Show Yone cooldowns and display state', 'yonestatus'},
    {'yoneweapon', 'Show Yone blade and combat state', 'yoneweapon'},
    {'yonehelp', 'List the Yone test commands', 'yonehelp'},
}

function Debug.init(mod, test, enqueue, status)
    local usage = {}
    for _, command in ipairs(commands) do
        local name, description, hint = table.unpack(command)
        usage[name] = hint
        Console.RegisterCommand(name, description, hint, false, AutocompleteType.NONE)
    end
    mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, name, args)
        local hint = usage[name]
        if not hint then return end
        local arg = (args or ''):match('^%s*(.-)%s*$'):lower()
        local line
        if name == 'yonetest' and (arg == '' or arg == 'on' or arg == 'off') then
            line = test(arg ~= 'off')
        elseif name == 'yonecast' and casts[arg] then
            line = enqueue('cast', arg)
        elseif name == 'yoneanim' and animations[arg] then
            line = enqueue('animation', arg)
        elseif arg == '' then
            if name == 'yoneq3' then line = enqueue('charge')
            elseif name == 'yonereset' then line = enqueue('reset')
            elseif name == 'yonemastery' then line = enqueue('animation', 'mastery')
            elseif name == 'yonestatus' or name == 'yoneweapon' then line = status()
            elseif name == 'yonehelp' then
                local help = {}
                for _, command in ipairs(commands) do help[#help + 1] = command[3] end
                line = table.concat(help, '\n') .. '\nyoneitems [page]\nyoneitem <Riot item ID>\nyoneshop\nyonevamp'
            end
        end
        Isaac.ConsoleOutput((line or 'Usage: ' .. hint) .. '\n')
    end)
end

return Debug
