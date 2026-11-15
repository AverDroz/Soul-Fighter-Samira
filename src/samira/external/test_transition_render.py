"""GPU regression: room handoff keeps identical HUD pixels and clears actor area."""
from overlay import create_window,ROOT,HERE,glfw,Effects,HUD,Image,np
from test_combat import snapshot
from visibility import layers

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        fbo=ctx.framebuffer([ctx.texture((1280,720),4)]);fbo.use();ctx.viewport=(0,0,1280,720)
        s=snapshot();s.update(hudVisible=True,cursor=dict(position=[500,100]),goldFX=[])
        pictures=[]
        for flags in (dict(transition=False,paused=False),dict(transition=True,occluded=True,paused=True),dict(transition=False,occluded=False,paused=False)):
            s.update(flags);actor,screen=layers(s);s['actorHidden']=not actor
            ctx.clear(0,0,0,0);fx.canvas.begin(s['screen'])
            if screen:hud.draw(s)
            ctx.finish();pictures.append(np.asarray(Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)))
        assert np.array_equal(pictures[0][610:,:,:],pictures[1][610:,:,:])
        assert np.array_equal(pictures[0][610:,:,:],pictures[2][610:,:,:])
        assert not pictures[1][200:500,400:800,3].any(),'overhead bar must vanish with actor'
        assert pictures[1][690,170,3]==255,'skill panel interior must be opaque'
        Image.fromarray(pictures[1]).save(HERE/'transition-hud-063.png')
        s.update(presentation=2,occluded=False,hudVisible=True)
        persistent=[]
        for transition,paused in ((False,False),(True,True),(False,True),(False,False)):
            s.update(transition=transition,paused=paused)
            actor,screen=layers(s);assert actor and screen
            s['actorHidden']=not actor
            ctx.clear(0,0,0,0);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
            persistent.append(fbo.read(components=4))
        assert all(frame==persistent[0] for frame in persistent),'HUD and overhead pixels survive room scroll and rainbow pause unchanged'
        assert layers(dict(s,occluded=True,hudVisible=False))==(False,False)
        # Nightmare snapshots must clear every external pixel, including cursor
        # and overhead, while the native cinematic supplies its own portrait.
        s.update(occluded=True,hudVisible=False,click=dict(position=[160,100],at=s['clock']))
        actor,screen=layers(s);ctx.clear(0,0,0,0)
        if actor:fx.draw(s,0);fx.pointer(s)
        if screen:hud.draw(s)
        ctx.finish()
        assert not np.frombuffer(fbo.read(components=4),dtype=np.uint8).any(),'cinematic framebuffer is completely transparent'
        # Full click pointer at start/middle/end, including the previously missing tip.
        sheet=Image.new('RGBA',(960,240),(55,39,30,255))
        for i,age in enumerate((0,4,9,15)):
            s=snapshot();s.update(position=[-999,-999],clock=age,click=dict(position=[160,100],at=0))
            ctx.clear(0,0,0,0);fx.draw(s,0);fx.pointer(s);ctx.finish()
            im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            box=im.getbbox();assert box and box[3]-box[1]>=16,(age,box)
            crop=im.crop((280,155,360,235)).resize((240,240))
            sheet.alpha_composite(crop,(i*240,0))
        sheet.save(HERE/'click-063-review.png')
        # Attack red transfers the source's green channel, not a dark red tint.
        colors=[]
        for enemy in (False,True):
            s=snapshot();s.update(position=[-999,-999],clock=4,click=dict(position=[160,100],at=0,enemy=enemy))
            ctx.clear(0,0,0,0);fx.draw(s,0);fx.pointer(s);ctx.finish()
            colors.append(np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(720,1280,4))
        green,red=colors
        assert np.array_equal(green[:,:,3],red[:,:,3]),'attack marker preserves authored opacity and shape'
        mask=red[:,:,3]>200
        assert mask.any() and red[:,:,0][mask].max()>200,'attack marker must be bright red'
        assert np.array_equal(green[:,:,1],red[:,:,0]) and np.array_equal(green[:,:,0],red[:,:,1])
        assert ctx.error=='GL_NO_ERROR',ctx.error
        print('GPU: identical HUD across room pause/reveal, hidden overhead, opaque backing and four complete click-arrow frames passed')
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
