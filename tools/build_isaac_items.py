"""Build the test-room's native collectibles from the Isaac-style atlas.

Run after tools/build_item_catalog.py. Requires Pillow.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree

from PIL import Image

from build_item_catalog import DD, ROOT, VERSION, WORK, write_json


MOD = ROOT / "src/samira-testroom/mod"
ITEM_GFX_ROOT = "gfx/items/"
ICON_ROOT = ITEM_GFX_ROOT + "collectibles"
ICON_CACHE = WORK / "icons"
ICON_LOCK = ROOT / "docs/items-icons.lock.json"
CATALOG = ROOT / "docs/items-catalog.json"
STYLED_ATLAS = ROOT / "assets/samira-items/isaac-atlas.png"
SPRITESHEET = "resources/gfx/items/samira_items_atlas.png"
COLUMNS, ROWS = 8, 6
TILE_SIZE, PADDING = 32, 2

# Native pickup banners use English; the Russian renderer reads the first field.
DESCRIPTIONS = {
    1001: ("Скорость передвижения ↑", "Speed up"),
    2501: ("Красные сердца усиливают урон. Раны усиливают прямые попадания.", "Health and wounds fuel damage"),
    2512: ("Ускоряет R. После R три быстрые автоатаки с гарантированным критом.", "Rapid critical attacks after R"),
    2517: ("Сила атаки ускоряет умения. Боссы временно усиливают шанс вампиризма.", "Haste and boss-triggered vamp"),
    2520: ("Попадание +1,5 урона раз в 8 с. Первый удар по боссу +15% его макс. HP.", "Bonus damage and boss breaker"),
    2523: ("Дальние попадания сильнее. Убийства временно увеличивают дальность.", "Distance amplifies shots"),
    2525: ("Урон врага оставил ≤30% красного HP — лечение 3 сердец. Раз на этаж.", "Emergency heal once per floor"),
    3006: ("Скорость передвижения и темп автоатак ↑", "Speed and attack speed up"),
    3008: ("Победы над боссами дают шанс восстановить ½ сердца при попадании.", "Boss kills stack vamp chance"),
    3009: ("Скорость ↑. Замедления от врагов и паутины слабее на 25%.", "Speed and slow resistance"),
    3031: ("Урон, шанс и множитель критического попадания ↑", "Stronger critical hits"),
    3032: ("Автоатаки набирают шанс крита. Первый удар в комнате ускоряет стрельбу.", "Attacks build critical chance"),
    3033: ("Прямые попадания метят цель. По 15% твоего урона в секунду на 3 с.", "Hits inflict Grievous Wounds"),
    3036: ("До +15% урона по целям с высоким максимальным HP.", "Bonus damage against giants"),
    3046: ("Дальние автоатаки проходят сквозь камни и обычные препятствия.", "Spectral shots"),
    3053: ("Урон ↑. Урон врага оставил ≤30% красного HP — лечение 3 сердец раз на этаж.", "Damage and emergency heal"),
    3071: ("Попадания наращивают уязвимость цели и кратко ускоряют Самиру.", "Stacking vulnerability"),
    3072: ("Шанс восстановить ½ сердца. Успешный бросок при полном HP даёт щит.", "Full-health vamp grants a shield"),
    3073: ("Ускоряет R. После R временно растут скорость и темп автоатак.", "Speed surge after R"),
    3078: ("После умения следующая автоатака +3 урона. КД 3 с.", "Ability primes a stronger attack"),
    3083: ("Доп. сердца за здоровье от предметов. Две зачистки без урона лечат ½ сердца.", "Heart synergy and clean-room healing"),
    3084: ("Пробудь рядом 2 с: автоатака ×1,5. Четыре разные цели дают ½ сердца.", "Charge a strike and grow health"),
    3085: ("Прямое попадание выпускает до 2 болтов в соседних врагов.", "Shots split into nearby foes"),
    3094: ("Движение заряжает выстрел: +1,2 урона и +35% дальности.", "Movement charges a long shot"),
    3095: ("Движение и атаки заряжают выстрел: +1,4 урона и всплеск скорости.", "Charged shots grant speed"),
    3153: ("Автоатака +25% твоего урона. Три атаки по цели замедляют её.", "Bonus damage and three-hit slow"),
    3158: ("Скорость передвижения и ускорение умений ↑", "Speed and ability haste up"),
    3161: ("Ускоряет Q/W/E. Попадания умениями временно наращивают их урон.", "Ability hits build ability damage"),
    3170: ("Сопротивление замедлениям. Скорость от предметов повышает урон.", "Bonus movement speed fuels damage"),
    3171: ("Умения временно увеличивают скорость на 8%.", "Abilities grant speed"),
    3172: ("Скорость и темп ↑. Шанс восстановить ½ сердца автоатакой.", "Attack speed and vamp chance"),
    3179: ("Прямое попадание +1,5 урона раз в 8 с.", "Periodic bonus attack damage"),
    3181: ("Каждая пятая успешная автоатака +4 урона.", "Fifth attack hits harder"),
    3814: ("Щит от снаряда. Возвращается в новой комнате или через 20 с боя.", "Rechargeable projectile shield"),
    6609: ("Прямые попадания метят цель. По 15% твоего урона в секунду на 3 с.", "Hits inflict Grievous Wounds"),
    6610: ("Первый удар по боссу — крит и ½ сердца. Лечение раз на комнату.", "First boss hit crits and heals"),
    6672: ("Каждая третья успешная автоатака +50% твоего урона.", "Third attack hits harder"),
    6673: ("Урон врага оставил ≤30% красного HP — лечение 3 сердец. Раз на этаж.", "Emergency heal once per floor"),
    6675: ("Успешные автоатаки сокращают оставшийся КД Q/W/E на 15%.", "Attacks shorten ability cooldowns"),
    6676: ("Добивание ниже 5% HP. +1 монета за зачистку с добиванием.", "Execute for extra coins"),
    6692: ("Два разных прямых попадания за 2 с дают щит. КД 12 с.", "Rapid mixed hits grant a shield"),
    6694: ("Умения замедляют врагов ниже половины HP на 30% на 1 с.", "Abilities slow injured targets"),
    6695: ("Автоатаки уничтожают вражеские снаряды.", "Attacks destroy hostile projectiles"),
    6696: ("Урон R +20%.", "R damage up"),
    6697: ("Новая боевая комната без урона навсегда даёт +0,1 урона.", "Clean combat rooms build damage"),
    6699: ("Умение заряжает выстрел: +40% твоего урона и временная летальность.", "Ability primes a charged shot"),
}


def item_name(item):
    return "Samira: " + item["name_en"]


def lua_value(value):
    if isinstance(value, dict):
        fields = (f"{key} = {lua_value(field)}" for key, field in value.items())
        return "{ " + ", ".join(fields) + " }"
    # Exported strings contain Cyrillic and ordinary punctuation, without control characters.
    return json.dumps(value, ensure_ascii=False)


def collectible_xml(items):
    # Isaac appends collectibles/ to gfxroot for passive items.
    root = ElementTree.Element("items", gfxroot=ITEM_GFX_ROOT, version="1")
    for index, item in enumerate(items, 1):
        riot_id = item["id"]
        entry = ElementTree.SubElement(
            root, "passive", id=str(index), name=item_name(item),
            description=DESCRIPTIONS[riot_id][1], gfx=f"samira_item_{riot_id}.png",
            quality="3", shopprice=str(item["price_coins"]),
        )
        if health := item["stats_isaac"].get("health_red_hearts"):
            half_hearts = str(int(health * 2))
            entry.set("maxhearts", half_hearts)
            entry.set("hearts", half_hearts)
    ElementTree.indent(root)
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def collectible_lua(items):
    lines = ["-- Generated by tools/build_isaac_items.py.", "return {"]
    for item in items:
        riot_id = item["id"]
        fields = {
            "riotId": riot_id,
            "name": item["name_ru"],
            "nameEn": item["name_en"],
            "collectibleName": item_name(item),
            "descriptionRu": DESCRIPTIONS[riot_id][0],
            "stats": item["stats_isaac"],
            "price": item["price_coins"],
            "tier": item["tier"],
            "icon": f"{ICON_ROOT}/samira_item_{riot_id}.png",
        }
        lines.append("    " + lua_value(fields) + ",")
    return "\n".join([*lines, "}", ""]).encode()


def fetch_source(item, lock):
    source_name = item["image_file"]
    if Path(source_name).name != source_name or not source_name.endswith(".png"):
        raise ValueError(f"Unexpected Riot icon name: {source_name}")
    source = ICON_CACHE / source_name
    url = f"{DD}/cdn/{VERSION}/img/item/{source_name}"
    if source.is_file():
        raw = source.read_bytes()
    else:
        with urlopen(url, timeout=30) as response:
            raw = response.read()
    digest = sha256(raw).hexdigest()
    if lock and digest != lock["source_sha256"]:
        raise ValueError(f"Riot icon checksum mismatch: {url}")
    with Image.open(BytesIO(raw)) as image:
        if image.format != "PNG" or image.size != (64, 64):
            raise ValueError(f"Unexpected Riot icon format or dimensions: {url}")
    if not source.is_file():
        source.write_bytes(raw)
    return {"riot_id": item["id"], "source_url": url, "source_sha256": digest}


def encode_png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def slice_atlas():
    source = STYLED_ATLAS.read_bytes()
    with Image.open(BytesIO(source)) as image:
        if image.format != "PNG" or "A" not in image.getbands():
            raise ValueError("The styled atlas must be a PNG with an alpha channel")
        atlas = image.convert("RGBA")
    packed = Image.new("RGBA", (COLUMNS * TILE_SIZE, ROWS * TILE_SIZE))
    tiles = []
    for index in range(COLUMNS * ROWS):
        column, row = index % COLUMNS, index // COLUMNS
        left = round(atlas.width * column / COLUMNS)
        top = round(atlas.height * row / ROWS)
        right = round(atlas.width * (column + 1) / COLUMNS)
        bottom = round(atlas.height * (row + 1) / ROWS)
        cell = atlas.crop((left, top, right, bottom))
        bounds = cell.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0).getbbox()
        if index >= 46:
            if bounds:
                raise ValueError(f"Expected an empty styled atlas cell at index {index}")
            continue
        if not bounds:
            raise ValueError(f"Missing icon in styled atlas cell {index}")
        x1, y1, x2, y2 = bounds
        fringe = 3
        if min(x1, y1, cell.width - x2, cell.height - y2) <= fringe:
            raise ValueError(f"Icon too close to the edge of source cell {index}")
        icon = cell.crop((x1 - fringe, y1 - fringe, x2 + fringe, y2 + fringe))
        icon.putalpha(icon.getchannel("A").point(lambda alpha: alpha if alpha >= 32 else 0))
        interior = TILE_SIZE - 2 * PADDING
        icon.thumbnail((interior, interior), Image.Resampling.NEAREST)
        tile = Image.new("RGBA", (TILE_SIZE, TILE_SIZE))
        tile.paste(icon, ((TILE_SIZE - icon.width) // 2, (TILE_SIZE - icon.height) // 2))
        packed.paste(tile, (column * TILE_SIZE, row * TILE_SIZE))
        tiles.append(tile)
    return tiles, packed, sha256(source).hexdigest()


def main():
    catalog = json.loads(CATALOG.read_bytes())
    items = catalog["items"]
    if catalog["version"] != VERSION or len(items) != 46 or set(DESCRIPTIONS) != {i["id"] for i in items}:
        raise ValueError("Expected the pinned catalog of 46 items with matching descriptions")
    expected = {}
    if ICON_LOCK.is_file():
        existing = json.loads(ICON_LOCK.read_bytes())
        if existing["data_dragon_version"] != VERSION:
            raise ValueError("Existing icon lock uses a different version")
        expected = {entry["riot_id"]: entry for entry in existing["icons"]}
    ICON_CACHE.mkdir(parents=True, exist_ok=True)
    tiles, packed, styled_atlas_hash = slice_atlas()
    with ThreadPoolExecutor(max_workers=12) as pool:
        sources = list(pool.map(lambda item: fetch_source(item, expected.get(item["id"])), items))
    icons = []
    for index, (source, tile) in enumerate(zip(sources, tiles, strict=True)):
        data = encode_png(tile)
        path = f"resources/{ICON_ROOT}/samira_item_{source['riot_id']}.png"
        icons.append(({
            **source, "output": path, "output_sha256": sha256(data).hexdigest(),
            "spritesheet_xy": [(index % COLUMNS) * TILE_SIZE, (index // COLUMNS) * TILE_SIZE],
        }, data))
    spritesheet = encode_png(packed)
    outputs = {
        "content/items.xml": collectible_xml(items),
        "samira_items_data.lua": collectible_lua(items),
        SPRITESHEET: spritesheet,
        **{entry["output"]: data for entry, data in icons},
    }
    for name, data in outputs.items():
        path = MOD / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(ICON_LOCK, {
        "source": "Riot Games League of Legends Data Dragon",
        "data_dragon_version": VERSION,
        "styled_atlas": {
            "asset": STYLED_ATLAS.relative_to(ROOT).as_posix(),
            "sha256": styled_atlas_hash,
            "generation": "One ImageGen style transfer of the 46 Riot icons in row-major order on a transparent 8×6 reference grid. Use Isaac-style collectible sprites and preserve the order and recognizable item silhouettes; leave the last two cells empty.",
        },
        "spritesheet": {"output": SPRITESHEET, "output_sha256": sha256(spritesheet).hexdigest()},
        "conversion": "Slice 8×6, trim the transparent fringe, fit and center in 32×32 RGBA tiles with 2px minimum padding using nearest-neighbor.",
        "icons": [entry for entry, _ in icons],
    })
    print(f"Generated {len(items)} native collectibles and verified {len(icons)} Riot icon sources")


if __name__ == "__main__":
    main()
