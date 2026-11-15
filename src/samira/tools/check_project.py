"""Fast identity/syntax/asset checks before the full example regression suite."""
import ast,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run():
    from check_native_resources import check
    check(ROOT/'mod')
    d=json.loads((ROOT/'hero.json').read_text());slug,name=d['id'],d['name']
    assert slug!='aatrox'
    metadata=ET.parse(ROOT/'mod/metadata.xml')
    assert metadata.findtext('directory')==d['mod_directory']
    assert ET.parse(ROOT/'mod/content/players.xml').find('player').get('name')==name
    for p in ROOT.rglob('*.py'):
        if not any(part in ('.venv','build','dist','__pycache__') for part in p.relative_to(ROOT).parts):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    for p in (ROOT/'mod').rglob('*.lua'):
        s=p.read_text(encoding='utf8')
        assert 'scripts.aatrox_' not in s and '[AATROX_EXTERNAL]' not in s and 'aatrox_external_link' not in s,p
    for rel,token in [('external/bridge.py',d['telemetry_prefix']),('companion/companion.py',d['telemetry_prefix']),
                      ('companion/bridge.c',d['ini']),('companion/installer.py',d['dll']),
                      ('mod/scripts/'+slug+'_external.lua',d['status_directory'])]:
        assert token in (ROOT/rel).read_text(encoding='utf8'),(rel,token)
    assert 'aatrox_ground_q2' in (ROOT/'external/model.py').read_text(),'Original GLB clip names must not be blindly renamed'
    sounds=ET.parse(ROOT/'mod/content/sounds.xml').getroot()
    for sound in sounds:
        assert sound.get('name').startswith(name+' ')
        for sample in sound:assert (ROOT/'mod/resources'/sounds.get('root')/sample.get('path')).is_file()
    print('Identity, Python syntax, original clip names and all registered audio paths passed:',slug)

if __name__=='__main__':run()
