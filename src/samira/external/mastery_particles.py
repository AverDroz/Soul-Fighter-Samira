"""Original mastery emitters; front-facing screen-space adapter derived from client_vfx.py.

Supports source curves, birth distributions, quads, SCB meshes, sprite atlases,
UV scrolling, palette lookup and alpha erosion. This is an adapter, not Riot's
renderer: scene distortion, stencil and skeletal attachment shaders are omitted.
"""
from pathlib import Path
import json,math,zlib
import numpy as np
from PIL import Image

VS='''#version 330
in vec3 vertex;in vec2 uv;
in vec3 center;in vec3 size;in vec3 rotation;in vec4 ink;
in vec2 scroll;in float frame;in float erosion;in float paletteRow;in vec2 multScroll;
uniform vec2 viewport,origin,facing,ground,divisions,multDivisions;
uniform float units,uvRotation;uniform vec2 uvScale;uniform int billboard,indicatorFlipV,sourceRotationOrder;
uniform vec3 geometryScale,geometryOffset;
out vec2 tc;out vec2 mtc;out vec4 tint;out float erode;out float row;
vec3 rotate3(vec3 p,vec3 a){
 vec3 c=cos(a),s=sin(a);
 p=vec3(p.x,c.x*p.y-s.x*p.z,s.x*p.y+c.x*p.z);
 if(sourceRotationOrder==1){
  p=vec3(c.z*p.x-s.z*p.y,s.z*p.x+c.z*p.y,p.z);
  return vec3(c.y*p.x+s.y*p.z,p.y,-s.y*p.x+c.y*p.z);
 }
 p=vec3(c.y*p.x+s.y*p.z,p.y,-s.y*p.x+c.y*p.z);
 return vec3(c.z*p.x-s.z*p.y,s.z*p.x+c.z*p.y,p.z);
}
vec2 project(vec3 p){return vec2(facing.x*p.x+facing.y*p.z,-p.y)*ground;}
void main(){
 vec2 screen;
 if(billboard==1){
  vec2 v=vertex.xy*size.xy;float c=cos(rotation.x),s=sin(rotation.x);
  screen=origin+(project(center)+vec2(v.x*c-v.y*s,-v.x*s-v.y*c))*units;
 }else screen=origin+project((rotate3(vertex*size,rotation)+center+geometryOffset)*geometryScale)*units;
 gl_Position=vec4(screen.x/viewport.x*2-1,1-screen.y/viewport.y*2,billboard==0?vertex.z*.001:0.,1);
 // Arbitrary-quad authoring places texture V along its first size axis.
 vec2 tex=billboard==2?vec2(1-uv.y,uv.x):uv;
 if(indicatorFlipV==1)tex.y=1-tex.y;
 vec2 q=(tex-.5)*uvScale;float co=cos(uvRotation),si=sin(uvRotation);
 tex=vec2(q.x*co-q.y*si,q.x*si+q.y*co)+.5;
 tc=(tex+vec2(mod(frame,divisions.x),floor(frame/divisions.x)))/divisions+scroll;
 mtc=(tex+vec2(mod(frame,multDivisions.x),floor(frame/multDivisions.x)))/multDivisions+multScroll;
 tint=ink;erode=erosion;row=paletteRow;
}'''
FS='''#version 330
uniform sampler2D image,erosionMap,paletteMap,multMap;
uniform vec4 erosionChannels,paletteMix;
uniform float feather,paletteCount,alphaCutoff,opacity;
uniform int useErosion,usePalette,repeatUV,blendMode,useMult,transparentAdditive;
in vec2 tc;in vec2 mtc;in vec4 tint;in float erode;in float row;out vec4 color;
void main(){
 vec2 uv=repeatUV==1?fract(tc):clamp(tc,vec2(0),vec2(1));
 vec4 v=texture(image,uv);
 if(useMult==1)v*=texture(multMap,fract(mtc));
 if(usePalette==1){float level=dot(v,paletteMix);v.rgb=texture(paletteMap,vec2(level,(row+.5)/paletteCount)).rgb;}
 if(useErosion==1){float mask=dot(texture(erosionMap,uv),erosionChannels);v.a*=smoothstep(erode-feather,erode+feather,mask);}
 color=v*tint;
 // Additive black is empty light, not an opaque black pixel. Preserve RGB
 // energy while encoding coverage for the premultiplied desktop compositor.
 if(transparentAdditive==1){
  float coverage=clamp(max(color.r,max(color.g,color.b)),0,1);
  if(coverage<0.00001)discard;
  color.rgb/=coverage;color.a*=coverage;
 }
 // Mode 2 is inverse-source darkening. Black alpha over the desktop gives
 // the same attenuation without requiring access to Isaac's framebuffer.
 if(blendMode==2)color=vec4(0,0,0,max(color.r,max(color.g,color.b))*color.a);
 if(color.a<alphaCutoff)discard;
 color.a*=opacity;
}'''

