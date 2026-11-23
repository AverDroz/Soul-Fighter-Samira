"""Add pinned crafting dependencies to the 46-item native catalog.

Run after build_isaac_items.py. Rendered icons come from three original,
transparent 3x3 sheets. Riot metadata and reference icons remain pinned.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
from hashlib import sha256
import json
import re
from build_isaac_items import encode_png, slice_atlas

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'src/samira-testroom/mod'
LOCK = ROOT / 'docs/components-data.lock.json'
SOURCES = ROOT / 'assets/samira-items/components'
SHEETS = (
    (1006, 1011, 1018, 1028, 1036, 1037, 1038, 1042, 1043),
    (1053, 2020, 2021, 2022, 3035, 3044, 3051, 3057, 3066),
    (3067, 3086, 3123, 3133, 3134, 3144, 3801, 6670, 6690),
)

# Data Dragon exposes some attributes only in description markup.
HASTE = {2020:10, 2022:5, 3057:10, 3067:10, 3133:10}
LETHALITY = {2020:2.5, 3134:5}
ARMOR_PEN = {3035:9}
PASSIVES = {
    1006: '½ сердца каждые 4 зачистки без урона. Общий счётчик с бронёй Вармога.',
    1043: 'Первое прямое попадание автоатаки +0,3 урона.',
    3044: 'Попадание даёт +0,04 скорости на 2 с.',
    3057: 'После умения автоатака +1 урона. Общий КД 3 с.',
    3123: 'Попадания: кровотечение 7,5% урона в секунду на 3 с.',
    3144: 'Прямое попадание +0,5 урона раз в 8 с.',
    3801: '½ сердца каждые 3 зачистки без урона. Общий счётчик с бронёй Вармога.',
}

def lua(value):
    if isinstance(value, bool): return str(value).lower()
    if isinstance(value, dict): return '{ ' + ', '.join(f'{k} = {lua(v)}' for k,v in value.items()) + ' }'
    if isinstance(value, list): return '{ ' + ', '.join(map(str, value)) + ' }'
    return json.dumps(value, ensure_ascii=False)

def adaptation(item_id, entry):
    source = entry['stats']; result = {}
    def add(key, value):
        if value: result[key] = value
    add('damage_flat', round(source.get('FlatPhysicalDamageMod', 0) * .04, 2))
    add('attack_speed_pct', round(source.get('PercentAttackSpeedMod', 0) * 100, 2))
    add('crit_chance_pct', round(source.get('FlatCritChanceMod', 0) * 100, 2))
    add('move_speed_pct', round(source.get('PercentMovementSpeedMod', 0) * 100, 2))
    add('lifesteal_chance_pct', round(source.get('PercentLifeStealMod', 0) * 25, 2))
    add('health_red_hearts', int(source.get('FlatHPPoolMod', 0) / 100) / 2)
    add('ability_haste', HASTE.get(item_id, 0))
    add('lethality_damage_bonus_pct', LETHALITY.get(item_id, 0))
    add('armor_pen_damage_bonus_pct', ARMOR_PEN.get(item_id, 0))
    labels = {'damage_flat':'урон', 'attack_speed_pct':'темп атак', 'crit_chance_pct':'шанс крита',
              'move_speed_pct':'скорость', 'lifesteal_chance_pct':'шанс вампиризма',
              'health_red_hearts':'красные сердца', 'ability_haste':'ускорение умений',
              'lethality_damage_bonus_pct':'летальность', 'armor_pen_damage_bonus_pct':'пробивание брони'}
    desc = ', '.join(labels[k] for k in result) + ' ↑.' if result else ''
    desc = (desc + ' ' + PASSIVES.get(item_id, '')).strip() or 'Пока без эффекта в Isaac.'
    return result, desc

def component_icons():
    art, atlases = {}, []
    for sheet, ids in enumerate(SHEETS, 1):
        path = SOURCES.parent / f'components-stylized-{sheet}.png'
        tiles, _, digest = slice_atlas(path, 3, 3, len(ids))
        asset = path.relative_to(ROOT).as_posix()
        atlases.append({'asset': asset, 'sha256': digest})
        for index, (riot_id, tile) in enumerate(zip(ids, tiles, strict=True)):
            art[riot_id] = (encode_png(tile), asset, [index % 3, index // 3])
    return art, atlases

def main():
    data=json.loads(LOCK.read_text(encoding='utf8')); entries={int(k):v for k,v in data['entries'].items()}
    original=data['original_ids']; additions=sorted(set(entries)-set(original)); assert len(original)==46 and len(additions)==27
    art, atlases = component_icons()
    assert sorted(art) == additions
    # Existing rows are the source of truth for names, descriptions, stats and save-compatible order.
    path=MOD/'samira_items_data.lua'; lines=path.read_text(encoding='utf8').splitlines()
    rows=[line for line in lines if re.search(r'riotId = \d+',line)][:46]
    assert [int(re.search(r'riotId = (\d+)',r).group(1)) for r in rows]==original
    rows=[re.sub(r', components = \{[^}]*\}, combinePrice = \d+', '', r).replace(', component = true', '') for r in rows]
    xmlpath=MOD/'content/items.xml'; root=ET.parse(xmlpath).getroot()
    for child in list(root)[46:]: root.remove(child)
    assert len(root)==46
    prices={int(re.search(r'riotId = (\d+)',r).group(1)):int(re.search(r'price = (\d+)',r).group(1)) for r in rows}
    prices.update({i:max(2,round(entries[i]['gold']/140)) for i in additions})
    def metadata(i):
        parts=entries[i]['from']
        if not parts: return ''
        fee=max(0, prices[i]-sum(prices[j] for j in parts))
        return ', components = '+lua(parts)+', combinePrice = '+str(fee)
    rows=[r[:-3]+metadata(i)+(', component = true' if i==1001 else '')+' },' for i,r in zip(original,rows)]
    icons=[]
    for offset,i in enumerate(additions,47):
        entry=entries[i]; stats,desc=adaptation(i,entry); name='Samira: '+entry['name_en']; icon=f'samira_item_{i}.png'
        fields={'riotId':i,'name':entry['name_ru'],'nameEn':entry['name_en'],'collectibleName':name,
                'descriptionRu':desc,'stats':stats,'price':prices[i],'tier':'component',
                'icon':'gfx/items/collectibles/'+icon,'component':True}
        line='    '+lua(fields)
        line=line[:-2]+metadata(i)+' }'
        rows.append(line+',')
        attrs={'id':str(offset),'name':name,'description':'Component passive' if i in PASSIVES else 'Crafting component',
               'gfx':icon,'quality':'1','shopprice':str(prices[i])}
        if stats.get('health_red_hearts'):
            attrs['maxhearts']=attrs['hearts']=str(int(stats['health_red_hearts']*2))
        ET.SubElement(root,'passive',attrs)
        raw=(SOURCES/f'{i}.png').read_bytes()
        tile, art_asset, art_cell = art[i]
        target=MOD/'resources/gfx/items/collectibles'/icon; target.write_bytes(tile)
        icons.append({'riot_id':i,'source_url':f'https://ddragon.leagueoflegends.com/cdn/16.22.1/img/item/{i}.png',
                      'source_sha256':sha256(raw).hexdigest(), 'art_asset':art_asset, 'art_cell':art_cell,
                      'output_sha256':sha256(tile).hexdigest()})
    path.write_text('-- Generated by tools/build_isaac_items.py and tools/build_item_components.py.\nreturn {\n'+'\n'.join(rows)+'\n}\n',encoding='utf8')
    ET.indent(root); xmlpath.write_bytes(ET.tostring(root,encoding='utf8',xml_declaration=True)+b'\n')
    icon_lock = {
        'source': 'Riot Data Dragon (original icon references)',
        'version': '16.22.1',
        'styled_atlases': atlases,
        'conversion': 'Slice 3x3, trim the transparent fringe, and fit into 32x32 RGBA with 2px padding using nearest-neighbor.',
        'icons': icons,
    }
    (ROOT/'docs/components-icons.lock.json').write_text(json.dumps(icon_lock, indent=2)+'\n', encoding='utf8')
    print(f'Generated {len(additions)} components and recipes for {sum(bool(e["from"]) for e in entries.values())} items')

if __name__=='__main__': main()
