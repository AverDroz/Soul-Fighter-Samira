"""Render the actual Soul Fighter rig offscreen; no game or desktop input."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/render-deps'))
sys.path.insert(0,str(ROOT/'src/samira/external'))
import glfw,moderngl,numpy as np
from PIL import Image,ImageDraw,ImageFont
from model import Model,GPURenderer,CLIPS


def main():
    output=ROOT/'work/model-preview';output.mkdir(parents=True,exist_ok=True)
    assert glfw.init(),'GLFW initialization failed'
    glfw.window_hint(glfw.VISIBLE,False)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,3)
    window=glfw.create_window(512,512,'Soul Fighter offscreen check',None,None)
    assert window,'Cannot create hidden OpenGL context'
    glfw.make_context_current(window)
    ctx=moderngl.create_context(require=330)
    model=Model(ROOT/'src/samira/reference/source/model.glb')
    renderer=GPURenderer(ctx,model)
    # Fit the authored motion, including jumps/root motion, without cropping.
    def bounds(action,phase,yaw=.3):
        matrices=model.matrices(model.sample(action,phase),action,phase)
        vertices=model.vertices
        skin=(matrices[vertices[:,5:9].astype(int)]*vertices[:,9:13,None,None]).sum(axis=1)
        pos=np.einsum('nij,nj->ni',skin,np.column_stack((vertices[:,:3],np.ones(len(vertices)))))[:,:3]
        visible=model.visibility(action,phase)
        indices=np.unique(np.concatenate([idx for name,idx,_ in model.parts if visible.get(name,True)]))
        pos=pos[indices]
        x=pos[:,0]*np.cos(yaw)+pos[:,2]*np.sin(yaw)
        z=-pos[:,0]*np.sin(yaw)+pos[:,2]*np.cos(yaw)
        xy=np.column_stack((x,-(pos[:,1]*.819152-z*.573576)))
        return xy.min(axis=0),xy.max(axis=0)
    def camera(samples):
        boxes=[bounds(action,phase) for action,phase in samples]
        lo=np.min([b[0] for b in boxes],axis=0);hi=np.max([b[1] for b in boxes],axis=0)
        scale=float(min(440/(hi-lo)))
        return scale,tuple(np.array([256,275])-(lo+hi)*.5*scale)
    fbo=ctx.framebuffer([ctx.texture((512,512),4)],ctx.depth_renderbuffer((512,512)))
    fbo.use();ctx.viewport=(0,0,512,512)
    def frame(action,phase,yaw=.3,view=None):
        fbo.use();ctx.viewport=(0,0,512,512);ctx.clear(0,0,0,0)
        renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None
        model.pixel_scale,origin=view or camera([(action,phase)])
        renderer.draw(action,phase,origin,(512,512),yaw,.2)
        ctx.finish()
        image=Image.frombytes('RGBA',(512,512),fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        assert image.getbbox(),f'Empty frame: {action}'
        return image
    actions=['Idle','Walk','AttackStart','Attack','MeleeAttack','Q','QMelee','W','E','RStart','R','Death']
    sheet=Image.new('RGB',(4*384,3*410),(17,19,30))
    checks=[]
    for index,action in enumerate(actions):
        actor=frame(action,.45)
        bbox=actor.getbbox();checks.append({'action':action,'clip':CLIPS[action],'bbox':bbox})
        actor.thumbnail((384,384));x=index%4*384;y=index//4*410
        sheet.paste(actor,(x,y+22),actor)
        ImageDraw.Draw(sheet).text((x+16,y+10),action,fill=(235,210,165))
    sheet.save(output/'soul-fighter-contact-sheet.png')
    frames=[]
    timeline=[('Idle',1.),('Walk',1.2),('AttackStart',.45),('Attack',.45),('Q',.7),('W',.9),('E',.6),('RStart',.5),('R',1.5)]
    samples=[(action,i/max(1,round(seconds*16)-1)) for action,seconds in timeline for i in range(max(2,round(seconds*16)))]
    view=camera(samples)
    for action,seconds in timeline:
        for i in range(max(2,round(seconds*16))):
            actor=frame(action,i/max(1,round(seconds*16)-1),view=view)
            canvas=Image.new('RGBA',actor.size,(17,19,30,255));canvas.alpha_composite(actor)
            ImageDraw.Draw(canvas).text((18,18),'SOUL FIGHTER SAMIRA  /  '+action,fill=(255,215,140))
            frames.append(canvas.convert('RGB'))
    frames[0].save(output/'soul-fighter-animation.gif',save_all=True,append_images=frames[1:],duration=62,loop=0,optimize=False)
    report={'scope':'Offscreen original-model animation rendering; not live Isaac gameplay',
        'gpu':ctx.info['GL_RENDERER'],'bones':len(model.joints),'animations':len(model.tracks),
        'rendered_actions':checks,'frames':len(frames)}
    (output/'render-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))
    glfw.destroy_window(window);glfw.terminate()


if __name__=='__main__':main()
