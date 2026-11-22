"""Read bounded experimental snapshots, without opening a socket or changing Isaac saves."""
import json,math,time,threading
from pathlib import Path
PREFIX='[SAMIRA_EXTERNAL] '

def continuous(a,b):
    keys=('session','room','screen','transition','paused','occluded','stasis')
    eligible=not b.get('transition') or b.get('presentation',0)>=2 and a.get('renderCaptured') and b.get('renderCaptured')
    return (a.get('hero','samira')==b.get('hero','samira') and all(a.get(k)==b.get(k) for k in keys)
            and eligible and not b.get('occluded')
            and math.dist(a['position'],b['position'])<100)

def coordinates(value):
    return len(value)==2 and all(isinstance(n,(int,float)) and math.isfinite(n) for n in value)

def parse(line):
    if PREFIX not in line:return None
    try:
        value=json.loads(line.split(PREFIX,1)[1])
        if value.get('version')!=1:return None
        if not value.get('active'):return {'active':False}
        for key in ('screen','position','face'):
            if not coordinates(value[key]):return None
        if min(value['screen'])<=0 or not isinstance(value['kind'],str):return None
        if not math.isfinite(value['phase']) or not math.isfinite(value['time']):return None
        if value.get('hero')=='yone':
            frame=value.get('actionFrame',0);badge=value.get('mastery')
            if not math.isfinite(frame) or frame<0:return None
            if badge is not None and (not 0<=badge['at']<=1 or not coordinates(badge['position'])):return None
        return value
    except (ValueError,KeyError,TypeError,AttributeError):return None

