"""Small static-pose mesh for runtime projection; no bone system or model dependency in game."""
from bake_model import ROOT,pose,uv,parts
from PIL import Image
import json
v=pose('Unsheath_Idle01',0);used=sorted({int(i) for indices,_ in parts for face in indices for i in face})
mapping={old:i+1 for i,old in enumerate(used)}
vertices=[[round(float(x),5) for x in (*v[i],*uv[i])] for i in used]
faces=[];textures=[]
out=ROOT/'mod/resources/gfx/samira/probe';out.mkdir(parents=True,exist_ok=True)
for material,(indices,tex) in enumerate(parts,1):
    tex=tex.copy();tex[:,:,3]=255
    Image.fromarray(tex).save(out/f'material{material}.png')
    textures.append(f'gfx/samira/probe/material{material}.png')
    for face in indices:faces.append([mapping[int(i)] for i in face]+[material])
def lua(a):
    if isinstance(a,list):return '{'+','.join(lua(x) for x in a)+'}'
    return json.dumps(a)
(ROOT/'mod/scripts/samira_mesh.lua').write_text('return {vertices='+lua(vertices)+',faces='+lua(faces)+',textures='+lua(textures)+'}\n',encoding='utf-8')
print(f'Probe: {len(vertices)} vertices, {len(faces)} triangles, {len(textures)} materials')