def curve(value,t,default,random=None):
    """Evaluate source values without multiplying the constant by its own curve."""
    if not isinstance(value,dict):return np.asarray(default if value is None else value,dtype=float)
    dynamics=value.get('dynamics',{});times=dynamics.get('times',[]);values=dynamics.get('values',[])
    if times and values:
        v=np.asarray(values,dtype=float)
        result=np.interp(t,times,v) if v.ndim==1 else np.stack([np.interp(t,times,v[:,i]) for i in range(v.shape[1])],axis=-1)
    else:result=np.asarray(value.get('constantValue',default),dtype=float)
    tables=dynamics.get('probabilityTables',[])
    if tables and random is not None:
        factors=[]
        for i,table in enumerate(tables):
            kt=table.get('keyTimes',[]);kv=table.get('keyValues',[])
            factors.append(np.interp(random[:,i%random.shape[1]],kt,kv) if kt and kv else np.ones(len(random)))
        factors=np.stack(factors,axis=-1)
        if np.ndim(result)==0 or (np.ndim(result)==1 and len(tables)==1):factors=factors[:,0]
        result=result*factors
    return result

def vector(value,count,dimensions):
    return np.broadcast_to(value,(count,dimensions)).copy() if dimensions>1 else np.broadcast_to(value,(count,)).copy()

def rotate_y(v,angle):
    c=np.cos(angle);s=np.sin(angle);out=v.copy()
    out[:,0]=v[:,0]*c+v[:,2]*s;out[:,2]=-v[:,0]*s+v[:,2]*c
    return out

