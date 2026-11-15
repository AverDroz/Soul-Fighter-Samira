"""Source animation visibility and scrolling-material rendering regressions."""
from overlay import Windows,create_window,glfw,Model,GPURenderer,ROOT,HERE,Image,np
from model import visible_parts
v=visible_parts('Idle',.5,1.9,False,True)
assert v['Banner'] and not v['Wings']
assert not visible_parts('Idle',.5,1.9,False,False)['Banner']
assert visible_parts('RIdle',.5,1.4,True,False)['Wings'],'Ctrl+5 cannot hide R wings'
assert not visible_parts('RIdle',.5,1.4,True,True)['Banner']
assert not visible_parts('Taunt_Into',5.2/6.2,6.2,False,True)['Wings']
v=visible_parts('Taunt_Into',5.4/6.2,6.2,False,True)
assert v['Wings'] and not v['Banner'] and not v['Shoulder']
assert visible_parts('Taunt_loop',0,1.7,False,False)['Wings']
Windows();window,ctx=create_window(False)
try:
    model=Model(ROOT/'reference/source/model.glb');renderer=GPURenderer(ctx,model)
    fbo=ctx.framebuffer([ctx.texture((1200,800),4)],ctx.depth_renderbuffer((1200,800)))
    fbo.use();ctx.viewport=(0,0,1200,800)
    shots=[]
    for t in (0,.8):
        ctx.clear(0,0,0,0);renderer.effect_time=t
        renderer.draw('Idle',.4,(300,280),(600,400),.35,0,banner=True)
        ctx.finish();shots.append(np.frombuffer(fbo.read(components=4),dtype=np.uint8).copy())
    assert np.count_nonzero(shots[0]!=shots[1])>50,'ribbon mask must visibly scroll while body pose is fixed'
    ctx.clear(0,0,0,0)
    examples=[('Unsheath_Idle01',.4,True,False),('Unsheath_Idle01',.4,False,False),('Idle_Ult_Base',.4,True,True),
              ('Taunt_Into',.5,True,False),('Taunt_Into',.95,True,False),('Taunt_loop',.4,False,False)]
    for i,(clip,phase,banner,ult) in enumerate(examples):
        renderer.kind=None;renderer.pose=None;renderer.previous=None
        renderer.draw('Idle',phase,(100+(i%3)*200,170+(i//3)*200),(600,400),.35,.2,ultimate=ult,clip=clip,banner=banner)
    ctx.finish()
    Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(HERE/'ribbons-preview.png')
    print('Banner toggle independent of R; taunt frame-159/loop visibility; animated source mask GPU checks passed.')
finally:glfw.destroy_window(window);glfw.terminate()
