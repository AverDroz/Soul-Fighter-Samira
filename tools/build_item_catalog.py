"""Audit Riot Data Dragon items and build the Isaac conversion proposal.

From the repository root: python tools/build_item_catalog.py --refresh
Without --refresh, regenerate the same catalog from the local source snapshot.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work/item-catalog"
OUTPUT = ROOT / "docs/items-catalog.json"
DD = "https://ddragon.leagueoflegends.com"
VERSIONS = f"{DD}/api/versions.json"
LANGUAGES = ("en_US", "ru_RU")
VERSION = "16.22.1"
POTION_IDS = {2003, 2031, 2138, 2140}
STARTER_IDS = {1054, 1055, 1086}
BOOT_CAPSTONES = {3170, 3171, 3172}
BOOT_IDS = {1001, 3006, 3008, 3009, 3158} | BOOT_CAPSTONES
ARAM_EXCLUSIVES = {2051, 3112, 3177, 3184}
SHOP_UPGRADES = {2421, 3173, 3174, 3175}
MANUAL_EXCLUSIONS = {
    1083: ("economy", "Убийства превращаются в золото. Экономические предметы исключены."),
    1101: ("role_quest", "Лесной питомец, квест и Smite в основной пул не входят."),
    1102: ("role_quest", "Лесной питомец, квест и Smite в основной пул не входят."),
    1103: ("role_quest", "Лесной питомец, квест и Smite в основной пул не входят."),
    1105: ("mode_variant", "Дубликат лесного питомца Mosstomper (1103)."),
    1106: ("mode_variant", "Дубликат лесного питомца Gustwalker (1102)."),
    1107: ("mode_variant", "Дубликат лесного питомца Scorchclaw (1101)."),
    2055: ("vision_only", "Расходник для обзора, обнаружения тотемов и ловушек."),
    2139: ("forbidden_stats", "Эликсир даёт силу умений и регенерацию маны."),
    2141: ("cosmetic", "Декоративный эликсир без игрового эффекта."),
    3168: ("forbidden_stats", "Now and Forever повышает входящее лечение и прочность щита при низком здоровье."),
    3074: ("active", "Ravenous Crescent — ручное применение, хотя описано без тега active."),
    3302: ("forbidden_stats", "Juxtaposition даёт владельцу броню и сопротивление магии."),
    3508: ("forbidden_stats", "Spellblade восстанавливает ману при попадании."),
    3865: ("role_quest", "Экономический квест и предмет обзора для роли поддержки."),
}
REASONS = {
    "other_mode": "Предмет недоступен на карте 11 по данным Riot.",
    "mode_variant": "Служебный или альтернативный ID режима. Основной ID учитывается отдельно.",
    "aram_exclusive": "Предмет линейки Guardian для ARAM, хотя флаг карты 11 также присутствует.",
    "unavailable": "В этой версии Riot пометила предмет как недоступный для обычной покупки.",
    "upgrade": "Улучшение, замена или итог превращения предмета. Покупка и сборка не входят в дизайн.",
    "bound": "Служебный предмет, закреплённый за чемпионом или событием.",
    "free": "Бесплатный служебный предмет или бесплатная замена.",
    "active": "В оригинале есть ручное применение.",
    "component": "Компонент сборки. В пуле только легендарные предметы и ботинки.",
    "starter": "Стартовый предмет. В пуле только легендарные предметы и ботинки.",
    "consumable": "Расходник. В пуле только легендарные предметы и ботинки.",
    "forbidden_stats": "Содержит характеристики, которых нет в адаптации.",
}
STAT_NAMES = {
    "attack damage": "ad", "attack speed": "attack_speed_pct", "health": "hp",
    "ability haste": "ability_haste", "lethality": "lethality",
    "critical strike chance": "crit_chance_pct", "critical strike damage": "crit_damage_pct",
    "move speed": "move_speed_flat", "armor penetration": "armor_penetration_pct",
    "base health regen": "health_regen_pct", "life steal": "lifesteal_pct",
    "omnivamp": "omnivamp_pct", "tenacity": "tenacity_pct", "armor": "armor",
    "magic resist": "magic_resist", "mana": "mana", "base mana regen": "mana_regen_pct",
    "ability power": "ap", "magic penetration": "magic_penetration",
    "heal and shield power": "heal_shield_power_pct",
}
BANNED = {"armor", "magic_resist", "mana", "mana_regen_pct", "ap", "magic_penetration", "heal_shield_power_pct"}
STRUCTURED_BANS = {
    "FlatArmorMod": "armor", "FlatSpellBlockMod": "magic_resist", "FlatMPPoolMod": "mana",
    "FlatMagicDamageMod": "ap", "FlatMPRegenMod": "mana_regen_pct",
    "PercentMPRegenMod": "mana_regen_pct",
}
MECHANICS_STATUS = "implemented_pending_game_test"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def download(url, path):
    with urlopen(url, timeout=20) as response:
        data = response.read()
    path.write_bytes(data)
    return json.loads(data), {"url": url, "sha256": sha256(data).hexdigest()}


def sources(refresh):
    if refresh:
        WORK.mkdir(parents=True, exist_ok=True)
        _, version_source = download(VERSIONS, WORK / "versions.json")
        version = VERSION

        def get_language(language):
            return download(f"{DD}/cdn/{version}/data/{language}/item.json", WORK / f"{language}.json")

        with ThreadPoolExecutor(max_workers=2) as pool:
            localized = dict(zip(LANGUAGES, pool.map(get_language, LANGUAGES)))
        metadata = {
            "version": version, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {"versions": version_source, **{lang: value[1] for lang, value in localized.items()}},
        }
        write_json(WORK / "snapshot.json", metadata)
        return metadata, {lang: value[0] for lang, value in localized.items()}
    metadata = json.loads((WORK / "snapshot.json").read_bytes())
    if metadata["version"] != VERSION:
        raise ValueError(f"Expected pinned Data Dragon patch {VERSION}")
    values = {}
    for language in (*LANGUAGES, "versions"):
        data = (WORK / f"{language}.json").read_bytes()
        if sha256(data).hexdigest() != metadata["sources"][language]["sha256"]:
            raise ValueError(f"Source snapshot checksum mismatch: {language}")
        values[language] = json.loads(data)
    return metadata, values


def plain(value):
    value = re.sub(r"<br\s*/?>|<li>", "\n", value)
    value = unescape(re.sub(r"<[^>]*>", "", value))
    return "\n".join(line for line in (" ".join(line.split()) for line in value.splitlines()) if line)


def source_stats(description):
    match = re.search(r"<stats>(.*?)</stats>", description, re.S)
    return plain(match.group(1)).splitlines() if match else []


def parse_stats(lines):
    values = {}
    for line in lines:
        match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(%?)\s+(.+)", line)
        if not match:
            continue
        raw, percent, name = match.groups()
        key = STAT_NAMES.get(name.casefold())
        if key == "move_speed_flat" and percent:
            key = "move_speed_pct"
        elif key == "magic_penetration" and percent:
            key = "magic_penetration_pct"
        if key:
            values[key] = float(raw) if "." in raw else int(raw)
    return values


def source_passives(description):
    body = re.sub(r"<stats>.*?</stats>", "", description, flags=re.S)
    markers = list(re.finditer(r"<(passive|active)>(.*?)</\1>", body, re.S))
    passives = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        passives.append({"type": marker[1], "name": plain(marker[2]), "text": plain(body[marker.end():end])})
    if (text := plain(body)) and not passives:
        passives.append({"type": "passive", "name": "", "text": text})
    return passives


def classify(item_id, item, numeric):
    gold, description = item["gold"], item["description"]
    if not item.get("maps", {}).get("11"):
        return "other_mode", None
    if item_id >= 100000:
        return "mode_variant", None
    if item_id in ARAM_EXCLUSIVES:
        return "aram_exclusive", None
    if item.get("requiredChampion") or item.get("requiredAlly"):
        return "bound", None
    if item_id in SHOP_UPGRADES or item.get("specialRecipe"):
        return "upgrade", None
    if not gold["purchasable"] or not item.get("inStore", True) or item.get("hideFromAll", False):
        return "unavailable", None
    if item_id in MANUAL_EXCLUSIONS:
        return MANUAL_EXCLUSIONS[item_id]
    if not gold["total"] or not gold["base"] and item_id not in BOOT_CAPSTONES:
        return "free", None
    forbidden = BANNED & numeric.keys()
    forbidden |= {name for key, name in STRUCTURED_BANS.items() if item["stats"].get(key)}
    if numeric.get("magic_penetration_pct"):
        forbidden.add("magic_penetration")
    if forbidden:
        return "forbidden_stats", REASONS["forbidden_stats"] + " " + ", ".join(sorted(forbidden)) + "."
    if item_id not in POTION_IDS and re.search(r"<active>|\bACTIVE\b", description):
        return "active", None
    item_tier = tier(item_id, item)
    if item_tier in {"component", "starter", "consumable"}:
        return item_tier, None
    return None, None


def tier(item_id, item):
    if item_id in POTION_IDS:
        return "consumable"
    if item_id in STARTER_IDS:
        return "starter"
    if item_id in BOOT_IDS:
        return "boots"
    return "component" if item.get("into") else "legendary"
# Both items apply the same damage-over-time effect.
WOUNDS = (
    "Прямое попадание ставит общую метку на 3 с: раз в секунду она наносит 15% "
    "собственного урона Самиры. Повторное попадание продлевает метку без сложения "
    "и не сдвигает ближайший тик. Тики не запускают предметы и вампиризм."
)
LIFELINE = (
    "Если вражеский урон оставляет ≤30% максимума красного здоровья, "
    "восстанавливает 3 красных сердца. Каждый предмет готов один раз на этаж. Приоритет: Immortal Shieldbow, Sterak’s Gage, затем Protoplasm Harness. Один случай урона запускает максимум один готовый предмет."
)
# Exact prototype tuning.
ADAPTATIONS = {
    2501: ("medium", "Tyranny: +0,20 урона за каждое дополнительное красное сердце от этих предметов, максимум +1,00. Retribution: от +0% до +10% прямого урона пропорционально доле недостающего красного здоровья."),
    2512: ("medium", "Night Vigil: +30 единиц ускорения только R. Opening Barrage: первые 3 автоатаки после R в течение 6 секунд гарантированно критуют и получают +25 процентных пунктов к темпу стрельбы, пока не потрачены."),
    2517: ("medium", "Famine: +1 ускорение за каждые 10 AD предметов, максимум +15. Feast: после смерти недавно задетого мини-босса или босса +1 процентный пункт к шансу вампиризма на 6 с; без стаков, общий кап 5%."),
    2520: ("high", "Первое прямое попадание при готовом эффекте добавляет +1,5 урона, КД 8 с. Первое прямое попадание по каждому боссу также наносит 15% его максимального HP."),
    2523: ("medium", "Magnification: прямые выстрелы получают до +10% урона линейно по пройденной дистанции до 100 игровых единиц. Arcane Aim: убийство прямой атакой даёт +20 к дальности прицеливания на 8 с; без стаков."),
    2525: ("high", LIFELINE),
    3008: ("medium", "Slay: за победу над уникальным боссом +0,15 процентного пункта к шансу вампиризма до конца забега, до 10 стаков. Повторные фазы одного босса считаются одним убийством."),
    3009: ("medium", "Fleetfooted: эффекты замедления от врагов и паутины на Самире на 25% слабее. Заморозка, оглушение и геометрия комнаты действуют по правилам Isaac."),
    3032: ("medium", "Спустя каждые 5 удачных отдельных автоатак шанс крита повышается на 1 процентный пункт до +25%. Первый прямой автоудар в новой комнате даёт +30% к темпу на 6 с, КД 20 с."),
    3033: ("medium", WOUNDS),
    3036: ("medium", "Giant Slayer: до +15% прямого урона по цели, линейно от +0% при 40 максимального HP цели до +15% при 160 HP. Проверка по исходному HP врага, без шкалирования от оставшегося."),
    3046: ("medium", "Spectral Waltz: дальние автоатаки становятся спектральными и проходят сквозь камни и обычные препятствия. Стены комнаты останавливают снаряды. Коллизии Самиры сохраняются."),
    3053: ("high", "Claws: +0,35 урона. " + LIFELINE),
    3071: ("medium", "Carve: успешные прямые попадания 1 раз за выстрел или каст дают цели +3% получаемого прямого урона, до +15% на 6 с. Fervor: +0,06 скорости на 2 с после попадания, без суммирования с другими эффектами ускорения от попадания."),
    3072: ("high", "Ichorshield: успешный бросок кражи жизни с прямой автоатаки при полном красном здоровье создаёт временный щит на одно попадание. Не накапливается, истекает при выходе из комнаты, КД успешного вампиризма 8 с."),
    3073: ("medium", "Hexcharged: +30 единиц ускорения только R. Overdrive после R: +25 процентных пунктов к темпу и +10% к скорости на 8 с."),
    3078: ("medium", "Spellblade: следующая успешная автоатака в течение 4 с после каста получает +3 урона. КД 3 с."),
    3083: ("high", "Regen: зачистив две новые боевые комнаты подряд без потери здоровья, восполни ½ красного сердца; счётчик сбрасывается. Vitality: ещё ½ красного сердца за каждые 4 красных сердца от других предметов каталога, до +2 сердец."),
    3084: ("high", "Через 2 с рядом с врагом следующая автоатака по нему наносит ×1,5 урона. КД 10 с отдельно на каждого врага. Каждые 4 срабатывания по разным врагам дают ½ постоянного красного сердца без лимита за забег. Размер +3% за такое сердце."),
    3085: ("high", "Лишь прямой выстрел, нанёсший урон, выпускает до 2 болтов в иных врагов в 50 единицах. Каждый наносит 25% урона исходного попадания. Болты не критуют повторно и не запускают предметы, лечебные броски или новые болты."),
    3094: ("medium", "После 120 единиц пройденного пути следующий прямой выстрел получает +1,2 урона и +35% дальности прицеливания. Заряд не растёт при стоянии. Максимум один общий заряд Energized."),
    3095: ("medium", "Energized от 120 пройденных единиц или 6 отдельных успешных автоатак. Заряженный прямой выстрел наносит +1,4 урона и даёт +20% скорости на 1,5 с. Общий слот заряда с Firecannon и Voltaic."),
    3153: ("high", "Первое прямое попадание автоатаки добавляет 25% собственного урона Самиры. Три отдельные успешные автоатаки по одной цели замедляют её на 30% на 1 с, общий КД 6 с."),
    3158: ("low", "Ionian Insight действует на способности Самиры из базовых статов. В Isaac нет отдельных Summoner Spells, поэтому бонус к ним не переносится на заряды активного предмета."),
    3161: ("medium", "Dragonforce: +25 единиц ускорения Q/W/E. Focused Will: один стак за отдельный успешный каст, +3% прямого урона способностей на 6 с, до 4 стаков. Серия R или два взмаха W дают по одному стаку."),
    3170: ("medium", "Fleetfooted: замедления от врагов и паутины на 25% слабее. Noxian Fervor: +0,13 урона за каждые +0,10 скорости от предметов, до +0,65. Адаптивная сила у Самиры идёт в ветку AD."),
    3171: ("medium", "Каждый отдельный успешный каст даёт +8% скорости на 4 с, без стаков и повторов от W/R. Ускорение Summoner Spells не переносится на активный предмет."),
    3179: ("high", "Nightstalker: первое прямое попадание при готовом эффекте получает +1,5 урона. КД 8 с."),
    3181: ("high", "Skipper: каждая пятая удачная автоатака добавляет +4 урона."),
    3814: ("high", "Annul: блокирует один вражеский снаряд. Щит восстанавливается при входе в новую комнату или через 20 с боя. Не поглощает контакт, шипы, взрывы и самоповреждение."),
    6609: ("medium", WOUNDS),
    6610: ("high", "Первая прямая автоатака по уникальному боссу или мини-боссу в новой комнате гарантированно критует и лечит ½ красного сердца. Здоровье восстанавливается не более одного раза за комнату."),
    6672: ("medium", "Каждая третья успешная отдельная автоатака добавляет 50% собственного урона Самиры."),
    6673: ("high", LIFELINE),
    6675: ("medium", "За отдельную успешную автоатаку уменьшает оставшийся КД Q, W и E на 15%. Лимит одной проверки в 0,4 с, КД R не затрагивается."),
    6676: ("high", "Death: прямая атака добивает врага, оставившегося ниже 5% HP. Боссы только в финальной уязвимой фазе. Taxes: +1 монета при зачистке новой комнаты, если в ней было хотя бы одно срабатывание казни. Не больше 1 монеты за комнату."),
    6692: ("high", "Два различных источника прямого урона за 2 с дают щит на одно попадание на 2 с. Отдельный выстрел или каст считается один раз на все попадания, КД щита 12 с."),
    6694: ("medium", "Bitter Cold: прямое попадание способностью по врагу ниже половины здоровья замедляет его на 30% на 1 с. Одна проверка по цели за каст."),
    6695: ("medium", "Автоатаки Самиры уничтожают вражеские снаряды."),
    6696: ("medium", "Урон R увеличивается на 20%."),
    6697: ("medium", "Каждая зачистка новой боевой комнаты без получения урона навсегда даёт +0,1 урона в текущем забеге."),
    6699: ("high", "Galvanize: успешное прямое попадание умением заряжает следующий прямой выстрел, КД 8 с. Firmament: заряженный выстрел добавляет 40% собственного урона Самиры и даёт +4 летальности на 4 с. Использует общий заряд Energized."),
}

ISAAC_CONVERSIONS = {
    "ad": ("damage_flat", .04),
    "attack_speed_pct": ("attack_speed_pct", 1),
    "ability_haste": ("ability_haste", 1),
    "lethality": ("lethality_damage_bonus_pct", .5),
    "crit_chance_pct": ("crit_chance_pct", 1),
    "crit_damage_pct": ("crit_multiplier_bonus", .01),
    "move_speed_flat": ("move_speed_flat", .003),
    "move_speed_pct": ("move_speed_pct", 1),
    "armor_penetration_pct": ("armor_pen_damage_bonus_pct", .5),
    "lifesteal_pct": ("lifesteal_chance_pct", .25),
    "omnivamp_pct": ("omnivamp_chance_pct", .25),
    "tenacity_pct": ("iframes_pct", 1),
}
PRICE_ADJUSTMENTS = dict.fromkeys(BOOT_CAPSTONES, 3)
PRICE_RANGES = {"boots": (5, 15), "legendary": (15, 30)}
STAT_OVERRIDES = {
    3078: {"damage_flat": 3.33, "attack_speed_pct": 33, "ability_haste": 33, "health_red_hearts": 3},
}


def nearest_positive(value, divisor):
    return int(value / divisor + .5)


def convert_stats(item_id, numeric):
    stats = {key: round(numeric[source] * factor, 4)
             for source, (key, factor) in ISAAC_CONVERSIONS.items() if source in numeric}
    if numeric.get("hp"):
        hearts = max(1, nearest_positive(numeric["hp"], 200)) / 2
        stats["health_red_hearts"] = 2 if hearts == 1.5 else hearts
    stats.update(STAT_OVERRIDES.get(item_id, {}))
    return stats


def item_record(item_id, item, item_ru, source_url):
    description = item["description"]
    stats_lol = source_stats(description)
    numeric = parse_stats(stats_lol)
    info = {
        "id": item_id, "name_ru": item_ru["name"], "name_en": item["name"],
        "gold_lol": item["gold"]["total"],
        "maps": [map_id for map_id, allowed in item["maps"].items() if allowed],
        "stats_lol": stats_lol,
        "stats_lol_ru": source_stats(item_ru["description"]),
        "stats_lol_numeric": numeric,
        "source_url": source_url,
    }
    reason_code, reason = classify(item_id, item, numeric)
    if reason_code:
        return False, {**info, "reason_code": reason_code, "reason_ru": reason or REASONS[reason_code],
                       "description_lol": plain(description)}
    item_tier = tier(item_id, item)
    low, high = PRICE_RANGES[item_tier]
    price_adjustment = PRICE_ADJUSTMENTS.get(item_id, 0)
    passives = source_passives(description)
    if passives and item_id not in ADAPTATIONS:
        raise ValueError(f"Candidate {item_id} {item['name']} has no specific effect design: {passives}")
    if len(numeric) != len(stats_lol):
        raise ValueError(f"Unmapped candidate stats {item_id}: {stats_lol}")
    complexity, adaptation = ADAPTATIONS.get(
        item_id, ("low", "Действуют указанные базовые статы. У оригинала отдельной пассивки нет."))
    return True, {
        **info, "image_file": item["image"]["full"], "tier": item_tier, "price_coins": min(high, max(low, nearest_positive(info["gold_lol"], 140)) + price_adjustment),
        "price_adjustment_coins": price_adjustment,
        "stats_isaac": convert_stats(item_id, numeric), "passives_lol": passives,
        "passives_lol_ru": source_passives(item_ru["description"]),
        "adaptation_ru": adaptation, "complexity": complexity, "status": MECHANICS_STATUS,
    }


def build(metadata, data):
    version = metadata["version"]
    for language in LANGUAGES:
        if data[language]["version"] != version:
            raise ValueError(f"Unexpected patch for locale {language}")
    en, ru = (data[language]["data"] for language in LANGUAGES)
    if en.keys() != ru.keys():
        raise ValueError("Mismatching localized item IDs")
    items, excluded = [], []
    for item_id in sorted(en, key=int):
        keep, record = item_record(int(item_id), en[item_id], ru[item_id], metadata["sources"]["en_US"]["url"])
        (items if keep else excluded).append(record)
    if set(ADAPTATIONS) - {item["id"] for item in items}:
        raise ValueError("A handcrafted adaptation disappeared from the eligible list")
    return {
        **metadata,
        "scope": "Проверены все записи Riot Data Dragon. Пул магазина Isaac включает 38 легендарных предметов Ущелья призывателей (карта 11) и 8 пар ботинок, в том числе три финальных улучшения как самостоятельные предметы.",
        "mechanics_status": MECHANICS_STATUS,
        "rules": {
            "stat_conversion": {key: {"target": target, "factor": factor}
                                for key, (target, factor) in ISAAC_CONVERSIONS.items()},
            "health_per_half_heart": 200, "minimum_half_hearts": 1,
            "health_1_5_to_2": True, "stat_overrides_by_item_id": STAT_OVERRIDES,
            "gold_per_coin": 140, "price_limits": PRICE_RANGES,
            "price_formula_ru": "Округлить золото/140 до целого, поднять к минимуму категории, прибавить надбавку и ограничить максимумом категории. Улучшенные ботинки +3 монеты.",
            "source_note_ru": "Data Dragon местами показывает пустые переменные описаний пассивок или 0s вместо КД. Исходный текст сохраняется как есть. Числа Isaac предложены отдельно.",
            "base_crit_multiplier": 1.5, "max_crit_chance_pct": 100, "max_vamp_chance_pct": 5,
            "stat_stacking_ru": "Проценты суммируются в пределах одной характеристики. Дубли одних именных пассивок не складываются. Три подходящие финальные пары ботинок представлены как самостоятельные предложения, их улучшение не реализуется.",
            "vamp_success_cooldown_sec": 8,
            "damage_formula": "(nativeDamage + 0.04 * sumAD) * (1 + 0.005 * sumLethality + 0.5 * sumArmorPenFraction)",
            "damage_formula_note_ru": "Формула принимает исходные AD, lethality и armor penetration. В таблице результатов уже рассчитаны их надбавки Isaac, поэтому повторно конвертировать эти вычисленные надбавки нельзя.",
            "attack_interval_formula": "nativeAttackInterval / (1 + sumAttackSpeedPercent / 100)",
            "ability_cooldown_formula": "baseSeconds * 100 / (100 + abilityHaste)",
            "vamp_trigger_ru": "Успешный прямой AA для lifesteal, AA или нанесший урон каст для omnivamp. Один общий бросок на выстрел/семейство снарядов или каст, включая W и R и все цели. Боковые эффекты, огонь, неподходящие объекты и урон сверх уже погибшей цели не учитываются. Вампиризм даёт шанс восстановить ½ красного сердца; успешное восстановление запускает глобальный КД 8 с. Лишние доли урона не копятся.",
            "incoming_damage_trigger_ru": "Защитные и лечебные эффекты на получение урона требуют фактической потери здоровья от врага. Самоповреждение, машины доната и другие добровольные траты здоровья не запускают эффект.",
            "other_mode_scope": "Исключённые записи сохраняют ID, флаги карт и исходный текст. Активные предметы, модернизация и эксклюзивы альтернативных режимов рассмотрены для отбора, без проекта адаптации.",
        },
        "counts": {
            "total": len(en), "included": len(items), "excluded": len(excluded),
            "included_by_tier": dict(Counter(row["tier"] for row in items)),
            "excluded_by_reason": dict(Counter(row["reason_code"] for row in excluded)),
        },
        "items": items,
        "excluded": excluded,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch and fingerprint current Riot sources.")
    args = parser.parse_args()
    metadata, data = sources(args.refresh)
    result = build(metadata, data)
    write_json(OUTPUT, result)
    print(json.dumps({"version": result["version"], **result["counts"]}, indent=2))


if __name__ == "__main__":
    main()
