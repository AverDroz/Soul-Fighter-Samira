"""Original hit texture: bounded opacity, transparent centre and scene gating."""
from overlay import create_window,ROOT,HERE,glfw,Effects,Image,np

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        fbo=ctx.framebuffer([ctx.texture((960,540),4)]);fbo.use();ctx.viewport=(0,0,960,540)
        state=dict(screen=[960,540],clock=120,hud=dict(hp=1000,maxHP=1000))
        assert fx.damage_opacity(state)==0
        state['screenHitAt']=120;assert fx.damage_opacity(state)==.12
        state['clock']=141;assert fx.damage_opacity(state)==0
        state['clock']=120;state['screenHitAt']=0
        values=[];frames=[]
        for hp in (1000,250,50):
            state['hud']['hp']=hp;values.append(fx.damage_opacity(state))
            ctx.clear(0,0,0,0);fx.canvas.begin(state['screen']);fx.screen(state);ctx.finish()
            im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            pixels=np.asarray(im)
            assert pixels[270,480,3]==0,'screen centre must remain fully transparent'
            assert pixels[180:360,320:640,3].max()<=5,'original texture compression speckles must remain imperceptible'
            if hp<300:assert pixels[:20,:,3].max()>0
            # GPU output is premultiplied: composite against opaque terrain in
            # the framebuffer, rather than multiplying its alpha a second time.
            ctx.clear(65/255,52/255,44/255,1);fx.canvas.begin(state['screen']);fx.screen(state);ctx.finish()
            frames.append(Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM))
        assert values[0]==0<values[1]<values[2]<.34
        state['screenHitAt']=120;assert fx.damage_opacity(state)<=.34
        for flag in ('dead','actorHidden','paused','occluded','transition','preview'):
            state[flag]=True;assert fx.damage_opacity(state)==0,flag;state[flag]=False
        review=Image.new('RGB',(960,540*3))
        for i,frame in enumerate(frames):review.paste(frame,(0,i*540))
        review.save(HERE/'damage-screen-review.png')
        assert ctx.error=='GL_NO_ERROR',ctx.error
        print('Damage screen GPU: native texture, clear centre, hit decay, low-health ramp, opacity cap and scene hiding passed')
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
