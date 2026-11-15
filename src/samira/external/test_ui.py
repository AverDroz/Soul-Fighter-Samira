"""Offscreen UI review only; no game input or live window control."""
import json
from pathlib import Path
from overlay import create_window,ROOT,HERE,glfw,Effects,HUD,Image,np
from test_combat import snapshot

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png');hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud')
        fbo=ctx.framebuffer([ctx.texture((1920,1080),4)]);fbo.use();ctx.viewport=(0,0,1920,1080)
        s=snapshot();s['hud']['inventory']=[dict(id=v,count=1,ready=0) for v in [-1,-4,3071,6333,6610,1055]];s['hud']['gold']=42;s['hud']['shield']=100;s['hud']['soulHP']=217;s['hud'].update(red=.75,soul=.25,buffs=[dict(icon='WhiteHeartHalf',count=1),dict(icon='GoldHeartOverlay',count=2)]);s['hud']['pocket']={'card':1,'pill':0};s['cursor']={'position':[95,105],'enemy':False}
        def draw(path):
            ctx.clear(.13,.11,.09,1);fx.canvas.begin(s['screen']);hud.draw(s);ctx.finish()
            assert ctx.error=='GL_NO_ERROR',ctx.error
            image=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            assert np.asarray(image)[:,:,:3].std()>8
            image.save(HERE/path)
        s['goldFX']=[]
        for key,skill in s['hud']['skills'].items():skill.update(rank=0,canUpgrade=key!='r')
        s['hud'].update(level=3,xp=0,skillPoints=3)
        draw('hud-skill-points-review.png')
        for key,rank in zip('qwer',[5,1,2,1]):s['hud']['skills'][key].update(rank=rank,canUpgrade=key!='q')
        s['hud'].update(level=11,xp=120,skillPoints=2,nextXP=1280)
        s['hud']['passive']=dict(remaining=240,total=450,ready=False)
        draw('hud-passive-cooldown-review.png')
        s['hud']['passive']=dict(remaining=0,total=450,ready=True)
        draw('hud-client-review.png')
        # Delayed interpolation must not invent a ready-state countdown of 1.
        labels=[];positions={};original_text=fx.canvas.text
        def capture(value,*args,**kwargs):
            labels.append(str(value));positions[str(value)]=args[:2];return original_text(value,*args,**kwargs)
        fx.canvas.text=capture
        s['packetClock']=s['clock']+1
        for skill in s['hud']['skills'].values():skill['remaining']=0
        fx.canvas.begin(s['screen']);hud.draw(s)
        # The equipment shortcut is the sole '1'; no skill countdown appears.
        assert labels.count('1')==1,labels
        assert positions['4'][1]<positions['G'][1],'pocket shortcut belongs to upper slot, bomb to lower slot'
        labels.clear();s['packetClock']=s['clock']-2;s['hud']['passive']['remaining']=1
        fx.canvas.begin(s['screen']);hud.draw(s);assert '0' not in labels,labels
        fx.canvas.text=original_text;s['hud']['passive']['remaining']=0
        k=(s['screen'][1]-24)/370
        s['shop']={'open':True,'layout':dict(x=(s['screen'][0]-540*k)/2,y=12,w=540*k,h=370*k,scale=k),'selected':3071,'items':list(hud.shop.items),'cost':50,'canBuy':True,'canSell':False,'canUndo':True}
        draw('shop-client-review.png')
        s['language']='en';draw('shop-english-review.png')
        for name in ('Rejuvenation Bead',"Caulfield's Warhammer",'Blade of The Ruined King'):
            lines=hud.shop.wrap(name,150,8)
            assert ' '.join(lines)==name and all(hud.shop.width(line,8)<=150 for line in lines),lines
        assert len(hud.shop.cells())==28 and max(cell['y'] for cell in hud.shop.cells())+36<308
        s['shop']['selected']=3153;s['cursor']['position']=[105,165];draw('shop-long-name-review.png')
        s['language']='zh';s['hud']['nativeItems']=[];draw('shop-empty-native-review.png')
        s['hud']['nativeItems']={'-1':dict(id=-1,name='Sad Onion',stats=[],components=[],price=0,sell=3,adaptation='Native passive')}
        s['shop'].update(selected=-1,selling=1,canSell=True,canBuy=False,cost=0)
        draw('shop-native-sale-review.png')
        for language in ('zh','en'):
            s['language']=language
            for selected in hud.shop.items:
                s['shop']['selected']=selected;fx.canvas.begin(s['screen']);hud.draw(s)
        assert ctx.error=='GL_NO_ERROR',ctx.error
        assert fx.canvas.font_size[1]<=ctx.info['GL_MAX_TEXTURE_SIZE']
        assert all(ch in fx.canvas.glyphs for item in hud.shop.items.values() for ch in item['name'])
        print('Native HUD regions, all catalog details, both languages, no category tabs and CJK glyphs rendered successfully')
    finally:glfw.destroy_window(window);glfw.terminate()
if __name__=='__main__':run()
