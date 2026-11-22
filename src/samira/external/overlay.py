"""Windows external GPU preview. Never sends keyboard/mouse input to the game."""
from pathlib import Path
import argparse,ctypes,json,math,os,sys,time,traceback
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE/'deps'))
import glfw,moderngl,numpy as np
from PIL import Image
from model import Model,GPURenderer
from combat_effects import Effects
from hud import HUD
from bridge import BufferedTail
from status import Status
from visibility import layers
from native_cursor import NativeCursor
from layered_surface import LayeredFrame

class Windows:
    def __init__(self):
        from ctypes import wintypes as w
        self.u=ctypes.WinDLL('user32',use_last_error=True);self.w=w
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.foreground_key=None
        self.foreground_isaac=None
        try:self.u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError,OSError):pass
        signatures={'GetForegroundWindow':([],w.HWND),'IsWindowVisible':([w.HWND],w.BOOL),'IsIconic':([w.HWND],w.BOOL),
         'GetWindowTextW':([w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),'GetClientRect':([w.HWND,ctypes.POINTER(w.RECT)],w.BOOL),
         'ClientToScreen':([w.HWND,ctypes.POINTER(w.POINT)],w.BOOL),'GetCursorPos':([ctypes.POINTER(w.POINT)],w.BOOL),'GetWindowLongW':([w.HWND,ctypes.c_int],w.LONG),
         'GetWindowThreadProcessId':([w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD),
         'GetWindow':([w.HWND,w.UINT],w.HWND),
         'SetWindowLongW':([w.HWND,ctypes.c_int,w.LONG],w.LONG),'ShowWindow':([w.HWND,ctypes.c_int],w.BOOL),
         'SetWindowPos':([w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint],w.BOOL)}
        for name,(args,result) in signatures.items():fn=getattr(self.u,name);fn.argtypes=args;fn.restype=result
        self.kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.kernel.OpenProcess.restype=w.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype=w.BOOL
        self.kernel.CloseHandle.argtypes=[w.HANDLE];self.kernel.CloseHandle.restype=w.BOOL

    def is_isaac_process(self,pid):
        process=self.kernel.OpenProcess(0x1000,False,pid)  # QUERY_LIMITED_INFORMATION
        if not process:return None
        try:
            path=ctypes.create_unicode_buffer(4096);size=self.w.DWORD(len(path))
            if not self.kernel.QueryFullProcessImageNameW(process,0,path,ctypes.byref(size)):
                return None
            return Path(path.value).name.casefold()=='isaac-ng.exe'
        finally:
            self.kernel.CloseHandle(process)

    def game(self):
        # Only the foreground game can be displayed. Enumerating unrelated desktop
        # windows here cost ~210ms per frame on the live desktop (under 5 FPS).
        front=self.u.GetForegroundWindow()
        if not front or not self.u.IsWindowVisible(front) or self.u.GetWindow(front,4):return None  # GW_OWNER
        pid=self.w.DWORD()
        self.u.GetWindowThreadProcessId(front,ctypes.byref(pid))
        key=(front,pid.value)
        if key!=self.foreground_key:
            self.foreground_key=key
            self.foreground_isaac=self.is_isaac_process(pid.value)
        if self.foreground_isaac is not None:
            return front if self.foreground_isaac else None
        # A protected process may only expose its window title.
        title=ctypes.create_unicode_buffer(512);self.u.GetWindowTextW(front,title,512)
        return front if title.value.startswith('The Binding of Isaac') else None
    def bounds(self,hwnd):
        r=self.w.RECT();p=self.w.POINT(0,0)
        if self.u.IsIconic(hwnd) or not self.u.GetClientRect(hwnd,ctypes.byref(r)) or not self.u.ClientToScreen(hwnd,ctypes.byref(p)):return None
        return p.x,p.y,r.right-r.left,r.bottom-r.top
    def passive(self,hwnd):
        # GLFW supplies OS mouse passthrough; NOACTIVATE prevents incidental focus changes.
        style=self.u.GetWindowLongW(hwnd,-20);self.u.SetWindowLongW(hwnd,-20,(style|0x08000000|0x80)&~0x40000)
    def cursor(self,box,screen):
        p=self.w.POINT()
        if self.u.GetCursorPos(ctypes.byref(p)):
            return [(p.x-box[0])*screen[0]/box[2],(p.y-box[1])*screen[1]/box[3]]
    def place(self,hwnd,box,show=True):
        self.u.SetWindowPos(hwnd,self.w.HWND(-1),*box,0x0010|(0x0040 if show else 0)) # NOACTIVATE | optional SHOWWINDOW
    def hide(self,hwnd):self.u.ShowWindow(hwnd,0)

def create_window(transparent):
    if not glfw.init():raise RuntimeError('GLFW initialization failed')
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,3)
    glfw.window_hint(glfw.OPENGL_PROFILE,glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.VISIBLE,False);glfw.window_hint(glfw.FOCUSED,False);glfw.window_hint(glfw.FOCUS_ON_SHOW,False)
    glfw.window_hint(glfw.DECORATED,False);glfw.window_hint(glfw.TRANSPARENT_FRAMEBUFFER,transparent)
    window=glfw.create_window(640,480,'Samira external GPU preview',None,None)
    if not window:raise RuntimeError('OpenGL 3.3 window creation failed')
    glfw.make_context_current(window);glfw.swap_interval(1)
    return window,moderngl.create_context(require=330)

def self_test(ctx,model,renderer,effects):
    fbo=ctx.framebuffer([ctx.texture((1280,720),4)],ctx.depth_renderbuffer((1280,720)))
    fbo.use();ctx.viewport=(0,0,1280,720);ctx.clear(0,0,0,0)
    for kind,phase,x,yaw in [('SheathedIdle',.2,100,0),('Walk',.3,245,.6),('Q1',.60,390,.8),('Q3',.53,535,-.3)]:
        renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None
        renderer.draw(kind,phase,(x,240),(640,360),yaw,.2)
    ctx.finish();image=Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    assert image.getbbox(),'GPU returned an empty image';image.save(HERE/'gpu-preview.png')
    timings=[]
    for i in range(150):
        start=time.perf_counter();ctx.clear(0,0,0,0)
        renderer.draw('Q1' if i%90<30 else 'Walk',(i%30)/30,(320,240),(640,360),i*.015,1/60)
        effects.draw({'screen':[640,360],'position':[320,240],'face':[1,0],
                      'fx':[{'age':i%10,'stage':1,'position':[320,240],'face':[1,0],
                             'shape':{'kind':'box','near':0,'far':182,'width':25.2,'sweet':134.4}}]},0)
        ctx.finish();timings.append((time.perf_counter()-start)*1000)
    report={'gpu':ctx.info['GL_RENDERER'],'vertices':len(model.vertices),'bones':len(model.joints),
            'draw_calls_model':sum(name not in ('Wings','Banner') for name,_,_ in renderer.parts),
            'mean_ms':float(np.mean(timings[10:])),'p95_ms':float(np.percentile(timings[10:],95)),
            'scope':'Offscreen 1280x720 model + Q impact, includes CPU bone sampling and GPU completion; not in-game latency.'}
    (HERE/'gpu-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)

def presentation_mode(args):
    mode=getattr(args,'presentation',None)
    config=HERE/'presentation.json'
    if mode is None:mode=json.loads(config.read_text(encoding='utf-8')).get('mode','glfw') if config.exists() else 'glfw'
    if mode not in ('glfw','layered'):raise ValueError('Unknown presentation mode: '+str(mode))
    return mode

def run(args):
    mode=presentation_mode(args)
    windows=Windows();window,ctx=create_window(mode=='glfw' and not args.self_test);status=None;native_cursor=None;mastery=None;layered=None
    try:
        print('GPU:',ctx.info['GL_RENDERER'],flush=True)
        model=Model(ROOT/'reference/source/model.glb');renderer=GPURenderer(ctx,model)
        effects=Effects(ctx,ROOT/'mod/resources/gfx/samira/combat/aatrox_base_q_hit_burst.png')
        from mastery_renderer import MasteryRenderer
        mastery=MasteryRenderer(ctx)
        hud=HUD(effects.canvas,ROOT/'mod/resources/gfx/samira/hud')
        if args.self_test:self_test(ctx,model,renderer,effects);return
        native_cursor=NativeCursor()
        glfw.swap_interval(0)
        if mode=='layered':
            layered=LayeredFrame(ctx)
            print('Composition: '+json.dumps({'mode':'layered','path':'offscreen OpenGL -> BGRA DIB -> UpdateLayeredWindow',
                'windows_build':sys.getwindowsversion().build,'glfw':glfw.get_version_string().decode()}),flush=True)
        else:
            if not glfw.get_window_attrib(window,glfw.TRANSPARENT_FRAMEBUFFER):raise RuntimeError('Transparent framebuffer unavailable; refusing opaque overlay')
            glfw.set_window_attrib(window,glfw.MOUSE_PASSTHROUGH,True)
            hwnd=glfw.get_win32_window(window);windows.passive(hwnd)
        status=Status(args.status_dir);status.write(force=True)
        tail=BufferedTail(args.log);start=last=report=time.perf_counter();count=0;draw_times=[];stage_times=[];frame_gaps=[];last_box=None;shown=False;announced=False;scene=None
        echoes=[];echo_at=None;deadline=start
        print('Ready. Samira 0.7.66; buffered telemetry, GPU actor outline, native size and original-asset effects enabled.',flush=True)
        owner=None
        if getattr(args,'owner_pid',None):
            from companion import K
            owner=K.OpenProcess(0x100000,False,args.owner_pid)
            if not owner: return
        while not glfw.window_should_close(window) and time.perf_counter()-start<args.seconds:
            if Path(getattr(args,'stop_file',None) or HERE/'stop.request').exists():break
            if owner and K.WaitForSingleObject(owner,0)!=258:break
            now=time.perf_counter();frame_gaps.append((now-last)*1000);dt=min(.1,now-last);last=now;glfw.poll_events();events_at=time.perf_counter()
            read_at=time.perf_counter()
            state=tail.sample(now);game=windows.game() if state else None;box=windows.bounds(game) if game else None
            window_at=time.perf_counter()
            if state and not announced:
                print('Received live Isaac telemetry, seq='+str(state.get('seq'))+'; kind='+state['kind'],flush=True);announced=True
            if not state or not box or min(box[2:])<=0:
                native_cursor.restore()
                status.hidden(state)
                if shown:
                    print('Overlay hidden: '+('telemetry stale' if not state else 'pause' if state.get('paused') else 'game not foreground'),flush=True)
                    layered.hide() if layered else windows.hide(hwnd)
                    shown=False;last_box=None
                report=now;count=0;draw_times=[];stage_times=[];frame_gaps=[]
                time.sleep(.02);deadline=time.perf_counter();continue
            actor_visible,hud_visible=layers(state)
            current_scene=(state.get('session'),state.get('room'))
            if current_scene!=scene:
                renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None
                effects.reset();echoes=[];echo_at=None
                if scene is None or scene[0]!=current_scene[0]:hud.reset()
                scene=current_scene
            # Present the first completed frame before acknowledging ownership.
            # Waiting for Lua takeover here would deadlock a fresh renderer.
            visible=actor_visible or hud_visible
            # Keep the composition surface alive through CG/room changes. Clear
            # its pixels instead of repeatedly hiding/showing a topmost window.
            if layered:layered.begin(tuple(box[2:]))
            else:
                if box!=last_box:windows.place(hwnd,box,False);last_box=box
                w,h=glfw.get_framebuffer_size(window);ctx.screen.use();ctx.viewport=(0,0,w,h)
            ctx.clear(0,0,0,0)
            t=time.perf_counter();face=state['face'];yaw=math.pi/2-math.atan2(face[1],face[0])
            offset=args.offset if args.offset is not None else (55 if state.get('preview',True) else 0)
            state['actorHidden']=not actor_visible
            if actor_visible:
                effects.draw(state,offset)
                clock=state.get('clock',0);echoes=[e for e in echoes if 0<clock-e[0]<7]
                if state.get('dead'):echoes=[]
                for at,old,pose,angle in echoes:
                    renderer.draw(old['kind'],old['phase'],(old['position'][0]+offset,old['position'][1]),tuple(state['screen']),angle,0,old.get('ultimate',False),old.get('clip'),old.get('banner'),ghost=(pose,angle,.24*(1-(clock-at)/7)),body_scale=old.get('bodyScale',(1,1)),flying=old.get('flying',False))
                sockets=renderer.draw(state['kind'],state['phase'],(state['position'][0]+offset,state['position'][1]),tuple(state['screen']),yaw,dt,state.get('ultimate',False),state.get('clip'),state.get('banner',state.get('wings')),state.get('hurt',False),stasis=state.get('stasis',False),locomotion=state.get('locomotion'),body_scale=state.get('bodyScale',(1,1)),flying=state.get('flying',False))
                if state.get('dash') and math.floor(clock)!=echo_at:
                    echo_at=math.floor(clock);echoes.append((clock,dict(state),renderer.pose,renderer.yaw));echoes=echoes[-3:]
                effects.foreground(state,sockets);effects.screen(state);effects.pointer(state)
            else:
                effects.reset();echoes=[];echo_at=None
                renderer.kind=None;renderer.pose=None;renderer.previous=None;renderer.yaw=None
                effects.canvas.begin(state['screen'])
            if hud_visible and not state.get('preview',False):
                # Visual pointer only: gameplay, clicks and targeting stay in Isaac.
                cursor=windows.cursor(box,state['screen'])
                if cursor is not None and state.get('cursor') and not state['cursor'].get('controller'):state['cursor']=dict(state['cursor'],position=cursor)
                if actor_visible:mastery.draw(state,effects.canvas)
                hud.draw(state)
            rendered=time.perf_counter();draw_times.append((rendered-t)*1000)
            if layered:layered.present(box)
            else:glfw.swap_buffers(window)
            swapped=time.perf_counter();count+=1
            # Show only after presenting this room's fresh framebuffer, never the previous room.
            if visible and not shown:
                layered.show() if layered else windows.place(hwnd,box,True)
                shown=True
                print('Overlay visible; game client='+str(box),flush=True)
            native_cursor.update(game,box,shown and visible and hud_visible and not state.get('preview',False))
            # Intentional transition hiding is not a renderer failure: keep the handshake alive.
            status.write(state,True,visible=shown and actor_visible,hud_visible=shown and hud_visible)
            stage_times.append([(events_at-now)*1000,(read_at-events_at)*1000,(window_at-read_at)*1000,(t-window_at)*1000,(swapped-rendered)*1000])
            if now-report>=5:
                print(json.dumps({'render_fps':round(count/(now-report),1),'cpu_ms':round(float(np.mean(draw_times)),2),
                                  'frame_gap_p95_ms':round(float(np.percentile(frame_gaps,95)),2),'frame_gap_max_ms':round(max(frame_gaps),2),
                                  'events_read_lookup_clear_swap_ms':np.round(np.mean(stage_times,axis=0),2).tolist(),
                                  'packets':tail.count,'last_seq':state.get('seq'),'kind':state['kind'],'client':box[2:]}),flush=True)
                count=0;draw_times=[];stage_times=[];frame_gaps=[];report=now
            # Carry the small sleep overshoot into the next frame rather than
            # adding it to every frame (which previously settled near 58.6 FPS).
            deadline=max(deadline+1/60,time.perf_counter())
            time.sleep(max(0,deadline-time.perf_counter()))
    finally:
        if 'tail' in locals():tail.close()
        if 'owner' in locals() and owner:K.CloseHandle(owner)
        if native_cursor:native_cursor.restore()
        if mastery:mastery.close()
        if status:status.write(force=True)
        if layered:layered.close()
        glfw.destroy_window(window);glfw.terminate()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--log',default=str(Path.home()/'Documents/My Games/Binding of Isaac Repentance+/log.txt'))
    parser.add_argument('--seconds',type=float,default=float('inf'));parser.add_argument('--offset',type=float,default=None)
    parser.add_argument('--status-dir',default=str(ROOT/'build/status/samira_external_link'))
    parser.add_argument('--stop-file');parser.add_argument('--owner-pid',type=int)
    parser.add_argument('--presentation',choices=('glfw','layered'),default=None)
    try:run(parser.parse_args())
    except Exception:traceback.print_exc();sys.exit(1)
