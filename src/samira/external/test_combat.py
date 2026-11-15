"""Hidden GPU regression and contact sheet; never touches the running game's input."""
import copy,json,math,time
from pathlib import Path
from overlay import create_window,ROOT,HERE,glfw,Model,GPURenderer,Effects,HUD,np,Image

def snapshot():
    return dict(screen=[640,360],ground=[1,.98],position=[260,190],face=[1,0],clock=100,packetClock=100,
        kind='Idle',phase=.3,banner=True,fx=[],hits=[],r={},
        hud=dict(hp=650,maxHP=650,red=1,soul=0,level=1,xp=120,nextXP=280,gold=12,qStage=1,
          layout=dict(left=dict(x=6,y=309,w=154,h=47),right=dict(x=518,y=324,w=122,h=36)),
          skills={k:dict(remaining=0,total=v) for k,v in zip('qwer',[150,420,90,3600])}))

SHAPES=[dict(kind='box',near=0,far=182,width=25.2,sweet=134.4),
        dict(kind='wedge',near=-28,far=147,narrow=42,width=70,sweet=105),
        dict(kind='circle',cx=56,radius=84,inner=50.4)]

def run():
    window,ctx=create_window(False)
    try:
        model=Model(ROOT/'reference/source/model.glb');renderer=GPURenderer(ctx,model)
        effects=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png');hud=HUD(effects.canvas,ROOT/'mod/resources/gfx/samira/hud')
        fbo=ctx.framebuffer([ctx.texture((1280,720),4)],ctx.depth_renderbuffer((1280,720)));fbo.use();ctx.viewport=(0,0,1280,720)
        cases=[]
        for stage in range(1,4):
            s=snapshot();s.update(kind='Q'+str(stage),phase=[.48,.65,.42][stage-1],shape=SHAPES[stage-1],cast=dict(kind='Q'+str(stage),stage=stage,age=15,impact=18,duration=24))
            cases.append(('Q'+str(stage)+' windup',s))
        s=snapshot();s.update(kind='Q3',phase=.56,fx=[dict(position=s['position'],face=s['face'],stage=3,age=2,shape=SHAPES[2])],hits=[dict(position=[326,184],at=98,strong=True)])
        cases.append(('Q3 impact / actual hit',s))
        s=snapshot();s.update(kind='W',phase=.6,bolt=dict(origin=s['position'],position=[440,190],face=s['face']));cases.append(('W chain missile',s))
        s=snapshot();s['chain']=dict(anchor=[410,190],target=[428,210],face=s['face'],expires=115,pulled=False,shape=dict(kind='wedge',near=-75.6,far=75.6,narrow=37.8,width=75.6,sweet=75.6));cases.append(('W tether / escape zone',s))
        s=snapshot();s.update(kind='Dash',phase=.5,dash=dict(age=5,duration=12,origin=[200,190],target=[284,190]));cases.append(('E model afterimages',s))
        s=snapshot();s.update(kind='RStart',phase=.6,ultimate=True,r=dict(started=92,untilTick=392));cases.append(('R startup / screen edge',s))
        pictures=[]
        def draw(s):
            ctx.clear(.14,.105,.075,1);effects.draw(s,0)
            if s.get('dash'):
                pose=model.sample(s['kind'],.3)
                for i in (3,2,1):renderer.draw(s['kind'],.3,(s['position'][0]-i*12,s['position'][1]),s['screen'],math.pi/2,0,ghost=(pose,math.pi/2,.12+i*.03))
            sockets=renderer.draw(s['kind'],s['phase'],s['position'],s['screen'],math.pi/2,1/60,s.get('ultimate',False),banner=True)
            assert all(np.isfinite(v).all() for v in sockets.values())
            effects.foreground(s,sockets);effects.screen(s);hud.draw(s)
        for name,s in cases:
            effects.reset();hud.reset();renderer.kind=None;renderer.pose=None;renderer.yaw=None
            draw(s);ctx.finish()
            effects.canvas.text(name,180,14,10);effects.canvas.flush()
            im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            assert np.asarray(im)[:,:,:3].std()>8,'empty output';pictures.append(im.resize((800,450)))
        sheet=Image.new('RGBA',(1600,1800))
        for i,im in enumerate(pictures):sheet.paste(im,((i%2)*800,(i//2)*450))
        sheet.save(HERE/'combat-review.png')
        # Same shared shape in cardinal and diagonal directions, with only 2% Y compression.
        for shape in SHAPES:
            for a in (0,math.pi/4,math.pi/2,math.pi):
                points=effects.outline((0,0),(math.cos(a),math.sin(a)),shape)
                assert all(math.isfinite(v) for pt in points for v in pt)
        # Exercise real telemetry combinations: QE, half HP, level 18, death, empty events.
        s=snapshot();s.update(kind='RQ2',phase=.8,ultimate=True,shape=SHAPES[1],cast=dict(kind='Q2',stage=2,age=17,impact=18,duration=24),dash=dict(age=4,duration=10),r=dict(started=30,untilTick=330),fx=cases[3][1]['fx'],hits=cases[3][1]['hits'],chain=cases[5][1]['chain'])
        s['hud'].update(hp=1800,maxHP=3600,red=.4,soul=.1,level=18);s['hud']['skills']['w']['remaining']=300
        timings=[]
        for i in range(90):
            start=time.perf_counter();draw(s);ctx.finish();timings.append((time.perf_counter()-start)*1000)
        s['dead']=True;s['kind']='Death';s['phase']=1;draw(s)
        effects.reset();hud.reset();assert not effects.trail and hud.hp is None
        assert ctx.error=='GL_NO_ERROR',ctx.error
        report=dict(gpu=ctx.info['GL_RENDERER'],mean_ms=float(np.mean(timings[10:])),p95_ms=float(np.percentile(timings[10:],95)),
            scope='Offscreen 1280x720: model + three E ghosts + Q/W/R effects + HD HUD. Not live FPS.',cases=[name for name,_ in cases])
        (HERE/'combat-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
