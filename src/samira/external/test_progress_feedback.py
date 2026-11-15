"""Actual GPU checks for XP and absence of custom level-up effects."""
from overlay import create_window,glfw,Effects,HUD,ROOT,HERE,np,Image
from test_combat import snapshot

window,ctx=create_window(False)
try:
    fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
    hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
    fbo=ctx.framebuffer([ctx.texture((1280,720),4)]);fbo.use();ctx.viewport=(0,0,1280,720)
    shots=[]
    for xp in (0,140,280):
        s=snapshot();s['hud']['xp']=xp;s['hud']['buffs']=[dict(icon='WhiteHeartHalf',count=1),dict(icon='GoldHeartOverlay',count=2)]
        hud.reset();ctx.clear(0,0,0,0);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
        frame=np.asarray(Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM));shots.append(frame)
    assert not np.array_equal(shots[0][630:690,60:84],shots[1][630:690,60:84]),'earning XP fills the portrait arc'
    assert not np.array_equal(shots[1][630:690,60:84],shots[2][630:690,60:84]),'the upper arc fills toward the threshold'
    assert np.array_equal(shots[0][702:714,96:306],shots[2][702:714,96:306]),'no horizontal XP strip below skills'
    for age in (0,15,45,60):
        s=snapshot();s['levelUp']=s['clock']-age
        ctx.clear(0,0,0,0);fx.draw(s,0);fx.foreground(s,None);ctx.finish()
        pixels=np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(720,1280,4)
        assert not pixels[:,:,3].any(),'leveling must not draw a custom burst, rays or text'
    calls=[];original=fx.client.draw
    fx.client.draw=lambda name,*args,**kwargs:calls.append(name)
    for age in (0,44,45,300):
        calls.clear();s=snapshot();s['r']=dict(started=s['clock']-age,untilTick=s['clock']+100)
        fx.draw(s,0)
        assert ('R_Fear' in calls)==(age<45),'fear particles cannot last the whole ultimate'
    fx.client.draw=original
    sheet=Image.new('RGBA',(640,390),(35,35,35,255))
    for i,frame in enumerate(shots):sheet.alpha_composite(Image.fromarray(frame).crop((0,580,640,710)),(0,i*130))
    sheet.save(HERE/'progress-077-review.png')
    assert ctx.error=='GL_NO_ERROR'
    print('GPU XP zero/half/full, buff row, no custom level burst and R fear particle expiry passed')
finally:
    glfw.destroy_window(window);glfw.terminate()
