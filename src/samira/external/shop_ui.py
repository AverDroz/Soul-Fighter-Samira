"""Client artwork with Lua-authoritative purchase state and hit boxes."""
import json, math, re
from localization import translate,NOTES

STATS={'hp':'生命','ad':'攻击力','ap':'法强','armor':'护甲','mr':'魔抗','attackSpeed':'攻速','crit':'暴击','haste':'技能急速','move':'移速','movePercent':'移速','lifesteal':'生命偷取','omnivamp':'全能吸血','mana':'法力','regenPercent':'生命回复','manaRegen':'法力回复','armorPen':'护甲穿透','magicPen':'法术穿透','magicPenPercent':'法术穿透','lethality':'穿甲','healPower':'治疗护盾','tenacity':'韧性','critDamage':'暴击伤害','regen':'生命回复'}
PERCENT={'attackSpeed','crit','movePercent','lifesteal','omnivamp','regenPercent','manaRegen','armorPen','magicPenPercent','healPower','tenacity','critDamage'}
NATIVE_NOTES={
    118:('Q落地时向施放方向释放硫磺火。','Q releases Brimstone in its cast direction on impact.'),
    52:('Q落地时向施放方向发射炸弹。','Q fires a bomb in its cast direction on impact.'),
    114:('Q释放菜刀，菜刀跟随鼠标方向。','Q releases a knife that follows your mouse aim.'),
    68:('Q落地时向施放方向释放科技激光。','Q releases a Technology laser in its cast direction on impact.'),
    152:('Q落地时向施放方向释放科技激光。','Q releases a Technology laser in its cast direction on impact.'),
    395:('Q落地时向施放方向释放科技X光环。','Q releases a Tech X ring in its cast direction on impact.'),
    2:('多重射击会增加同时释放的Q数量。','Multishot increases the number of simultaneous Q strikes.'),
    153:('多重射击会增加同时释放的Q数量。','Multishot increases the number of simultaneous Q strikes.'),
    245:('多重射击会增加同时释放的Q数量。','Multishot increases the number of simultaneous Q strikes.'),
    275:('完成Q3时触发硫磺火宝宝的蓄力攻击。','Completing Q3 triggers Lil Brimstone\'s charged attack.'),
}
class ShopUI:
    def __init__(self,hud,root):
        self.hud=hud;self.c=hud.c
        self.items={v['id']:v for v in json.loads((root/'shop_catalog.json').read_text(encoding='utf-8'))}
        self.native_descriptions=json.loads((root/'native_descriptions.json').read_text(encoding='utf-8'))
        for name in ('shop_frame','shop_background','shop_buy','shop_buy_hover','shop_disabled','shop_sell','shop_close','shop_coin','shop_item_selected','shop_undo','shop_undo_hover','shop_undo_disabled','shop_sell_hover','shop_tree','shop_line','shop_divider','shop_icon_frame','shop_icon_hover','shop_owned','shop_inventory_frame','shop_tree_vertical','shop_tree_horizontal'):
            self.c.load(name,root/(name+'.png'))
        for id in self.items:self.c.load('item_'+str(id),root/('item_'+str(id)+'.png'))
    def width(self,value,size):
        return sum(self.c.glyphs.get(ch,self.c.glyphs['?'])[2]*size/48 for ch in str(value))
    def wrap(self,value,width,size):
        # English wraps at words; CJK wraps at glyphs. Long unbroken tokens also fit.
        lines=[];line=''
        for token in re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*|[ \t]+|\n|.",value):
            if token=='\n':lines.append(line.rstrip());line='';continue
            if not line and token.isspace():continue
            if line and self.width(line+token,size)>width:
                lines.append(line.rstrip());line='';token=token.lstrip()
            for ch in token:
                if line and self.width(line+ch,size)>width:lines.append(line);line=''
                line+=ch
        if line.strip():lines.append(line.rstrip())
        return lines
    def cells(self):
        counts=[0,0,0];cells=[]
        for item in self.items.values():
            if not item.get('buyable'):continue
            group=0 if not item['components'] else 1 if item['price']<50 else 2
            n=counts[group];counts[group]+=1
            cells.append(dict(id=item['id'],x=22+n%6*48,y=50+group*91+n//6*39))
        return cells
    def tree(self,id):
        if id not in self.items:return []
        upgrades=[v['id'] for v in self.items.values() if v.get('buyable') and id in v.get('components',[])]
        nodes=[dict(id=v,x=414+(i-(len(upgrades)-1)/2)*27,y=40,size=20) for i,v in enumerate(upgrades)]
        nodes.append(dict(id=id,x=408,y=77,size=32,selected=True))
        children=self.items[id]['components']
        nodes.extend(dict(id=v,x=412+(i-(len(children)-1)/2)*58,y=134,size=24,component=True) for i,v in enumerate(children))
        return nodes
    def native_description(self,item,language):
        entry=self.native_descriptions.get(str(-item['id']),{})
        return entry.get(language) or entry.get('en')
    def name(self,item,language):
        entry=self.native_description(item,language) if item['id']<0 else None
        return entry['name'] if entry else item.get('english',item['name']) if language=='en' else item['name']
    def native_lines(self,item,language):
        tr=lambda value:translate(value,language)
        entry=self.native_description(item,language);lines=[]
        if entry:
            for title,key in [('原版属性（EID）','attributes'),('原版效果（EID）','effects')]:
                if entry[key]:
                    lines+=self.wrap(tr(title),185,7)
                    for text in entry[key]:lines+=self.wrap(text,185,7)
                    lines.append('')
        else:
            lines+=self.wrap(tr('原版效果')+': '+(item.get('description') or tr('暂无详细描述')),185,7)+['']
        note=NATIVE_NOTES.get(-item['id'])
        if note:lines+=self.wrap(tr('Samira适配：')+note[1 if language=='en' else 0],185,7)+['']
        lines+=self.wrap(tr('原版说明供参考，实际按本Mod的技能与生命规则结算。'),185,7)
        return lines
    def draw(self,s):
        native=s['hud'].get('nativeItems')
        if isinstance(native,dict):self.items.update({int(k):v for k,v in native.items()})
        language=s.get('language','zh');tr=lambda value:translate(value,language)
        shop=s['shop'];l=shop['layout'];x,y,k=l['x'],l['y'],l['scale'];c=self.c
        def rect(rx,ry,w,h,color=(1,1,1,1),texture='white'):c.rect(x+rx*k,y+ry*k,w*k,h*k,color,texture)
        def text(value,rx,ry,size=7,color=(.78,.75,.64,1),center=False):c.text(tr(value) if isinstance(value,str) else value,x+rx*k,y+ry*k,size*k,color,center)
        def icon(id,rx,ry,size,frame='shop_icon_frame'):
            self.hud.item_icon(id,x+rx*k,y+ry*k,size*k,size*k)
            rect(rx-1,ry-1,size+2,size+2,texture=frame)
        def line(rx,ry,w):rect(rx,ry,w,.5,texture='shop_line')
        rect(0,0,540,370,(.018,.035,.039,1))
        rect(8,30,310,292,texture='shop_background');rect(322,30,208,145,texture='shop_tree')
        self.hud.nine('shop_frame',x,y,540*k,370*k,196,180,54,73,13*k)
        text('全部装备',20,15,9,(.91,.85,.67,1));rect(517,12,10,10,texture='shop_close')
        text('P',503,15,6,(.45,.5,.5,1));line(16,29,508)
        rect(320,30,.5,294,texture='shop_divider')
        cursor=s.get('cursor',{}).get('position',[-1,-1]);mx=(cursor[0]-x)/k;my=(cursor[1]-y)/k
        hovered=None
        titles=('基础装备','中级装备','高级装备')
        sections=shop.get('sections',[dict(group=n+1,y=36+n*91) for n in range(3)])
        for section in sections:
            text(titles[section['group']-1],20,section['y'],6,(.68,.64,.5,1))
        scroll=shop.get('scroll',{})
        if scroll.get('maximum',0)>0:
            top=scroll['top'];height=scroll['bottom']-top
            thumb=max(20,height*height/(height+scroll['maximum']))
            position=top+(height-thumb)*scroll['offset']/scroll['maximum']
            rect(310,top,2,height,(.12,.18,.18,1));rect(308,position,6,thumb,(.55,.51,.35,1))
        for cell in shop.get('cells',self.cells()):
            id=cell['id'];item=self.items[id];ix=cell['x'];iy=cell['y']
            selected=id==shop['selected'];hover=ix-2<=mx<ix+30 and iy-2<=my<iy+36
            if hover:hovered=item
            icon(id,ix,iy,28,'shop_item_selected' if selected else 'shop_icon_hover' if hover else 'shop_icon_frame')
            text(item['price'],ix+14,iy+30,6,(.85,.73,.42,1),True)
        item=self.items.get(shop['selected'],dict(id=0,name='',english='',price=0,sell=0,stats={},components=[]))
        nodes=shop['tree'] if 'tree' in shop else self.tree(item['id'])
        if shop.get('upgradeTotal',0)>6:
            start=shop.get('upgradeOffset',0)
            text(str(start+1)+'-'+str(start+6)+' / '+str(shop['upgradeTotal'])+'  '+('Scroll' if language=='en' else '滚轮'),332,65,5.5)
        parents=[n for n in nodes if not n.get('selected') and not n.get('component')]
        children=[n for n in nodes if n.get('component')]
        if parents:text('可合成',332,30,6)
        # Native tree-line textures connect the selected item to its components.
        if children:
            rect(423.5,109,1,14,texture='shop_tree_vertical')
            centers=[n['x']+n['size']/2 for n in children]
            if len(centers)>1:
                # Preserve the native 3-slice end caps instead of stretching them.
                left=min(centers);right=max(centers)
                for rx,width,u0,u1 in ((left,.5,0,2/12),(left+.5,right-left-1,2/12,10/12),(right-.5,.5,10/12,1)):
                    c.rect(x+rx*k,y+120*k,width*k,4*k,(1,1,1,1),'shop_tree_horizontal',uv=(u0,0,u1,1))
            for cx in centers:rect(cx-.5,123,1,11,texture='shop_tree_vertical')
        owned={}
        for slot in s['hud'].get('inventory',[]):owned[slot.get('id',0)]=owned.get(slot.get('id',0),0)+slot.get('count',1)
        for node in nodes:
            id=node['id'];ix=node['x'];iy=node['y'];size=node['size']
            hover=ix<=mx<ix+size and iy<=my<iy+size
            if hover:hovered=self.items[id]
            icon(id,ix,iy,size,'shop_item_selected' if node.get('selected') else 'shop_icon_hover' if hover else 'shop_icon_frame')
            if node.get('component'):
                have=owned.get(id,0)>0
                if have:owned[id]-=1;rect(ix+size-6,iy+size-5,10,8,texture='shop_owned')
                text(self.items[id]['price'],ix+size/2,iy+size+3,5.5,center=True)
        line(330,177,192)
        icon(item['id'],332,186,30)
        name=self.name(item,language)
        if item['id']<0 and any(ch not in c.glyphs for ch in name):name=item.get('english',name)
        name_size=8
        while name_size>6 and len(self.wrap(name,150,name_size))>2:name_size-=.25
        for i,label in enumerate(self.wrap(name,150,name_size)):text(label,372,186+i*11,name_size,(.93,.83,.52,1))
        price=(tr('出售')+' '+str(item['sell'])) if item['id']<0 else str(item['price'])+' '+tr('金币')
        text(price,372,210,6.5,(.85,.73,.42,1))
        attrs=item.get('stats',{});attrs=attrs if isinstance(attrs,dict) else {}
        lines=[]
        for key,v in attrs.items():
            label=str(round(v*100 if key in PERCENT else v,1)).removesuffix('.0')+('%' if key in PERCENT else '')+' '+tr(STATS.get(key,key))
            lines+=self.wrap(label,185,6.5)
        notes=(item.get('adaptationEn') or NOTES.get(item['id'],'Base stats apply.')) if language=='en' else item.get('adaptation','')
        if item['id']<0:lines=self.native_lines(item,language)
        else:lines=(lines or [tr('无基础属性')])+['']+self.wrap(notes,185,6.5)
        if item['id']==3084:lines.insert(0,'+'+str(round(s['hud'].get('heartsteel',0),1))+' '+tr('永久生命'))
        line_count=9;pages=max(1,math.ceil(len(lines)/line_count));page=min(shop.get('detailPage',0),pages-1)
        for i,label in enumerate(lines[page*line_count:(page+1)*line_count]):text(label,332,227+i*8.5,6.5)
        if pages>1:
            text(str(page+1)+' / '+str(pages),461,310,6);text('<',491,310,8);text('>',510,310,8)
        if shop.get('credit'):text(tr('已抵扣')+' '+str(shop['credit']),332,310,5.5)
        line(16,325,508)
        slots=s['hud'].get('inventory',[])
        for i in range(6):
            ix=18+i*25;a=slots[i] if i<len(slots) else {};id=a.get('id',0)
            if id:icon(id,ix+1,335,21,'shop_item_selected' if shop.get('selling')==i+1 else 'shop_inventory_frame')
            else:rect(ix,334,23,23,texture='shop_inventory_frame')
            if id and ix<=mx<ix+23 and 334<=my<357:hovered=self.items.get(id)
        rect(180,340,10,9,texture='shop_coin');text(s['hud']['gold'],195,340,7,(.93,.78,.42,1))
        can_sell=shop.get('canSell',False)
        refund=self.items.get(slots[shop['selling']-1]['id'],{}).get('sell',0) if can_sell and shop.get('selling') and len(slots)>=shop['selling'] else 0
        def button(rx,width,label,enabled,base,hovertex,disabled='shop_undo_disabled'):
            hover=rx<=mx<rx+width and 334<=my<358
            rect(rx,334,width,24,texture=hovertex if enabled and hover else base if enabled else disabled)
            text(label,rx+width/2,342,6.5,(.95,.9,.72,1) if enabled else (.4,.44,.45,1),True)
        button(236,68,tr('出售')+(' '+str(refund) if refund else ''),can_sell,'shop_sell','shop_sell_hover')
        button(313,78,'撤回',shop.get('canUndo',False),'shop_undo','shop_undo_hover')
        button(400,120,tr('购买')+' '+str(shop.get('cost',item['price'])),shop.get('canBuy',False),'shop_buy','shop_buy_hover','shop_disabled')
        message=shop.get('message') or shop.get('reason')
        if message:text(message,20,313,6,(.88,.64,.4,1))
        # Full names on hover, like the icon view of the client shop; never slice words.
        if hovered:
            labels=self.wrap(self.name(hovered,language),160,7)
            tw=178;th=22+len(labels)*10;tx=min(540-tw-12,max(12,mx+14));ty=min(322-th,max(32,my+18))
            rect(tx,ty,tw,th,(.018,.035,.039,1));self.hud.nine('shop_frame',x+tx*k,y+ty*k,tw*k,th*k,196,180,54,73,7*k)
            for i,label in enumerate(labels):text(label,tx+9,ty+8+i*10,7,(.93,.83,.52,1))
            text(str(hovered['price'] if hovered['id']>0 else hovered['sell'])+' '+tr('金币'),tx+9,ty+9+len(labels)*10,6)
