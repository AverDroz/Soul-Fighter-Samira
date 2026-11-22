"""Live Soul Fighter rendering. Lua owns movement, projectiles, and damage."""
from pathlib import Path
import argparse,json,math,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/render-deps'))
sys.path.insert(0,str(ROOT/'src/samira/external'))
from model import Model,GPURenderer
from bridge import BufferedTail
from layered_surface import LayeredFrame
from samira_audio import MAX_PACKET_AGE_MS, Mixer, SamiraAudio

YONE_ASSETS=ROOT/'assets/yone-local'
YONE_EMOTES={'joke','taunt','dance','laugh'}
YONE_DANCE_INTRO_SECONDS=3.1
YONE_ANCHORED_CASTS={'attack','attack2','q','q_follow','q3','q3_in','q3_out','w','e','e_dash',
                     'e_return','e_return_out','r','r_out'}

def actor_yaw(state):
    x, y = state["face"]
    if state["kind"] == "QMelee":
        visual = state.get("visual") or {}
        skill = visual.get("skill") or {}
        age = skill.get("age") if skill.get("kind") == "qmelee" else None
        events = reversed(visual.get("events") or [])
        # The cast is emitted on keypress, the hit only after the windup.
        # A previous strike can still be fading when another Q is cast.
        event_face = next((event.get("direction") for event in events
                           if event["kind"] == "cast" and event.get("source") == "qmelee"
                           and age is not None and abs(event["age"] - age) < .05), None)
        if age is None and event_face is None:
            event_face = next((event.get("direction") for event in reversed(visual.get("events") or [])
                               if event["kind"] == "qmelee" and event["age"] < .45), None)
        if event_face is not None:
            x, y = event_face
        else:
            gx, gy = visual.get("ground") or (1, 1)
            x, y = x * gx, y * gy
        # GPU yaw describes a heading on the ground before camera projection.
        y /= .573576
    return math.pi / 2 - math.atan2(y, x)

def actor_phase(state):
    phase = state["phase"]
    if state["kind"] != "QMelee":
        return phase
    skill = (state.get("visual") or {}).get("skill") or {}
    windup = skill.get("windup")
    if skill.get("kind") != "qmelee" or not windup or not skill.get("duration"):
        return phase
    elapsed = phase * skill["duration"]
    # In the one-second Skin30 clip Sword_Tip2 crosses rig forward (+Z)
    # at source frame 7.65/30. Meet that frame at the Lua damage tick,
    # then play the authored follow-through at its original speed.
    contact = 7.65 / 30
    if elapsed < windup:
        return contact * elapsed / windup
    return min(1, contact + elapsed - windup)


def yone_animation(state,durations):
    clip=state.get('clip') or state['kind']
    ticks=state.get('actionFrame')
    duration=durations.get(clip)
    if ticks is None or clip not in YONE_EMOTES or not duration:
        return clip,state['phase']
    seconds=ticks/30
    if clip=='dance':
        intro=durations.get('dance_in',0)
        if seconds<intro:return 'dance_in',seconds/intro
        return clip,((seconds-intro)/duration)%1
    if clip=='taunt' and seconds>=duration and durations.get('taunt_loop'):
        return 'taunt_loop',((seconds-duration)/durations['taunt_loop'])%1
    return clip,min(1,seconds/duration)


class YoneRenderer:
    def __init__(self,ctx,path):
        self.actor=self.mastery=None
        if path.is_file():
            try:
                self.actor=GPURenderer(ctx,Model(path,hero='yone'))
            except Exception as error:
                print('Yone model unavailable; native character retained: '+repr(error),flush=True)
        try:
            from mastery_renderer import MasteryRenderer
            self.mastery=MasteryRenderer(ctx)
        except Exception as error:
            print('Mastery renderer unavailable: '+repr(error),flush=True)

    def reset(self):
        if self.actor:self.actor.reset()

    def draw(self,state,dt):
        capabilities={};model_drawn=badge_drawn=False
        if self.actor:
            try:
                clip,phase=yone_animation(state,self.actor.model.durations)
                self.actor.draw(state['kind'],phase,tuple(state['position']),tuple(state['screen']),actor_yaw(state),dt,
                                clip=clip,hurt=state.get('hurt',False),body_scale=state.get('bodyScale',(1,1)),
                                anchor_root=clip in YONE_ANCHORED_CASTS)
                model_drawn=True
                capabilities['yoneModel']=True
            except Exception as error:
                print('Yone model disabled; native character restored: '+repr(error),flush=True)
                self.actor.close();self.actor=None
        if self.mastery:
            try:
                badge_drawn=self.mastery.draw(state,normalized=True)
                capabilities['mastery']=True
            except Exception as error:
                print('Mastery renderer disabled: '+repr(error),flush=True)
                self.mastery.close();self.mastery=None
        return model_drawn or badge_drawn,capabilities

    def close(self):
        if self.mastery:self.mastery.close()
        if self.actor:self.actor.close()


