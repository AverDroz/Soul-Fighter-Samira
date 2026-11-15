"""Exercise the original clips through the actual GPU path without touching Isaac."""
from pathlib import Path
import json,time
from overlay import Windows,create_window,glfw,Model,GPURenderer,ROOT,HERE,np,Image
Windows();window,ctx=create_window(False)
try:
    model=Model(ROOT/'reference/source/model.glb');renderer=GPURenderer(ctx,model)
    catalog=json.loads((HERE/'actions.json').read_text())
    assert set(catalog)==set(model.tracks) and len(catalog)==105
    fbo=ctx.framebuffer([ctx.texture((1024,768),4)],ctx.depth_renderbuffer((1024,768)))
    fbo.use();ctx.viewport=(0,0,1024,768)
    start=time.perf_counter()
    upper=next(i for i,n in enumerate(model.nodes) if n.get('name')=='Spine2')
    for action in ('Draw','Sheathe','RStart'):
        locomotion=dict(kind='RWalk' if action=='RStart' else 'Walk',phase=.3)
        mixed=model.moving_pose(action,.4,locomotion);gesture=model.sample(action,.4);walk=model.sample(locomotion['kind'],.3)
        for part,g,w in zip(mixed,gesture,walk):
            assert np.allclose(part[model.walk_nodes],w[model.walk_nodes])
            assert np.allclose(part[upper],g[upper])
        assert np.isfinite(model.matrices(mixed)).all()
        renderer.draw(action,.4,(256,260),(512,384),.35,1/30,locomotion=locomotion)
    for clip in catalog:
        for phase in (0,.5,1):
            pose=model.sample(clip,phase)
            assert np.isfinite(model.matrices(pose)).all(),clip
            ctx.clear(0,0,0,0)
            renderer.draw('Idle',phase,(256,260),(512,384),.35,1/30,clip=clip,banner=True)
    ctx.finish()
    ctx.clear(0,0,0,0)
    examples=[('Joke',.35,False),('Taunt_Into',.7,False),('Dance_Loop',.25,False),('Laugh',.5,False),
              ('Unsheath_Idle01',.5,True),('Run_Ult',.5,True),('Death',.7,False),('Respawn',.5,False)]
    for i,(clip,phase,wings) in enumerate(examples):
        renderer.kind=None;renderer.pose=None;renderer.previous=None
        renderer.draw('Idle',phase,(64+(i%4)*128,165+(i//4)*190),(512,384),.35,.2,ultimate=clip=='Run_Ult',clip=clip,banner=wings)
    ctx.finish()
    image=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    assert image.getbbox();image.save(HERE/'actions-preview.png')
    print(f'All {len(catalog)} original clips sampled and GPU-rendered at start/middle/end ({time.perf_counter()-start:.2f}s); preview saved.')
finally:
    glfw.destroy_window(window);glfw.terminate()
