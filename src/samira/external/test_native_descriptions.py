"""Imported EID text, paging, Chinese glyph coverage and actual shop GPU rendering."""
import json,math
from overlay import create_window,ROOT,HERE,glfw,Effects,HUD,Image
from test_combat import snapshot

def run():
    window,ctx=create_window(False)
    try:
        fx=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        hud=HUD(fx.canvas,ROOT/'mod/resources/gfx/samira/hud');shop=hud.shop
        catalog=shop.native_descriptions
        assert len(catalog)==732
        for entry in catalog.values():
            assert set(entry)=={'zh','en'}
            for text in entry.values():
                for value in [text['name']]+text['attributes']+text['effects']:
                    assert '{{' not in value and '#' not in value
                    assert all(ch in fx.canvas.glyphs for ch in value),value
        assert catalog['1']['zh']['name']=='悲伤洋葱'
        assert any('0.7' in line for line in catalog['1']['en']['attributes'])
        assert any('Persist' in line for line in catalog['117']['en']['effects']),'Repentance+ override must win'
        assert any('x1.5' in line for line in catalog['4']['en']['attributes'])
        s=snapshot();s['screen']=[640,360]
        s['hud']['nativeItems']={str(-id):dict(id=-id,name='fallback',english='fallback',price=0,sell=3,stats={},components=[]) for id in [1,4,12,52,118,395]}
        s['hud']['inventory']=[dict(id=-id,count=1,ready=0) for id in [1,4,12,52,118,395]]
        s['shop']={'open':True,'layout':dict(x=50,y=12,w=540,h=290,scale=1),'selected':-12,
                   'items':[1036,1055],'page':0,'pages':1,'cost':0,'canBuy':False,'canSell':True,'selling':3}
        fbo=ctx.framebuffer([ctx.texture((1920,1080),4)]);fbo.use();ctx.viewport=(0,0,1920,1080)
        labels=[];original=fx.canvas.text
        def capture(value,*args,**kwargs):labels.append(str(value));return original(value,*args,**kwargs)
        fx.canvas.text=capture
        for lang in ['zh','en']:
            s['language']=lang
            for ident,item in s['hud']['nativeItems'].items():
                s['shop'].update(selected=int(ident),detailPage=0)
                lines=shop.native_lines(item,lang);pages=max(1,math.ceil(len(lines)/11))
                for page in range(pages):
                    s['shop']['detailPage']=page;labels.clear();ctx.clear(.13,.11,.09,1)
                    fx.canvas.begin(s['screen']);shop.draw(s);fx.canvas.flush();ctx.finish()
                    assert ctx.error=='GL_NO_ERROR'
                    assert shop.name(item,lang) in labels
                    assert '无基础属性' not in labels and 'No base stats' not in labels
                    assert all('{{' not in value for value in labels)
                    if ident=='-12' and page==0:
                        Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(HERE/f'shop-eid-{lang}.png')
            fallback=dict(id=-99999,name='Unknown',description='Fallback native description')
            assert any('Fallback' in line for line in shop.native_lines(fallback,lang))
        assert fx.canvas.font_size[1]<=ctx.info['GL_MAX_TEXTURE_SIZE']
        print('732 bilingual EID entries, Repentance+ precedence, CJK coverage, native stats/effects, paging and shop GPU rendering passed; atlas:',fx.canvas.font_size)
    finally:glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':run()
