"""Isaac-scale Yone effects. All positions and damage marks come from Lua."""

import math

from samira_vfx import CombatCanvas, direction


RUBY = (.99, .18, .36)
ROSE = (1., .68, .79)
WIND = (.40, .85, .98)
IVORY = (.91, .98, 1.)
SHADE = (.10, .025, .09)
DURATIONS = {'attack': .22, 'attack2': .22, 'q': .27, 'q3': .47, 'w': .38,
             'e': .36, 'e_return': .42, 'r': .57, 'shield': .31}


def number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def point(value):
    return isinstance(value, (tuple, list)) and len(value) == 2 and all(map(number, value))


def entries(value):
    return value if isinstance(value, (tuple, list)) else ()


def ellipse(center, radii, start=0, end=math.tau, steps=24):
    x, y = center
    rx, ry = radii
    return [(x + rx * math.cos(a), y + ry * math.sin(a))
            for a in (start + (end - start) * j / steps for j in range(steps + 1))]


def offset(origin, face, along, across):
    x, y = origin
    dx, dy = face
    return x + dx * along - dy * across, y + dy * along + dx * across


class YoneVFX:
    def __init__(self, ctx):
        self.canvas = CombatCanvas(ctx)

    def close(self):
        canvas = self.canvas
        for resource in (*canvas.textures.values(), canvas.vao, canvas.buffer, canvas.program):
            resource.release()

    def begin(self, state):
        payload = state.get('yone')
        self.payload = payload if isinstance(payload, dict) else {}
        self.spirit = None
        if not self.payload:
            return None
        self.canvas.begin(state['screen'])
        self.position = state['position']
        self.facing = direction(state['face'])
        clock = state.get('clock', 0)
        self.clock = clock / 30
        self.delay = max(0., state.get('packetClock', clock) - clock) / 30
        spirit = self.payload.get('spirit')
        if isinstance(spirit, dict) and point(spirit.get('anchor')) and point(spirit.get('face')):
            remaining = spirit.get('remaining')
            if number(remaining) and 0 <= remaining <= 1:
                self.spirit = spirit
                self.tether(spirit)
        if state.get('kind') == 'r' and number(state.get('phase')) and 0 <= state['phase'] < 23 / 40:
            self.anticipation(state['phase'] / (23 / 40))
        if self.payload.get('shield') is True:
            x, y = self.position
            self.shield((x, y - 12), 0, .51 + .09 * math.sin(self.clock * 6))
        self.canvas.flush()
        return self.spirit

    def finish(self):
        if not self.payload:
            return False
        if self.spirit:
            for mark in entries(self.spirit.get('marks'))[:32]:
                if isinstance(mark, dict) and point(mark.get('position')) and number(mark.get('amount')) and mark['amount'] > 0:
                    self.mark(mark['position'], mark['amount'])
        for event in entries(self.payload.get('fx'))[:24]:
            if isinstance(event, dict):
                self.event(event)
        self.canvas.flush()
        return self.canvas.draw_calls > 0

    def ribbon(self, points, width, hue, opacity, *, tapered=True):
        """Build an antialiased centerline with graduated edges and pointed tips."""
        sections = []
        last = len(points) - 1
        for i, center in enumerate(points):
            a, b = points[max(0, i - 1)], points[min(last, i + 1)]
            face = direction((b[0] - a[0], b[1] - a[1]))
            t = i / last
            spread = width * (.12 + .88 * math.sin(math.pi * t)) if tapered else width
            sections.append([offset(center, face, 0, spread * v) for v in (-1, -.22, .22, 1)])
        clear, rich = (*hue, 0), (*hue, opacity)
        colors = (clear, rich, rich, clear)
        for near, far in zip(sections, sections[1:]):
            for i in range(3):
                self.canvas.polygon((near[i], far[i], far[i + 1], near[i + 1]),
                                    (colors[i], colors[i], colors[i + 1], colors[i + 1]))
        # Bound each geometry batch to the shared canvas buffer capacity.
        self.canvas.flush()

    def sparks(self, center, hue, progress, opacity, seed, count=7, reach=12):
        for i in range(count):
            theta = (i / count + seed * .3819) * math.tau
            face = math.cos(theta), math.sin(theta)
            distance = (reach * (.27 + progress)) * (.60 + .40 * abs(math.sin(i * 7.1 + seed)))
            tip = offset(center, face, distance, 0)
            tail = offset(tip, face, -3.3 * (1.12 - progress), 0)
            self.canvas.line(tail, tip, .9 + .7 * (i % 2), (*hue, opacity))

    def tether(self, spirit):
        x, y = spirit['anchor']
        remaining = spirit['remaining']
        pulse = (.72 + .20 * math.sin(self.clock * (8.5 if remaining < .25 else 4.5)))
        outer = ellipse((x, y + 1), (13, 5.4))
        self.ribbon(outer, 4.0, RUBY, .9 * pulse, tapered=False)
        self.ribbon(ellipse((x, y - 13), (11, 16)), 2.3, RUBY, .55 * pulse, tapered=False)
        self.canvas.lines(ellipse((x, y + 1), (9.7, 3.6), end=remaining * math.tau), 1.1, (*ROSE, .9))
        start, end = (x, y - 9), (self.position[0], self.position[1] - 8)
        if math.dist(start, end) >= 3:
            path = []
            for i in range(13):
                t = i / 12
                sag = math.sin(t * math.pi) * (4 + 2 * math.sin(t * 8 - self.clock * 6))
                path.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t + sag))
            self.ribbon(path, 7.0, SHADE, .82 * pulse)
            self.ribbon(path, 4.2, RUBY, .95 * pulse)
            self.ribbon(path, 1.5, IVORY, .88)
            for i in range(1, 5):
                p = int((i / 5 + self.clock * .62) % 1 * 12)
                self.canvas.line(path[p], path[p + 1], 1.3, (*ROSE, .74))

    def mark(self, position, amount):
        x, y = position[0], position[1] - 24
        pulse = .83 + .13 * math.sin(self.clock * 8 + x)
        halo = [(x, y - 6.5), (x + 6, y), (x, y + 6.5), (x - 6, y)]
        self.canvas.polygon(halo, (*SHADE, .92))
        self.canvas.lines([*halo, halo[0]], 1.45, (*RUBY, pulse))
        self.canvas.line((x - 2, y + 2.5), (x + 2, y - 2.5), 1.8, (*ROSE, .95))
        label = f'{max(.1, amount):.1f}'.removesuffix('.0') if amount < 100 else f'{min(amount, 9999):.0f}'
        self.canvas.text(label, x + .5, y - 15.5, 8, (*SHADE, .98), center=True)
        self.canvas.text(label, x, y - 16, 8, (*ROSE, .98), center=True)

    def shield(self, center, progress, opacity):
        radii = (17 + progress * 11, 19 + progress * 13)
        for start, end in ((-.96, .97), (2.17, 4.10)):
            arc = ellipse(center, radii, start, end, 12)
            self.ribbon(arc, 3.3, WIND, opacity)
            self.ribbon(arc, .85, IVORY, opacity)
        x, y = center
        h = radii[1]
        self.canvas.lines([(x - 4, y - h + 2), (x, y - h - 1), (x + 4, y - h + 2)], 1.2, (*IVORY, opacity))

    def event(self, event):
        kind, age = event.get('kind'), event.get('age')
        duration = DURATIONS.get(kind) if isinstance(kind, str) else None
        start, end = event.get('origin'), event.get('target')
        if duration is None or not point(start) or not point(end) or not number(age):
            return
        age -= self.delay
        if not 0 <= age < duration:
            return
        progress = age / duration
        alpha = (1 - progress) ** 1.4
        seed = event.get('id', 0)
        seed = seed % 97 if number(seed) else 0
        face = direction((end[0] - start[0], end[1] - start[1]), self.facing)
        length = math.dist(start, end)
        if kind == 'shield':
            center = end[0], end[1] - 12
            self.shield(center, progress, alpha)
            self.sparks(center, IVORY, progress, alpha, seed, reach=19)
        elif kind == 'w':
            arc = event.get('arc')
            self.sweep(start, face, length, progress, alpha, arc)
            self.sparks((end[0], end[1] - 8), ROSE, progress, alpha * .68, seed)
        elif kind == 'q3':
            self.wind_cut(start, face, length, progress, alpha)
            self.sparks((end[0], end[1] - 9), IVORY, progress, alpha, seed, count=9)
        elif kind == 'r':
            self.ultimate(start, face, length, progress, alpha)
            self.sparks((end[0], end[1] - 7), ROSE, progress, alpha, seed, count=12, reach=18)
        elif kind in ('e', 'e_return'):
            self.spirit_dash(start, end, face, length, progress, alpha, kind == 'e_return')
            self.sparks((end[0], end[1] - 6), ROSE, progress, alpha, seed, reach=15)
        else:
            self.strike(start, face, length, kind, progress, alpha)

    def anticipation(self, progress):
        x, y = self.position
        pulse = .45 + .45 * progress
        self.ribbon(ellipse((x, y + 1), (12 + 7 * progress, 5 + 3 * progress)),
                    2.5, RUBY, pulse, tapered=False)
        for side, hue in ((-1, WIND), (1, RUBY)):
            a = offset((x, y - 12), self.facing, -10, side * (8 + progress * 6))
            b = offset((x, y - 12), self.facing, 12, side * (8 + progress * 6))
            self.ribbon([a, ((a[0]+b[0])/2, (a[1]+b[1])/2), b], 2, hue, pulse)

    def sweep(self, start, face, length, progress, alpha, arc=None):
        # Ease along the swing and keep the arc on the attack side of the actor.
        radius = length * (.82 + .18 * min(1., progress * 4))
        origin = start[0], start[1] - 8
        valid_arc = isinstance(arc, (list, tuple)) and 3 <= len(arc) <= 33 and all(point(p) for p in arc)
        for inset, width, hue, fade in ((.82, 9.5, RUBY, .72), (1., 5.2, ROSE, .96), (.96, 1.6, IVORY, .90)):
            if valid_arc:
                points = [(start[0] + (p[0] - start[0]) * inset,
                           start[1] + (p[1] - start[1]) * inset - 8) for p in arc]
            else:
                points = [offset(origin, face, math.cos(a) * radius * inset, math.sin(a) * radius * inset)
                          for a in (-1.213 + 2.426 * i / 18 for i in range(19))]
            self.ribbon(points, width, hue, alpha * fade)

    def wind_cut(self, start, face, length, progress, alpha):
        origin = start[0], start[1] - 7
        for side in (-1, 1):
            width = 9 + progress * 8
            points = [offset(origin, face, length * t, side * math.sin(math.pi * t) * width)
                      for t in (i / 10 for i in range(11))]
            self.ribbon(points, 4.7, WIND, alpha * .76)
            self.ribbon(points, 1.2, IVORY, alpha * .83)
        tip = offset(origin, face, length * min(1, .18 + progress * 2.7), 0)
        gust = [offset(tip, face, -7 + 8 * math.cos(a), 12 * math.sin(a))
                for a in (-1.45 + i * 2.9 / 14 for i in range(15))]
        self.ribbon(gust, 5, RUBY, alpha * .75)
        self.ribbon(gust, 2.5, IVORY, alpha * .95)
        curl = [offset(tip, face, -9 + 10 * math.cos(a), 7 * math.sin(a))
                for a in (-2.1 + i * .28 for i in range(16))]
        self.ribbon(curl, 3.7, WIND, alpha)

    def ultimate(self, start, face, length, progress, alpha):
        origin = start[0], start[1] - 7
        core = [offset(origin, face, length * t, 0) for t in (0, .5, 1)]
        for side, hue in ((-1, WIND), (1, RUBY)):
            edge = [offset(origin, face, length * t, side * 14) for t in (0, .25, .5, .75, 1)]
            self.ribbon(edge, 3.3, hue, alpha * .9)
        for t in (.25, .78):
            center = offset(origin, face, length * t, 0)
            self.ribbon(ellipse(center, (8 + 8 * progress, 5 + 5 * progress)),
                        2.4, ROSE, alpha, tapered=False)
        self.ribbon(core, 10 + 9 * progress, RUBY, alpha * .62)
        self.ribbon(core, 4.2, IVORY, alpha * .94)
        for side in (-1, 1):
            span = 10 + 11 * progress
            blade = [offset(origin, face, length * t, side * span * (2 * t - 1))
                     for t in (0, .28, .58, .82, 1)]
            self.ribbon(blade, 3.9, ROSE if side == 1 else WIND, alpha * .82)

    def spirit_dash(self, start, end, face, length, progress, alpha, returning):
        origin = start[0], start[1] - 7
        offset_start = progress * .76 if returning else 0
        for side in (-1, 1):
            points = [offset(origin, face, t * length,
                             side * math.sin(math.pi * t) * (5 + 8 * progress))
                      for t in (offset_start + (1 - offset_start) * i / 10 for i in range(11))]
            self.ribbon(points, 4.3, RUBY, alpha * .81)
        x, y = end
        self.ribbon(ellipse((x, y), (6 + 11 * progress, 3 + 6 * progress)), 2, ROSE, alpha, tapered=False)

    def strike(self, start, face, length, kind, progress, alpha):
        origin = start[0], start[1] - 8
        if kind == 'q':
            points = [offset(origin, face, length * t, 0) for t in (0, .25, .5, .75, 1)]
            self.ribbon(points, 3.6, WIND, alpha * .8)
            self.ribbon(points, 1.2, IVORY, alpha)
            return
        side = -1 if kind == 'attack2' else 1
        width = 4 if kind == 'q' else 12
        points = [offset(origin, face, length * t, side * width * math.sin(t * 2.8 + progress))
                  for t in (0, .2, .43, .65, .81, 1)]
        self.ribbon(points, width * .6, RUBY if kind == 'attack2' else WIND, alpha * .86)
        self.ribbon(points, 1.3, ROSE if kind == 'attack2' else IVORY, alpha)
