"""Export bind mesh, inverse bind matrices and local bone keys, not rendered poses."""
import bake_model as b
import numpy as np,json,math
from export_mesh_probe import lua
order=[]
def visit(i):
    order.append(i)
    for child in b.nodes[i].get('children',[]):visit(child)
for i in range(len(b.nodes)):
    if i not in b.parents:visit(i)
mapping={old:i+1 for i,old in enumerate(order)}
defaults=[];parents=[]
for i in order:
    n=b.nodes[i];defaults.append(n.get('translation',[0,0,0])+n.get('rotation',[0,0,0,1])+n.get('scale',[1,1,1]))
    parents.append(mapping[b.parents[i]] if i in b.parents else 0)
used=sorted({int(i) for indices,_ in b.parts for f in indices for i in f});vm={old:i+1 for i,old in enumerate(used)}
vertices=[]
for i in used:
    v=[*b.pos[i],*b.uv[i]]
    for joint,weight in zip(b.joints[i],b.weights[i]):v.extend([int(joint)+1,float(weight)])
    vertices.append(v)
faces=[[vm[int(i)] for i in f]+[mat] for mat,(indices,_) in enumerate(b.parts,1) for f in indices]
clips={}
for name,clip in [('idle','Sheathe_Idle'),('walk','Sheathe_Run_Slow')]:
    anim=b.animations[clip];duration=max(float(b.acc(s['input'])[-1,0]) for s in anim['samplers'])
    tracks=[]
    for ch in anim['channels']:
        sm=anim['samplers'][ch['sampler']];tracks.append((mapping[ch['target']['node']]-1,ch['target']['path'],b.acc(sm['input'])[:,0],b.acc(sm['output'])))
    count=math.ceil(duration*30);frames=[]
    for frame in range(count):
        trs=np.array(defaults,dtype=float);time=duration*frame/count
        for node,path,times,values in tracks:
            i=max(0,min(len(times)-1,int(np.searchsorted(times,time,side='right'))-1));j=min(i+1,len(times)-1)
            a=values[i].copy();z=values[j].copy();alpha=0 if i==j else (time-times[i])/(times[j]-times[i])
            if path=='rotation' and a@z<0:z=-z
            v=a*(1-alpha)+z*alpha
            if path=='rotation':v/=max(1e-9,np.linalg.norm(v))
            start={'translation':0,'rotation':3,'scale':7}[path];trs[node,start:start+len(v)]=v
        frames.append(trs.flatten().tolist())
    clips[name]=dict(duration=duration,frames=frames)
def clean(x):
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)):return round(float(x),6)
    if isinstance(x,np.integer):return int(x)
    return x
text='return {parents='+lua(parents)+',jointNodes='+lua([mapping[i] for i in b.skin['joints']])+',inverse='+lua(clean(b.ibm[:,:3,:].reshape(-1,12).tolist()))+',vertices='+lua(clean(vertices))+',faces='+lua(faces)+',clips={'
text+=','.join(k+'={duration='+str(v['duration'])+',frames='+lua(clean(v['frames']))+'}' for k,v in clips.items())+'}}\n'
(b.ROOT/'mod/scripts/samira_skeleton_data.lua').write_text(text,encoding='utf-8')
# Small exact-pose references for checking Lua matrix order and skin weights offline.
ref={}
for name,clip in [('idle','Sheathe_Idle'),('walk','Sheathe_Run_Slow')]:
    ref[name]=b.pose(clip,.25)[used].tolist()
(b.ROOT/'reference/skeleton-reference.json').write_text(json.dumps(ref))
print('Skeleton data:',len(vertices),'vertices,',len(parents),'nodes;',round(len(text)/1048576,2),'MiB')
