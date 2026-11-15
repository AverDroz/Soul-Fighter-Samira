"""Export the existing GLB clip catalogue; no new images or baked animations."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'external'))
from model import Model
model=Model(ROOT/'reference/source/model.glb')
catalogue=dict(sorted(model.durations.items()))
(ROOT/'mod/scripts/samira_external_actions.lua').write_text(
    '-- Generated from reference/source/model.glb by tools/export_external_actions.py\nreturn {\n'+
    ''.join(f' [{json.dumps(name)}]={duration:.9f},\n' for name,duration in catalogue.items())+'}\n',encoding='utf-8')
(ROOT/'external/actions.json').write_text(json.dumps(catalogue,indent=2),encoding='utf-8')
print(f'Exported {len(catalogue)} existing animation names and durations')
