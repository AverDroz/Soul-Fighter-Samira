"""Add pinned crafting dependencies to the 46-item native catalog.

Run after build_isaac_items.py. Component sources are pinned in
assets/samira-items/components and their metadata in docs/components-data.lock.json.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
from hashlib import sha256
from io import BytesIO
import json
import re
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'src/samira-testroom/mod'
LOCK = ROOT / 'docs/components-data.lock.json'
SOURCES = ROOT / 'assets/samira-items/components'

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

def main():
    data=json.loads(LOCK.read_text(encoding='utf8')); entries={int(k):v for k,v in data['entries'].items()}
    original=data['original_ids']; additions=sorted(set(entries)-set(original)); assert len(original)==46 and len(additions)==27
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
        source=SOURCES/f'{i}.png'; raw=source.read_bytes()
        with Image.open(BytesIO(raw)) as im:
            assert im.format=='PNG' and im.size==(64,64)
            sprite=im.convert('RGBA').resize((28,28),Image.Resampling.LANCZOS)
            tile=Image.new('RGBA',(32,32),(0,0,0,0)); tile.paste(sprite,(2,2))
            target=MOD/'resources/gfx/items/collectibles'/icon; tile.save(target)
        icons.append({'riot_id':i,'source_url':f'https://ddragon.leagueoflegends.com/cdn/16.22.1/img/item/{i}.png',
                      'source_sha256':sha256(raw).hexdigest(),'output_sha256':sha256(target.read_bytes()).hexdigest()})
    path.write_text('-- Generated by tools/build_isaac_items.py and tools/build_item_components.py.\nreturn {\n'+'\n'.join(rows)+'\n}\n',encoding='utf8')
    ET.indent(root); xmlpath.write_bytes(ET.tostring(root,encoding='utf8',xml_declaration=True)+b'\n')
    (ROOT/'docs/components-icons.lock.json').write_text(json.dumps({'source':'Riot Data Dragon','version':'16.22.1','conversion':'64x64 Riot PNG resized to 28x28 with Lanczos and centered in a transparent 32x32 RGBA tile','icons':icons},indent=2)+'\n',encoding='utf8')
    print(f'Generated {len(additions)} components and recipes for {sum(bool(e["from"]) for e in entries.values())} items')

if __name__=='__main__': main()
