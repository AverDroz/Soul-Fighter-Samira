"""Live Soul Fighter rendering. Lua owns movement, projectiles, and damage."""
from pathlib import Path
import argparse,json,math,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/render-deps'))
sys.path.insert(0,str(ROOT/'src/samira/external'))
from model import Model,GPURenderer,YONE_VIEW
from bridge import BufferedTail
from display_geometry import DisplayGate
from layered_surface import LayeredFrame
from samira_audio import MAX_PACKET_AGE_MS, Mixer, SamiraAudio
from yone_combat_audio import YoneCombatAudio

YONE_ASSETS=ROOT/'assets/yone-local'
YONE_EMOTES={'joke','taunt','dance','laugh'}
YONE_DANCE_INTRO_SECONDS=3.1
YONE_SPIRIT_SECONDS=5
YONE_ANCHORED_CASTS={'attack','attack2','q','q_follow','q3','q3_in','q3_out','w','e','e_dash',
                     'e_return','e_return_out','r','r_out'}
YONE_CAST_TICKS={'q':(6,16),'q3':(7,22),'w':(8,22),'e':(3,14),'e_return':(0,13),'r':(23,40)}
YONE_DASH_TICKS={'q3':5,'e':2,'e_return':5}

def actor_yaw(state, view=None):
    x, y = state["face"]
    if view is not None:
        x, y = state.get("viewFace") or (x, y)
        sx, sy = state.get("bodyScale", (1, 1))
        return math.pi / 2 - math.atan2(y / (view[1] * (sy or 1)), x / (sx or 1))
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
    if clip in YONE_CAST_TICKS:
        hit, length = YONE_CAST_TICKS[clip]
        timing = state.get('yoneTiming')
        if isinstance(timing, dict):
            impact, total = timing.get('hit'), timing.get('length')
            if type(impact) is int and type(total) is int and 0 <= impact < total <= 120:
                hit, length = impact, total
        tick = min(1., max(0., state['phase'])) * length
        if clip == 'q' and hit and durations.get('q_follow'):
            if tick < hit:
                return 'q', tick / hit
            return 'q_follow', (tick - hit) / (length - hit)
        if clip == 'q3' and durations.get('q3_in') and durations.get('q3_out'):
            end = hit + YONE_DASH_TICKS['q3']
            if tick < hit:
                return 'q3_in', tick / hit
            if tick < end:
                return 'q3', (tick - hit) / (end - hit)
            if tick < end + 2:
                return 'q3_out', (tick - end) / 2
            return yone_movement_animation(state)
        if clip == 'r' and durations.get('r_out'):
            if tick < hit:
                return 'r', tick / hit
            return 'r_out', min(1., (tick - hit) / (30 * durations['r_out']))
        if clip == 'e' and durations.get('e_dash'):
            if tick < hit:
                return 'e', tick / hit
            if tick < hit + YONE_DASH_TICKS['e']:
                return 'e_dash', (tick - hit) / YONE_DASH_TICKS['e']
            return yone_movement_animation(state)
        if clip == 'e_return' and durations.get('e_return_out'):
            travel = YONE_DASH_TICKS['e_return']
            if tick < travel:
                return 'e_return', tick / travel
            return 'e_return_out', min(1., (tick - travel) / (30 * durations['e_return_out']))
        if clip in ('q', 'w') and hit:
            # Place the extended steel thrust and the middle of the cleave on
            # the damage tick while preserving their different silhouettes.
            contact = .75 if clip == 'q' else .58
            if tick < hit:
                return clip, tick / hit * contact
            return clip, contact + (1 - contact) * ((tick - hit) / (length - hit))
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


def yone_movement_animation(state):
    clock = state.get('clock', 0)
    return ('run', clock / 24 % 1) if state.get('yoneMoving') else ('idle', clock / 60 % 1)


def yone_dash_position(state, event):
    kind = state['kind']
    ticks = YONE_DASH_TICKS.get(kind)
    if not ticks or event.get('kind') != kind:
        return None
    age = event.get('age')
    start = event.get('origin')
    end = event.get('landing') if kind == 'q3' else event.get('target')
    if (not isinstance(age, (int, float)) or not math.isfinite(age)
            or not all(isinstance(p, (list, tuple)) and len(p) == 2
                       and all(isinstance(x, (int, float)) and math.isfinite(x) for x in p)
                       for p in (start, end))):
        return None
    clock = state.get('clock', 0)
    elapsed = max(0., age * 30 - max(0., state.get('packetClock', clock) - clock))
    if elapsed >= ticks or start == end:
        return None
    progress = elapsed / ticks
    progress = progress * progress * (3 - 2 * progress)
    return tuple(a + (b - a) * progress for a, b in zip(start, end))