class YoneAudio:
    """Locally imported audio keyed to emote activations."""

    def __init__(self, root, backend=Mixer, *, dance_intro=YONE_DANCE_INTRO_SECONDS):
        self.samples = {clip: [{'file': f'{clip}.wav'}] for clip in sorted(YONE_EMOTES | {'dance_loop'})
                        if (root / f'{clip}.wav').is_file()}
        self.backend = backend(root, self.samples) if self.samples else None
        self.dance_intro = dance_intro
        self.scene = self.action = None
        self.playing = False
        self.dance_looping = False

    def update(self, state, visible, _now):
        if self.backend is None:
            return
        active = state and state.get('active') and state.get('hero') == 'yone'
        scene, action = self.scene, self.action
        if active:
            clip = state['kind']
            session = state.get('session')
            scene = (session, state.get('room'))
            serial = state.get('actionId')
            action = (session, clip, serial) if clip in self.samples and serial is not None else None
            volume = state.get('sfxVolume', 1.)
            volume = min(1., max(0., volume)) if isinstance(volume, (int, float)) and math.isfinite(volume) else 1.
            fresh = state.get('heartbeatTime', 0) - state.get('time', 0) <= MAX_PACKET_AGE_MS
        else:
            fresh = False
            volume = 0.

        audible = bool(active and visible and fresh and action and volume > 0)
        changed = action != self.action
        if self.playing and (changed or scene != self.scene or not audible):
            self.backend.stop_all()
            self.playing = False
            self.dance_looping = False
        if audible:
            self.backend.set_volume(volume)
            ticks = state.get('actionFrame', float('inf'))
            if changed and ticks <= 5:
                self.backend.play(action[1], 'voice', .44)
                self.playing = True
            elif (self.playing and action[1] == 'dance' and not self.dance_looping
                  and ticks / 30 >= self.dance_intro and 'dance_loop' in self.samples):
                self.backend.play('dance_loop', 'voice', .44, loops=-1)
                self.dance_looping = True
        self.scene, self.action = scene, action

    def close(self):
        if self.backend:
            self.backend.close()


def open_audio(hero, *, dance_intro=YONE_DANCE_INTRO_SECONDS):
    try:
        if hero == 'samira':
            audio = SamiraAudio(ROOT / 'assets/samira-soul-fighter/audio')
            print('Soul Fighter audio ready: Skin30 SFX + Russian voice', flush=True)
            return audio
        if hero == 'yone':
            audio = YoneAudio(YONE_ASSETS / 'audio', dance_intro=dance_intro)
            if audio.backend:
                print('Yone local emote audio ready', flush=True)
                return audio
    except Exception as error:
        print(f'{hero} audio unavailable: {error!r}', flush=True)
    return None


def acknowledge(folder,state,visible,capabilities=None):
    payload={'version':1,'session':state.get('session'),'room':state.get('room'),
        'seq':state.get('seq',0),
        # Use the original packet timestamp. A blocked game cannot extend its lease.
        'time':state.get('time',0),'ready':visible,'visible':visible,
        'hudVisible':False,'capabilities':capabilities or {}}
    if state.get('hero') is not None:payload['hero']=state['hero']
    data=json.dumps(payload,separators=(',',':'))
    folder.mkdir(parents=True,exist_ok=True)
    for slot in (1,2,3):
        target=folder/f'save{slot}.dat';tmp=target.with_suffix('.tmp')
        try:
            tmp.write_text(data,encoding='utf8');os.replace(tmp,target)
        except OSError:pass

