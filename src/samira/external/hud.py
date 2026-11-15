"""High-resolution corner HUD and champion health bar; all values come from the mod."""
import math, json
from pathlib import Path

class HUD:
    def __init__(self,canvas,root):
        self.c=canvas;root=Path(root)
        for name in ('portrait','portrait_round','portrait_frame','native_panel','skill_frame','passive','q','w','e','r','equipment','health','shield'):
            canvas.load('hud_'+name,root/(name+'.png'))
        for name in ('client_bars','client_resource','champion_bars','hand2','hovershop','hoveruse'):canvas.load(name,root/(name+'.png'))
        canvas.load('experience_arc',root/'experience_arc.png')
        canvas.load('experience_background',root/'experience_background.png')
        self.portrait_layout=json.loads((root/'portrait_layout.json').read_text())
        from shop_ui import ShopUI
        self.shop=ShopUI(self,root)
        self.pocket=json.loads((root/'pocket.json').read_text(encoding='utf-8'))
        for name in ('pocket_cards','pocket_pills'):canvas.load(name,root/(name+'.png'))
        canvas.load('native_pickups',root/'native_pickups.png')
        self.native_icons=json.loads((root/'native_items.json').read_text(encoding='utf-8'))
        self.buff_icons=json.loads((root/'heart_buffs.json').read_text(encoding='utf-8'))
        canvas.load('native_items',root/'native_items.png');canvas.load('heart_buffs',root/'heart_buffs.png')
        self.reset()
    def reset(self):self.hp=None;self.trail=0;self.changed=0;self.xp=None;self.xp_level=None;self.xp_from=0;self.xp_at=0
    def region(self,name,box,x,y,w,h,color=(1,1,1,1)):
        tw,th=self.c.textures[name].size;l,t,r,b=box
        self.c.rect(x,y,w,h,color,name,(l/tw,t/th,r/tw,b/th))
    def experience(self,x,y,ratio):
        k=38/self.portrait_layout['frame'][2];dx,dy,w,h=self.portrait_layout['arc']
        frame=round(max(0,min(1,ratio))*100);sx=frame%11*48;sy=frame//11*120
        self.c.rect(x+dx*k,y+3+dy*k,w*k,h*k,(1,1,1,1),'experience_background')
        self.region('experience_arc',(sx,sy,sx+48,sy+120),x+dx*k,y+3+dy*k,w*k,h*k)
    def health_fill(self,x,y,w,h,red,soul,trail=0,shield=0):
        c=self.c
        # Same client-atlas materials in both HUDs; thin dark/gold edging stays readable.
        c.rect(x-1,y-1,w+2,h+2,(.29,.31,.24,1));c.rect(x,y,w,h,(.02,.04,.025,1))
        if trail>red+soul:c.rect(x,y,w*trail,h,(.72,.36,.15,1))
        if red>0:self.region('client_bars',(2,919,2+459*red,939),x,y,w*red,h,(.72,.85,.72,1))
        if soul>0:self.region('client_bars',(2,985,2+459*soul,1005),x+w*red,y,w*soul,h,(1,1,1,1))
        if shield>0:self.region('client_bars',(2,985,2+459*shield,1005),x+w*(red+soul),y,w*shield,h)
        c.rect(x,y,w,h*.16,(.8,1,.7,.13))
    def item_icon(self,id,x,y,w,h):
        if id<0:
            box=self.native_icons.get(str(-id))
            if box:self.region('native_items',box,x,y,w,h)
            else:self.c.text('?',x+w/2,y+h/4,h/2,center=True)
        elif id in self.shop.items:self.c.rect(x,y,w,h,(1,1,1,1),'item_'+str(id))
    def panel(self,x,y,w,h):
        self.c.rect(x+2,y+2,w-4,h-4,(.025,.055,.06,1))
        self.nine('hud_native_panel',x,y,w,h,314,312,20,20,5)
    def nine(self,texture,x,y,w,h,sw,sh,bx,by,border):
        xs=[x,x+border,x+w-border,x+w];ys=[y,y+border,y+h-border,y+h]
        us=[0,bx/sw,1-bx/sw,1];vs=[0,by/sh,1-by/sh,1]
        for row in range(3):
            for col in range(3):
                self.c.rect(xs[col],ys[row],xs[col+1]-xs[col],ys[row+1]-ys[row],(1,1,1,1),texture,(us[col],vs[row],us[col+1],vs[row+1]))
    def radial(self,x,y,size,ratio):
        if ratio<=0:return
        # Cooldown sweep, clipped to the square icon perimeter.
        pts=[(x+size/2,y+size/2)];steps=max(2,math.ceil(ratio*64))
        for i in range(steps+1):
            a=-math.pi/2+i/steps*ratio*math.tau;dx=math.cos(a);dy=math.sin(a);r=size/2/max(abs(dx),abs(dy),.001)
            pts.append((x+size/2+dx*r,y+size/2+dy*r))
        self.c.polygon(pts,(0,0,0,.72))
    def draw(self,s):
        h=s.get('hud')
        if not h:return
        c=self.c;clock=s.get('clock',0);w,height=s['screen'];layout=h['layout'];left=layout['left'];right=layout['right']
        ratio=h['hp']/max(1,h['maxHP'])
        if self.hp is None:self.hp=ratio;self.trail=ratio;self.changed=clock
        if self.hp!=ratio:
            self.trail=max(self.hp,ratio);self.hp=ratio;self.changed=clock
        trailing=ratio+(self.trail-ratio)*(1-min(1,max(0,(clock-self.changed-4)/15)))
        target=1 if h['level']==18 else min(1,h['xp']/max(1,h['nextXP']))
        if self.xp_level!=h['level'] or self.xp is None:
            self.xp_level=h['level'];self.xp=target;self.xp_from=target;self.xp_at=clock
        blend=min(1,max(0,(clock-self.xp_at)/6));xp=self.xp_from+(self.xp-self.xp_from)*blend
        if target!=self.xp:self.xp_from=xp;self.xp=target;self.xp_at=clock
        x,y=left['x'],left['y'];self.panel(x+38,y,116,left['h'])
        self.experience(x,y,xp)
        k=38/self.portrait_layout['frame'][2];px,py,pw,ph=self.portrait_layout['portrait']
        c.rect(x+px*k,y+3+py*k,pw*k,ph*k,(1,1,1,1),'hud_portrait_round')
        c.rect(x,y+3,38,self.portrait_layout['frame'][3]*k,(1,1,1,1),'hud_portrait_frame')
        lx,ly,lw,lh=self.portrait_layout['level']
        c.text(h['level'],x+(lx+lw/2)*k,y+3+(ly+lh/2)*k-2.4,6.5,(1,.91,.64,1),center=True)
        c.rect(x+11,y-18,16,16,(1,1,1,1),'hud_passive')
        c.rect(x+10,y-19,18,18,(1,1,1,1),'hud_skill_frame')
        for i,buff in enumerate(h.get('buffs',[])):
            bx=x+42+i*13;by=y-(25 if any(v.get('canUpgrade') for v in h['skills'].values()) else 13)
            c.rect(bx-1,by-1,12,12,(1,1,1,1),'hud_skill_frame')
            box=self.buff_icons.get(buff['icon'])
            if box:self.region('heart_buffs',box,bx,by,10,10)
            if buff['count']>1:c.text(buff['count'],bx+8,by+5,4,(1,1,1,1),center=True)
        passive=h.get('passive')
        remaining=max(0,passive.get('remaining',0)-max(0,clock-s.get('packetClock',clock))) if passive else 0
        if passive and remaining>0:
            self.radial(x+11,y-18,16,min(1,remaining/max(1,passive['total'])))
            c.text(math.ceil(remaining/30),x+19,y-14,7,(1,1,1,1),center=True)
        elif passive:
            c.rect(x+11,y-3,16,1,(1,.78,.32,1))
        for i,key in enumerate('qwer'):
            ix=x+42+i*27;iy=y+4;c.rect(ix,iy,24,24,(1,1,1,1),'hud_'+key);c.rect(ix-1,iy-1,26,26,(1,1,1,1),'hud_skill_frame')
            skill=h['skills'][key];cd=max(0,skill['remaining']-max(0,clock-s.get('packetClock',clock)))
            rank=skill.get('rank',1)
            active=key=='r' and s.get('ultimate')
            if rank==0:c.rect(ix,iy,24,24,(0,0,0,.72))
            elif cd>0 and not active:
                self.radial(ix,iy,24,min(1,cd/max(1,skill['total'])))
                c.text(math.ceil(cd/30),ix+12,iy+7,10,(1,1,1,1),center=True)
            c.rect(ix,iy+19,24,5,(.01,.02,.025,.8));c.text(h.get('keys',{}).get(key,key.upper()),ix+12,iy+19.2,5.5,center=True)
            if key=='q' and h.get('qStage',1)>1:
                c.rect(ix+16,iy,8,7,(.015,.02,.025,.9));c.text(h['qStage'],ix+20,iy+.5,6,(1,.74,.3,1),center=True)
            if active:c.line((ix,iy+24),(ix+24*min(1,(s['r']['untilTick']-clock)/300),iy+24),1.5,(1,.18,.03,1))
            maximum=3 if key=='r' else 5
            for n in range(maximum):
                c.rect(ix+2+(5-maximum)*2+n*4,y+30,3,2,(.9,.72,.32,1) if n<rank else (.12,.14,.14,1))
            if skill.get('canUpgrade'):
                pulse=.55+.45*math.sin(clock*.12)**2
                self.region('client_bars',(208,12,279,84),ix-2,iy-2,28,28,(1,1,1,pulse))
                self.region('client_bars',(208,12,279,84),ix+7,y-11,10,9)
                c.rect(ix+8,y-10,8,7,(.025,.06,.065,1))
                c.text('+',ix+12,y-10,7,(1,.91,.53,1),center=True)
        total=h['maxHP']+h.get('soulHP',0);shield=h.get('shield',0)
        factor=total/max(1,total+shield)
        self.health_fill(x+42,y+35,105,6,h['red']*factor,h['soul']*factor,trailing*factor,1-factor)
        c.text(str(h['hp'])+' / '+str(h['maxHP']),x+94.5,y+35,5.5,(1,1,1,1),center=True)
        # Keep the requested corner layout and native room view. No center-bottom panel.
        x,y=right['x']+46,right['y']
        self.region('hud_equipment',(0,0,249,132),x,y,76,34)
        self.region('hud_equipment',(0,165,249,175),x,y+34,76,2)
        for i,key in enumerate((1,2,3,5,6,7)):
            ix=x+7+(i%3)*15.5;iy=y+7+(i//3)*13.4
            a=h.get('inventory',[{}]*6)[i];id=a.get('id',0)
            if id:
                self.item_icon(id,ix,iy,12.5,12.5)
                remaining=max(0,a.get('ready',0)-h.get('gearTime',0))
                if remaining:
                    c.rect(ix,iy,12.5,12.5,(0,0,0,.65));c.text(math.ceil(remaining/30),ix+6.25,iy+3,6,(1,1,1,1),True)
                count=a.get('charges',0) if id==2031 else a.get('count',0)
                if count>1 or id==2031:c.text(count,ix+10,iy+7,4.5,(1,1,1,1),True)
            c.rect(ix,iy,4.5,4.5,(0,0,0,.8));c.text(key,ix+.6,iy+.3,4,(.92,.88,.66,1))
            if h.get('gearSelected')==i+1:c.rect(ix-1,iy-1,14.5,14.5,(1,.85,.38,1),'hud_skill_frame')
        # Reuse the authored empty item cell to cover the atlas's cut-out slots.
        self.region('hud_equipment',(18,22,70,74),x+55,y+5,18,15)
        self.region('hud_equipment',(18,22,70,74),x+55,y+20,18,14)
        pocket=h.get('pocket',{});card=pocket.get('card',0);pill=pocket.get('pill',0)
        kind='cards' if card else 'pills';value=card or (pill & 0x7ff)
        region=self.pocket.get(kind,{}).get(str(value)) if value else None
        if region:
            texture='pocket_'+kind;tw,th=c.textures[texture].size;rx,ry,rw,rh=region
            fit=min(12/rw,12/rh);c.rect(x+59+(12-rw*fit)/2,y+7+(12-rh*fit)/2,rw*fit,rh*fit,(1,1,1,1),texture,(rx/tw,ry/th,(rx+rw)/tw,(ry+rh)/th))
        c.text('4',x+59,y+6,4,(.92,.88,.66,1))
        self.region('native_pickups',(0,16,16,32),x+60,y+22,11,11)
        c.text('G',x+59,y+22,4,(.92,.88,.66,1))
        self.region('hud_equipment',(0,175,249,214),x-46,height-12,46,12)
        c.text(h['gold'],x-21,height-9,6.5,(1,.85,.4,1),center=True)
        if not s.get('dead') and not s.get('actorHidden'):
            p=s['position'];x=max(4,min(w-56,p[0]-28));y=max(15,p[1]-(76 if s.get('ultimate') else 66)*s.get('bodyScale',[1,1])[1])
            # Snap the whole moving bar to physical pixels, not Isaac's logical
            # grid. Fractional translation otherwise makes thin ticks shimmer.
            sx=c.ctx.viewport[2]/w;sy=c.ctx.viewport[3]/height
            x=round(x*sx)/sx;y=round(y*sy)/sy
            self.region('champion_bars',(3,3,139,30),x,y,56,11)
            bx=x+10.3;by=y+1.65;bw=44.5;bh=6.9
            shield=h.get('shield',0);total=h['maxHP']+h.get('soulHP',0)
            factor=total/max(1,total+shield)
            for ratio,offset,source in [(trailing*factor,0,(147,17,257,27)),(h['red']*factor,0,(147,4,257,15)),(h['soul']*factor,h['red']*factor,(147,29,257,39)),(1-factor,(h['red']+h['soul'])*factor,(147,29,257,39))]:
                if ratio>0:self.region('champion_bars',source,bx+bw*offset,by,bw*ratio,bh)
            step=max(100,math.ceil(total/100/24)*100)
            for hp in range(step,total,step):
                tx=round((bx+bw*hp/total*factor)*sx)/sx
                self.region('champion_bars',(260,4,262,15),tx,round(by*sy)/sy,max(1,round(.45*sx))/sx,round(3*sy)/sy)
            c.text(h['level'],x+4.7,y+2.4,5.8,(1,.94,.75,1),center=True)
            label=str(h['hp'])+' / '+str(h['maxHP'])
            c.text(label,bx+bw/2+.25,by+1.45,4.5,(0,0,0,1),center=True)
            c.text(label,bx+bw/2,by+1.2,4.5,(1,1,1,1),center=True)
        for reward in ([] if s.get('actorHidden') else s.get('goldFX',[])):
            age=clock-reward['at']
            if not 0<=age<42:continue
            alpha=min(1,(42-age)/12);lane=reward.get('lane',0)
            px,py=reward['position'];px+=(0,-12,12,0)[lane%4];py-=22+age*.7+lane*9
            label='+'+str(reward['amount']);size=9*(1+.16*max(0,1-age/6))
            width=sum(c.glyphs[ch][2] for ch in label)*size/48
            left=px-(width+11)/2
            c.rect(left,py,8,8,(1,.86,.38,alpha),'shop_coin')
            c.text(label,left+11+.7,py+.7,size,(.04,.02,0,alpha))
            c.text(label,left+11,py,size,(1,.82,.24,alpha))
        if s.get('shop'):self.shop.draw(s)
        cursor=s.get('cursor')
        if cursor:
            p=cursor['position'];name='hovershop' if cursor.get('shop') else 'hoverenemy' if cursor.get('enemy') else 'hand2' if cursor.get('down') else 'hand1'
            c.rect(p[0],p[1],17,17,(1,1,1,1),name)
        c.flush()
