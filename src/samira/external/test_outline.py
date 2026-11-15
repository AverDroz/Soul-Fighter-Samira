"""Hidden GPU checks for the actor silhouette, transparency and render cost."""
import json,time
from overlay import create_window,glfw,Model,GPURenderer,ROOT,HERE,np,Image

window,ctx=create_window(False)
try:
    renderer=GPURenderer(ctx,Model(ROOT/'reference/source/model.glb'))
    fbo=ctx.framebuffer([ctx.texture((800,600),4)],ctx.depth_renderbuffer((800,600)))
    fbo.use();ctx.viewport=(0,0,800,600)
    def frame(outline,kind='Idle',phase=.25,origin=(200,215),**opts):
        ctx.clear(0,0,0,0)
        renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None
        renderer.draw(kind,phase,origin,(400,300),.35,0,outline=outline,**opts)
        assert ctx.fbo is fbo and ctx.viewport==(0,0,800,600)
        ctx.finish()
        return np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(600,800,4).copy()
    views=[]
    for kind,opts in [('Idle',{'banner':False}),('RIdle',{'ultimate':True}),('Death',{}),('Q3',{'hurt':True})]:
        base=frame(False,kind,**opts);outlined=frame(True,kind,**opts)
        solid=base[:,:,3]==255;added=(base[:,:,3]==0)&(outlined[:,:,3]>10)
        assert added.any(),kind+' gains a visible external edge'
        assert np.array_equal(base[solid],outlined[solid]),'opaque original material is unchanged'
        assert outlined[added,:3].max()<10,'edge is dark, not a glow'
        grown=base[:,:,3]>0
        for _ in range(3):
            pad=np.pad(grown,1)
            grown=np.logical_or.reduce([pad[y:y+600,x:x+800] for y in range(3) for x in range(3)])
        assert not np.any((outlined[:,:,3]>0)&~grown),'outline stays within three physical pixels'
        for image in (base,outlined):
            # GPU readback is premultiplied; composite directly onto the preview background.
            pixels=image.astype(float);alpha=pixels[:,:,3:]/255
            rgb=np.clip(pixels[:,:,:3]+np.array([92,64,52])*(1-alpha),0,255).astype('uint8')
            views.append(Image.fromarray(rgb[::-1]).crop((210,140,590,580)))
    sheet=Image.new('RGB',(760,1760))
    for i,view in enumerate(views):sheet.paste(view,((i%2)*380,(i//2)*440))
    sheet.save(HERE/'outline-review.png')
    surface=renderer.actor_surface
    frame(True,origin=(300,215))
    assert renderer.actor_surface is surface,'reuse GPU surface between frames'
    ghost=(renderer.pose,renderer.yaw,.2)
    assert np.array_equal(frame(False,ghost=ghost),frame(True,ghost=ghost)),'E echoes do not receive solid outlines'
    fbo=ctx.framebuffer([ctx.texture((1920,1080),4)],ctx.depth_renderbuffer((1920,1080)))
    fbo.use();ctx.viewport=(0,0,1920,1080)
    timings={}
    for enabled in (False,True):
        for i in range(10):
            ctx.clear(0,0,0,0);renderer.draw('Walk',i/10,(320,260),(640,360),.35,1/60,outline=enabled)
        ctx.finish();start=time.perf_counter()
        for i in range(90):
            ctx.clear(0,0,0,0);renderer.draw('Walk',(i%30)/30,(320,260),(640,360),.35,1/60,outline=enabled)
        ctx.finish();timings[str(enabled)]=(time.perf_counter()-start)*1000/90
    assert ctx.error=='GL_NO_ERROR',ctx.error
    print(json.dumps({'hidden_gpu_actor_ms':timings,'note':'Includes GPU completion; excludes game/compositor and HUD.'}))
    print('Original opaque pixels, thin dark silhouette, wings/death/Q, ghosts, surface reuse and resize passed')
finally:
    glfw.destroy_window(window);glfw.terminate()
