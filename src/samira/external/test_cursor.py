"""Pointer proportions on GPU and balanced, game-scoped native visibility."""
import ctypes
from native_cursor import NativeCursor,CursorInfo


def test_visibility():
    class API:
        def __init__(self):self.count=0;self.x=50;self.y=50;self.calls=[];self.fail=False
        def GetCursorInfo(self,ptr):
            info=ctypes.cast(ptr,ctypes.POINTER(CursorInfo)).contents
            info.flags=int(self.count>=0);info.ptScreenPos.x=self.x;info.ptScreenPos.y=self.y;return True
        def GetWindowThreadProcessId(self,hwnd,_):return hwnd
        def AttachThreadInput(self,source,target,on):self.calls.append((target,on));return not self.fail
        def ShowCursor(self,on):self.count+=1 if on else -1;return self.count
    c=NativeCursor.__new__(NativeCursor);c.u=API();c.thread=10;c.owner=None;c.hidden=0
    c.update(20,(0,0,100,100),True);assert c.u.count==-1 and c.hidden==1
    for _ in range(30):c.update(20,(0,0,100,100),True)
    assert c.u.calls==[(20,True)] and c.hidden==1,'never reattach/reset keyboard state every frame'
    c.u.count+=2;c.update(20,(0,0,100,100),True);assert c.hidden==3 and c.u.count==-1
    c.u.x=120;c.update(20,(0,0,100,100),True);assert c.owner is None and c.u.count==2,'leaving client restores only our decrements'
    c.u.x=50;c.update(20,(0,0,100,100),True);c.update(None,None,False)
    assert c.owner is None and c.u.count==2,'focus loss/stale telemetry restores pointer'
    c.update(20,(0,0,100,100),False);assert c.owner is None,'paused/menu/preview cannot hide OS pointer'
    c.u.fail=True;c.update(20,(0,0,100,100),True);assert c.hidden==0 and c.owner is None
    c.restore();assert c.u.count==2,'failed attachment cannot change visibility'
    c.u.fail=False;c.update(20,(0,0,100,100),True);c.restore();c.restore();assert c.u.count==2
    print('Native pointer visibility: balanced show count, foreground/client scope, no repeated attachment, failed attachment and cleanup passed')


def test_pixels():
    from overlay import create_window,ROOT,glfw,Effects,HUD,Image,np
    from test_combat import snapshot
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        assert fx.canvas.textures['hand1'].size==fx.canvas.textures['hand2'].size==(114,114)
        fbo=ctx.framebuffer([ctx.texture((1280,720),4)]);fbo.use();ctx.viewport=(0,0,1280,720)
        s=snapshot();s.update(screen=[640,360],actorHidden=True,goldFX=[])
        boxes=[]
        for x,down in ((400,False),(500,True),(500,False)):
            s['cursor']={'position':[x,100],'down':down}
            ctx.clear(0,0,0,0);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
            im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            crop=im.crop((x*2,200,x*2+40,240));box=crop.getchannel('A').getbbox()
            assert box and box[2]-box[0]<.8*(box[3]-box[1]),'pointer must not be widened to a square'
            boxes.append(box)
        assert boxes[0]==boxes[1]==boxes[2],('moving/held/rest pointer dimensions differ',boxes)
        assert ctx.error=='GL_NO_ERROR'
        print('GPU cursor: moving, held and stationary bounding boxes match; source proportions preserved:',boxes[0])
    finally:glfw.destroy_window(window);glfw.terminate()


if __name__=='__main__':test_visibility();test_pixels()
