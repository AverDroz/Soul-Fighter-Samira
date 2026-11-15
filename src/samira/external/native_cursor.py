"""Hide only the foreground game's pointer; balance every visibility decrement.

No cursor replacement, confinement, input blocking or system settings changes.
The input queues are attached once for the active interval, never once per frame.
"""
import ctypes
from ctypes import wintypes as w


class CursorInfo(ctypes.Structure):
    _fields_=[('cbSize',w.DWORD),('flags',w.DWORD),('hCursor',w.HANDLE),('ptScreenPos',w.POINT)]


class NativeCursor:
    def __init__(self):
        self.u=ctypes.WinDLL('user32',use_last_error=True)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentThreadId.restype=w.DWORD
        self.thread=kernel.GetCurrentThreadId();self.owner=None;self.hidden=0
        for name,args,result in (
            ('GetWindowThreadProcessId',[w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD),
            ('AttachThreadInput',[w.DWORD,w.DWORD,w.BOOL],w.BOOL),
            ('ShowCursor',[w.BOOL],ctypes.c_int),
            ('GetCursorInfo',[ctypes.POINTER(CursorInfo)],w.BOOL)):
            fn=getattr(self.u,name);fn.argtypes=args;fn.restype=result

    def restore(self):
        if self.owner is None:return
        # Undo exactly our changes, even if the game also changed its counter.
        for _ in range(self.hidden):self.u.ShowCursor(True)
        self.hidden=0
        self.u.AttachThreadInput(self.thread,self.owner,False);self.owner=None

    def update(self,hwnd,box,active):
        info=CursorInfo();info.cbSize=ctypes.sizeof(info)
        valid=bool(self.u.GetCursorInfo(ctypes.byref(info)))
        inside=bool(valid and box and box[0]<=info.ptScreenPos.x<box[0]+box[2]
                    and box[1]<=info.ptScreenPos.y<box[1]+box[3])
        owner=self.u.GetWindowThreadProcessId(hwnd,None) if hwnd and active and inside else 0
        if self.owner!=owner:self.restore()
        if not owner:return
        if self.owner is None:
            if owner==self.thread or not self.u.AttachThreadInput(self.thread,owner,True):return
            self.owner=owner
        if info.flags&1:
            # Bounded work if another program is continuously changing the count.
            for _ in range(8):
                count=self.u.ShowCursor(False);self.hidden+=1
                if count<0:break
