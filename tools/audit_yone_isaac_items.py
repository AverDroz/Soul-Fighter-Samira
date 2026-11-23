"""Inventory stock Isaac item IDs and suggest Yone synergy checks from local data."""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree


REGISTRIES = {'collectible': 'CollectibleType', 'trinket': 'TrinketType'}
XML_KINDS = {'active', 'passive', 'familiar', 'trinket'}
STAT_CACHES = {'damage', 'firedelay', 'speed', 'range', 'luck', 'shotspeed', 'size', 'all'}
TEAR_CACHES = {'tearflag', 'tearcolor', 'shotspeed', 'all'}
EID_TABLES = {'repCollectibles': 'collectible', 'collectibles': 'collectible',
              'repTrinkets': 'trinket', 'trinkets': 'trinket'}
EID_ROW = re.compile(r'^\s*(?:\[\d+\]\s*=\s*)?\{\s*"(\d+)"\s*,\s*"(?:\\.|[^"\\])*"\s*,\s*"((?:\\.|[^"\\])*)"')
TEXT_HINTS = {
    'status': r'\b(?:poison|burn|freeze|petrif\w*|fear|charm|slow|confus\w*|shrink)\b',
    'tear-hit': r'\b(?:on (?:impact|hit)|when (?:\w+ ){0,3}hit|(?:tears|shots) (?:split|explode|stick|pierce|bounce))\b',
    'tear-path': r'\b(?:homing|boomerang|spectral|orbit|spiral|trajectory|wavy|wiggle|bounce)\b',
    'fire-input': r'\b(?:(?:while|after|when) (?:\w+ ){0,3}(?:firing|shooting)|charged shot|fire button|shooting direction)\b',
    'kill': r'\b(?:(?:on|after|when) kill\w*|enemy dies|enemies die)\b',
    'independent': r'\b(?:room clear|taking damage|on pickup|per floor|passive familiar|new room)\b',
    'weapon': r'\b(?:replaces? (?:\w+ ){0,4}(?:tears|weapon)|instead of (?:\w+ ){0,3}tears)\b',
}


def item_enums(path):
    text = path.read_text(encoding='utf-8-sig')
    stock, aliases = {}, defaultdict(list)
    for kind, registry in REGISTRIES.items():
        block = re.search(rf'^\s*{registry}\s*=\s*\{{(.*?)^\s*\}}', text, re.MULTILINE | re.DOTALL)
        if not block:
            raise ValueError(f'No {registry} table in {path}')
        upper = kind.upper()
        bounds = dict(re.findall(r'^\s*(NUM_\w+)\s*=\s*(\d+)', block[1], re.MULTILINE))
        end = int(bounds[f'NUM_{upper}S'])
        for name, value in re.findall(rf'^\s*({upper}_\w+)\s*=\s*(0x[\da-fA-F]+|\d+)', block[1], re.MULTILINE):
            item_id = int(value, 0)
            if 0 < item_id < end:
                key = kind, item_id
                if key in stock:
                    aliases[key].append(name)
                else:
                    stock[key] = name
        for name, value in re.findall(rf'^\s*{registry}\.({upper}_\w+)\s*=\s*(\d+)\b', text, re.MULTILINE):
            aliases[kind, int(value)].append(name)
    return stock, aliases


def item_xml(paths):
    items = {}
    for path in paths:
        for element in ElementTree.parse(path).getroot():
            if element.tag in XML_KINDS and element.get('id') is not None:
                kind = 'trinket' if element.tag == 'trinket' else 'collectible'
                items[kind, int(element.get('id'))] = (element.tag, element.attrib)
    return items


def eid_descriptions(directory):
    entries = {}
    for edition in ('ab+', 'rep', 'rep+'):
        path = directory / edition / 'en_us.lua'
        kind = None
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            table = re.match(r'^(?:local\s+|EID\.descriptions\[languageCode\]\.)(\w+)\s*=\s*\{', line)
            if table:
                kind = EID_TABLES.get(table[1])
            elif line.startswith('}'):
                kind = None
            elif kind and (row := EID_ROW.match(line)):
                entries[kind, int(row[1])] = (edition, row[2])
    return entries


def audit_hints(item_type, attributes, description):
    cache = set(attributes.get('cache', '').split())
    hints = set()
    if item_type == 'active':
        hints.add('active-use')
    if item_type == 'familiar':
        hints.add('familiar')
    if cache & STAT_CACHES:
        hints.add('native-stat')
    if cache & TEAR_CACHES:
        hints.add('tear-cache')
    if 'weapon' in cache:
        hints.add('weapon')
    for key, pattern in TEXT_HINTS.items():
        if re.search(pattern, description, re.IGNORECASE):
            hints.add(key)
    return sorted(hints) or ['manual-review']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enums', type=Path, required=True, help='Installed resources/scripts/enums.lua')
    parser.add_argument('--items', type=Path, action='append', default=[],
                        help='Extracted items.xml, repeat in load order')
    parser.add_argument('--eid', type=Path, help='Local EID descriptions directory, for keyword hints only')
    parser.add_argument('--summary', action='store_true', help='Print counts only')
    args = parser.parse_args()

    stock, aliases = item_enums(args.enums)
    items = item_xml(args.items)
    descriptions = eid_descriptions(args.eid) if args.eid else {}
    counts = Counter()
    coverage = Counter()
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    if not args.summary:
        writer.writerow(['registry', 'id', 'enum', 'aliases', 'registry_state', 'xml_type', 'cache',
                         'eid_hint_source', 'candidate_checks'])
    rows = stock.keys() | aliases.keys() | items.keys()
    for key in sorted(rows):
        if key in stock:
            state = 'obsolete' if stock[key].endswith('_OBSOLETE') else 'stock'
        else:
            state = 'xml-only' if key in items else 'alias-only'
        item_type, attributes = items.get(key, ('', {}))
        counts[key[0], state, item_type or 'missing-xml'] += 1
        coverage[key[0], 'EID entries'] += key in descriptions
        coverage[key[0], 'numeric compatibility aliases'] += len(aliases[key])
        edition, description = descriptions.get(key, ('', ''))
        hints = audit_hints(item_type, attributes, description)
        if not args.summary:
            writer.writerow([*key, stock.get(key, ''), ','.join(aliases[key]), state, item_type,
                             attributes.get('cache', ''), edition, ','.join(hints)])

    summary = sys.stdout if args.summary else sys.stderr
    for (registry, state, item_type), count in sorted(counts.items()):
        print(f'{registry} {state} {item_type}: {count}', file=summary)
    for (registry, group), count in sorted(coverage.items()):
        print(f'{registry} {group}: {count}', file=summary)


if __name__ == '__main__':
    main()
