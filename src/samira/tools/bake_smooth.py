"""30 samples/second from original bones; vectorized rasterization and tight atlases."""
import bake_model as b
import numpy as np
from PIL import Image
import math,time,json,xml.etree.ElementTree as E
clips={'Idle':'Unsheath_Idle01','Walk':'Unsheath_run01','Attack':'Attack1',
 'Q1':'Q1_Ult','Q2':'aatrox_ground_q2','Q3':'Q3_Ult','Dash':'Spell_Dash_walking_In',
 'SheathedIdle':'Sheathe_Idle','SheathedWalk':'Sheathe_Run_Slow','Draw':'Unsheath_Upper','Sheathe':'Sheathe',
 'W':'Spell3','RStart':'Spell4','RIdle':'Idle_Ult_Base','RWalk':'Run_Ult','RAttack':'Attack1_Ult',
 'RQ1':'Q1_Ult','RQ2':'Q2_Ult','RQ3':'Q3_Ult','RDash':'Spell_Dash_Ult_In','Death':'Death'}
normal=b.parts.copy();wings=[]
for p in b.prim:
    mat=b.g['materials'][p['material']]
    if mat['name']=='Wings':
        tid=b.g['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
        wings.append((b.acc(p['indices']).reshape(-1,3),b.textures[tid]))

def render(verts,direction,parts,size=480,pivot=(240,360),scale=48):
    yaw=direction*math.tau/8;cs,sn=math.cos(yaw),math.sin(yaw)
    p=verts@np.array([[cs,0,sn],[0,1,0],[-sn,0,cs]]).T;e=math.radians(35)
    proj=np.column_stack((pivot[0]+p[:,0]*scale,pivot[1]-p@np.array([0,math.cos(e),-math.sin(e)])*scale,p@np.array([0,math.sin(e),math.cos(e)])))
    depth=np.full(size*size,-np.inf);rgba=np.zeros((size*size,4),np.uint8)
    for indices,tex in parts:
        v=proj[indices];coords=b.uv[indices]
        lo=np.maximum(0,np.floor(v[:,:,:2].min(axis=1)).astype(int));hi=np.minimum(size,np.ceil(v[:,:,:2].max(axis=1)).astype(int))
        wh=np.maximum(0,hi-lo);counts=wh[:,0]*wh[:,1]
        starts=np.cumsum(counts)-counts;ids=np.repeat(np.arange(len(indices)),counts)
        local=np.arange(len(ids))-np.repeat(starts,counts)
        x=lo[ids,0]+local%wh[ids,0];y=lo[ids,1]+local//wh[ids,0];q=v[ids]
        den=(q[:,1,1]-q[:,2,1])*(q[:,0,0]-q[:,2,0])+(q[:,2,0]-q[:,1,0])*(q[:,0,1]-q[:,2,1])
        den=np.where(np.abs(den)>1e-8,den,np.nan)
        a=((q[:,1,1]-q[:,2,1])*(x+.5-q[:,2,0])+(q[:,2,0]-q[:,1,0])*(y+.5-q[:,2,1]))/den
        c=((q[:,2,1]-q[:,0,1])*(x+.5-q[:,2,0])+(q[:,0,0]-q[:,2,0])*(y+.5-q[:,2,1]))/den;d=1-a-c
        mask=(a>=0)&(c>=0)&(d>=0)
        ids=ids[mask];a=a[mask];c=c[mask];d=d[mask];pix=y[mask]*size+x[mask];q=q[mask]
        z=a*q[:,0,2]+c*q[:,1,2]+d*q[:,2,2];old=depth[pix].copy();np.maximum.at(depth,pix,z)
        visible=(z==depth[pix])&(z>old)
        ids=ids[visible];a=a[visible];c=c[visible];d=d[visible];pix=pix[visible]
        uv=coords[ids];th,tw=tex.shape[:2]
        tx=np.clip(((a*uv[:,0,0]+c*uv[:,1,0]+d*uv[:,2,0])*tw).astype(int),0,tw-1)
        ty=np.clip(((a*uv[:,0,1]+c*uv[:,1,1]+d*uv[:,2,1])*th).astype(int),0,th-1)
        rgba[pix]=tex[ty,tx];rgba[pix,3]=255
    return Image.fromarray(rgba.reshape(size,size,4))

def bake(name,clip):
    start=time.monotonic();out=b.OUT;metadata=out/(name.lower()+'.smooth.json')
    if metadata.exists():return json.loads(metadata.read_text())
    anim=b.animations[clip];duration=max(float(b.acc(s['input'])[-1,0]) for s in anim['samplers'])
    count=max(30,math.ceil(duration*30));loop=name in ('Idle','Walk','SheathedIdle','SheathedWalk','RIdle','RWalk')
    poses=[b.pose(clip,f/(count if loop else count-1)) for f in range(count)]
    frames=[];anims={};parts=normal+wings if name.startswith('R') else normal
    canvas=720 if name=='Death' else 480;pivot=(canvas//2,canvas*3//4)
    for direction in range(8):
        anims[name+str(direction)]=[]
        for i,v in enumerate(poses):
            im=render(v,direction,parts,size=canvas,pivot=pivot);box=im.getbbox()
            assert box and min(box[:2])>0 and max(box[2:])<canvas,(name,direction,i,box)
            x,y,r,bt=box;x-=1;y-=1;r+=1;bt+=1;tile=im.crop((x,y,r,bt))
            frames.append((tile,(pivot[0]-x,pivot[1]-y)));anims[name+str(direction)].append(len(frames)-1)
    # One atlas per action, never exceeding 4096; cropped frames retain their original foot pivot.
    for width in (2048,4096):
        x=y=row=0;packed=[]
        for im,pivot in frames:
            if x+im.width+1>width:x=0;y+=row+1;row=0
            packed.append((x,y,im,pivot));x+=im.width+1;row=max(row,im.height)
        height=y+row
        if height<=4096:break
    assert height<=4096,(name,height)
    sheet=Image.new('RGBA',(width,height))
    for x,y,im,_ in packed:sheet.alpha_composite(im,(x,y))
    path=out/(name.lower()+'.anm2');b.actor(path,name.lower()+'.png',{k:[(0,0)]*len(v) for k,v in anims.items()},(0,0),1)
    t=E.parse(path)
    for anim in t.findall('Animations/Animation'):
        anim.set('Loop','true' if loop else 'false')
        for f,idx in zip(anim.findall('.//LayerAnimation/Frame'),anims[anim.get('Name')]):
            x,y,im,pivot=packed[idx]
            for k,val in dict(XCrop=x,YCrop=y,Width=im.width,Height=im.height,XPivot=pivot[0],YPivot=pivot[1]).items():f.set(k,str(val))
    sheet.save(out/(name.lower()+'.png'));t.write(path,encoding='utf-8',xml_declaration=True)
    data=dict(frames=count,duration=duration,scale=2/3,pixels=width*height)
    metadata.write_text(json.dumps(data));print(name,count,'frames/direction',round(time.monotonic()-start,1),'sec',flush=True);return data

if __name__=='__main__':
    import sys
    if '--benchmark' in sys.argv:
        v=b.pose('Unsheath_run01',.3);start=time.monotonic();im=render(v,0,normal,size=160,pivot=(80,116),scale=32)
        print('fast seconds',time.monotonic()-start);ref=b.render(v,0)
        print('different pixels',np.any(np.array(im)!=np.array(ref),axis=2).sum());im.save(b.ROOT/'reference/fast-render-check.png')
    else:
        data={name:bake(name,clip) for name,clip in clips.items()}
        lua='return {'+','.join('["'+k+'"]={frames='+str(v['frames'])+',duration='+str(v['duration'])+',scale='+str(v['scale'])+'}' for k,v in data.items())+'}\n'
        (b.ROOT/'mod/scripts/samira_animation_data.lua').write_text(lua)
        print('All actions rebuilt; RGBA MiB',round(sum(v['pixels']*4 for v in data.values())/1048576,1),flush=True)
