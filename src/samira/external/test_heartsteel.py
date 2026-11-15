"""Original asset integrity, persistent ready state, and bounded GPU playback."""
import json,time
from overlay import create_window,HERE,glfw,Image,np
from client_vfx import ClientParticles

def run():
    window,ctx=create_window(False)
    try:
        fx=ClientParticles(ctx,bundle='heartsteel')
        manifest=json.loads((HERE/'assets/client/heartsteel-manifest.json').read_text())
        assert len(fx.systems)==10 and len(manifest['assets'])==43 and not manifest['missing']
        fbo=ctx.framebuffer([ctx.texture((800,600),4)]);fbo.use();ctx.viewport=(0,0,800,600)
        # A black additive texel contributes no light. It must also contribute
        # no desktop opacity: otherwise rotating quads become black diamonds.
        fx.add_texture('test_black',Image.new('RGBA',(1,1),(0,0,0,255)))
        fx.systems['test_additive']={'complexEmitterDefinitionData':[dict(rate=1,isSingleParticle=True,
            particleLifetime=1,birthScale0=[40,40,1],texture='test_black',blendMode=4)]}
        for authored in (False,True):
            fx.authored=authored;fx.reset();ctx.clear(0,0,0,0);fx.begin((400,300),(1,1),0)
            fx.draw('test_additive',.2,(200,150),(0,-1));ctx.finish()
            alpha=np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(600,800,4)[:,:,3]
            assert (alpha.max()==0) if authored else (alpha.max()>0)
        del fx.systems['test_additive'];fx.reset()
        pictures=[];cost=[]
        cases=[('3084_Goliath_'+n+'Stack',t) for n in ('Two','Three','Four','Five','Six') for t in (.1,.45)]
        cases += [('3084_Goliath_SixStack',10),('3084_Goliath_SixStack',60)]
        cases += [(n,t) for n in ('3084_Goliath_Impact','3084_Goliath_Impact_Chest') for t in (.08,.2,.5)]
        for index,(name,age) in enumerate(cases):
            ctx.clear(.13,.11,.09,1);fx.begin((400,300),(1,.98),index)
            start=time.perf_counter();fx.draw(name,age,(200,200),(0,-1),key=1,bound_size=100);ctx.finish();cost.append((time.perf_counter()-start)*1000)
            assert fx.stats['particles']>0,(name,age)
            assert fx.stats['particles']<2048,fx.stats
            im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            pixels=np.asarray(im)[:,:,:3]
            assert np.count_nonzero(np.max(np.abs(pixels.astype(float)-pixels[0,0]),axis=2)>8)>10,(name,age,'invisible particles')
            from PIL import ImageDraw
            ImageDraw.Draw(im).text((15,15),name+' / '+str(age)+'s',fill='white')
            pictures.append(im.resize((400,300)))
        sheet=Image.new('RGBA',(1200,1800))
        for i,im in enumerate(pictures):sheet.paste(im,((i%3)*400,(i//3)*300))
        sheet.save(HERE/'heartsteel-original-review.png')
        fx.reset()
        for frame in range(180):
            fx.begin((400,300),(1,.98),frame)
            fx.draw('3084_Goliath_SixStack',frame/3,(200,200),(0,-1),key='enemy',bound_size=100)
        assert len(fx.cache)<=3,len(fx.cache)
        fx.begin((400,300),(1,.98),400);assert not fx.cache
        assert ctx.error=='GL_NO_ERROR',ctx.error
        report=dict(systems=10,assets=43,missing=[],transparent_additive_regression='passed',unsupported=sorted(fx.unsupported),sample_mean_ms=sum(cost)/len(cost),scope='Hidden 800x600 original particle playback; not live game FPS')
        (HERE/'heartsteel-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
