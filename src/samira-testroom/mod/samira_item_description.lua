local Description = {}

local fields = {
    {'damage_flat', 'Урон'},
    {'attack_speed_pct', 'Темп автоатак', '%'},
    {'crit_chance_pct', 'Шанс крита', '%'},
    {'crit_multiplier_bonus', 'Множитель крита', '×'},
    {'lethality_damage_bonus_pct', 'Урон от летальности', '%'},
    {'armor_pen_damage_bonus_pct', 'Урон от пробивания', '%'},
    {'ability_haste', 'Ускорение умений'},
    {'health_red_hearts', 'Красные сердца'},
    {'move_speed_flat', 'Скорость движения'},
    {'move_speed_pct', 'Скорость движения', '%'},
    {'lifesteal_chance_pct', 'Шанс вампиризма автоатак', '%'},
    {'omnivamp_chance_pct', 'Шанс вампиризма попаданий', '%'},
    {'iframes_pct', 'Кадры неуязвимости', '%'},
}

function Description.statText(stats)
    local parts = {}
    for _, field in ipairs(fields) do
        local value = stats[field[1]]
        if value ~= nil then
            local number = (value == 0 and '0' or ('%+g'):format(value)):gsub('%.', ',')
            parts[#parts + 1] = field[2] .. ' ' .. number .. (field[3] or '')
        end
    end
    return table.concat(parts, ' · ')
end

function Description.wrap(font, value, maxWidth)
    local lines, current = {}, ''
    for word in value:gmatch('[^ \t\r\n]+') do
        local candidate = current == '' and word or current .. ' ' .. word
        if current ~= '' and font:GetStringWidthUTF8(candidate) > maxWidth then
            lines[#lines + 1], current = current, word
        else
            current = candidate
        end
    end
    if current ~= '' then lines[#lines + 1] = current end
    return lines
end

function Description.lines(font, item, maxWidth)
    local stats = Description.wrap(font, Description.statText(item.stats), maxWidth)
    local passive = item.descriptionRu or ''
    local attributes = item.stats
    if ((attributes.lifesteal_chance_pct or 0) > 0 or (attributes.omnivamp_chance_pct or 0) > 0)
        and not passive:find('½', 1, true) then
        passive = passive .. ' Вампиризм лечит ½ красного сердца.'
    end
    return stats, Description.wrap(font, passive, maxWidth)
end

return Description