def run(args):
    from overlay import Windows,create_window,glfw

    window=ctx=surface=tail=audio=renderer=yone=None
    status=Path(args.status_dir);last_state={}
    stop=ROOT/'work/testroom-renderer.stop'
    windows=Windows()
    try:
        window,ctx=create_window(False)
        glfw.swap_interval(0)
        model=Model(ROOT/'src/samira/reference/source/model.glb')
        renderer=GPURenderer(ctx,model);surface=LayeredFrame(ctx)
        yone=YoneRenderer(ctx,YONE_ASSETS/'yone.glb')
        dances=yone.actor.model.durations if yone.actor else {}
        dance_intro=dances.get('dance_in',YONE_DANCE_INTRO_SECONDS)
        vfx=None
        try:
            from samira_vfx import SoulFighterVFX
            vfx=SoulFighterVFX(ctx,ROOT/'assets/samira-soul-fighter/vfx')
        except Exception as error:
            print('VFX unavailable; native projectiles retained: '+repr(error),flush=True)
        pointer=None
        try:
            from system_pointer import SystemPointer
            pointer=SystemPointer(ctx)
        except (OSError,ValueError) as error:
            print('Standard cursor overlay unavailable: '+repr(error),flush=True)
        audio_hero='samira'
        audio=open_audio(audio_hero)
        tail=BufferedTail(args.log)
        print('Ready: Soul Fighter; GPU '+ctx.info['GL_RENDERER'],flush=True)
        last=time.perf_counter();last_ack=0;last_report=last;count=0;scene=None;next_settings=0
        last_presentation=None
        settings=ROOT/'src/samira-testroom/visual-settings.json'
        while not stop.exists():
            now=time.perf_counter();dt=min(.1,now-last);last=now;glfw.poll_events()
            if now>=next_settings:
                next_settings=now+1
                try:
                    value=float(json.loads(settings.read_text(encoding='utf8'))['model_pixel_scale'])
                    if math.isfinite(value) and .08<=value<=.4:model.pixel_scale=value
                except (OSError,ValueError,KeyError,TypeError):pass
            state=tail.sample(now);hwnd=windows.game() if state else None
            box=windows.bounds(hwnd) if hwnd else None
            visible=bool(state and box and min(box[2:])>0 and not state.get('occluded')
                         and not state.get('transition') and not state.get('paused'))
            hero=state.get('hero','samira') if state else None
            if hero and hero!=audio_hero:
                if audio:audio.close()
                audio_hero=hero
                audio=open_audio(hero,dance_intro=dance_intro)
            if audio:
                try:
                    audio.update(state,visible,now)
                except Exception as error:
                    print(f'{audio_hero} audio disabled: {error!r}',flush=True)
                    audio.close();audio=None
            if not visible:
                surface.hide()
                if last_presentation is not None or now-last_ack>.1:
                    acknowledge(status,state or last_state,False);last_ack=now;last_presentation=None
                time.sleep(.02);continue
            last_state=state
            current=(hero,state.get('session'),state.get('room'))
            new_scene=current!=scene
            if new_scene:
                renderer.reset();yone.reset();scene=current
                if vfx:vfx.reset()
            surface.begin(tuple(box[2:]));ctx.clear(0,0,0,0)
            rendered=False;capabilities={}
            if hero=='yone':
                rendered,capabilities=yone.draw(state,dt)
            elif hero=='samira':
                if vfx:
                    try:vfx.begin(state);vfx.ground(state)
                    except Exception as error:
                        print('VFX disabled; native projectiles restored: '+repr(error),flush=True)
                        vfx=None
                yaw=actor_yaw(state)
                sockets=renderer.draw(state['kind'],actor_phase(state),tuple(state['position']),tuple(state['screen']),yaw,dt,
                              clip=state.get('clip'),hurt=state.get('hurt',False),body_scale=state.get('bodyScale',(1,1)),
                              anchor_root=((state.get('visual') or {}).get('skill') or {}).get('kind') in ('e','eq'),
                              snap_facing=state['kind']=='QMelee')
                rendered=True
                if vfx:
                    try:
                        vfx.foreground(state,sockets)
                        capabilities={'visual':1,'projectiles':bool(vfx.can_projectiles),'styleHud':True}
                    except Exception as error:
                        print('VFX disabled; native projectiles restored: '+repr(error),flush=True)
                        vfx=None
            if pointer:
                pointer.draw(hwnd,box,state.get('nativeCursor',False))
            surface.present(box);surface.show()
            presentation=(rendered,capabilities)
            if new_scene or presentation!=last_presentation or now-last_ack>.1:
                acknowledge(status,state,rendered,capabilities);last_ack=now;last_presentation=presentation
            count+=1
            if new_scene and rendered:print('LIVE frame presented: '+json.dumps({k:state.get(k) for k in ('hero','session','room','kind','position','screen')}),flush=True)
            if now-last_report>10:
                print(f'Live: {count/(now-last_report):.1f} frames/s; action={state["kind"]}; room={state.get("room")}',flush=True)
                count=0;last_report=now
            time.sleep(max(0,1/60-(time.perf_counter()-now)))
    finally:
        if audio:audio.close()
        acknowledge(status,last_state,False)
        if tail:tail.close()
        if surface:surface.close()
        if yone:yone.close()
        if renderer:renderer.close()
        if ctx:ctx.release()
        if window:glfw.destroy_window(window)
        glfw.terminate()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--log',required=True);parser.add_argument('--status-dir',required=True)
    run(parser.parse_args())
