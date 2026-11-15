"""Self-contained glTF 2 inspection and animated preview, without hero-specific bones."""
import io
import json
import math
import struct
from pathlib import Path
import numpy as np
from PIL import Image


class AssetError(ValueError):
    pass


class GLB:
    def __init__(self, path):
        blob = Path(path).read_bytes()
        if len(blob) < 20 or blob[:4] != b'glTF':
            raise AssetError('请选择 GLB 2.0 模型；FBX/SKN/SKL 需要先转换。')
        _, version, size = struct.unpack_from('<4sII', blob)
        if version != 2 or size != len(blob):
            raise AssetError('GLB 版本或文件长度无效。')
        chunks = {}; offset = 12
        while offset < len(blob):
            length, kind = struct.unpack_from('<II', blob, offset); offset += 8
            if offset + length > len(blob): raise AssetError('GLB 数据块不完整。')
            chunks[kind] = blob[offset:offset+length]; offset += length
        self.g = json.loads(chunks[0x4E4F534A].decode('utf-8'))
        self.buf = chunks.get(0x004E4942, b''); self.cache = {}
        g = self.g
        if g.get('extensionsRequired'):
            raise AssetError('模型需要未支持的扩展：' + ', '.join(g['extensionsRequired']))
        if any(b.get('uri') for b in g.get('buffers', [])) or any(i.get('uri') for i in g.get('images', [])):
            raise AssetError('请导出自包含 GLB，将贴图和缓冲区嵌入文件。')
        self.nodes = g.get('nodes', []); self.parents = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                if c in self.parents or c < 0 or c >= len(self.nodes): raise AssetError('骨架层级无效。')
                self.parents[c] = i
        self.order = []; visited = set(); active = set()
        def visit(i):
            if i in active: raise AssetError('节点存在循环引用。')
            if i in visited: return
            active.add(i)
            if i in self.parents: visit(self.parents[i])
            active.remove(i); visited.add(i); self.order.append(i)
        for i in range(len(self.nodes)): visit(i)
        self.t = np.array([n.get('translation', [0,0,0]) for n in self.nodes], dtype='f4')
        self.r = np.array([n.get('rotation', [0,0,0,1]) for n in self.nodes], dtype='f4')
        self.s = np.array([n.get('scale', [1,1,1]) for n in self.nodes], dtype='f4')
        self.tracks = {}; self.durations = {}; self.warnings = []
        if any(m.get('weights') for m in g.get('meshes', [])):
            self.warnings.append('形变目标暂不支持。')
        for index, animation in enumerate(g.get('animations', [])):
            name = animation.get('name') or f'Animation {index+1}'
            if name in self.tracks: raise AssetError('动画名称重复，请在导出前重命名：' + name)
            tracks = []
            for channel in animation.get('channels', []):
                sampler = animation['samplers'][channel['sampler']]
                mode = sampler.get('interpolation', 'LINEAR'); target = channel['target']
                if mode not in ('LINEAR', 'STEP') or target['path'] not in ('translation','rotation','scale'):
                    raise AssetError('暂不支持 CUBICSPLINE 或形变动画，请导出为 LINEAR/STEP。')
                node = target['node']
                if 'matrix' in self.nodes[node]: raise AssetError('带动画节点请导出为 TRS，不能同时使用 matrix。')
                times = self.acc(sampler['input']).reshape(-1)
                values = self.acc(sampler['output'])
                if not len(times) or len(times) != len(values) or np.any(np.diff(times) <= 0):
                    raise AssetError('动画时间轴无效。')
                tracks.append((node,target['path'],times,values,mode))
            self.tracks[name] = tracks
            self.durations[name] = max([float(t[2][-1]) for t in tracks] + [0])
        self.images = []
        for im in g.get('images', []):
            view = g['bufferViews'][im['bufferView']]; start = view.get('byteOffset',0)
            self.images.append(Image.open(io.BytesIO(self.buf[start:start+view['byteLength']])).convert('RGBA'))
        self.skins = []
        for skin in g.get('skins', []):
            joints = np.array(skin['joints'])
            ibm = self.acc(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1) if 'inverseBindMatrices' in skin else np.repeat(np.eye(4)[None],len(joints),axis=0)
            self.skins.append((joints,ibm))
            if len(joints)>128: self.warnings.append('超过旧版游戏渲染器的 128 骨骼限制；预览可用，游戏适配需扩展。')
        self.parts = []
        for ni, node in enumerate(self.nodes):
            if 'mesh' not in node: continue
            for primitive in g['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4) != 4: raise AssetError('预览仅支持三角形网格。')
                a = primitive['attributes']; pos = self.acc(a['POSITION']).astype('f4')
                mat = g.get('materials',[])[primitive['material']] if 'material' in primitive else {}
                pbr = mat.get('pbrMetallicRoughness',{}); tex = pbr.get('baseColorTexture')
                tid = g['textures'][tex['index']]['source'] if tex else None
                uv = self.acc(a['TEXCOORD_0']) if 'TEXCOORD_0' in a else np.zeros((len(pos),2),dtype='f4')
                joints = self.acc(a['JOINTS_0']).astype(int) if 'JOINTS_0' in a else None
                weights = self.acc(a['WEIGHTS_0']).astype('f4') if 'WEIGHTS_0' in a else None
                if weights is not None: weights /= np.maximum(weights.sum(axis=1,keepdims=True),1e-8)
                indices = self.acc(primitive['indices']).reshape(-1).astype('u4') if 'indices' in primitive else np.arange(len(pos),dtype='u4')
                self.parts.append(dict(node=ni,skin=node.get('skin'),pos=pos,uv=uv,joints=joints,weights=weights,indices=indices,texture=tid,
                                       name=mat.get('name',f'Material {len(self.parts)+1}'),factor=pbr.get('baseColorFactor',[1,1,1,1])))
        if not self.parts: raise AssetError('模型没有可显示的网格。')
        base = np.concatenate(self.positions('',0)); self.center=(base.min(axis=0)+base.max(axis=0))/2
        self.extent=max(float(np.max(base.max(axis=0)-base.min(axis=0))),.001)

    def acc(self,index):
        if index in self.cache: return self.cache[index]
        a=self.g['accessors'][index]
        if 'sparse' in a: raise AssetError('暂不支持 sparse accessor。')
        view=self.g['bufferViews'][a['bufferView']]
        dtype=np.dtype({5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']])
        width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        data=np.ndarray((a['count'],width),dtype,self.buf,view.get('byteOffset',0)+a.get('byteOffset',0),strides=(view.get('byteStride',dtype.itemsize*width),dtype.itemsize)).copy()
        if a.get('normalized') and dtype.kind in 'iu': data=np.maximum(data.astype('f4')/np.iinfo(dtype).max,-1)
        if not np.all(np.isfinite(data)): raise AssetError('模型含非有限数值。')
        self.cache[index]=data;return data

    def world(self,clip,seconds):
        t,r,s=self.t.copy(),self.r.copy(),self.s.copy(); values_by_path={'translation':t,'rotation':r,'scale':s}
        for node,path,times,values,mode in self.tracks.get(clip,[]):
            k=max(0,min(len(times)-1,int(np.searchsorted(times,seconds,side='right'))-1)); j=min(k+1,len(times)-1)
            a=values[k];b=values[j]; weight=0 if k==j or mode=='STEP' else np.clip((seconds-times[k])/(times[j]-times[k]),0,1)
            if path=='rotation':
                dot=float(np.dot(a,b))
                if dot<0:b=-b;dot=-dot
                if dot<.9995:
                    angle=math.acos(np.clip(dot,-1,1));v=(a*math.sin((1-weight)*angle)+b*math.sin(weight*angle))/math.sin(angle)
                else:v=a*(1-weight)+b*weight
            else:v=a*(1-weight)+b*weight
            values_by_path[path][node]=v
        r/=np.maximum(np.linalg.norm(r,axis=1,keepdims=True),1e-8);x,y,z,w=r.T
        local=np.zeros((len(t),4,4),dtype='f4')
        local[:,0,0]=1-2*(y*y+z*z);local[:,0,1]=2*(x*y-z*w);local[:,0,2]=2*(x*z+y*w)
        local[:,1,0]=2*(x*y+z*w);local[:,1,1]=1-2*(x*x+z*z);local[:,1,2]=2*(y*z-x*w)
        local[:,2,0]=2*(x*z-y*w);local[:,2,1]=2*(y*z+x*w);local[:,2,2]=1-2*(x*x+y*y)
        local[:,:3,:3]*=s[:,None,:];local[:,:3,3]=t;local[:,3,3]=1
        for i,n in enumerate(self.nodes):
            if 'matrix' in n:local[i]=np.array(n['matrix']).reshape(4,4).T
        world=np.empty_like(local)
        for i in self.order:world[i]=world[self.parents[i]]@local[i] if i in self.parents else local[i]
        return world

    def positions(self,clip,seconds):
        world=self.world(clip,seconds);result=[]
        for part in self.parts:
            pos=np.c_[part['pos'],np.ones(len(part['pos']))]
            if part['skin'] is not None and part['joints'] is not None:
                joints,ibm=self.skins[part['skin']];matrices=world[joints]@ibm
                out=np.zeros((len(pos),4))
                for k in range(4):out+=np.einsum('nij,nj->ni',matrices[part['joints'][:,k]],pos)*part['weights'][:,k,None]
            else:out=pos@world[part['node']].T
            result.append(out[:,:3].astype('f4'))
        return result

    def info(self):
        return dict(animations=self.durations,bones=[n.get('name',str(i)) for i,n in enumerate(self.nodes)],materials=list(dict.fromkeys(p['name'] for p in self.parts)),
                    vertices=sum(len(p['pos']) for p in self.parts),skins=len(self.skins),warnings=self.warnings)