class YoneRenderer:
    def __init__(self,ctx,path):
        self.actor=self.mastery=self.vfx=None
        if path.is_file():
            try:
                self.actor=GPURenderer(ctx,Model(path,hero='yone'))
                print('Yone model loaded',flush=True)
            except Exception as error:
                print('Yone model unavailable; native character retained: '+repr(error),flush=True)
        else:
            print(f'Yone model file missing; native character retained: {path}',flush=True)
        try:
            from mastery_renderer import MasteryRenderer
            self.mastery=MasteryRenderer(ctx)
        except Exception as error:
            print('Mastery renderer unavailable: '+repr(error),flush=True)
        try:
            from yone_vfx import YoneVFX
            self.vfx=YoneVFX(ctx)
        except Exception as error:
            print('Yone effects unavailable: '+repr(error),flush=True)

    def reset(self):
        if self.actor:self.actor.reset()

    def disable_vfx(self,error):
        print('Yone effects disabled; native cues restored: '+repr(error),flush=True)
        self.vfx.close();self.vfx=None

    def draw(self,state,dt):
        if state.get('occluded') or state.get('transition') or state.get('paused'):
            return False,{}
        capabilities={};model_drawn=badge_drawn=False
        spirit=None
        dash=None
        if state['kind'] in YONE_DASH_TICKS:
            picture=state.get('yone')
            events=picture.get('fx') if isinstance(picture,dict) else None
            for event in reversed(events[-24:] if isinstance(events,(list,tuple)) else ()):
                if isinstance(event,dict) and event.get('kind') == state['kind']:
                    dash=yone_dash_position(state,event)
                    break
            if dash is not None:
                state=dict(state,position=dash)
        recalling = dash is not None and state['kind'] == 'e_return'
        if self.vfx:
            try:
                spirit=self.vfx.begin(state)
                body=spirit
                if recalling:
                    body={'anchor':event['target'],'face':state['face'],
                          'viewFace':event.get('bodyFace'),'remaining':event.get('bodyRemaining',1)}
                if body and self.actor and 'e_body' in self.actor.model.tracks:
                    remaining=body['remaining']
                    duration=self.actor.model.durations['e_body']
                    phase=((1-remaining)*YONE_SPIRIT_SECONDS/duration)%1
                    scale=state.get('bodyScale',(1,1))
                    yaw=actor_yaw({'face':body['face'],'viewFace':body.get('viewFace'),'bodyScale':scale},YONE_VIEW)
                    self.actor.draw('e_body',phase,tuple(body['anchor']),tuple(state['screen']),yaw,dt,
                                    clip='e_body',detached=True,form='body',opacity=.46+.43*remaining,
                                    body_scale=scale,anchor_root=True)
            except Exception as error:
                self.disable_vfx(error);spirit=None
        if self.actor:
            try:
                clip,phase=yone_animation(state,self.actor.model.durations)
                self.actor.draw(state['kind'],phase,tuple(state['position']),tuple(state['screen']),actor_yaw(state,YONE_VIEW),dt,
                                clip=clip,hurt=state.get('hurt',False),body_scale=state.get('bodyScale',(1,1)),
                                anchor_root=clip in YONE_ANCHORED_CASTS or clip in ('idle','run'),
                                blend_seconds=.025 if clip in YONE_ANCHORED_CASTS else .10,
                                snap_facing=clip in YONE_ANCHORED_CASTS,
                                form='spirit' if spirit or recalling else None,opacity=.90 if spirit or recalling else 1)
                model_drawn=True
                capabilities['yoneModel']=True
            except Exception as error:
                print('Yone model disabled; native character restored: '+repr(error),flush=True)
                self.actor.close();self.actor=None
        if self.vfx:
            try:
                if self.vfx.finish():capabilities['yoneVfx']=True
            except Exception as error:
                self.disable_vfx(error)
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
        if self.vfx:self.vfx.close()


class YoneAudio:
    """Locally imported audio keyed to emote activations."""

    def __init__(self, root, backend=Mixer, *, dance_intro=YONE_DANCE_INTRO_SECONDS):
        self.samples = {clip: [{'file': f'{clip}.wav'}] for clip in sorted(YONE_EMOTES | {'dance_loop'})
                        if (root / f'{clip}.wav').is_file()}
        combat_samples = YoneCombatAudio.load_samples(root)
        samples = {**self.samples, **combat_samples}
        self.backend = backend(root, samples) if samples else None
        self.combat = YoneCombatAudio(root, mixer=self.backend, samples=combat_samples) if combat_samples else None
        self.dance_intro = dance_intro
        self.scene = self.action = None
        self.playing = False
        self.dance_looping = False

    def update(self, state, visible, _now):
        if self.backend is None:
            return
        if self.combat:
            self.combat.update(state, visible, _now)
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
            self.backend.stop('voice')
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
                print('Yone local audio ready', flush=True)
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
    display=state.get('display')
    if isinstance(display,dict) and isinstance(display.get('id'),int):payload['display']=display['id']
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
    display_gate=DisplayGate()
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
        print(f'Game log: {args.log}\nPresentation status: {status}',flush=True)
        last=time.perf_counter();last_ack=0;last_report=last;count=0;scene=None;next_settings=0
        last_presentation=None
        last_display_reason=None
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
            client=windows.bounds(hwnd) if hwnd else None
            box=display_gate.choose(hwnd,client,state)
            if state and display_gate.reason!=last_display_reason:
                logical=state.get('screen')
                print(f'Display: {display_gate.reason or "viewport confirmed"}; logical={logical}; '
                      f'render={state.get("display")}; client={client}; overlay={box}',flush=True)
                last_display_reason=display_gate.reason
            visible=bool(state and box and not state.get('occluded')
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
            presentation=(rendered,capabilities,box)
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
