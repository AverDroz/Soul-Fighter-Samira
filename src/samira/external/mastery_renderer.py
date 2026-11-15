"""Live original mastery rig and 27 source emitters, at framebuffer resolution."""
from pathlib import Path
import numpy as np
import moderngl
from mastery_glb import GLB
from mastery_particles import ClientParticles


class MasteryRenderer:
    def __init__(self,ctx,asset=None):
        self.ctx=ctx
        asset=Path(asset or Path(__file__).parent/'assets/mastery/crest.glb')
        self.model=GLB(asset);self.clip=next(iter(self.model.durations))
        self.duration=self.model.durations[self.clip];self.target=None
        self.particles=ClientParticles(ctx,asset.parent,'mastery')
        system=self.particles.systems['Mastery']
        self.mesh=next(e['primitive']['mMesh']['mMeshName'].lower() for e in system['complexEmitterDefinitionData'] if e.get('emitterName')=='BaseCrest2')
        self.particles.add_mesh(self.mesh,self.vertices(0))
        self.program=ctx.program(vertex_shader="""#version 330
        in vec2 pos;in vec2 uv;out vec2 texcoord;uniform vec2 screen;
        void main(){gl_Position=vec4(pos.x/screen.x*2-1,1-pos.y/screen.y*2,0,1);texcoord=uv;}
        """,fragment_shader="""#version 330
        in vec2 texcoord;out vec4 color;uniform sampler2D image;
        void main(){color=texture(image,texcoord);}
        """)
        self.buffer=ctx.buffer(reserve=6*4*4)
        self.vao=ctx.vertex_array(self.program,[(self.buffer,'2f 2f','pos','uv')])

    def vertices(self,seconds):
        return np.concatenate([np.c_[position[p['indices']],p['uv'][p['indices']]]
            for p,position in zip(self.model.parts,self.model.positions(self.clip,seconds))]).astype('f4')

    def draw(self,state,canvas):
        badge=state.get('mastery')
        if not badge or state.get('paused') or state.get('dead') or state.get('shop') or state.get('preview'):return False
        seconds=(state.get('clock',0)-badge['at'])/30
        if not 0<=seconds<self.duration:return False
        ctx=self.ctx;x,y=badge['position'];sw,sh=state['screen'];vx,vy,vw,vh=ctx.viewport
        size=(max(160,int(160*vw/sw)),max(160,int(160*vh/sh)))
        canvas.flush();previous=ctx.fbo;viewport=ctx.viewport
        if self.target is None or self.target.size!=size:
            if self.target:self.target.release();self.color.release();self.depth.release()
            self.color=ctx.texture(size,4);self.color.filter=(moderngl.LINEAR,moderngl.LINEAR)
            self.depth=ctx.depth_renderbuffer(size);self.target=ctx.framebuffer([self.color],self.depth)
        self.target.use();ctx.viewport=(0,0,*size);self.target.clear(0,0,0,0,depth=1)
        try:
            self.particles.meshes[self.mesh][2].write(self.vertices(seconds).tobytes())
            self.particles.begin((160,160),(1,1),state['clock'])
            # Original crest uses uniform 1.4 scale and y=250. Anchor its center above the hero.
            units=54/(114.96*1.4)
            self.particles.draw('Mastery',seconds,(80,80+(250+44.128*1.4)*units),(-1,0),units,key=badge['at'])
        finally:
            previous.use();ctx.viewport=viewport
        ctx.disable(moderngl.DEPTH_TEST);ctx.enable(moderngl.BLEND)
        # The effect surface is already premultiplied; do not multiply alpha again.
        ctx.blend_func=(moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA,moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
        self.program['screen'].value=(sw,sh);self.program['image'].value=0;self.color.use()
        l,r,t,b=x-80,x+80,y-80,y+80
        self.buffer.write(np.array([(l,t,0,1),(r,t,1,1),(r,b,1,0),(l,t,0,1),(r,b,1,0),(l,b,0,0)],dtype='f4').tobytes())
        self.vao.render();return True

    def close(self):
        for vao,count,buf in self.particles.meshes.values():vao.release();buf.release()
        for t in self.particles.textures.values():t.release()
        self.particles.instances.release();self.particles.program.release()
        if self.target:self.target.release();self.color.release();self.depth.release()
        self.vao.release();self.buffer.release();self.program.release()