class Emitter:
    def __init__(self,data,seed,authored=False):
        self.data=data;self.authored=authored;rng=np.random.default_rng(seed)
        self.single=data.get('isSingleParticle',False)
        self.rate=float(curve(data.get('rate'),0,0));self.delay=data.get('timeBeforeFirstEmission',0)
        self.duration=min(3.,data.get('lifetime',.5))
        self.loop=authored and not self.single and 'lifetime' not in data
        if self.loop:self.duration=4.
        self.count=1 if self.single else min(128,max(0,math.ceil(self.rate*self.duration)))
        n=self.count;self.random=rng.random((n,4));self.birth={}
        for key,default,dim in [('particleLifetime',3,1),('birthVelocity',[0,0,0],3),('birthDrag',[0,0,0],3),
            ('birthScale0',[1,1,1],3),('birthColor',[1,1,1,1],4),('birthRotation0',[0,0,0],3),
            ('birthRotationalVelocity0',[0,0,0],3),('EmitterPosition',[0,0,0],3),
            ('birthUvScrollRate',[0,0],2),('birthUVOffset',[0,0],2),('worldAcceleration',[0,0,0],3),('birthOrbitalVelocity',[0,0,0],3)]:
            self.birth[key]=vector(curve(data.get(key),0,default,self.random),n,dim)
        mult=data.get('textureMult',{})
        self.multSpeed=vector(curve(mult.get('birthUvScrollRateMult'),0,[0,0],self.random),n,2)
        self.multOffset=vector(curve(mult.get('birthUVOffsetMult'),0,[0,0],self.random),n,2)
        self.birthTime=np.full(n,self.delay) if self.single else self.delay+np.arange(n)/max(self.rate,1)
        shape=data.get('SpawnShape',{});kind=shape.get('~class','')
        self.spawn=vector(curve(shape.get('emitOffset'),0,[0,0,0],self.random),n,3)
        if kind=='VfxShapeBox':self.spawn+=(rng.random((n,3))*2-1)*np.asarray(shape.get('Size',[0,0,0]))
        elif kind in ('VfxShapeSphere','VfxShapeCylinder'):
            radius=curve(shape.get('radius',shape.get('Radius')),0,0,self.random)
            a=rng.random(n)*math.tau;r=radius*np.sqrt(rng.random(n));self.spawn[:,0]+=r*np.cos(a);self.spawn[:,2]+=r*np.sin(a)
            if kind=='VfxShapeSphere':self.spawn[:,1]+=(rng.random(n)*2-1)*radius
        self.spawnAngle=np.zeros(n)
        for angle,axis in zip(shape.get('emitRotationAngles',[]),shape.get('emitRotationAxes',[])):
            if abs(axis[1])>.9:self.spawnAngle+=np.radians(curve(angle,0,0,self.random))
        self.spawn=rotate_y(self.spawn,self.spawnAngle)
        self.birth['birthVelocity']=rotate_y(self.birth['birthVelocity'],self.spawnAngle)
        self.startFrame=rng.integers(0,max(1,data.get('numFrames',1)),n) if data.get('isRandomStartFrame') else np.full(n,data.get('startFrame',0))

    def instances(self,time,moving_speed=0,bound_size=100,moving_duration=None):
        d=self.data;t=time-self.birthTime;life=np.maximum(.001,self.birth['particleLifetime'])
        if self.authored:life=np.where(self.birth['particleLifetime']<0,np.inf,life)
        if self.loop:
            period=self.count/max(self.rate,1)
            t=np.where(t>=0,np.mod(t,max(.001,period)),t)
        keep=(t>=0)&(t<life)
        if not keep.any():return None
        age=np.clip(t/life,0,1);t=np.maximum(0,t);n=self.count
        def prop(key,default,dim):return vector(curve(d.get(key),age,default,self.random),n,dim)
        drag=self.birth['birthDrag'];travel=-np.expm1(-drag*t[:,None])/np.maximum(drag,.0001)
        travel=np.where(drag>.0001,travel,t[:,None])
        pos=self.spawn+self.birth['EmitterPosition']+self.birth['birthVelocity']*travel+self.birth['worldAcceleration']*t[:,None]**2*.5
        if self.authored:
            pos=rotate_y(pos,self.birth['birthOrbitalVelocity'][:,1]*t)
            flex=d.get('FlexShapeDefinition',{})
            factor=flex.get('scaleEmitOffsetByBoundObjectSize')
            if factor is not None:pos+=self.spawn*(factor*bound_size-1)
        # Unbound projectile particles remain behind the travelling W head.
        travel_time=t if moving_duration is None else np.minimum(time,moving_duration)-np.minimum(self.birthTime,moving_duration)
        bind=prop('bindWeight',0,1)
        pos[:,2]-=moving_speed*travel_time*(1-bind)
        scale=self.birth['birthScale0']*prop('scale0',[1,1,1],3)
        if d.get('isUniformScale'):scale[:]=scale[:,:1]
        if self.authored:scale*=d.get('FlexShapeDefinition',{}).get('scaleBirthScaleByBoundObjectSize',1/bound_size)*bound_size
        ink=self.birth['birthColor']*prop('Color',[1,1,1,1],4)
        ink*=np.asarray(d.get('modulationFactor',[1,1,1,1]))
        ramp=getattr(self,'colorRamp',None)
        if ramp is not None:
            # Legacy particleColorTexture modulates RGBA; it is not a mesh texture.
            h,w,_=ramp.shape;x=np.clip(age,0,1)*(w-1)
            y=np.clip(self.random[:,3] if d.get('colorLookUpTypeY')==3 else age,0,1)*(h-1)
            x0=x.astype(int);y0=y.astype(int);x1=np.minimum(w-1,x0+1);y1=np.minimum(h-1,y0+1)
            fx=(x-x0)[:,None];fy=(y-y0)[:,None]
            ink*=((ramp[y0,x0]*(1-fx)+ramp[y0,x1]*fx)*(1-fy)+(ramp[y1,x0]*(1-fx)+ramp[y1,x1]*fx)*fy)
        angle=self.birth['birthRotation0']+self.birth['birthRotationalVelocity0']*t[:,None]+prop('rotation0',[0,0,0],3)
        if d.get('isDirectionOriented'):angle[:,1]+=np.degrees(self.spawnAngle)
        uv=self.birth['birthUVOffset']+self.birth['birthUvScrollRate']*t[:,None]
        frame=(self.startFrame+np.floor(t*prop('birthFrameRate',0,1)))%max(1,d.get('numFrames',1))
        erosion=d.get('alphaErosionDefinition',{})
        erode=vector(curve(erosion.get('erosionDriveCurve'),age,0,self.random),n,1)
        palette=d.get('paletteDefinition',{})
        rows=vector(curve(palette.get('paletteSelector'),age,[0,0,0],self.random),n,3)[:,0]
        return np.column_stack((pos,scale,np.radians(angle),ink,uv,frame,erode,rows,self.multOffset+self.multSpeed*t[:,None]))[keep].astype('f4')

