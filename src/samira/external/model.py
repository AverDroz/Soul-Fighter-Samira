"""Original GLB animation sampling. Only bone matrices cross to the GPU each frame."""
import io,json,struct
from pathlib import Path
import numpy as np
from PIL import Image

MAX_BONES=192
CLIPS={'Idle':'idle_gun','Walk':'run_gun_base','Attack':'attack1_gun_hit',
 'AttackStart':'attack1_gun_start','AttackRecovery':'attack1_gun_into_idle',
 'MeleeAttack':'attack1_sword_ht','MeleeIdle':'idle_sword','MeleeWalk':'run_sword_base',
 'Q':'spell1_gun','QMelee':'spell1_sword_from_idle','EQ':'spell1_during_dash',
 'W':'spell2','E':'spell3','Dash':'spell3','RStart':'spell4_start_a',
 'R':'spell4_loop_a','RLoop':'spell4_loop_a','RDash':'spell4_dash','REnd':'spell4_into_idle',
 'Death':'death','Dance':'dance_loop','Taunt':'taunt','Joke':'joke','Laugh':'laugh',
 'SheathedIdle':'idle','SheathedWalk':'run_ooc','Draw':'idle_gun_in','Sheathe':'sheath_gun_idle',
 # Transitional aliases keep the original telemetry readable during the port.
 'Q1':'spell1_gun','Q2':'spell1_sword_from_idle','Q3':'spell1_during_dash',
 'RIdle':'idle_gun','RWalk':'run_gun_base','RAttack':'attack1_gun_hit',
 'RQ1':'spell1_gun','RQ2':'spell1_sword_from_idle','RQ3':'spell1_during_dash'}

def visible_parts(action,phase,duration,ultimate,banner):
    # Default submesh visibility comes from Soul Fighter's skin record.
    # Blur/crown events are not emulated by borrowing Aatrox wing rules.
    return {name:name not in ('Pistol_Blur','Revolver_Blur','Viego_Crown') for name in
            ('Assets','Body','Hair','Holster','Pistol','Revolver','Sword','Sword_Eye',
             'Pistol_Blur','Revolver_Blur','Viego_Crown')}

