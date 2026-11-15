"""Moving overhead ticks must keep identical pixels at fractional positions."""
from overlay import create_window,ROOT,glfw,Effects,HUD,Image,np
from test_combat import snapshot

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        for size in ((1280,720),(1920,1080),(2561,1440)):
            fbo=ctx.framebuffer([ctx.texture(size,4)]);fbo.use();ctx.viewport=(0,0,*size)
            s=snapshot();s.update(screen=[640,360],cursor=None,goldFX=[],ultimate=False,actorHidden=False)
            sx,sy=size[0]/640,size[1]/360;baseline=None
            for frame in range(24):
                s['position']=[320+frame*.17,210+frame*.13]
                ctx.clear(0,0,0,0);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
                im=Image.frombytes('RGBA',size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                x=round((s['position'][0]-28)*sx);y=round((s['position'][1]-66)*sy)
                crop=np.asarray(im.crop((x,y,x+round(56*sx),y+round(11*sy)))).astype('i2')
                if baseline is None:baseline=crop
                # Allow one quantization level from GPU floating-point interpolation.
                else:assert np.abs(crop-baseline).max()<=1,(size,frame,int(np.abs(crop-baseline).max()))
            fbo.release()
        assert ctx.error=='GL_NO_ERROR'
        print('GPU health bar: 24 fractional XY positions at 1280, 1920 and 2561 widths preserve identical tick/bar pixels (<=1/255 quantization)')
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
