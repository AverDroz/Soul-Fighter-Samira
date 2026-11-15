"""Bake the original animated GLB into Isaac sprites; no 3D runtime dependency."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import struct,json,io,math,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'mod/resources/gfx/samira'
blob=(ROOT/'reference/source/model.glb').read_bytes(); n=struct.unpack_from('<I',blob,12)[0]
g=json.loads(blob[20:20+n]); buf=blob[28+n:]
def acc(index):
    a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
    dtype={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    step=v.get('byteStride',np.dtype(dtype).itemsize*width)
    return np.ndarray((a['count'],width),dtype,buf,v.get('byteOffset',0)+a.get('byteOffset',0),strides=(step,np.dtype(dtype).itemsize)).copy()
def trs(t,r,s):
    x,y,z,w=r; m=np.eye(4)
    m[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])*s
    m[:3,3]=t;return m
nodes=g['nodes'];parents={c:i for i,n in enumerate(nodes) for c in n.get('children',[])}
skin=g['skins'][0]; ibm=acc(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
prim=g['meshes'][0]['primitives'];a=prim[0]['attributes'];pos=acc(a['POSITION']);uv=acc(a['TEXCOORD_0'])
joints=acc(a['JOINTS_0']).astype(int);weights=acc(a['WEIGHTS_0']);hp=np.column_stack((pos,np.ones(len(pos))))
textures=[]
for im in g['images']:
    v=g['bufferViews'][im['bufferView']];start=v.get('byteOffset',0)
    textures.append(np.array(Image.open(io.BytesIO(buf[start:start+v['byteLength']])).convert('RGBA')))
parts=[]
for p in prim:
    mat=g['materials'][p['material']]
    if mat['name'] in ('Wings','Banner'):continue
    tid=g['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
    parts.append((acc(p['indices']).reshape(-1,3),textures[tid]))
animations={x['name']:x for x in g['animations']}
def pose(name,fraction):
    anim=animations[name]; tracks={}; end=max(float(acc(s['input'])[-1,0]) for s in anim['samplers'])
    for ch in anim['channels']:
        sm=anim['samplers'][ch['sampler']];times=acc(sm['input'])[:,0];values=acc(sm['output']);t=end*fraction
        k=max(0,min(len(times)-1,int(np.searchsorted(times,t,side='right'))-1));k2=min(k+1,len(times)-1)
        v=values[k].copy(); v2=values[k2].copy();path=ch['target']['path']
        if path=='rotation' and np.dot(v,v2)<0:v2=-v2
        blend=0 if k==k2 else (t-times[k])/(times[k2]-times[k]);v=v*(1-blend)+v2*blend
        if path=='rotation':v/=max(1e-9,np.linalg.norm(v))
        tracks.setdefault(ch['target']['node'],{})[path]=v
    worlds={}
    def world(i):
        if i in worlds:return worlds[i]
        nd=nodes[i];tr=tracks.get(i,{})
        local=trs(tr.get('translation',nd.get('translation',[0,0,0])),tr.get('rotation',nd.get('rotation',[0,0,0,1])),tr.get('scale',nd.get('scale',[1,1,1])))
        worlds[i]=world(parents[i])@local if i in parents else local;return worlds[i]
    matrices=np.array([world(i) for i in skin['joints']])@ibm
    verts=np.zeros((len(pos),4))
    for c in range(4):verts+=np.einsum('nij,nj->ni',matrices[joints[:,c]],hp)*weights[:,c,None]
    return verts[:,:3]
SIZE=160; PIVOT=(80,116); SCALE=32
def render(verts,direction):
    yaw=direction*math.tau/8; cs,sn=math.cos(yaw),math.sin(yaw)
    p=verts@np.array([[cs,0,sn],[0,1,0],[-sn,0,cs]]).T
    elev=math.radians(35); cam=np.array([0,math.sin(elev),math.cos(elev)]); up=np.array([0,math.cos(elev),-math.sin(elev)])
    proj=np.column_stack((PIVOT[0]+p[:,0]*SCALE,PIVOT[1]-p@up*SCALE,p@cam))
    rgba=np.zeros((SIZE,SIZE,4),dtype=np.uint8);depth=np.full((SIZE,SIZE),-1e9)
    for indices,tex in parts:
        th,tw=tex.shape[:2]
        for ids in indices:
            v=proj[ids]; coords=uv[ids]
            x0=max(0,int(np.floor(v[:,0].min())));x1=min(SIZE,int(np.ceil(v[:,0].max())))
            y0=max(0,int(np.floor(v[:,1].min())));y1=min(SIZE,int(np.ceil(v[:,1].max())))
            if x1<=x0 or y1<=y0:continue
            den=(v[1,1]-v[2,1])*(v[0,0]-v[2,0])+(v[2,0]-v[1,0])*(v[0,1]-v[2,1])
            if abs(den)<1e-8:continue
            yy,xx=np.mgrid[y0:y1,x0:x1];xx=xx+.5;yy=yy+.5
            aa=((v[1,1]-v[2,1])*(xx-v[2,0])+(v[2,0]-v[1,0])*(yy-v[2,1]))/den
            bb=((v[2,1]-v[0,1])*(xx-v[2,0])+(v[0,0]-v[2,0])*(yy-v[2,1]))/den;cc=1-aa-bb
            z=aa*v[0,2]+bb*v[1,2]+cc*v[2,2]
            tx=np.clip(((aa*coords[0,0]+bb*coords[1,0]+cc*coords[2,0])*tw).astype(int),0,tw-1)
            ty=np.clip(((aa*coords[0,1]+bb*coords[1,1]+cc*coords[2,1])*th).astype(int),0,th-1)
            sample=tex[ty,tx].copy(); sample[:,:,3]=255
            mask=(aa>=0)&(bb>=0)&(cc>=0)&(z>depth[y0:y1,x0:x1]);depth[y0:y1,x0:x1][mask]=z[mask];rgba[y0:y1,x0:x1][mask]=sample[mask]
    return Image.fromarray(rgba)
def actor(path,sheet,anims,pivot=PIVOT,frame_size=SIZE):
    root=E.Element('AnimatedActor');E.SubElement(root,'Info',CreatedBy='Samira sprite baker',Version='1',Fps='30')
    content=E.SubElement(root,'Content');s=E.SubElement(content,'Spritesheets');E.SubElement(s,'Spritesheet',Path=sheet,Id='0')
    l=E.SubElement(content,'Layers');E.SubElement(l,'Layer',Name='body',Id='0',SpritesheetId='0');E.SubElement(content,'Nulls');E.SubElement(content,'Events')
    aa=E.SubElement(root,'Animations',DefaultAnimation=next(iter(anims)))
    for name,frames in anims.items():
        an=E.SubElement(aa,'Animation',Name=name,FrameNum=str(len(frames)),Loop='true');ra=E.SubElement(an,'RootAnimation')
        attr=dict(XPosition='0',YPosition='0',XScale='100',YScale='100',Rotation='0',RedTint='255',GreenTint='255',BlueTint='255',AlphaTint='255',RedOffset='0',GreenOffset='0',BlueOffset='0',Delay='1',Visible='true',Interpolated='false')
        E.SubElement(ra,'Frame',**(attr|{'Delay':str(len(frames))}));la=E.SubElement(an,'LayerAnimations');layer=E.SubElement(la,'LayerAnimation',LayerId='0',Visible='true')
        for x,y in frames:E.SubElement(layer,'Frame',**attr,XCrop=str(x),YCrop=str(y),Width=str(frame_size),Height=str(frame_size),XPivot=str(pivot[0]),YPivot=str(pivot[1]))
        E.SubElement(an,'NullAnimations');E.SubElement(an,'Triggers')
    E.indent(root);E.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
def main():
    global SIZE,PIVOT
    import sys
    OUT.mkdir(parents=True,exist_ok=True)
    clips={'Idle':'Unsheath_Idle01','Walk':'Unsheath_run01','Attack':'Attack1','Q1':'Q1_Ult','Q2':'aatrox_ground_q2','Q3':'Q3_Ult','Dash':'Spell_Dash_walking_In'}
    if '--preview' in sys.argv:
        v=pose(clips['Idle'],0);print('bounds',v.min(0),v.max(0));render(v,0).resize((640,640)).save(ROOT/'reference/model-preview.png');return
    preview=Image.new('RGBA',(320*7,320*3),(32,27,34,255))
    only=next((a.split('=',1)[1].split(',') for a in sys.argv if a.startswith('--only=')),None)
    for ci,(name,clip) in enumerate(clips.items()):
        if only and name not in only:continue
        SIZE=320 if name.startswith('Q') else 160
        PIVOT=(160,240) if SIZE==320 else (80,116)
        frames=12; sheet=Image.new('RGBA',(SIZE*frames,SIZE*8));anims={}
        posed=[pose(clip,f/(frames if name in ('Idle','Walk') else frames-1)) for f in range(frames)]
        for d in range(8):
            anims[name+str(d)]=[]
            for f,v in enumerate(posed):
                im=render(v,d);sheet.alpha_composite(im,(f*SIZE,d*SIZE));anims[name+str(d)].append((f*SIZE,d*SIZE))
                bb=im.getbbox()
                assert bb and bb[0]>0 and bb[1]>0 and bb[2]<SIZE and bb[3]<SIZE,(name,d,f,'clipped',bb)
                if d==0 and f in (0,5,9):preview.alpha_composite(im,(ci*320,(0,5,9).index(f)*320))
        sheet.save(OUT/(name.lower()+'.png'));actor(OUT/(name.lower()+'.anm2'),name.lower()+'.png',anims,PIVOT,SIZE);print(name,'baked',flush=True)
    preview.save(ROOT/'reference'/('q-preview.png' if only else 'animation-preview.png'))
if __name__=='__main__':main()
