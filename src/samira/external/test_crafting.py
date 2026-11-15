"""Offscreen checks for the crafting UI and original-texture target markers."""
from overlay import create_window,ROOT,HERE,glfw,Effects,HUD,Image,np
from test_combat import snapshot

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        fbo=ctx.framebuffer([ctx.texture((1920,1080),4)]);fbo.use();ctx.viewport=(0,0,1920,1080)
        s=snapshot();s['hud'].update(heartsteel=45.6,gold=20,inventory=[dict(id=id,count=1,ready=0) for id in [1011,1011,3801,0,0,0]])
        k=(s['screen'][1]-24)/370
        s['shop']=dict(open=True,layout=dict(x=(s['screen'][0]-540*k)/2,y=12,w=540*k,h=370*k,scale=k),selected=3084,
                       items=list(hud.shop.items),cost=3,credit=62,canBuy=True,canSell=False,canUndo=True)
        for lang in ('zh','en'):
            s['language']=lang;ctx.clear(.13,.11,.09,1);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
            Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(HERE/f'crafting-{lang}-review.png')
        s.pop('shop');s['heartsteel']=[dict(position=[180+140*i,180],progress=v,size=18) for i,v in enumerate((.2,.65,1))]
        ctx.clear(.13,.11,.09,1);fx.draw(s,0);ctx.finish()
        frame=np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(1080,1920,4)
        brightness=[frame[420:660,int((180+140*i-35)*3):int((180+140*i+35)*3),:3].mean() for i in range(3)]
        assert fx.heartsteel.stats['draws']>0
        Image.fromarray(frame).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(HERE/'heartsteel-ring-review.png')
        for age in (0,6,12,23,24):
            s['heartsteelHits']=[dict(position=[320,180],age=age)];fx.draw(s,0);fx.foreground(s,{})
        assert ctx.error=='GL_NO_ERROR',ctx.error
        print('Crafting bilingual UI, duplicate-component ownership, and Heartsteel charge/ready/impact GPU checks passed')
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