class ClientParticles:
    def __init__(self,ctx,root=None,bundle=None):
        self.ctx=ctx;self.root=root or Path(__file__).parent/'assets/client';self.bundle=bundle;self.colorRamps={}
        self.authored=bundle is not None;prefix=bundle+'-' if bundle else ''
        self.systems=json.loads((self.root/(prefix+'systems.json')).read_text())
        self.manifest=json.loads((self.root/(prefix+'manifest.json')).read_text())['assets']
        self.program=ctx.program(vertex_shader=VS,fragment_shader=FS)
        self.instances=ctx.buffer(reserve=128*20*4,dynamic=True);self.meshes={};self.mesh_vertices={};self.textures={};self.cache={};self.wall_frames={}
        self.unsupported=set();self.stats={'particles':0,'draws':0}
        quad=np.array([[-1,-1,0,0,1],[1,-1,0,1,1],[1,1,0,1,0],[-1,-1,0,0,1],[1,1,0,1,0],[-1,1,0,0,0]],dtype='f4')
        self.add_mesh('quad',quad)
        self.add_texture('white',Image.new('RGBA',(1,1),'white'))
        for key,asset in self.manifest.items():
            path=self.root/asset['file']
            if path.suffix=='.png':self.add_texture(key,Image.open(path))
            else:self.add_mesh(key,np.array(json.loads(path.read_text()),dtype='f4'))

    def add_texture(self,name,image):
        import moderngl
        image=image.convert('RGBA');texture=self.ctx.texture(image.size,4,image.tobytes())
        texture.filter=(moderngl.LINEAR,moderngl.LINEAR);texture.repeat_x=False;texture.repeat_y=False
        self.textures[name]=texture

    def add_mesh(self,name,data):
        self.mesh_vertices[name]=data[:,:3].copy()
        buf=self.ctx.buffer(data.tobytes())
        self.meshes[name]=(self.ctx.vertex_array(self.program,[(buf,'3f 2f','vertex','uv'),
            (self.instances,'3f 3f 3f 4f 2f 1f 1f 1f 2f /i','center','size','rotation','ink','scroll','frame','erosion','paletteRow','multScroll')]),len(data),buf)

    def reset(self):self.cache.clear()

    def wall_frame(self,name):
        if name not in self.wall_frames:
            data=next(e for e in self.systems[name]['complexEmitterDefinitionData'] if e.get('emitterName')=='wind_wall')
            instance=Emitter(data,0,True).instances(1)[0]
            vertices=self.mesh_vertices[data['primitive']['mMesh']['mSimpleMeshName'].lower()]*instance[3:6]
            # Same X-Z-Y basis as the GPU, calibrated once from the original mesh.
            for axis in (0,2,1):
                a=instance[6+axis];c=math.cos(a);s=math.sin(a);v=vertices.copy()
                if axis==0:vertices[:,1]=c*v[:,1]-s*v[:,2];vertices[:,2]=s*v[:,1]+c*v[:,2]
                elif axis==2:vertices[:,0]=c*v[:,0]-s*v[:,1];vertices[:,1]=s*v[:,0]+c*v[:,1]
                else:vertices[:,0]=c*v[:,0]+s*v[:,2];vertices[:,2]=-s*v[:,0]+c*v[:,2]
            lo,hi=vertices[:,0].min(),vertices[:,0].max()
            self.wall_frames[name]=(float((lo+hi)/2),float(hi-lo))
        return self.wall_frames[name]
    def begin(self,screen,ground,clock):
        self.program['viewport'].value=tuple(screen);self.program['ground'].value=tuple(ground)
        self.stats={'particles':0,'draws':0}
        # Short-lived emitter caches cannot accumulate during an endless run.
        self.cache={k:v for k,v in self.cache.items() if clock-v[1]<120}
        self.clock=clock

    def draw(self,name,age,position,face,units=.28,key=0,moving_speed=0,bound_size=100,children=True,opacity=1,moving_duration=None):
        if age<0 or (not self.authored and age>=3.5):return
        import moderngl
        cache_key=(name,key)
        if cache_key not in self.cache:
            emitters=[]
            for index,data in enumerate(self.systems[name].get('complexEmitterDefinitionData',[])):
                if data.get('disabled'):continue
                # This source emitter is a character material override, not a
                # free billboard. Rendering its white quad leaves an E diamond.
                if name=='E_Dash2' and data.get('emitterName')=='Temp_Mesh':continue
                kind=data.get('primitive',{}).get('~class','billboard')
                # Ground-layer meshes need terrain depth/soft-particle clipping.
                # The overlay cannot read Isaac's depth buffer; omit those shells
                # instead of displaying an opaque disc over the original cracks.
                allowed=('billboard','VfxPrimitiveArbitraryQuad','VfxPrimitiveMesh')+(('VfxPrimitiveRay',) if self.authored else ())
                if kind not in allowed or data.get('emitterName')=='distort' or data.get('distortionDefinition') or (not self.authored and kind=='VfxPrimitiveMesh' and data.get('isGroundLayer')):
                    self.unsupported.add((name,data.get('emitterName'),kind));continue
                seed=zlib.crc32(f'{name}/{key}/{index}'.encode())
                emitter=Emitter(data,seed,self.authored)
                ramp=data.get('particleColorTexture','').lower()
                if ramp in self.manifest:
                    if ramp not in self.colorRamps:self.colorRamps[ramp]=np.asarray(Image.open(self.root/self.manifest[ramp]['file']).convert('RGBA'),dtype=float)/255
                    emitter.colorRamp=self.colorRamps[ramp]
                emitters.append(emitter)
            emitters.sort(key=lambda e:e.data.get('pass',0));self.cache[cache_key]=(emitters,self.clock)
        emitters,_=self.cache[cache_key];self.cache[cache_key]=(emitters,self.clock)
        self.ctx.disable(moderngl.DEPTH_TEST|moderngl.CULL_FACE);self.ctx.enable(moderngl.BLEND)
        pr=self.program;pr['origin'].value=tuple(position);pr['facing'].value=tuple(face);pr['opacity'].value=max(0,min(1,opacity))
        pr['sourceRotationOrder'].value=int(self.bundle=='yasuo')
        transform=self.systems[name].get('transform') if self.authored else None
        actual_units=units*(transform[0][0] if transform else 1);pr['units'].value=actual_units
        # Q marker artwork places the closed/sweet edge at texture V=1. Its
        # +90-degree source rotation otherwise maps that edge behind the caster.
        pr['indicatorFlipV'].value=int(name.startswith('Q_Indicator_'))
        for emitter in emitters:
            d=emitter.data;primitive=d.get('primitive',{});kind=primitive.get('~class','billboard')
            mesh=primitive.get('mMesh',{}).get('mMeshName',primitive.get('mMesh',{}).get('mSimpleMeshName','quad')).lower()
            if mesh not in self.meshes:continue
            if self.bundle=='yasuo' and name.startswith('Yasuo_Base_W_windwall') and name[-1:].isdigit() and kind=='VfxPrimitiveMesh':
                center,width=self.wall_frame(name)
                pr['geometryOffset'].value=(-center,0,0)
                pr['geometryScale'].value=((250+70*int(name[-1]))/max(1,width),1,1)
            else:
                pr['geometryOffset'].value=(0,0,0);pr['geometryScale'].value=(1,1,1)
            instances=emitter.instances(age,moving_speed,bound_size,moving_duration)
            if instances is None:continue
            tex=d.get('texture','white').lower()
            if tex not in self.textures:continue
            erosion=d.get('alphaErosionDefinition',{});palette=d.get('paletteDefinition',{})
            erode_texture=erosion.get('erosionMapName',tex).lower();pal=palette.get('paletteTexture','white').lower()
            mult=d.get('textureMult',{}).get('textureMult','white').lower()
            for slot,path in enumerate((tex,erode_texture,pal,mult)):self.textures.get(path,self.textures['white']).use(slot)
            pr['image'].value=0;pr['erosionMap'].value=1;pr['paletteMap'].value=2;pr['multMap'].value=3
            pr['useMult'].value=int(mult!='white')
            pr['useErosion'].value=int(bool(erosion));pr['usePalette'].value=int(bool(palette) and pal in self.textures)
            pr['erosionChannels'].value=tuple(curve(erosion.get('erosionMapChannelMixer'),0,[1,0,0,0]))
            pr['paletteMix'].value=tuple(curve(palette.get('palleteSrcMixColor'),0,[1,0,0,0]))
            pr['feather'].value=max(.01,erosion.get('erosionFeatherOut',.1))
            pr['paletteCount'].value=max(1,palette.get('paletteCount',1))
            pr['repeatUV'].value=int(d.get('texAddressModeBase',0)==0)
            pr['divisions'].value=tuple(d.get('texDiv',[1,1]))
            pr['uvScale'].value=tuple(curve(d.get('uvScale'),age,[1,1])) if self.authored else (1,1)
            pr['uvRotation'].value=math.radians(float(curve(d.get('uvRotation'),age,0))) if self.authored else 0
            pr['multDivisions'].value=tuple(d.get('textureMult',{}).get('texDivMult',[1,1]))
            pr['alphaCutoff'].value=d.get('alphaRef',0)/255
            pr['billboard'].value=1 if kind=='billboard' or (kind=='VfxPrimitiveRay' and not d.get('isGroundLayer')) else 2 if kind=='VfxPrimitiveArbitraryQuad' else 0
            blend=d.get('blendMode',0);add=blend in (0,4);pr['blendMode'].value=blend
            pr['transparentAdditive'].value=int(self.authored and add)
            # Use a premultiplied-alpha-compatible target for the transparent OS overlay.
            self.ctx.blend_func=(moderngl.SRC_ALPHA,moderngl.ONE if add else moderngl.ONE_MINUS_SRC_ALPHA,moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
            if mesh.endswith('.skn'):self.ctx.enable(moderngl.DEPTH_TEST);self.ctx.depth_func='<='
            else:self.ctx.disable(moderngl.DEPTH_TEST)
            self.instances.write(instances.tobytes());vao,count,_=self.meshes[mesh];vao.render(vertices=count,instances=len(instances))
            self.stats['particles']+=len(instances);self.stats['draws']+=1
        if self.authored and children:
            for emitter in emitters:
                links=emitter.data.get('childParticleSetDefinition',{}).get('childrenIdentifiers',[])
                if not links:continue
                parents=emitter.instances(age,bound_size=bound_size)
                if parents is None:continue
                for index,parent in enumerate(parents):
                    x,y,z=parent[:3];gx,gy=self.program['ground'].value
                    anchor=(position[0]+(face[0]*z-face[1]*x)*gx*actual_units,position[1]+((face[1]*z+face[0]*x)*gy-y*.819152)*actual_units)
                    for link in links:
                        child=link['effect'].rsplit('/',1)[-1]
                        if child in self.systems:self.draw(child,age,anchor,face,actual_units,key=(key,index),bound_size=bound_size,children=False,opacity=opacity)
