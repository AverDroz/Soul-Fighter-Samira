"""Equivalence and timed before/after comparison; hidden GPU surface only."""
import json,time,types
from overlay import Model,GPURenderer,create_window,glfw,ROOT,np
from canvas import Canvas
from combat_effects import Effects
from hud import HUD
from test_combat import snapshot


def reference_sample(self,kind,phase):
    from model import CLIPS
    name=CLIPS.get(kind,kind if kind in self.tracks else CLIPS['Idle'])
    at=max(0,min(1,phase))*self.durations[name]
    t,r,s=self.t.copy(),self.r.copy(),self.s.copy();targets={'translation':t,'rotation':r,'scale':s}
    for node,path,times,values,mode in self.tracks[name]:
        if path not in targets:continue
        k=max(0,min(len(times)-1,int(np.searchsorted(times,at,side='right'))-1));k2=min(k+1,len(times)-1)
        a,b=values[k],values[k2]
        if path=='rotation' and np.dot(a,b)<0:b=-b
        weight=0 if k==k2 or mode=='STEP' else (at-times[k])/(times[k2]-times[k])
        targets[path][node]=a*(1-weight)+b*weight
    r/=np.maximum(1e-8,np.linalg.norm(r,axis=1,keepdims=True))
    return t,r,s


def reference_rect(self,x,y,w,h,color,texture='white',uv=(0,0,1,1),**opts):
    if w<=0 or h<=0:return
    u,v,r,b=uv
    self.polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],color,texture,[(u,v),(r,v),(r,b),(u,b)],**opts)


def run():
    model=Model(ROOT/'reference/source/model.glb');largest=0
    for name in model.tracks:
        for phase in (-.1,0,.013,.171,.333,.501,.739,.999,1,1.1):
            for actual,expected in zip(model.sample(name,phase),reference_sample(model,name,phase)):
                largest=max(largest,float(np.max(np.abs(actual-expected))))
                np.testing.assert_array_equal(actual,expected,err_msg=f'{name} at {phase}')
    # In addition to pixels, verify blend flags/UVs/triangle ordering exactly.
    def geometry(rect):
        c=object.__new__(Canvas);c.vertices=[];c.batch=None;flushed=[]
        def flush():flushed.append((c.batch,list(c.vertices)));c.vertices=[]
        c.flush=flush
        for opts in ({},{'add':True},{'brightness':True}):
            rect(c,1.25,3.5,42,11,(.1,.2,.3,.4),'test',(.1,.3,.7,.9),**opts)
        rect(c,0,1,4,5,[(1,0,0,1)]*4)
        flush();return flushed
    assert geometry(Canvas.rect)==geometry(reference_rect)

    window,ctx=create_window(False)
    try:
        renderer=GPURenderer(ctx,model)
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        fbo=ctx.framebuffer([ctx.texture((1920,1080),4)],ctx.depth_renderbuffer((1920,1080)))
        fbo.use();ctx.viewport=(0,0,1920,1080)
        optimized_sample=model.sample;optimized_rect=fx.canvas.rect
        def mode(fast):
            model.sample=optimized_sample if fast else types.MethodType(reference_sample,model)
            fx.canvas.rect=optimized_rect if fast else types.MethodType(reference_rect,fx.canvas)
        def reset():
            renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None;renderer.effect_time=0
            fx.reset();hud.reset()
        def frame(i,kind='Walk'):
            s=snapshot();s.update(clock=100+i*.5,phase=(i%100)/100,kind=kind)
            ctx.clear(0,0,0,0);fx.draw(s,0)
            sockets=renderer.draw(kind,s['phase'],s['position'],s['screen'],.5,1/60)
            fx.foreground(s,sockets);fx.screen(s);fx.pointer(s);hud.draw(s)
        for kind in ('Walk','Q1','Q2','Q3','Death'):
            images=[]
            for fast in (False,True):
                mode(fast);reset();frame(43,kind);ctx.finish();images.append(fbo.read(components=4))
            assert images[0]==images[1],f'GPU image changed: {kind}'
        timings={False:[],True:[]}
        for _ in range(3):
            for fast in (False,True):
                mode(fast);reset()
                for i in range(20):frame(i)
                ctx.finish();start=time.perf_counter()
                for i in range(180):frame(i)
                ctx.finish();timings[fast].append((time.perf_counter()-start)*1000/180)
        assert ctx.error=='GL_NO_ERROR',ctx.error
        result={'clips':len(model.tracks),'max_pose_error':largest,'gpu_pixels_identical':True,
                'resolution':[1920,1080],'before_frame_ms':float(np.median(timings[False])),
                'after_frame_ms':float(np.median(timings[True])),
                'before_runs_ms':timings[False],'after_runs_ms':timings[True],
                'note':'Hidden GPU Walk+HUD workload; includes submission and final GPU completion, excludes game, compositor and frame limiter.'}
        (ROOT/'reference/performance-0721.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:glfw.destroy_window(window);glfw.terminate()


if __name__=='__main__':run()
