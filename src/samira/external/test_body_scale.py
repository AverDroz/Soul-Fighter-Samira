"""Real GPU silhouette and weapon socket scaling for native size changes."""
from overlay import create_window,glfw,Model,GPURenderer,ROOT,np

window,ctx=create_window(False)
try:
    renderer=GPURenderer(ctx,Model(ROOT/'reference/source/model.glb'))
    fbo=ctx.framebuffer([ctx.texture((800,600),4)],ctx.depth_renderbuffer((800,600)))
    fbo.use();ctx.viewport=(0,0,800,600);sizes=[];sockets=[]
    for scale in (.5,1,1.5):
        ctx.clear(0,0,0,0)
        sockets.append(renderer.draw('Idle',.25,(200,215),(400,300),.35,0,banner=False,body_scale=(scale,scale)))
        ctx.finish()
        alpha=np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(600,800,4)[:,:,3]
        y,x=np.where(alpha>128);assert len(x)>0
        sizes.append(np.array([x.max()-x.min()+1,y.max()-y.min()+1]))
    for index,scale in enumerate((.5,1,1.5)):
        assert np.max(abs(sizes[index]-sizes[1]*scale))<=3,'visible model must scale with native SpriteScale'
        for name in ('base','tip'):
            expected=np.array([200,215])+(np.array(sockets[1][name])-[200,215])*scale
            assert np.allclose(sockets[index][name],expected),'weapon sockets must scale with the body'
    flight_sizes=[];flight_sockets=[]
    for ultimate in (False,True):
        ctx.clear(0,0,0,0)
        flight_sockets.append(renderer.draw('RIdle',.25,(200,215),(400,300),.35,0,
                                           ultimate=ultimate,flying=True,banner=False))
        ctx.finish()
        alpha=np.frombuffer(fbo.read(components=4),dtype=np.uint8).reshape(600,800,4)[:,:,3]
        y,x=np.where(alpha>128);assert len(x)>0
        flight_sizes.append(np.array([x.max()-x.min()+1,y.max()-y.min()+1]))
        assert abs(renderer.program['scale'].value-(26.24 if ultimate else 23.04))<1e-4
    ratio=26.24/23.04
    assert np.max(abs(flight_sizes[1]-flight_sizes[0]*ratio))<=3,'only active R enlarges the flying silhouette'
    for name in ('base','tip'):
        expected=np.array([200,215])+(np.array(flight_sockets[0][name])-[200,215])*ratio
        assert np.allclose(flight_sockets[1][name],expected)
    print('GPU normal-size flight and enlarged R silhouette/socket comparison passed')
    assert ctx.error=='GL_NO_ERROR' 
    print('GPU body silhouette and sword sockets at half/normal/1.5 native size passed')
finally:
    glfw.destroy_window(window);glfw.terminate()
