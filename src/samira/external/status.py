"""Small renderer acknowledgement in its own folder, never in gameplay save data."""
import json,os,time
from pathlib import Path

class Status:
    def __init__(self,folder):
        self.folder=Path(folder);self.last=0;self.ready=None;self.session=None;self.visible=False;self.room=None;self.hud_visible=False
        self.folder.mkdir(parents=True,exist_ok=True)
    def hidden(self,state):
        # Pause, room loading and loss of foreground intentionally hide the window.
        # Keep an already-rendered session ready without acknowledging a new one.
        return self.write(state,bool(state and self.ready and state.get('session')==self.session),visible=False)
    def write(self,state=None,ready=False,force=False,visible=True,hud_visible=None):
        now=time.perf_counter();session=(state or {}).get('session')
        room=(state or {}).get('room');visible=bool(ready and visible)
        hud_visible=bool(ready and (visible if hud_visible is None else hud_visible))
        if not force and ready==self.ready and session==self.session and visible==self.visible and hud_visible==self.hud_visible and room==self.room and now-self.last<.2:return
        payload={'version':1,'session':session,'time':(state or {}).get('heartbeatTime',(state or {}).get('time',0)),'ready':bool(ready),
                 'capabilities':{'combat':1,'mastery':1,'hud':1,'shop':1} if ready else {},'visible':visible,'hudVisible':hud_visible,'room':room}
        data=json.dumps(payload,separators=(',',':'))
        try:
            for slot in (1,2,3):
                target=self.folder/f'save{slot}.dat';temporary=self.folder/f'save{slot}.tmp'
                temporary.write_text(data,encoding='utf-8')
                os.replace(temporary,target)
        except OSError:
            # A brief reader/file-sharing lock should cause retry, not crash the renderer.
            return False
        self.last=now;self.ready=ready;self.session=session;self.visible=visible;self.hud_visible=hud_visible;self.room=room
        return True