class Model:
    def __init__(self,path,*,hero='samira'):
        self.hero=hero
        self.clips=CLIPS if hero=='samira' else {}
        self.idle_clip='idle_gun' if hero=='samira' else 'idle'
        blob=Path(path).read_bytes()
        if blob[:4]!=b'glTF':raise ValueError('Expected GLB')
        n=struct.unpack_from('<I',blob,12)[0];self.g=json.loads(blob[20:20+n]);self.buf=blob[28+n:];self.cache={}
        g=self.g;self.nodes=g['nodes'];count=len(self.nodes)
        self.node_names={n.get('name'):i for i,n in enumerate(self.nodes)}
        events_path=Path(path).with_name('rig-events.json')
        self.rig_events=json.loads(events_path.read_text(encoding='utf8')) if events_path.exists() else {}
        self.clip_events={}
        for state in self.rig_events.get('states',{}).values():
            events=self.clip_events.setdefault(state['clip'],[])
            for event in state['events']:
                if event not in events:events.append(event)
        self.parents={c:i for i,n in enumerate(self.nodes) for c in n.get('children',[])}
        self.walk_nodes={i for i,n in enumerate(self.nodes) if n.get('name') in ('Root','BodyRoot')}
        pending=[self.node_names['Pelvis']] if 'Pelvis' in self.node_names else []
        while pending:
            i=pending.pop();self.walk_nodes.add(i);pending.extend(self.nodes[i].get('children',[]))
        self.walk_nodes=sorted(self.walk_nodes)
        self.leg_nodes=[i for i in self.walk_nodes if self.nodes[i].get('name') not in ('Root','BodyRoot')]
        self.t=np.array([n.get('translation',[0,0,0]) for n in self.nodes],dtype=np.float32)
        self.r=np.array([n.get('rotation',[0,0,0,1]) for n in self.nodes],dtype=np.float32)
        self.s=np.array([n.get('scale',[1,1,1]) for n in self.nodes],dtype=np.float32)
        assert not any('matrix' in n for n in self.nodes),'This asset uses TRS nodes'
        def depth(i):return 0 if i not in self.parents else depth(self.parents[i])+1
        self.order=sorted(range(count),key=depth)
        skin=g['skins'][0];self.joints=np.array(skin['joints'])
        if len(self.joints)>MAX_BONES:raise ValueError(f'Rig has {len(self.joints)} joints; GPU limit is {MAX_BONES}')
        self.ibm=self.acc(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
        self.tracks={};self.durations={};self.track_groups={}
        self.motion_anchors={}
        for anim in g['animations']:
            tracks=[]
            for ch in anim['channels']:
                sm=anim['samplers'][ch['sampler']];times=self.acc(sm['input'])[:,0];values=self.acc(sm['output'])
                interpolation=sm.get('interpolation','LINEAR')
                assert interpolation in ('LINEAR','STEP'),interpolation
                tracks.append((ch['target']['node'],ch['target']['path'],times,values,interpolation))
            self.tracks[anim['name']]=tracks;self.durations[anim['name']]=max(float(t[2][-1]) for t in tracks)
            # Most bones share a time axis. Search it once, then interpolate the
            # original samples together; no time quantization or pose caching.
            groups={}
            duplicates=len({(n,p) for n,p,*_ in tracks})!=len(tracks)
            for i,(node,path,times,values,interpolation) in enumerate(tracks):
                if path not in ('translation','rotation','scale'):continue
                key=(path,interpolation,times.tobytes(),i if duplicates else None)
                group=groups.setdefault(key,[path,times,interpolation,[],[]])
                group[3].append(node);group[4].append(values)
            self.track_groups[anim['name']]=[(p,t,mode,np.asarray(nodes),np.stack(values,axis=1))
                for p,t,mode,nodes,values in groups.values()]
        if self.durations.get(self.idle_clip,0)<=0:raise ValueError('Missing idle animation: '+self.idle_clip)
        self.textures=[]
        for image in g['images']:
            v=g['bufferViews'][image['bufferView']];start=v.get('byteOffset',0)
            self.textures.append(Image.open(io.BytesIO(self.buf[start:start+v['byteLength']])).convert('RGBA'))
        vertex_groups={};vertices=[];vertex_count=0
        self.parts=[]
        self.banner_mask=0
        self.banner_params={'Scroll_Speed':[0,0],'Scroll_Speed_BLUE':[0,0],'Alpha_Bias':[0]}
        # Riot centimetres -> Isaac logical pixels. Calibrated down after the
        # first live room test; collision geometry remains authoritative in Lua.
        self.pixel_scale=.17
        for p in g['meshes'][0]['primitives']:
            attrs=p['attributes'];key=tuple(attrs[k] for k in ('POSITION','TEXCOORD_0','JOINTS_0','WEIGHTS_0'))
            if key not in vertex_groups:
                data=np.concatenate([self.acc(i).astype('f4') for i in key],axis=1)
                vertices.append(data);vertex_groups[key]=vertex_count;vertex_count+=len(data)
            mat=g['materials'][p['material']];name=mat.get('name','')
            tid=g['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
            self.parts.append((name,self.acc(p['indices']).reshape(-1).astype('u4')+vertex_groups[key],tid))
        self.vertices=np.concatenate(vertices,axis=0)

    def acc(self,index):
        if index in self.cache:return self.cache[index]
        a=self.g['accessors'][index];v=self.g['bufferViews'][a['bufferView']]
        dtype={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        step=v.get('byteStride',np.dtype(dtype).itemsize*width)
        result=np.ndarray((a['count'],width),dtype,self.buf,v.get('byteOffset',0)+a.get('byteOffset',0),strides=(step,np.dtype(dtype).itemsize)).copy()
        self.cache[index]=result;return result

    def sample(self,kind,phase):
        name=self.clips.get(kind,kind if kind in self.tracks else self.idle_clip);time=max(0,min(1,phase))*self.durations[name]
        t,r,s=self.t.copy(),self.r.copy(),self.s.copy();targets={'translation':t,'rotation':r,'scale':s}
        for path,times,interpolation,nodes,values in self.track_groups[name]:
            k=max(0,min(len(times)-1,int(np.searchsorted(times,time,side='right'))-1));k2=min(k+1,len(times)-1)
            a=values[k];b=values[k2]
            if path=='rotation':b=b*np.where(np.sum(a*b,axis=1,keepdims=True)<0,-1,1).astype(b.dtype)
            weight=0 if k==k2 or interpolation=='STEP' else (time-times[k])/(times[k2]-times[k])
            targets[path][nodes]=a*(1-weight)+b*weight
        r/=np.maximum(1e-8,np.linalg.norm(r,axis=1,keepdims=True))
        return t,r,s

    @staticmethod
    def blend(a,b,amount):
        t=a[0]*(1-amount)+b[0]*amount;s=a[2]*(1-amount)+b[2]*amount
        br=b[1]*np.where(np.sum(a[1]*b[1],axis=1,keepdims=True)<0,-1,1)
        r=a[1]*(1-amount)+br*amount;r/=np.maximum(1e-8,np.linalg.norm(r,axis=1,keepdims=True))
        return t,r,s

    def moving_pose(self,kind,phase,locomotion=None):
        pose=self.sample(kind,phase)
        if locomotion and kind in ('Walk','SheathedWalk','MeleeWalk'):
            pose=self.sample(locomotion['kind'],locomotion['phase'])
        return pose

    def anchor_motion(self,pose,kind):
        # The game already moves the player during E. Keep the authored jump,
        # but do not add the clip's horizontal travel on top of that collision.
        root=self.node_names.get(self.rig_events.get('motion_root','Root'))
        if root is None:return pose
        if kind not in self.motion_anchors:self.motion_anchors[kind]=self.sample(kind,0)[0][root].copy()
        t=pose[0].copy();delta=self.motion_anchors[kind][[0,2]]-t[root,[0,2]]
        t[root,[0,2]]+=delta
        # Yone's sheath is a parallel root and must follow the same correction.
        sheath=self.node_names.get('Sheath') if self.hero=='yone' else None
        if sheath is not None and sheath not in self.parents:t[sheath,[0,2]]+=delta
        return t,pose[1],pose[2]

    def active_events(self,kind,phase):
        clip=self.clips.get(kind,kind)
        frame=max(0,min(1,phase))*self.durations.get(clip,0)*self.rig_events.get('frames_per_second',30)
        return [e for e in self.clip_events.get(clip,[])
                if e.get('mStartFrame',0)<=frame<e.get('mEndFrame',float('inf'))]

    def visibility(self,kind,phase):
        result=visible_parts(kind,phase,0,False,False) if self.hero=='samira' else {
            name:False for name in self.rig_events.get('hidden_materials',[])}
        for event in self.active_events(kind,phase):
            if event.get('__type')=='SubmeshVisibilityEventData':
                result.update({name:True for name in event.get('mShowSubmeshList',[])})
                result.update({name:False for name in event.get('mHideSubmeshList',[])})
        return result

    def matrices(self,pose,kind=None,phase=0):
        t,r,s=pose;x,y,z,w=r.T;n=len(t);local=np.zeros((n,4,4),dtype='f4')
        local[:,0,0]=1-2*(y*y+z*z);local[:,0,1]=2*(x*y-z*w);local[:,0,2]=2*(x*z+y*w)
        local[:,1,0]=2*(x*y+z*w);local[:,1,1]=1-2*(x*x+z*z);local[:,1,2]=2*(y*z-x*w)
        local[:,2,0]=2*(x*z-y*w);local[:,2,1]=2*(y*z+x*w);local[:,2,2]=1-2*(x*x+y*y)
        local[:,:3,:3]*=s[:,None,:];local[:,:3,3]=t;local[:,3,3]=1
        world=np.empty_like(local)
        for i in self.order:world[i]=world[self.parents[i]]@local[i] if i in self.parents else local[i]
        snaps={self.node_names[e['mJointNameToOverride']]:self.node_names[e['mJointNameToSnapTo']]
               for e in self.active_events(kind,phase) if e.get('__type')=='JointSnapEventData'} if kind is not None else {}
        if snaps:
            # Snap targets can occur later in the skeleton array. Resolve both
            # target and parent dependencies rather than relying on index order.
            resolved=set();visiting=set()
            def resolve(i):
                if i in resolved:return world[i]
                if i in visiting:raise ValueError('Cycle in joint attachment events')
                visiting.add(i)
                if i in snaps:world[i]=resolve(snaps[i])
                elif i in self.parents:world[i]=resolve(self.parents[i])@local[i]
                else:world[i]=local[i]
                visiting.remove(i);resolved.add(i)
                return world[i]
            for i in self.order:resolve(i)
        return world[self.joints]@self.ibm

VERTEX='''#version 330
in vec3 position; in vec2 uv; in vec4 joints; in vec4 weights;
layout(std140) uniform Bones { mat4 bones[%d]; };
uniform vec2 viewport; uniform vec2 origin; uniform vec2 bodyScale; uniform float scale; uniform float yaw;
out vec2 texcoord;
void main(){
 mat4 skin=bones[int(joints.x)]*weights.x+bones[int(joints.y)]*weights.y+bones[int(joints.z)]*weights.z+bones[int(joints.w)]*weights.w;
 vec3 p=(skin*vec4(position,1)).xyz;
 float x=p.x*cos(yaw)+p.z*sin(yaw), z=-p.x*sin(yaw)+p.z*cos(yaw);
 float up=p.y*0.819152-z*0.573576, depth=p.y*0.573576+z*0.819152;
 vec2 pixel=origin+vec2(x,-up)*scale*bodyScale;
 gl_Position=vec4(pixel.x/viewport.x*2-1,1-pixel.y/viewport.y*2,-depth*scale*.001,1);
 texcoord=uv;
}''' % MAX_BONES
FRAGMENT='''#version 330
uniform sampler2D material; uniform sampler2D bannerMask;
uniform float hurt; uniform bool stasis; uniform bool isBanner; uniform float effectTime;uniform float opacity;uniform bool ghost;
uniform vec2 redScroll; uniform vec2 blueScroll; uniform float alphaBias;
in vec2 texcoord; out vec4 color;
void main(){
 vec4 tex=texture(material,texcoord); float alpha=tex.a;
 if(isBanner){
   float red=texture(bannerMask,texcoord+redScroll*effectTime).r;
   float blue=texture(bannerMask,texcoord+blueScroll*effectTime).b;
   alpha*=clamp(red+blue-alphaBias,0.0,1.0);
 }
 if(alpha<.01)discard;
 float light=dot(tex.rgb,vec3(.3,.6,.1));
 vec3 c=mix(tex.rgb,vec3(1,.055,.025)*(.5+.5*light),hurt*.82);
 if(stasis)c=vec3(1,.67,.09)*(.25+dot(tex.rgb,vec3(.3,.6,.1))*.9);
 if(ghost)c=mix(c,vec3(.8,.035,.015),.8);
 color=vec4(c,alpha*opacity);
}'''

OUTLINE_VERTEX='''#version 330
out vec2 uv;
void main(){
 vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);
 uv=p;gl_Position=vec4(p*2-1,0,1);
}'''
OUTLINE_FRAGMENT='''#version 330
uniform sampler2D actor;uniform vec2 radius;
in vec2 uv;out vec4 color;
void main(){
 vec4 body=texture(actor,uv);float edge=0;
 for(int i=0;i<8;i++){
  float angle=float(i)*.7853981634;
  edge=max(edge,texture(actor,uv+vec2(cos(angle),sin(angle))*radius).a);
 }
 // Actor colors are already premultiplied by the offscreen blend pass.
 float alpha=edge*.9*(1-body.a);
 color=vec4(body.rgb+vec3(.018,.012,.022)*alpha,body.a+alpha);
}'''

class GPURenderer:
    def __init__(self,ctx,model):
        import moderngl
        self.ctx=ctx;self.model=model;self.program=ctx.program(vertex_shader=VERTEX,fragment_shader=FRAGMENT)
        self.outline_program=ctx.program(vertex_shader=OUTLINE_VERTEX,fragment_shader=OUTLINE_FRAGMENT)
        self.outline_quad=ctx.vertex_array(self.outline_program,[])
        self.actor_surface=None;self.actor_texture=None;self.actor_depth=None
        self.bones=ctx.buffer(reserve=MAX_BONES*64);self.bones.bind_to_uniform_block(0);self.program['Bones'].binding=0
        self.vbo=ctx.buffer(model.vertices.tobytes());self.textures=[];self.parts=[];self.indices=[]
        for im in model.textures:
            tex=ctx.texture(im.size,4,im.tobytes());tex.filter=(moderngl.LINEAR,moderngl.LINEAR);self.textures.append(tex)
        # Diffuse colour clamps; the separate source mask repeats as it scrolls.
        for tex in self.textures:tex.repeat_x=False;tex.repeat_y=False
        p=self.program;params=model.banner_params
        p['bannerMask'].value=1;p['redScroll'].value=tuple(params['Scroll_Speed'][:2])
        p['blueScroll'].value=tuple(params['Scroll_Speed_BLUE'][:2]);p['alphaBias'].value=params['Alpha_Bias'][0]
        for name,indices,tid in model.parts:
            ibo=ctx.buffer(indices.tobytes())
            self.indices.append(ibo)
            vao=ctx.vertex_array(self.program,[(self.vbo,'3f 2f 4f 4f','position','uv','joints','weights')],ibo,index_element_size=4)
            self.parts.append((name,vao,tid))
        self.parts.sort(key=lambda part:part[0]!='Body')
        self.matrix_upload=np.repeat(np.eye(4,dtype='f4')[None,:,:],MAX_BONES,axis=0)
        self.sockets={}
        if model.hero=='samira':
            for label,name in [('base','Sword'),('tip','Sword_Tip2'),('pistol','Pistol_Muzzle'),('revolver','Revolver_Muzzle')]:
                joint=next(i for i,node in enumerate(model.joints) if model.nodes[node].get('name')==name)
                self.sockets[label]=(joint,np.linalg.inv(model.ibm[joint])[:,3])
        self.reset()

    def reset(self):
        self.kind=self.pose=self.previous=self.yaw=None
        self.transition=self.effect_time=0
        self.rig_sample=('Idle',0)
        self.stasis_snapshot=self.last_actor=None

    def close(self):
        for _,vao,_ in self.parts:vao.release()
        for resource in (*self.indices,*self.textures,self.outline_quad,self.outline_program,
                         self.vbo,self.bones,self.program,self.actor_surface,self.actor_texture,self.actor_depth):
            if resource is not None:resource.release()

    def draw(self,kind,phase,origin,viewport,yaw,dt,ultimate=False,clip=None,banner=None,hurt=False,ghost=None,stasis=False,locomotion=None,body_scale=(1,1),flying=False,outline=True,anchor_root=False,snap_facing=False):
        import moderngl
        action=clip if clip in self.model.tracks else kind
        frozen=stasis and ghost is None and self.pose is not None
        if not stasis or self.pose is None:self.stasis_snapshot=None
        if frozen and self.stasis_snapshot is None:self.stasis_snapshot=self.last_actor
        if ghost is None and not frozen:
            if self.kind!=action:self.previous=self.pose;self.transition=0;self.kind=action
            self.transition=min(1,self.transition+dt/.10);pose=self.model.moving_pose(action,phase,locomotion)
            if anchor_root:pose=self.model.anchor_motion(pose,action)
            if self.previous is not None and self.transition<1:pose=self.model.blend(self.previous,pose,self.transition)
            self.pose=pose
            self.rig_sample=(action,phase)
        elif frozen:pose=self.pose
        else:pose=ghost[0]
        if ghost is None and not frozen:self.effect_time+=dt
        rig_action,rig_phase=self.rig_sample if frozen else (action,phase)
        visibility=self.model.visibility(rig_action,rig_phase)
        if ghost is None:
            if self.yaw is None or snap_facing:self.yaw=yaw
            delta=(yaw-self.yaw+np.pi)%(2*np.pi)-np.pi
            if not frozen:self.yaw+=delta*(1-np.exp(-dt/.075))
            draw_yaw=self.yaw
        else:draw_yaw=ghost[1]
        actual=self.model.matrices(pose,rig_action,rig_phase);self.matrix_upload[:len(actual)]=actual
        self.bones.bind_to_uniform_block(0)
        self.bones.write(self.matrix_upload.transpose(0,2,1).tobytes())
        scale=self.model.pixel_scale
        if frozen and self.stasis_snapshot is not None:visibility,body_scale,scale=self.stasis_snapshot
        if ghost is None:self.last_actor=(dict(visibility),tuple(body_scale),scale)
        self.program['bodyScale'].value=tuple(body_scale)
        p=self.program;p['viewport'].value=viewport;p['origin'].value=origin;p['scale'].value=scale;p['yaw'].value=draw_yaw;p['material'].value=0;p['hurt'].value=float(hurt)
        p['stasis'].value=stasis
        p['opacity'].value=ghost[2] if ghost else 1;p['ghost'].value=ghost is not None
        p['effectTime'].value=self.effect_time;self.textures[self.model.banner_mask].use(1)
        target=None
        if outline and ghost is None:
            target=self.ctx.fbo;target_viewport=self.ctx.viewport;size=target_viewport[2:]
            if self.actor_surface is None or self.actor_surface.size!=size:
                if self.actor_surface is not None:
                    self.actor_surface.release();self.actor_texture.release();self.actor_depth.release()
                self.actor_texture=self.ctx.texture(size,4)
                self.actor_texture.filter=(moderngl.LINEAR,moderngl.LINEAR)
                self.actor_texture.repeat_x=False;self.actor_texture.repeat_y=False
                self.actor_depth=self.ctx.depth_renderbuffer(size)
                self.actor_surface=self.ctx.framebuffer([self.actor_texture],self.actor_depth)
            self.actor_surface.use();self.ctx.viewport=(0,0,*size);self.ctx.clear(0,0,0,0)
        self.ctx.enable(moderngl.DEPTH_TEST);self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func=(moderngl.SRC_ALPHA,moderngl.ONE_MINUS_SRC_ALPHA,moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
        # Opaque body first so back-mounted translucent ribbons cannot cover it.
        for name,vao,tid in self.parts:
            if not visibility.get(name,True):continue
            is_banner=self.model.hero=='samira' and name=='Banner'
            p['isBanner'].value=is_banner;self.ctx.depth_mask=ghost is None and not is_banner
            self.textures[tid].use(0);vao.render()
        self.ctx.depth_mask=True
        if target is not None:
            target.use();self.ctx.viewport=target_viewport
            self.ctx.disable(moderngl.DEPTH_TEST)
            self.ctx.blend_func=(moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
            self.actor_texture.use(0);self.outline_program['actor'].value=0
            pixels=min(2.2,max(1.,size[1]/viewport[1]*.65))
            self.outline_program['radius'].value=(pixels/size[0],pixels/size[1])
            self.outline_quad.render(vertices=3)
            self.ctx.blend_func=(moderngl.SRC_ALPHA,moderngl.ONE_MINUS_SRC_ALPHA,moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
            self.ctx.enable(moderngl.DEPTH_TEST)
        points={}
        for name,(joint,rest) in self.sockets.items():
            v=actual[joint]@rest;x=v[0]*np.cos(draw_yaw)+v[2]*np.sin(draw_yaw);z=-v[0]*np.sin(draw_yaw)+v[2]*np.cos(draw_yaw)
            points[name]=(origin[0]+float(x)*scale*body_scale[0],origin[1]-float(v[1]*.819152-z*.573576)*scale*body_scale[1])
        return points
