"""Hidden GPU resolution matrix using the real Lua layouts; no game input/settings.

DPI/monitor-origin cases test coordinate math, not physical multi-monitor hardware.
"""
import ctypes
import json
import math
import sys
import time
from pathlib import Path

from overlay import create_window, Windows, ROOT, glfw, Effects, HUD, Image, np, Model, GPURenderer
from test_combat import snapshot
from visibility import layers

sys.path.insert(0, str(ROOT.parent/'mcxisaac-steve/tools/deps'))
from lupa.lua54 import LuaRuntime

CASES=[(800,600),(1024,768),(1280,720),(1366,768),(1280,800),
       (1920,1080),(2560,1440),(3840,2160),(3440,1440),(5120,1440)]


def run():
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.globals().include=lambda name: lua.execute((ROOT/'mod/scripts/samira_shop_catalog.lua').read_text(encoding='utf8')) if name.endswith('shop_catalog') else lua.table()
    h=lua.execute((ROOT/'mod/scripts/samira_hud.lua').read_text(encoding='utf8'))
    shop=lua.execute((ROOT/'mod/scripts/samira_shop.lua').read_text(encoding='utf8'))
    def plain(t):
        return {k:plain(v) if hasattr(v,'items') else v for k,v in t.items()}
    windows=Windows()
    window,ctx=create_window(False)
    output=ROOT/'reference/release-qa';output.mkdir(exist_ok=True)
    report={'gpu':ctx.info['GL_RENDERER'],'max_texture_size':ctx.info['GL_MAX_TEXTURE_SIZE'],
            'scope':'Offscreen GPU; real Lua layout; synthetic DPI/origin coordinates. Not ten physical computers.', 'cases':[]}
    pictures=[]
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        model=Model(ROOT/'reference/source/model.glb');renderer=GPURenderer(ctx,model)
        for width,height in CASES:
            tex=ctx.texture((width,height),4);depth=ctx.depth_renderbuffer((width,height));fbo=ctx.framebuffer([tex],depth)
            fbo.use();ctx.viewport=(0,0,width,height)
            elapsed=[]
            for logical_height in (270,360):
                logical_width=logical_height*width/height
                layout=plain(h.layout(logical_width,logical_height));sl=plain(shop.layout(logical_width,logical_height))
                assert layout['left']['x']+layout['left']['w']<layout['right']['x']
                for r in layout.values():
                    assert r['x']>=0 and r['y']-25>=0 and r['x']+r['w']<=logical_width and r['y']+r['h']<=logical_height
                assert sl['scale']>0 and sl['x']>=11.99 and sl['y']>=11.99
                assert sl['x']+sl['w']<=logical_width-11.99 and sl['y']+sl['h']<=logical_height-11.99
                # Match the external OS pointer with Lua's logical shop coordinates,
                # including negative monitor positions and fractional display scale.
                for dpi in (1,1.25,1.5,1.75,2):
                    for origin in ((0,0),(-2560,120),(1920,-900)):
                        box=(*origin,round(width*dpi),round(height*dpi))
                        class CursorAPI:
                            def GetCursorPos(self,ptr):
                                p=ctypes.cast(ptr,ctypes.POINTER(windows.w.POINT)).contents
                                p.x=round(box[0]+(sl['x']+460*sl['scale'])/logical_width*box[2])
                                p.y=round(box[1]+(sl['y']+346*sl['scale'])/logical_height*box[3]);return True
                        probe=Windows.__new__(Windows);probe.w=windows.w;probe.u=CursorAPI()
                        mx,my=probe.cursor(box,(logical_width,logical_height))
                        ux=(mx-sl['x'])/sl['scale'];uy=(my-sl['y'])/sl['scale']
                        assert 400<=ux<520 and 334<=uy<358,'OS pointer missed Lua Buy hitbox'
                for language in ('zh','en'):
                    s=snapshot();s.update(screen=[logical_width,logical_height],position=[logical_width/2,logical_height*.55],
                        hudVisible=True,presentation=2,language=language,cursor={'position':[logical_width*.75,logical_height*.4]},goldFX=[])
                    s['hud'].update(layout=layout,level=18,hp=12345,maxHP=15000,xp=1,nextXP=1,gold=99,
                        inventory=[dict(id=v,count=1) for v in (3084,3153,3071,6333,6610,2501)])
                    for skill in s['hud']['skills'].values():skill.update(rank=3,canUpgrade=True)
                    for shopping in (False,True):
                        hud.reset();fx.reset();renderer.kind=None;renderer.pose=None;renderer.yaw=None
                        if shopping:s['shop']=dict(open=True,layout=sl,selected=3153,items=list(hud.shop.items),cost=50,canBuy=True,canSell=True,canUndo=True)
                        else:s.pop('shop',None)
                        start=time.perf_counter();fbo.use();ctx.viewport=(0,0,width,height);ctx.clear(.13,.10,.08,1)
                        fx.draw(s,0);renderer.draw('Idle',.3,s['position'],s['screen'],math.pi/2,1/60,banner=True);hud.draw(s);ctx.finish()
                        elapsed.append((time.perf_counter()-start)*1000)
                        assert ctx.error=='GL_NO_ERROR',(width,height,ctx.error)
                        im=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                        a=np.asarray(im)
                        assert a[:,:,:3].std()>8
                        if language=='en' and logical_height==360:
                            thumb=im.copy();thumb.thumbnail((512,288));pictures.append(((width,height,shopping),thumb))
                            if width in (800,3840,5120):im.save(output/f'{width}x{height}-{"shop" if shopping else "hud"}.png')
                    # HUD must survive the ordinary room transition; CG is empty.
                    s.pop('shop',None);s.update(transition=True,paused=True)
                    assert layers(s)==(True,True)
                    s.update(occluded=True,hudVisible=False)
                    assert layers(s)==(False,False)
                    ctx.clear(0,0,0,0);ctx.finish()
                    assert not np.frombuffer(fbo.read(components=4),np.uint8).any()
            report['cases'].append(dict(physical=[width,height],logical_heights=[270,360],languages=['zh','en'],
                frames=len(elapsed),mean_ms=round(sum(elapsed)/len(elapsed),2)))
            print('Passed',width,height,flush=True)
            fbo.release();depth.release();tex.release()
        sheet=Image.new('RGB',(1024,288*len(CASES)),(30,30,30))
        from PIL import ImageDraw
        d=ImageDraw.Draw(sheet)
        for i,((w,hh,shopping),im) in enumerate(pictures):
            x=i%2*512;y=i//2*288;sheet.paste(im,(x,y));d.text((x+5,y+5),f'{w} x {hh} / '+('Shop' if shopping else 'HUD'),fill='white')
        sheet.save(output/'display-matrix.jpg',quality=90)
        (output/'display-matrix.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print('80 GPU frames, 300 DPI/origin mappings, Lua bounds and transition/CG checks passed')
    finally:glfw.destroy_window(window);glfw.terminate()


if __name__=='__main__':run()
