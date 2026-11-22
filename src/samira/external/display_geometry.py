"""Map a fresh Isaac logical viewport to the physical Win32 client."""
import math


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def viewport_box(display, screen, client):
    x, y, width, height = client
    rect = display.get("viewport")
    x_slop, y_slop = max(6, width / 200), max(6, height / 200)
    if rect is None:
        # Some builds cannot sample the projection. The full client is safe
        # only when it has the same aspect ratio as the logical render area.
        sw, sh = screen
        if sw > 0 and sh > 0 and abs(width - height * sw / sh) <= x_slop:
            return client
        return None
    if not isinstance(rect, (list, tuple)) or len(rect) != 4 or not all(map(_number, rect)):
        return None
    left, top, render_width, render_height = rect
    right, bottom = left + render_width, top + render_height
    if (render_width <= 0 or render_height <= 0
            or left < -x_slop or top < -y_slop or right > width + x_slop or bottom > height + y_slop
            or abs(left + right - width) > x_slop or abs(top + bottom - height) > y_slop):
        # A valid viewport inside an earlier, smaller client is stale after
        # fullscreen/resize. Isaac's render area is centered in its client.
        return None
    l, t = max(0, round(left)), max(0, round(top))
    r, b = min(width, round(right)), min(height, round(bottom))
    return (x + l, y + t, r - l, b - t) if r > l and b > t else None


class DisplayGate:
    def __init__(self):
        self.key = None
        self.cutover = None
        self.reason = None

    def choose(self, hwnd, client, state):
        if not hwnd or not client or not state or min(client[2:]) <= 0:
            self.key = self.cutover = None
            self.reason = "waiting for the active Isaac window and a game snapshot"
            return None
        display = state.get("display")
        if display is None:
            self.reason = None
            return client
        if (not isinstance(display, dict) or type(display.get("id")) is not int
                or display.get("mode") not in ("windowed", "borderless", "exclusive")):
            self.reason = "invalid display snapshot"
            return None
        if display.get("mode") == "exclusive":
            self.key = self.cutover = None
            self.reason = "exclusive fullscreen; waiting for borderless composition"
            return None

        key = (hwnd, *client[2:], display["id"], display.get("mode"))
        frame = (state.get("session"), state.get("room"), state.get("seq", 0))
        if key != self.key:
            self.key, self.cutover = key, frame
        if self.cutover and frame[:2] == self.cutover[:2] and frame[2] <= self.cutover[2]:
            self.reason = "waiting for a newer snapshot after a display change"
            return None
        result = viewport_box(display, state["screen"], client)
        if result is None:
            self.reason = "waiting for an Isaac viewport that matches the current client"
            return None
        self.cutover = self.reason = None
        return result
