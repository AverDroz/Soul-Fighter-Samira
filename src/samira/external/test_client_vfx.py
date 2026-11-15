"""Source curve semantics, bounded particles and whole-system GPU lifecycle."""
import json,time,unittest
from pathlib import Path
import numpy as np
from client_vfx import curve,Emitter

class Curves(unittest.TestCase):
    def test_curve_replaces_constant(self):
        source={'constantValue':100,'dynamics':{'times':[0,1],'values':[100,0]}}
        self.assertEqual(curve(source,.5,1),50)
    def test_probabilities_stay_per_particle(self):
        source={'constantValue':[2,3,4],'dynamics':{'probabilityTables':[{'keyTimes':[0,1],'keyValues':[-1,1]},{},{}]}}
        values=curve(source,0,[0,0,0],np.array([[0,0,0],[1,0,0]]))
        np.testing.assert_allclose(values,[[-2,3,4],[2,3,4]])
    def test_source_lifetime_delay_and_determinism(self):
        d={'rate':{'constantValue':12},'isSingleParticle':True,'timeBeforeFirstEmission':.2,'particleLifetime':{'constantValue':.5}}
        a=Emitter(d,10);b=Emitter(d,10)
        self.assertIsNone(a.instances(.19));self.assertIsNone(a.instances(.71))
        np.testing.assert_array_equal(a.instances(.3),b.instances(.3))
        self.assertEqual(len(a.instances(.3)),12)

def gpu_check():
    from overlay import create_window,glfw
    from client_vfx import ClientParticles
    win,ctx=create_window(False)
    try:
        fx=ClientParticles(ctx);target=ctx.framebuffer([ctx.texture((1280,720),4)]);target.use();ctx.viewport=(0,0,1280,720)
        sampled=0
        for name in fx.systems:
            for t in (0,.04,.1,.3,.8,1.4,2.5,3.5):
                ctx.clear(0,0,0,0);fx.begin([640,360],[1,.98],t*30)
                fx.draw(name,t,[270,220],[.70710678,.70710678],key=name)
                assert fx.stats['particles']<=1000,(name,fx.stats)
                assert ctx.error=='GL_NO_ERROR',(name,t,ctx.error)
                sampled+=1
        # Actual pixels, not just shape math: the original Q1 closed/sweet edge
        # must face away from the caster, and Q2 must widen toward its tip.
        def marker(stage):
            ctx.clear(0,0,0,0);fx.begin([640,360],[1,.98],15)
            fx.draw('Q_Indicator_0'+str(stage),.5,[200,180],[1,0],key='orientation')
            ctx.finish()
            return np.frombuffer(target.read(components=4),dtype=np.uint8).reshape(720,1280,4)[::-1]
        pixels=marker(1)
        near=pixels[354:360,430:540,0].max();far=pixels[354:360,670:782,0].max()
        assert int(far)>int(near)+20,('Q1 sweet edge must be forward',int(near),int(far))
        pixels=marker(2)
        def width(x):
            ys=np.where(pixels[:,int(x*2)-3:int(x*2)+4,0].max(axis=1)>20)[0]
            return int(ys[-1]-ys[0]) if len(ys) else 0
        assert width(330)>width(220)+30,('Q2 must widen forward',width(220),width(330))
        # Simultaneous 16-target sweetspot hit plus Q3, W, E and R startup.
        timings=[]
        for i in range(90):
            age=(i%25)/30;start=time.perf_counter();ctx.clear(0,0,0,0);fx.begin([640,360],[1,.98],100+age*30)
            for j in range(16):fx.draw('Q_Sweet_hit_tar',age,[150+j%4*70,130+j//4*35],[1,0],key=j)
            for name in ['Q_cas3','R_Fear','E_Dash2','W_mis']:fx.draw(name,age,[270,220],[1,0],key=name)
            ctx.finish();timings.append((time.perf_counter()-start)*1000)
        fx.reset();assert not fx.cache
        report={'samples':sampled,'stress_mean_ms':float(np.mean(timings[10:])),'stress_p95_ms':float(np.percentile(timings[10:],95)),
            'scope':'Offscreen particle-only stress, 16 simultaneous sweetspot targets; not live game FPS.',
            'omitted_emitters':sorted(fx.unsupported)}
        Path('client-vfx-test.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='omitted_emitters'}))
    finally:glfw.destroy_window(win);glfw.terminate()

if __name__=='__main__':
    result=unittest.main(exit=False)
    if not result.result.wasSuccessful():raise SystemExit(1)
    gpu_check()
