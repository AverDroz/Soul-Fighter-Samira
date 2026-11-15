"""Live Soul Fighter rendering. Lua owns movement, projectiles, and damage."""
from pathlib import Path
import argparse,json,math,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/render-deps'))
sys.path.insert(0,str(ROOT/'src/samira/external'))
from overlay import Windows,create_window,glfw
from model import Model,GPURenderer
from bridge import BufferedTail
from layered_surface import LayeredFrame

def actor_yaw(state):
    x, y = state["face"]
    if state["kind"] == "QMelee":
        visual = state.get("visual") or {}
        event_face = next((event.get("direction") for event in reversed(visual.get("events") or [])
                           if event["kind"] == "qmelee" and event["age"] < .45), None)
        if event_face:
            x, y = event_face
        else:
            gx, gy = visual.get("ground") or (1, 1)
            x, y = x * gx, y * gy
        # GPU yaw describes a heading on the ground before camera projection.
        y /= .573576
    return math.pi / 2 - math.atan2(y, x)


def acknowledge(folder,state,visible,capabilities=None):
    data=json.dumps({'version':1,'session':state.get('session'),'room':state.get('room'),
        'seq':state.get('seq',0),
        # Use the original packet timestamp. A blocked game cannot extend its lease.
        'time':state.get('time',0),'ready':visible,'visible':visible,
        'hudVisible':False,'capabilities':capabilities if visible and capabilities else {}},separators=(',',':'))
    folder.mkdir(parents=True,exist_ok=True)
    for slot in (1,2,3):
        target=folder/f'save{slot}.dat';tmp=target.with_suffix('.tmp')
        try:
            tmp.write_text(data,encoding='utf8');os.replace(tmp,target)
        except OSError:pass

def run(args):
    window=ctx=surface=tail=audio=None
    status=Path(args.status_dir);last_state={}
    stop=ROOT/'work/testroom-renderer.stop'
    windows=Windows()
    try:
        window,ctx=create_window(False)
        glfw.swap_interval(0)
        model=Model(ROOT/'src/samira/reference/source/model.glb')
        renderer=GPURenderer(ctx,model);surface=LayeredFrame(ctx)
        vfx=None;capabilities={}
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
        try:
            from samira_audio import SamiraAudio
            audio=SamiraAudio(ROOT/'assets/samira-soul-fighter/audio')
            print('Soul Fighter audio ready: Skin30 SFX + Russian voice',flush=True)
        except Exception as error:
            print('Soul Fighter audio unavailable: '+repr(error),flush=True)
        tail=BufferedTail(args.log)
        print('Ready: Soul Fighter; GPU '+ctx.info['GL_RENDERER'],flush=True)
        last=time.perf_counter();last_ack=0;last_report=last;count=0;seen=False;scene=None;next_settings=0
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
            if audio:
                try:
                    audio.update(state,visible,now)
                except Exception as error:
                    print('Soul Fighter audio disabled: '+repr(error),flush=True)
                    audio.close();audio=None
            if not visible:
                surface.hide()
                if now-last_ack>.1:acknowledge(status,state or last_state,False);last_ack=now
                time.sleep(.02);continue
            last_state=state
            current=(state.get('session'),state.get('room'))
            if current!=scene:
                renderer.kind=renderer.pose=renderer.previous=renderer.yaw=None;scene=current
                if vfx:vfx.reset()
            surface.begin(tuple(box[2:]));ctx.clear(0,0,0,0)
            if vfx:
                try:vfx.begin(state);vfx.ground(state)
                except Exception as error:
                    print('VFX disabled; native projectiles restored: '+repr(error),flush=True)
                    vfx=None;capabilities={}
            yaw=actor_yaw(state)
            sockets=renderer.draw(state['kind'],state['phase'],tuple(state['position']),tuple(state['screen']),yaw,dt,
                          clip=state.get('clip'),hurt=state.get('hurt',False),body_scale=state.get('bodyScale',(1,1)),
                          anchor_root=((state.get('visual') or {}).get('skill') or {}).get('kind') in ('e','eq'),
                          snap_facing=state['kind']=='QMelee')
            if vfx:
                try:
                    vfx.foreground(state,sockets)
                    capabilities={'visual':1,'projectiles':bool(vfx.can_projectiles),'styleHud':True}
                except Exception as error:
                    print('VFX disabled; native projectiles restored: '+repr(error),flush=True)
                    vfx=None;capabilities={}
            if pointer:
                pointer.draw(hwnd,box,state.get('nativeCursor',False))
            surface.present(box);surface.show()
            if now-last_ack>.1:acknowledge(status,state,True,capabilities);last_ack=now
            count+=1
            if not seen:print('LIVE model presented: '+json.dumps({k:state.get(k) for k in ('session','room','kind','position','screen')}),flush=True);seen=True
            if now-last_report>10:
                print(f'Live: {count/(now-last_report):.1f} frames/s; action={state["kind"]}; room={state.get("room")}',flush=True)
                count=0;last_report=now
            time.sleep(max(0,1/60-(time.perf_counter()-now)))
    finally:
        if audio:audio.close()
        acknowledge(status,last_state,False)
        if tail:tail.close()
        if surface:surface.close()
        if window:glfw.destroy_window(window)
        glfw.terminate()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--log',required=True);parser.add_argument('--status-dir',required=True)
    run(parser.parse_args())
