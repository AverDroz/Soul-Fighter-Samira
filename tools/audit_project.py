"""Read-only source checks. No mod or installer is loaded into Isaac."""
from pathlib import Path
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from lupa.lua54 import LuaRuntime


def main():
    base = ROOT / 'src/samira'
    lua = LuaRuntime(unpack_returned_tuples=True)
    compile_lua = lua.eval('function(s,n) local f,e=load(s,n); return f~=nil,e end')
    failures, missing = [], []
    py_count = lua_count = 0
    for p in base.rglob('*.py'):
        try:
            ast.parse(p.read_text('utf-8-sig'), filename=str(p))
            py_count += 1
        except SyntaxError as exc:
            failures.append({'file': str(p.relative_to(ROOT)), 'error': str(exc)})
    for p in (base / 'mod').rglob('*.lua'):
        text = p.read_text('utf-8-sig')
        ok, error = compile_lua(text, str(p.relative_to(base)))
        lua_count += 1
        if not ok:
            failures.append({'file': str(p.relative_to(ROOT)), 'error': error})
        for module in re.findall(r"include\(['\"](scripts\.[A-Za-z0-9_]+)['\"]\)", text):
            target = base / 'mod' / (module.replace('.', '/') + '.lua')
            if not target.is_file():
                missing.append({'file': str(p.relative_to(base)), 'module': module})
    identity = json.loads((base / 'hero.json').read_text('utf8'))
    identity_ok = (
        ET.parse(base / 'mod/metadata.xml').findtext('directory') == 'samira_isaac'
        and ET.parse(base / 'mod/content/players.xml').find('player').get('name') == 'Samira'
        and identity['telemetry_prefix'] == '[SAMIRA_EXTERNAL] '
    )
    completed = subprocess.run([sys.executable, str(base / 'tools/check_project.py')],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1'))
    (ROOT / 'work/native-check.log').write_text(completed.stdout + completed.stderr, encoding='utf8')
    report = {'python_files_parsed': py_count, 'lua_files_compiled': lua_count,
        'syntax_failures': failures, 'identity_ok': identity_ok,
        'missing_literal_include_modules': missing,
        'upstream_check_project_exit_code': completed.returncode,
        'upstream_check_project_log': 'work/native-check.log',
        'samira_assets_imported': False, 'samira_gameplay_implemented': False,
        'live_game_test': False, 'installable': False}
    (ROOT / 'docs/source-check-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
