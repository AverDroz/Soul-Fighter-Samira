"""Explicit per-pixel Win32 presentation, validated by the standalone sample.

UpdateLayeredWindow takes premultiplied BGRA. A bottom-up DIB accepts GL's
bottom-up readback directly. No color key or global-opacity window APIs used.
https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-updatelayeredwindow
"""
import ctypes
from ctypes import wintypes as w

class Header(ctypes.Structure):
    _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),
              ('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),
              ('xppm',w.LONG),('yppm',w.LONG),('used',w.DWORD),('important',w.DWORD)]
class Info(ctypes.Structure):
    _fields_=[('header',Header),('colors',w.DWORD*1)]
class Blend(ctypes.Structure):
    _fields_=[('operation',w.BYTE),('flags',w.BYTE),('alpha',w.BYTE),('format',w.BYTE)]

class LayeredSurface:
    def __init__(self,width,height):
        self.width=width;self.height=height;self.hwnd=None;self.dc=None;self.bitmap=None;self.old=None
        self.u=ctypes.WinDLL('user32',use_last_error=True);self.g=ctypes.WinDLL('gdi32',use_last_error=True)
        self.gl=ctypes.WinDLL('opengl32')
        signatures=[(self.u,'CreateWindowExW',[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p],w.HWND),
            (self.u,'UpdateLayeredWindow',[w.HWND,w.HDC,ctypes.POINTER(w.POINT),ctypes.POINTER(w.SIZE),w.HDC,ctypes.POINTER(w.POINT),w.DWORD,ctypes.POINTER(Blend),w.DWORD],w.BOOL),
            (self.u,'DestroyWindow',[w.HWND],w.BOOL),(self.u,'ShowWindow',[w.HWND,ctypes.c_int],w.BOOL),
            (self.u,'SetWindowPos',[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT],w.BOOL),
            (self.g,'CreateCompatibleDC',[w.HDC],w.HDC),
            (self.g,'CreateDIBSection',[w.HDC,ctypes.POINTER(Info),w.UINT,ctypes.POINTER(ctypes.c_void_p),w.HANDLE,w.DWORD],w.HBITMAP),
            (self.g,'SelectObject',[w.HDC,w.HANDLE],w.HANDLE),
            (self.g,'DeleteObject',[w.HANDLE],w.BOOL),(self.g,'DeleteDC',[w.HDC],w.BOOL),
            (self.gl,'glReadPixels',[ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p],None)]
        for dll,name,args,result in signatures:
            fn=getattr(dll,name);fn.argtypes=args;fn.restype=result
        try:
            # LAYERED | TRANSPARENT | NOACTIVATE | TOOLWINDOW | TOPMOST.
            self.hwnd=self.u.CreateWindowExW(0x080800a8,'STATIC','Samira layered renderer',0x80000000,0,0,width,height,None,None,None,None)
            if not self.hwnd:raise ctypes.WinError(ctypes.get_last_error())
            self.dc=self.g.CreateCompatibleDC(None)
            if not self.dc:raise ctypes.WinError(ctypes.get_last_error())
            self.resize(width,height)
        except Exception:self.close();raise

    def resize(self,width,height):
        if self.bitmap and (width,height)==(self.width,self.height):return
        if width<=0 or height<=0:raise ValueError('Invalid surface size')
        info=Info();info.header=Header(ctypes.sizeof(Header),width,height,1,32,0,width*height*4,0,0,0,0)
        bits=ctypes.c_void_p()
        bitmap=self.g.CreateDIBSection(self.dc,ctypes.byref(info),0,ctypes.byref(bits),None,0)
        if not bitmap:raise ctypes.WinError(ctypes.get_last_error())
        old=self.g.SelectObject(self.dc,bitmap)
        if not old:
            self.g.DeleteObject(bitmap);raise ctypes.WinError(ctypes.get_last_error())
        if self.bitmap:self.g.DeleteObject(self.bitmap)
        else:self.old=old
        self.width=width;self.height=height;self.bits=bits;self.bitmap=bitmap

    def present(self,fbo,x,y):
        if fbo.size!=(self.width,self.height):raise ValueError('Surface and framebuffer sizes differ')
        fbo.use()
        self.gl.glReadPixels(0,0,self.width,self.height,0x80e1,0x1401,self.bits) # BGRA / UNSIGNED_BYTE
        position=w.POINT(x,y);size=w.SIZE(self.width,self.height);origin=w.POINT(0,0);blend=Blend(0,0,255,1)
        if not self.u.UpdateLayeredWindow(self.hwnd,None,ctypes.byref(position),ctypes.byref(size),self.dc,ctypes.byref(origin),0,ctypes.byref(blend),2):
            raise ctypes.WinError(ctypes.get_last_error())

    def show(self):
        if not self.u.SetWindowPos(self.hwnd,w.HWND(-1),0,0,0,0,0x53): # NOSIZE|NOMOVE|NOACTIVATE|SHOWWINDOW
            raise ctypes.WinError(ctypes.get_last_error())
    def hide(self):self.u.ShowWindow(self.hwnd,0)
    def close(self):
        if self.hwnd:self.u.DestroyWindow(self.hwnd);self.hwnd=None
        if self.old:self.g.SelectObject(self.dc,self.old);self.old=None
        if self.bitmap:self.g.DeleteObject(self.bitmap);self.bitmap=None
        if self.dc:self.g.DeleteDC(self.dc);self.dc=None


class LayeredFrame:
    """Keep one native window; reallocate only its full-resolution buffers on resize."""
    def __init__(self,ctx):
        self.ctx=ctx;self.surface=None;self.fbo=None;self.texture=None;self.depth=None

    def begin(self,size):
        if not self.fbo or self.fbo.size!=size:
            self.release_buffers()
            self.texture=self.ctx.texture(size,4)
            self.depth=self.ctx.depth_renderbuffer(size)
            self.fbo=self.ctx.framebuffer([self.texture],self.depth)
            if self.surface:self.surface.resize(*size)
            else:self.surface=LayeredSurface(*size)
        self.fbo.use();self.ctx.viewport=(0,0,*size)

    def present(self,box):self.surface.present(self.fbo,*box[:2])
    def show(self):self.surface.show()
    def hide(self):
        if self.surface:self.surface.hide()
    def release_buffers(self):
        for name in ('fbo','depth','texture'):
            obj=getattr(self,name)
            if obj:obj.release();setattr(self,name,None)
    def close(self):
        if self.surface:self.surface.close();self.surface=None
        self.release_buffers()
