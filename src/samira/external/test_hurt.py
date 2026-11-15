"""Verify the real GPU body tint changes color, not silhouette/visibility."""
from overlay import create_window,glfw,Model,GPURenderer,ROOT,HERE,np,Image

window,ctx=create_window(False)
try:
    renderer=GPURenderer(ctx,Model(ROOT/'reference/source/model.glb'))
    fbo=ctx.framebuffer([ctx.texture((800,600),4)],ctx.depth_renderbuffer((800,600)))
    fbo.use();ctx.viewport=(0,0,800,600);frames=[]
    for hurt in (False,True,False):
        ctx.clear(0,0,0,0)
        renderer.draw('Idle',.25,(200,215),(400,300),.35,0,hurt=hurt,banner=False)
        ctx.finish()
        frames.append(np.asarray(Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)))
    normal,red,restored=frames;mask=normal[:,:,3]>240
    assert mask.any() and np.array_equal(normal[:,:,3],red[:,:,3]),'tint must not flicker or change opacity'
    assert np.array_equal(normal,restored),'hurt ends without leaving a tint behind'
    assert red[mask,0].mean()>normal[mask,0].mean()+40,'dark armor receives a visible red flash'
    assert red[mask,0].mean()>red[mask,1].mean()*3,'flash is red rather than white'
    assert ctx.error=='GL_NO_ERROR'
    sheet=Image.new('RGBA',(600,300),(45,35,32,255))
    for i,frame in enumerate(frames):sheet.alpha_composite(Image.fromarray(frame).crop((300,200,500,500)),(i*200,0))
    sheet.save(HERE/'hurt-073-review.png')
    print('GPU hurt: strong red body, identical silhouette/alpha, exact recovery passed')
finally:
    glfw.destroy_window(window);glfw.terminate()