class Tail:
    def __init__(self,path):
        self.path=Path(path);self.offset=self.path.stat().st_size if self.path.exists() else 0;self.pending=b''
        self.latest=None;self.previous=None;self.received=0;self.interval=1/30;self.count=0;self.settle_until=0
    def poll(self,now=None):
        realtime=now is None
        now=time.perf_counter() if now is None else now
        try:
            size=self.path.stat().st_size
            if size<self.offset:self.offset=0;self.pending=b'';self.latest=None;self.previous=None
            if size==self.offset:return
            with self.path.open('rb') as f:
                f.seek(self.offset);chunk=f.read(2*1024*1024);self.offset=f.tell()
        except OSError:return
        if realtime:now=time.perf_counter()
        lines=(self.pending+chunk).split(b'\n');self.pending=lines.pop()[-65536:]
        for line in lines:
            value=parse(line.decode('utf-8',errors='replace'))
            if value is None:continue
            if value.get('active') and self.latest and self.latest.get('active'):
                if math.dist(value['position'],self.latest['position'])>=100:self.settle_until=now+.12
                dt=(value['time']-self.latest['time'])/1000
                if 0<dt<.3 and value.get('seq',0)>self.latest.get('seq',0) and continuous(self.latest,value):self.previous=self.latest;self.interval=dt
                else:self.previous=None
            else:self.previous=None
            self.latest=value;self.received=now;self.count+=1
    def sample(self,now=None):
        now=time.perf_counter() if now is None else now
        if not self.latest or not self.latest.get('active'):return None
        # During the engine's blocking room load, hold only the acknowledged HUD.
        # No extrapolation of the actor, particles or new gameplay state.
        timeout=.5
        if self.latest.get('hero')!='yone':
            if self.latest.get('presentation',0)>=2:timeout=3
            elif self.latest.get('transition') and self.latest.get('hudVisible'):timeout=2
        if now-self.received>timeout:return None
        result=dict(self.latest);a=self.previous;b=self.latest
        result['positionReset']=now<self.settle_until
        result['packetClock']=b.get('clock',0)
        result['heartbeatTime']=b['time']+max(0,now-self.received)*1000
        if a and not b.get('paused'):
            weight=min(1,max(0,(now-self.received)/self.interval))
            result['position']=[x+(y-x)*weight for x,y in zip(a['position'],b['position'])]
            if a['kind']==b['kind'] and a.get('clip')==b.get('clip'):
                delta=b['phase']-a['phase']
                looping=b.get('looping',not b.get('cast'))
                if delta<-.5 and looping:delta+=1
                result['phase']=(a['phase']+delta*weight)%1 if looping else a['phase']+delta*weight
                if (a.get('actionId')==b.get('actionId') and 'actionFrame' in a and 'actionFrame' in b
                        and a['actionFrame']<=b['actionFrame']):
                    result['actionFrame']=a['actionFrame']+(b['actionFrame']-a['actionFrame'])*weight
            result['clock']=a['clock']+(b['clock']-a['clock'])*weight
            old_walk=a.get('locomotion');new_walk=b.get('locomotion')
            if old_walk and new_walk and old_walk['kind']==new_walk['kind']:
                delta=new_walk['phase']-old_walk['phase']
                if delta<-.5:delta+=1
                result['locomotion']=dict(new_walk,phase=(old_walk['phase']+delta*weight)%1)
            # Cast marker, animation and impact all use the same delayed timeline.
            result['fx']=[dict(f,age=max(0,f['age']-(b['clock']-result['clock']))) for f in b.get('fx',[]) if f['age']>=b['clock']-result['clock']]
            delay=b['clock']-result['clock']
            result['heartsteelHits']=[dict(f,age=f['age']-delay) for f in b.get('heartsteelHits',[]) if f['age']>=delay]
            old_badge=a.get('mastery');new_badge=b.get('mastery')
            if old_badge and new_badge:
                old_at,new_at=old_badge['at'],new_badge['at']
                if old_at==new_at or b.get('hero')=='yone' and old_at<new_at:
                    result['mastery']=dict(new_badge,at=old_at+(new_at-old_at)*weight,
                        position=[x+(y-x)*weight for x,y in zip(old_badge['position'],new_badge['position'])])
            previous_marks={f['key']:f for f in a.get('heartsteel',[]) if 'key' in f}
            result['heartsteel']=[]
            for mark in b.get('heartsteel',[]):
                old=previous_marks.get(mark.get('key'));current=dict(mark)
                if old:
                    current['position']=[x+(y-x)*weight for x,y in zip(old['position'],mark['position'])]
                    if old.get('stage')==mark.get('stage'):current['age']=old['age']+(mark['age']-old['age'])*weight
                result['heartsteel'].append(current)
            if b.get('cast') and a.get('cast') and a['cast'].get('stage')==b['cast'].get('stage') and a['cast'].get('kind')==b['cast'].get('kind'):
                result['cast']=dict(b['cast'],age=a['cast']['age']+(b['cast']['age']-a['cast']['age'])*weight)
            for key,identity,positions in [('bolt','origin',('position',)),('chain','anchor',('target',)),('dash','origin',())]:
                old=a.get(key);new=b.get(key)
                if old and new and identity in old and identity in new and old[identity]==new[identity]:
                    result[key]=dict(new)
                    for name in positions:result[key][name]=[x+(y-x)*weight for x,y in zip(old[name],new[name])]
                    if 'age' in old and 'age' in new:result[key]['age']=old['age']+(new['age']-old['age'])*weight
        return result


class BufferedTail:
    """Keep log I/O off the render thread; publish complete immutable views.

    The reader never touches GPU/window state. Sampling retains Tail's existing
    interpolation, room epochs and stale-data policy without waiting on a lock.
    """
    def __init__(self,path):
        self._tail=Tail(path);self._view=None;self._error=None
        self.read_ms=0;self._stop=threading.Event()
        self._publish()
        self._thread=threading.Thread(target=self._run,name='Samira-log-reader',daemon=True)
        self._thread.start()

    def _publish(self):
        view=object.__new__(Tail)
        view.__dict__=self._tail.__dict__.copy()
        # Tail replaces packets/bytes rather than modifying published packets.
        # One reference assignment publishes the entire view under CPython's GIL.
        self._view=view

    def _run(self):
        try:
            while not self._stop.is_set():
                start=time.perf_counter();self._tail.poll()
                self.read_ms=(time.perf_counter()-start)*1000
                self._publish()
                self._stop.wait(1/120)
        except Exception as error:
            self._error=error

    @property
    def count(self):return self._view.count

    def sample(self,now=None):
        if self._error:raise RuntimeError('Samira log reader failed') from self._error
        return self._view.sample(now)

    def close(self):
        self._stop.set();self._thread.join(timeout=.25)
