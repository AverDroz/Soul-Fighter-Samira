"""Original client particle systems plus combat-authoritative range indicators."""
import math,json
from pathlib import Path
from canvas import Canvas
from client_vfx import ClientParticles

class Effects:
    def __init__(self,ctx,texture):
        root=Path(texture).parent;self.canvas=Canvas(ctx,root)
        for p in root.glob('*.png'):self.canvas.load(p.stem,p,crop=p.stem not in ('aatrox_base_w_chain_beam','hand1','hoverenemy'))
        self.canvas.textures['aatrox_base_w_chain_beam'].repeat_y=True
        self.client=ClientParticles(ctx)
        asset=Path(__file__).parent/'assets/client'
        self.click_mesh=json.loads((asset/'cursor_moveto.json').read_text())
        self.canvas.load('click_original',asset/'color-movetogreen.png')
        self.canvas.load('damage_screen',asset/'lol_ingame_hit.png',crop=False)
        self.canvas.load('click_attack',asset/'color-movetogreen.png')
        self.heartsteel=ClientParticles(ctx,bundle='heartsteel')
        # Transfer the authored green ramp into red, preserving shading/alpha.
        # Multiplying green by a red tint only darkens it into brown.
        self.canvas.textures['click_attack'].swizzle='GRBA'
        self.ground=(1,.98);self.offset=0;self.indicators='client';self.clock=0;self.reset()
    def reset(self):
        self.trail=[];self.last_trail=None;self.client.reset();self.heartsteel.reset()
    def position(self,p):return (p[0]+self.offset,p[1])
    def point(self,p,f,x,y):return (p[0]+(f[0]*x-f[1]*y)*self.ground[0],p[1]+(f[1]*x+f[0]*y)*self.ground[1])
    def corners(self,p,f,near,far,width,narrow=None):
        n=width if narrow is None else narrow
        return [self.point(p,f,x,y) for x,y in ((near,-n),(near,n),(far,width),(far,-width))]
    def stamp(self,name,p,f,near,far,width,color=(1,1,1,1),add=False,brightness=False):
        self.canvas.polygon(self.corners(p,f,near,far,width),color,name,[(0,0),(1,0),(1,1),(0,1)],add,brightness)
    def billboard(self,name,p,w,h,color,angle=0,add=False,brightness=False):
        c=math.cos(angle);s=math.sin(angle)
        pts=[(p[0]+x*c-y*s,p[1]+x*s+y*c) for x,y in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2))]
        self.canvas.polygon(pts,color,name,[(0,0),(1,0),(1,1),(0,1)],add,brightness)
    def ring(self,p,f,r,color,width=1.2,cx=0):
        self.canvas.lines([self.point(p,f,cx+math.cos(i*math.tau/64)*r,math.sin(i*math.tau/64)*r) for i in range(65)],width,color)
    def outline(self,p,f,s,sweet=False):
        if s['kind']=='circle':
            r=s['inner'] if sweet else s['radius']
            return [self.point(p,f,s['cx']+math.cos(i*math.tau/64)*r,math.sin(i*math.tau/64)*r) for i in range(65)]
        near=s['sweet'] if sweet else s['near'];n=s.get('narrow',s['width'])
        if sweet:n+=(s['width']-n)*(near-s['near'])/(s['far']-s['near'])
        pts=self.corners(p,f,near,s['far'],s['width'],n);return pts+[pts[0]]
    def indicator(self,p,f,s,stage,progress=None):
        c=self.canvas;cast=progress is not None;t=progress or 0
        if self.indicators=='off':return
        color=(.654902,.007843,.03137,.65+.25*t) if cast else (.18,.78,1,.8)
        if s['kind']=='circle':near=s['cx']-s['radius'];far=s['cx']+s['radius'];width=s['radius']
        else:near=s['near'];far=s['far'];width=s['width']
        # Original white artwork requires runtime tint. Geometry matches the damage shape.
        if cast:
            c.flush();scale=s['radius']/84 if stage==3 else s['far']/(182 if stage==1 else 147)
            self.client.draw('Q_Indicator_0'+str(stage),t*.6,p,f,.28*scale,key=round(self.clock-t*18))
        else:self.stamp('aatrox_base_q_indicator_0'+str(stage),p,f,near,far,width,color)
        if self.indicators!='debug':return
        c.polygon(self.outline(p,f,s)[:-1],(*color[:3],.035+.045*t))
        c.lines(self.outline(p,f,s),.7,(*color[:3],.75))
        c.lines(self.outline(p,f,s,True),1.05,(1,.16,.12,.9) if cast else (.45,.9,1,.8))
        if cast and stage<3:self.stamp('aatrox_base_q_indicator_sweetspot_0'+str(stage),p,f,s['sweet'],s['far'],s['width'],(1,1,1,.2+.6*t),True)
        elif cast:c.polygon(self.outline(p,f,s,True)[:-1],(1,.16,.02,.04+.09*t))
    def sparks(self,center,age,count,speed,lifetime):
        if not 0<=age<lifetime:return
        for i in range(count):
            a=i*2.399;v=speed*(.7+(i%5)*.15);dx=math.cos(a);dy=math.sin(a)
            tip=(center[0]+dx*age*v,center[1]+dy*age*v*.65-math.sin(age/lifetime*math.pi)*(6+i%4*3))
            self.canvas.line(tip,(tip[0]-dx*3,tip[1]-dy*3),1 if i%3 else 1.6,(1,.3+i%3*.15,.06,1-age/lifetime))
    def impact(self,fx):
        age=fx['age'];shape=fx['shape'];stage=fx['stage']
        scale=shape['radius']/84 if stage==3 else shape['far']/(182 if stage==1 else 147)
        self.canvas.flush()
        self.client.draw('Q_cas'+str(stage),age/30,self.position(fx['position']),fx['face'],.28*scale,key=round(self.clock-age),opacity=.9 if stage==3 else 1)
    def chain(self,a,b,alpha,pull=False):
        length=math.dist(a,b)
        if length<.01:return
        width=3.5 if pull else 3
        nx=-(b[1]-a[1])/length*width;ny=(b[0]-a[0])/length*width
        points=[(a[0]-nx,a[1]-ny),(a[0]+nx,a[1]+ny),(b[0]+nx,b[1]+ny),(b[0]-nx,b[1]-ny)]
        repeat=max(.2,length/30)
        self.canvas.polygon(points,(1,1,1,alpha),'aatrox_base_w_chain_beam',[(0,0),(1,0),(1,repeat),(0,repeat)])
    def draw(self,s,offset):
        self.ground=tuple(s.get('ground',[1,.98]));self.offset=offset;c=self.canvas;c.begin(s['screen'])
        p=self.position(s['position']);f=s['face'];clock=s.get('clock',0);cast=s.get('cast')
        self.clock=clock;self.indicators=s.get('indicators','client');self.client.begin(s['screen'],self.ground,clock)
        if s.get('dead'):c.flush();return
        self.heartsteel.begin(s['screen'],self.ground,clock)
        c.flush()
        stages=('One','Two','Three','Four','Five','Six')
        for mark in s.get('heartsteel',[]):
            stage=max(1,min(6,mark.get('stage',int(mark['progress']*6))))
            self.heartsteel.draw('3084_Goliath_'+stages[stage-1]+'Stack',mark.get('age',0)/30,
                self.position(mark['position']),(0,-1),units=.28*.75,key=mark.get('key',tuple(mark['position'])),bound_size=max(30,mark.get('size',12)*2/.28))
        for steel_hit in s.get('heartsteelHits',[]):
            if not 0<=steel_hit['age']<90:continue
            self.heartsteel.draw('3084_Goliath_Impact',steel_hit['age']/30,self.position(steel_hit['position']),
                (0,-1),key=steel_hit.get('at',round(clock-steel_hit['age'])),bound_size=max(30,steel_hit.get('size',12)*2/.28))
        preview=s.get('previewQ')
        if preview:
            for face in preview.get('faces',[preview['face']]):self.indicator(p,face,preview['shape'],preview['stage'])
        if cast and cast.get('stage') and cast['age']<cast['impact'] and s.get('shape'):
            for face in cast.get('faces',[f]):self.indicator(p,face,s['shape'],cast['stage'],cast['age']/cast['impact'])
        elif self.indicators=='debug' and cast and cast.get('kind')=='W' and cast['age']<cast['impact']:
            u=s.get('units',.28);pts=self.corners(p,f,0,825*u,40*u);c.lines(pts+[pts[0]],.8,(.95,.23,.07,.45))
        for fx in s.get('fx',[]):self.impact(fx)
        chain=s.get('chain')
        if chain:
            anchor=self.position(chain['anchor']);shape=chain['shape'];t=max(0,min(1,1-(chain['expires']-clock)/45))
            if self.indicators!='off':self.stamp('aatrox_base_w_indicator',anchor,chain['face'],shape['near'],shape['far'],shape['width'],(1,.45*(1-t)+.05,.24*(1-t),.8))
            if self.indicators=='debug':c.lines(self.outline(anchor,chain['face'],shape),.8,(1,.7,.3,.9))
        r=s.get('r',{});started=r.get('started')
        if r.get('untilTick',0)>clock and started is not None:
            age=clock-started
            if 0<=age<45:
                c.flush();self.client.draw('R_Fear',age/30,p,f,key=started)
            self.ring(p,(1,0),19+2*math.sin(clock*.1),(.85,.035,.01,.2),1)
        dash=s.get('dash')
        if dash:
            origin=self.position(dash.get('origin',s['position']));target=dash.get('target',s['position'])
            dx=target[0]-origin[0]+self.offset;dy=(target[1]-origin[1])/self.ground[1];length=max(.001,math.hypot(dx,dy))
            c.flush();self.client.draw('E_Dash2',dash['age']/30,origin,(dx/length,dy/length),key=round(clock-dash['age']))
        redemption=s.get('redemption')
        if redemption and redemption['remaining']>0:
            rp=self.position(redemption['position']);self.ring(rp,(1,0),155,(.35,1,.65,.65),1.2)
            self.ring(rp,(1,0),155*(1-redemption['remaining']/75),(.7,1,.85,.8),1)
        c.flush()
    def pointer(self,s):
        """Four copies of the client arrow converge on the actual click point.

        Draw after the actor; X/Z form the ground and Y is mesh height. The
        former XY-only projection discarded the radial axis entirely.
        """
        click=s.get('click');age=s.get('clock',0)-(click or {}).get('at',0)
        if not click or not 0<=age<18 or s.get('dead') or s.get('actorHidden'):return
        c=self.canvas;cp=self.position(click['position']);t=age/18
        scale=.36;radius=5*(1-t)**3;alpha=min(1,(1-t)*3)
        color=(1,1,1,alpha)
        texture='click_attack' if click.get('enemy') else 'click_original'
        for angle in (0,math.pi/2,math.pi,3*math.pi/2):
            co,si=math.cos(angle),math.sin(angle)
            for i in range(0,len(self.click_mesh),3):
                tri=self.click_mesh[i:i+3];pts=[]
                for x,y,z,u,v in tri:
                    x*=scale;z=z*scale+radius;y*=scale
                    gx=x*co+z*si;gz=z*co-x*si
                    pts.append((cp[0]+gx,cp[1]+gz*.90-y*.12))
                c.polygon(pts,color,texture,[(v[3],v[4]) for v in tri])
        c.flush()
    def foreground(self,s,sockets):
        c=self.canvas;clock=s.get('clock',0);cast=s.get('cast')
        if s.get('dead'):self.trail=[];return
        for steel_hit in s.get('heartsteelHits',[]):
            if not 0<=steel_hit['age']<90:continue
            c.flush();p=self.position(steel_hit['position'])
            self.heartsteel.draw('3084_Goliath_Impact_Chest',steel_hit['age']/30,(p[0],p[1]-steel_hit.get('size',12)),
                (0,-1),key=steel_hit.get('at',round(clock-steel_hit['age'])),bound_size=max(30,steel_hit.get('size',12)*2/.28))
        # Blade trail follows actual animated weapon sockets. Original fixed
        # trail meshes still need bone attachment transforms for this GLB rig.
        active=cast and (cast.get('stage') or cast.get('kind')=='Attack') and not s.get('dead')
        if active and cast.get('impact') and cast['impact']-7<=cast['age']<=cast['impact']+3 and sockets:
            key=(cast.get('kind'),round(clock,3))
            if key!=self.last_trail:self.trail.append((clock,sockets['base'],sockets['tip']));self.trail=self.trail[-12:];self.last_trail=key
        else:self.trail=[]
        self.trail=[v for v in self.trail if clock-v[0]<3.5]
        for a,b in zip(self.trail,self.trail[1:]):
            alpha=max(0,1-(clock-a[0])/3.5)*.32
            c.polygon([a[1],a[2],b[2],b[1]],[(.55,.02,.005,alpha*.2),(1,.28,.025,alpha),(1,.55,.15,alpha),(.55,.02,.005,alpha*.2)],add=True)
            c.line(a[2],b[2],1.1,(1,.58,.22,alpha*2))
        bolt=s.get('bolt')
        if bolt:
            a=self.position(bolt['origin']);b=self.position(bolt['position']);self.chain(a,b,.95)
            age=bolt.get('age',math.dist(a,b)/(1800*.28))
            c.flush();self.client.draw('W_mis',age,b,bolt.get('face',s['face']),units=.14,key=round(clock-age*30),moving_speed=1800)
        chain=s.get('chain')
        if chain:
            a=self.position(chain['anchor']);target=self.position(chain['target']);b=(target[0],target[1]-12)
            self.chain(a,b,1,chain.get('pulled'))
            c.flush()
            self.client.draw('W_Hit_Tar',(clock-chain['expires']+45)/30,b,chain['face'],key=chain['expires'])
            if chain.get('pulled'):self.client.draw('W_Beam_Tar_Pull',(clock-chain['expires'])/30,b,chain['face'],key=chain['expires'])
        for hit in s.get('hits',[]):
            age=clock-hit['at']
            if not 0<=age<60:continue
            p=self.position(hit['position']);center=(p[0],p[1]-12);strong=hit.get('strong');size=44 if strong else 26
            c.flush();self.client.draw('Q_Sweet_hit_tar' if strong else 'Q_Hit_Tar',age/30,center,s['face'],key=hit['at'])
        c.flush()
    @staticmethod
    def damage_opacity(s):
        if any(s.get(k) for k in ('dead','actorHidden','paused','occluded','transition','preview')):return 0
        clock=s.get('clock',0);hit=s.get('screenHitAt');age=clock-hit if hit is not None else -1
        flash=.12*(1-age/21)**2 if 0<=age<21 else 0
        hud=s.get('hud',{});maximum=hud.get('maxHP',0)
        ratio=max(0,min(1,hud.get('hp',maximum)/maximum)) if maximum>0 else 1
        danger=max(0,(.30-ratio)/.30)
        low=.28*danger*(.93+.07*math.sin(clock*math.tau/48))
        return min(.34,flash+low)
    def screen(self,s):
        c=self.canvas;r=s.get('r',{});clock=s.get('clock',0);started=r.get('started')
        opacity=self.damage_opacity(s)
        if opacity>0:
            w,h=s['screen'];c.rect(0,0,w,h,(1,1,1,opacity),'damage_screen');c.flush()
        if s.get('dead') or started is None or r.get('untilTick',0)<=clock:return
        age=clock-started;strength=(.045+.22*math.exp(-age/15))*min(1,age/3)*min(1,(r['untilTick']-clock)/24)
        w,h=s['screen'];outer=(.65,.005,.002,strength);inner=(.65,.005,.002,0)
        c.rect(0,0,w,h*.16,[outer,outer,inner,inner]);c.rect(0,h*.84,w,h*.16,[inner,inner,outer,outer])
        c.rect(0,0,w*.12,h,[outer,inner,inner,outer]);c.rect(w*.88,0,w*.12,h,[inner,outer,outer,inner]);c.flush()
