"""Batched, screen-resolution quads. Original assets stay unmodified on disk."""
from pathlib import Path
import math,os
import numpy as np
from PIL import Image,ImageDraw,ImageFont

VS='''#version 330
in vec2 position;in vec2 uv;in vec4 tint;uniform vec2 viewport;
out vec2 texcoord;out vec4 ink;
void main(){gl_Position=vec4(position.x/viewport.x*2-1,1-position.y/viewport.y*2,0,1);texcoord=uv;ink=tint;}'''
FS='''#version 330
in vec2 texcoord;in vec4 ink;uniform sampler2D image;uniform int brightnessAlpha;out vec4 color;
void main(){vec4 v=texture(image,texcoord);if(brightnessAlpha==1)v.a*=max(v.r,max(v.g,v.b));color=v*ink;}'''

class Canvas:
    def __init__(self,ctx,root):
        import moderngl
        self.ctx=ctx;self.root=Path(root);self.program=ctx.program(vertex_shader=VS,fragment_shader=FS)
        self.buffer=ctx.buffer(reserve=2**20,dynamic=True)
        self.vao=ctx.vertex_array(self.program,[(self.buffer,'2f 2f 4f','position','uv','tint')])
        self.textures={};self.vertices=[];self.batch=None;self.draw_calls=0
        self.add('white',Image.new('RGBA',(1,1),'white'))
        # Rasterize glyphs once at 48px, not at Isaac's small internal resolution.
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        font=ImageFont.truetype(str(fonts/'arialbd.ttf'),48)
        labels=Path(__file__).resolve().parents[1]/'mod/resources/gfx/samira/hud/ui-labels.txt'
        from shop_ui import NATIVE_NOTES
        from localization import EN
        text=labels.read_text(encoding='utf-8')+labels.with_name('eid-glyphs.txt').read_text(encoding='utf-8')+''.join(EN)+''.join(''.join(note) for note in NATIVE_NOTES.values())
        chars=[chr(i) for i in range(32,127)]+sorted(set(text)-set(chr(i) for i in range(128)))
        cjk_path=fonts/'msyh.ttc'
        if not cjk_path.exists():cjk_path=Path(__file__).parent/'assets/fonts/NotoSansCJKsc-Regular.otf'
        cjk=ImageFont.truetype(str(cjk_path),48)
        max_size=ctx.info['GL_MAX_TEXTURE_SIZE'];rows=max_size//80
        columns=max(16,math.ceil(len(chars)/rows))
        self.font_size=(columns*64,math.ceil(len(chars)/columns)*80)
        atlas=Image.new('RGBA',self.font_size);d=ImageDraw.Draw(atlas);self.glyphs={}
        for n,ch in enumerate(chars):
            x=n%columns*64;y=n//columns*80;face=cjk if ord(ch)>127 else font
            # One baseline per font, not one top edge per glyph. Top-aligning
            # every letter makes lowercase letters/descenders jump in English.
            baseline=-face.getbbox('H' if ord(ch)<128 else '国',anchor='ls')[1]
            d.text((x+3,y+3+baseline),ch,font=face,fill='white',anchor='ls')
            self.glyphs[ch]=(x,y,face.getlength(ch))
        self.add('font',atlas)

    def add(self,name,image):
        import moderngl
        image=image.convert('RGBA');tex=self.ctx.texture(image.size,4,image.tobytes())
        tex.filter=(moderngl.LINEAR,moderngl.LINEAR);tex.repeat_x=False;tex.repeat_y=False
        self.textures[name]=tex

    def load(self,name,path,crop=False):
        if name not in self.textures:
            im=Image.open(path).convert('RGBA')
            if crop:im=im.crop(im.getbbox())
            self.add(name,im)

    def begin(self,screen):
        self.flush();self.program['viewport'].value=tuple(screen);self.draw_calls=0

    def flush(self):
        if not self.vertices:return
        import moderngl
        texture,add,brightness=self.batch
        self.ctx.disable(moderngl.DEPTH_TEST);self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func=(moderngl.SRC_ALPHA,moderngl.ONE if add else moderngl.ONE_MINUS_SRC_ALPHA,moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
        self.textures[texture].use(0);self.program['image'].value=0;self.program['brightnessAlpha'].value=int(brightness)
        data=np.asarray(self.vertices,dtype='f4');self.buffer.write(data.tobytes());self.vao.render(vertices=len(data))
        self.vertices=[];self.draw_calls+=1

    def polygon(self,points,color,texture='white',uvs=None,add=False,brightness=False):
        key=(texture,add,brightness)
        if self.batch!=key or len(self.vertices)>24000:self.flush();self.batch=key
        uvs=uvs or [(0,0)]*len(points)
        colors=color if isinstance(color[0],(tuple,list)) else [color]*len(points)
        for i in range(1,len(points)-1):
            for j in (0,i,i+1):self.vertices.append((*points[j],*uvs[j],*colors[j]))

    def rect(self,x,y,w,h,color,texture='white',uv=(0,0,1,1),**opts):
        if w<=0 or h<=0:return
        u,v,r,b=uv
        if isinstance(color[0],(tuple,list)):
            self.polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],color,texture,[(u,v),(r,v),(r,b),(u,b)],**opts)
            return
        key=(texture,opts.get('add',False),opts.get('brightness',False))
        if self.batch!=key or len(self.vertices)>24000:self.flush();self.batch=key
        # Same two triangles and draw order, without temporary polygon/UV lists.
        a=(x,y,u,v,*color);c=(x+w,y+h,r,b,*color)
        self.vertices.extend((a,(x+w,y,r,v,*color),c,a,c,(x,y+h,u,b,*color)))

    def line(self,a,b,width,color):
        dx=b[0]-a[0];dy=b[1]-a[1];n=max(.001,math.hypot(dx,dy));nx=-dy/n*width/2;ny=dx/n*width/2
        self.polygon([(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny),(a[0]-nx,a[1]-ny)],color)

    def lines(self,points,width,color):
        for a,b in zip(points,points[1:]):self.line(a,b,width,color)

    def text(self,label,x,y,size=7,color=(.94,.91,.8,1),center=False):
        label=str(label);scale=size/48
        if center:x-=sum(self.glyphs.get(ch,self.glyphs['?'])[2] for ch in label)*scale/2
        for ch in label:
            u,v,advance=self.glyphs.get(ch,self.glyphs['?'])
            self.rect(x-3*scale,y-3*scale,64*scale,80*scale,color,'font',(u/self.font_size[0],v/self.font_size[1],(u+64)/self.font_size[0],(v+80)/self.font_size[1]))
            x+=advance*scale
