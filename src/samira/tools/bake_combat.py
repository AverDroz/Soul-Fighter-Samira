"""Only bake newly requested action sets; keep the existing combat sheets."""
import bake_model as b
from PIL import Image
import sys
clips={'SheathedIdle':'Sheathe_Idle','SheathedWalk':'Sheathe_Run_Slow','Draw':'Unsheath_Upper',
       'Sheathe':'Sheathe','W':'Spell3','RStart':'Spell4','RIdle':'Idle_Ult_Base','RWalk':'Run_Ult',
       'RAttack':'Attack1_Ult','RQ1':'Q1_Ult','RQ2':'Q2_Ult','RQ3':'Q3_Ult','RDash':'Spell_Dash_Ult_In'}
normal=b.parts.copy();wing=[]
for p in b.prim:
    mat=b.g['materials'][p['material']]
    if mat['name']=='Wings':
        tid=b.g['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
        wing.append((b.acc(p['indices']).reshape(-1,3),b.textures[tid]))
names=sys.argv[1:] or clips
for name in names:
    file=b.OUT/(name.lower()+'.anm2')
    if file.exists():print(name,'cached',flush=True);continue
    ult=name.startswith('R');b.parts=normal+wing if ult else normal
    b.SIZE=320 if ult or name in ('W','Sheathe') else 160;b.PIVOT=(b.SIZE//2,240 if b.SIZE==320 else 116)
    count=12;sheet=Image.new('RGBA',(b.SIZE*count,b.SIZE*8));anims={}
    loop=name in ('SheathedIdle','SheathedWalk','RIdle','RWalk')
    poses=[b.pose(clips[name],f/(count if loop else count-1)) for f in range(count)]
    for direction in range(8):
        anims[name+str(direction)]=[]
        for f,vertices in enumerate(poses):
            im=b.render(vertices,direction);box=im.getbbox()
            assert box and box[0]>0 and box[1]>0 and box[2]<b.SIZE and box[3]<b.SIZE,(name,direction,f,box)
            sheet.alpha_composite(im,(f*b.SIZE,direction*b.SIZE));anims[name+str(direction)].append((f*b.SIZE,direction*b.SIZE))
    sheet.save(b.OUT/(name.lower()+'.png'));b.actor(file,name.lower()+'.png',anims,b.PIVOT,b.SIZE)
    print(name,'baked',flush=True)
