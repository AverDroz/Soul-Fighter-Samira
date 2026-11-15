"""Draw the stock Windows arrow when the foreground game hides its cursor."""

import ctypes
from ctypes import wintypes as w
from io import BytesIO
import os
from pathlib import Path
from struct import pack, unpack_from

import moderngl
import numpy as np
from PIL import Image

from canvas import FS, VS
from native_cursor import CursorInfo


def stock_arrows():
    path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Cursors/aero_arrow.cur"
    data = path.read_bytes()
    _, kind, count = unpack_from("<HHH", data)
    if kind != 2 or count == 0:
        raise ValueError(f"Invalid Windows cursor at {path}")
    for index in range(count):
        width, height, colors, _, hot_x, hot_y, length, offset = unpack_from(
            "<BBBBHHII", data, 6 + 16 * index
        )
        # CUR and ICO have the same DIB payload. Decode its alpha with Pillow
        # while retaining the hotspot from the separate CUR directory entry.
        header = pack("<HHHBBBBHHII", 0, 1, 1, width, height, colors, 0, 1, 32, length, 22)
        with Image.open(BytesIO(header + data[offset:offset + length])) as cursor:
            yield cursor.convert("RGBA"), (hot_x, hot_y)


def fallback_position(box, point, flags, game_cursor=False):
    x, y, width, height = box
    px, py = point
    if game_cursor or flags & 0x03:  # CURSOR_SHOWING or CURSOR_SUPPRESSED (touch)
        return None
    if x <= px < x + width and y <= py < y + height:
        return px - x, py - y
    return None


class SystemPointer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        for name, args, result in (
            ("GetCursorInfo", [ctypes.POINTER(CursorInfo)], w.BOOL),
            ("GetPhysicalCursorPos", [ctypes.POINTER(w.POINT)], w.BOOL),
            ("GetDpiForWindow", [w.HWND], w.UINT),
        ):
            func = getattr(self.user32, name)
            func.argtypes = args
            func.restype = result

        self.program = ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.buffer = ctx.buffer(reserve=6 * 8 * 4, dynamic=True)
        self.vao = ctx.vertex_array(self.program, [(self.buffer, "2f 2f 4f", "position", "uv", "tint")])
        self.arrows = {}
        for arrow, hotspot in stock_arrows():
            texture = ctx.texture(arrow.size, 4, arrow.tobytes())
            texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            texture.repeat_x = texture.repeat_y = False
            self.arrows[arrow.width] = (texture, hotspot)

    def draw(self, hwnd, box, game_cursor=False):
        if game_cursor:
            return
        info = CursorInfo()
        info.cbSize = ctypes.sizeof(info)
        point = w.POINT()
        if not self.user32.GetCursorInfo(ctypes.byref(info)):
            return
        # SetCursor(NULL) can remove the visible handle independently of
        # the visibility counter. Preserve touch suppression either way.
        flags = info.flags if info.hCursor else info.flags & ~1
        if flags & 0x03 or not self.user32.GetPhysicalCursorPos(ctypes.byref(point)):
            return
        origin = fallback_position(box, (point.x, point.y), flags)
        if origin is not None:
            self.paint(origin, box[2:], self.user32.GetDpiForWindow(hwnd) or 96)

    def paint(self, origin, size, dpi):
        desired = 32 * dpi / 96
        native = min(self.arrows, key=lambda width: abs(width - desired))
        texture, (hot_x, hot_y) = self.arrows[native]
        scale = desired / native
        x, y = origin[0] - hot_x * scale, origin[1] - hot_y * scale
        dx, dy = texture.width * scale, texture.height * scale
        points = ((x, y, 0, 0), (x + dx, y, 1, 0), (x + dx, y + dy, 1, 1),
                  (x, y, 0, 0), (x + dx, y + dy, 1, 1), (x, y + dy, 0, 1))
        vertices = np.array([(*point, 1, 1, 1, 1) for point in points], dtype="f4")
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA,
                               moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        self.program["viewport"].value = size
        self.program["image"].value = 0
        self.program["brightnessAlpha"].value = 0
        self.buffer.write(vertices.tobytes())
        texture.use(0)
        self.vao.render(vertices=6)
