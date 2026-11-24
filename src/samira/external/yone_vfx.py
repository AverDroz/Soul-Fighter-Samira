"""Isaac-scale Yone effects. All positions and damage marks come from Lua."""

import math
from pathlib import Path

from samira_vfx import CombatCanvas, direction


RUBY = (.99, .18, .36)
ROSE = (1., .68, .79)
WIND = (.40, .85, .98)
IVORY = (.91, .98, 1.)
SHADE = (.10, .025, .09)
DURATIONS = {'attack': .22, 'attack2': .22, 'q': .27, 'q3': .47, 'w': .38, 'cricket': .25,
             'e': .36, 'e_return': .42, 'e_echo': .31, 'r': .57, 'shield': .31}
SOURCE_TEXTURES = ('q_slash', 'q3_wind', 'w_sweep', 'w_shield', 'e_flash', 'e_mark', 'e_timer', 'r_ground')


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


def countdown_pulse(remaining):
    return max(0., 1 - 4 * remaining) * (.5 - .5 * math.cos(10 * math.tau * remaining))


class YoneVFX:
    def __init__(self, ctx, assets=None):
        self.canvas = CombatCanvas(ctx)
        if assets is not None:
            for name in SOURCE_TEXTURES:
                path = Path(assets) / f'{name}.png'
                if path.is_file():
                    self.canvas.load(name, path)

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
        timing = state.get('yoneTiming')
        hit_phase = 23 / 40
        if isinstance(timing, dict) and number(timing.get('hit')) and number(timing.get('length')):
            if 0 < timing['hit'] <= timing['length']:
                hit_phase = timing['hit'] / timing['length']
        phase = state.get('phase')
        if state.get('kind') == 'r' and number(phase) and 0 <= phase < hit_phase:
            self.anticipation(phase / hit_phase)
        if self.payload.get('qReady') is True:
            self.gathering_storm()
        if self.payload.get('shield') is True:
            x, y = self.position
            self.shield((x, y - 12), 0, .51 + .09 * math.sin(self.clock * 6))
        self.canvas.flush()
        return self.spirit

    def gathering_storm(self):
        x, y = self.position
        remaining = self.payload.get('qRemaining', 1.)
        opacity = .82 if not number(remaining) else .69 + .16 * min(1., max(0., remaining))
        turn = self.clock * 4.1
        for height, radius, phase in ((4, 26, 0.), (17, 22, math.pi)):
            arc = ellipse((x, y - height), (radius, 8), turn + phase, turn + phase + 2.55, 15)
            self.ribbon(arc, 4.0, WIND, opacity)
            self.ribbon(arc, 1.1, IVORY, opacity)
        for i in range(4):
            lift = (self.clock * 1.25 + i * .25) % 1.
            theta = turn + i * math.pi / 2
            head = x + 24 * math.cos(theta), y - 4 - 25 * lift + 5 * math.sin(theta)
            tail = head[0] - math.sin(theta) * 3, head[1] + 5
            self.canvas.line(tail, head, 1.4, (*WIND, opacity * math.sin(math.pi * lift)))

    def finish(self):
        if not self.payload:
            return False
        if self.spirit:
            for mark in entries(self.spirit.get('marks'))[:32]:
                if isinstance(mark, dict) and point(mark.get('position')) and number(mark.get('amount')) and mark['amount'] > 0:
                    self.mark(mark['position'], mark.get('lethal') is True)
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

    def source(self, name, center, size, hue, opacity, face=(1, 0), *, add=False):
        if name in self.canvas.textures and min(size) > 0 and opacity > 0:
            self.canvas.sprite(name, center, size, (*hue, opacity), face, add=add)

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
        glow = .72 + .20 * math.sin(self.clock * 4.5)
        start, end = (x, y - 9), (self.position[0], self.position[1] - 8)
        if math.dist(start, end) >= 3:
            path = []
            for i in range(13):
                t = i / 12
                sag = math.sin(t * math.pi) * (4 + 2 * math.sin(t * 8 - self.clock * 6))
                path.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t + sag))
            self.ribbon(path, 7.0, SHADE, .82 * glow)
            self.ribbon(path, 4.2, RUBY, .95 * glow)
            self.ribbon(path, 1.5, IVORY, .88)
            for i in range(1, 5):
                p = int((i / 5 + self.clock * .62) % 1 * 12)
                self.canvas.line(path[p], path[p + 1], 1.3, (*ROSE, .74))
        if remaining > 0:
            center = (x, y + 2)
            pulse = countdown_pulse(remaining)
            self.source('e_timer', center, (34, 14), RUBY, .36 + .25 * pulse, add=True)
            self.canvas.lines(ellipse(center, (16, 6.4)), 1, (.55, .20, .30, .40))
            ring = ellipse(center, (16 * remaining, 6.4 * remaining))
            self.canvas.lines(ring, 3, (.30, .04, .09, .90))
            self.canvas.lines(ring, 1.5, (1., .62 - .30 * pulse, .75 - .28 * pulse, .95))

    @staticmethod
    def body_opacity(remaining):
        return (.42 + .49 * remaining) * (1 - .58 * countdown_pulse(remaining))

    def mark(self, position, lethal):
        x, y = position[0], position[1] - 24
        pulse = .83 + .13 * math.sin(self.clock * 8 + x)
        halo = [(x, y - 6.5), (x + 6, y), (x, y + 6.5), (x - 6, y)]
        self.canvas.polygon(halo, (*SHADE, .92))
        hue = (1., .84, .55) if lethal else RUBY
        if 'e_mark' in self.canvas.textures:
            self.source('e_mark', (x, y), (21, 21), hue, pulse)
        else:
            self.canvas.lines([*halo, halo[0]], 1.8, (*hue, pulse))
            self.canvas.line((x - 2, y + 2.5), (x + 2, y - 2.5), 1.8, (*ROSE, .95))
        if lethal:
            self.canvas.line((x - 4, y - 9), (x + 4, y - 9), 2, (*hue, .98))

    def shield(self, center, progress, opacity):
        radii = (17 + progress * 11, 19 + progress * 13)
        self.source('w_shield', center, tuple(2.5 * radius for radius in radii), ROSE, opacity, add=True)
        for start, end in ((-.96, .97), (2.17, 4.10)):
            arc = ellipse(center, radii, start, end, 12)
            self.ribbon(arc, 5.2, RUBY, opacity * .65)
            self.ribbon(arc, 1.2, ROSE, opacity * .9)
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
        contacts = [p for p in entries(event.get('contacts'))[:24] if point(p)]
        half_width = event.get('halfWidth')
        if not number(half_width) or not 0 < half_width <= 80:
            half_width = None
        if kind == 'shield':
            center = end[0], end[1] - 12
            self.shield(center, progress, alpha)
            self.sparks(center, IVORY, progress, alpha, seed, reach=19)
        elif kind == 'w':
            arc = event.get('arc')
            self.sweep(start, face, length, progress, alpha, arc)
        elif kind == 'q3':
            self.wind_cut(start, face, length, progress, alpha)
            for contact in contacts:
                along = max(0., min(1., ((contact[0]-start[0])*face[0] + (contact[1]-start[1])*face[1]) / max(length, .001)))
                if min(1., .14 + progress * 2.7) >= along:
                    self.sparks((contact[0], contact[1] - 9), IVORY, progress, alpha, seed, count=9)
                    self.canvas.flush()
        elif kind == 'r':
            self.ultimate(start, face, length, progress, alpha * (1 if contacts else .55), half_width or 17)
            for contact in contacts:
                self.contact_burst(contact, progress, alpha, seed, ultimate=True)
        elif kind == 'cricket':
            for tip in entries(event.get('rays'))[:4]:
                if point(tip) and math.dist(start, tip) > 1:
                    self.cricket_slash(start, tip, progress, alpha)
        elif kind in ('e', 'e_return'):
            self.spirit_dash(start, end, face, length, progress, alpha, kind == 'e_return')
            if kind == 'e_return':
                for contact in contacts:
                    self.contact_burst(contact, progress, alpha, seed)
        elif kind == 'e_echo':
            for contact in contacts:
                self.contact_burst(contact, progress, alpha, seed)
        else:
            self.strike(start, face, length, kind, progress, alpha, half_width)

    def contact_burst(self, position, progress, alpha, seed, ultimate=False):
        center = position[0], position[1] - 9
        flash = max(0., 1 - progress * 4)
        if flash:
            x, y = center
            self.canvas.polygon(((x - 7, y), (x, y - 12), (x + 7, y), (x, y + 12)),
                                (*(IVORY if ultimate else ROSE), alpha * flash))
        self.sparks(center, WIND if ultimate else RUBY, progress, alpha, seed, count=9, reach=13)
        self.sparks(center, RUBY, progress, alpha * .8, seed + 5, count=6, reach=9)
        self.canvas.flush()

    def anticipation(self, progress):
        x, y = self.position
        pulse = .45 + .45 * progress
        telegraph = self.payload.get('rTelegraph')
        if isinstance(telegraph, dict):
            corners = telegraph.get('corners')
            if isinstance(corners, (tuple, list)) and len(corners) == 4 and all(map(point, corners)):
                self.canvas.polygon(corners, self.telegraph_color(progress))
                if 'r_ground' in self.canvas.textures:
                    self.canvas.polygon(corners, (*ROSE, pulse), 'r_ground',
                                        [(0, 0), (1, 0), (1, 1), (0, 1)], add=True, brightness=True)
                else:
                    self.canvas.lines((*corners, corners[0]), 1.7, (*RUBY, pulse))
        self.ribbon(ellipse((x, y + 1), (12 + 7 * progress, 5 + 3 * progress)),
                    2.5, RUBY, pulse, tapered=False)
        for side, hue in ((-1, WIND), (1, RUBY)):
            a = offset((x, y - 12), self.facing, -10, side * (8 + progress * 6))
            b = offset((x, y - 12), self.facing, 12, side * (8 + progress * 6))
            self.ribbon([a, ((a[0]+b[0])/2, (a[1]+b[1])/2), b], 2, hue, pulse)

    @staticmethod
    def telegraph_color(progress):
        near = (*SHADE, .23 + .17 * progress)
        far = (*RUBY, .07 + .13 * progress)
        return (near, far, far, near)

    def sweep(self, start, face, length, progress, alpha, arc=None):
        # Ease along the swing and keep the arc on the attack side of the actor.
        radius = length * (.82 + .18 * min(1., progress * 4))
        origin = start[0], start[1] - 8
        valid_arc = isinstance(arc, (list, tuple)) and 3 <= len(arc) <= 33 and all(point(p) for p in arc)
        if valid_arc:
            boundary = [(p[0], p[1] - 8) for p in arc]
        else:
            boundary = [offset(origin, face, math.cos(a) * radius, math.sin(a) * radius)
                        for a in (-1.213 + 2.426 * i / 18 for i in range(19))]
        if 'w_sweep' in self.canvas.textures and length > 0:
            sector = [origin, *boundary]
            dx, dy = face
            uv = [(((px - origin[0]) * dx + (py - origin[1]) * dy) / length,
                   .5 + (-(px - origin[0]) * dy + (py - origin[1]) * dx) / (1.87 * length))
                  for px, py in sector]
            self.canvas.polygon(sector, (*RUBY, alpha * .76), 'w_sweep', uv, add=True)
        # Broad tapered crescent inside the actual cone, with a bright sector
        # that travels from one edge to the other during the fast swing.
        center = min(1., progress * 3.3) * (len(boundary) - 1)
        for i, (p, q) in enumerate(zip(boundary, boundary[1:])):
            inner_p = (origin[0] + .53 * (p[0] - origin[0]), origin[1] + .53 * (p[1] - origin[1]))
            inner_q = (origin[0] + .53 * (q[0] - origin[0]), origin[1] + .53 * (q[1] - origin[1]))
            glow = max(0., 1 - abs(i + .5 - center) / 3.5)
            revealed = max(0., min(1., center - i + .5))
            self.canvas.polygon((inner_p, inner_q, q, p),
                ((*RUBY, alpha * revealed * (.04 + .25 * glow)), (*RUBY, alpha * revealed * (.04 + .25 * glow)),
                 (*ROSE, alpha * revealed * (.10 + .55 * glow)), (*ROSE, alpha * revealed * (.10 + .55 * glow))))
        self.canvas.flush()
        for i, (p, q) in enumerate(zip(boundary, boundary[1:])):
            glow = max(0., 1 - abs(i + .5 - center) / 3.5)
            if glow:
                self.canvas.line(p, q, 2.4, (*ROSE, alpha * glow))
        leading = max(0, min(len(boundary) - 2, int(center)))
        self.canvas.line(origin, boundary[leading], 2.2, (*IVORY, alpha * .65))

    def wind_cut(self, start, face, length, progress, alpha):
        origin = start[0], start[1] - 7
        head = min(1., .14 + progress * 2.7)
        tail = max(0., head - .72)
        self.source('q3_wind', offset(origin, face, length * (tail + head) / 2, 0),
                    (length * (head - tail), 31), WIND, alpha * .85, face, add=True)
        for side, hue in ((-1, WIND), (1, IVORY)):
            points = []
            for i in range(17):
                t = tail + (head - tail) * i / 16
                twist = math.sin(t * math.tau * 1.35 - progress * 8)
                taper = math.sin(math.pi * i / 16)
                points.append(offset(origin, face, length * t, side * (2 + 11 * taper) * twist))
            self.ribbon(points, 4.0, hue, alpha * .85)
            self.ribbon(points, 1.2, IVORY, alpha * .9)
        tip = offset(origin, face, length * head, 0)
        blade = [offset(tip, face, -8 + 10 * math.cos(a), 13 * math.sin(a))
                 for a in (-1.45 + i * 2.9 / 14 for i in range(15))]
        self.ribbon(blade, 7, WIND, alpha * .8)
        self.ribbon(blade, 3.2, IVORY, alpha)
        for side in (-1, 1):
            streak = [offset(tip, face, -length * .25 * t, side * (4 + 9 * t)) for t in (0, .3, .7, 1)]
            self.ribbon(streak, 2.2, WIND, alpha * .7)

    def ultimate(self, start, face, length, progress, alpha, half_width):
        origin = start[0], start[1] - 7
        self.source('r_ground', offset(start, face, length * .5, 0),
                    (length, half_width * 2), RUBY, alpha * .88, face, add=True)
        core = [offset(origin, face, length * t, 0) for t in (0, .5, 1)]
        for side, hue in ((-1, WIND), (1, RUBY)):
            converge = [offset(origin, face, length * t, side * half_width * (1 - t)) for t in (0, .25, .5, .75, 1)]
            self.ribbon(converge, 4.2, hue, alpha * .85)
        for side, hue in ((-1, WIND), (1, RUBY)):
            edge = [offset(origin, face, length * t, side * half_width * .85) for t in (0, .25, .5, .75, 1)]
            self.ribbon(edge, 3.3, hue, alpha * .9)
        self.ribbon(core, 10 + 9 * progress, WIND, alpha * .65)
        self.ribbon(core, 4.2, IVORY, alpha * .98)
        for side in (-1, 1):
            span = half_width * (.6 + .4 * progress)
            blade = [offset(origin, face, length * t, side * span * (2 * t - 1))
                     for t in (0, .28, .58, .82, 1)]
            self.ribbon(blade, 3.9, ROSE if side == 1 else WIND, alpha * .82)

    def cricket_slash(self, start, tip, progress, alpha):
        dx, dy = tip[0] - start[0], tip[1] - start[1]
        reveal = min(1., .45 + 4 * progress)
        origin = start[0], start[1] - 7
        slash = [(origin[0] + dx * reveal * t - dy * .10 * math.sin(math.pi * t),
                  origin[1] + dy * reveal * t + dx * .10 * math.sin(math.pi * t))
                 for t in (0., .25, .5, .75, 1.)]
        self.ribbon(slash, 4, RUBY, alpha * .8)
        self.ribbon(slash, 1.2, ROSE, alpha)

    def spirit_dash(self, start, end, face, length, progress, alpha, returning):
        origin = start[0], start[1] - 7
        offset_start = progress * .76 if returning else 0
        for side in (-1, 1):
            points = [offset(origin, face, t * length,
                             side * math.sin(math.pi * t) * (5 + 8 * progress))
                      for t in (offset_start + (1 - offset_start) * i / 10 for i in range(11))]
            self.ribbon(points, 4.3, RUBY, alpha * .81)
        head = min(1., progress * 3 + .12)
        tip = offset(origin, face, length * head, 0)
        self.source('e_flash', tip, (29 if returning else 23, 17), ROSE if returning else RUBY,
                    alpha * .78, face, add=True)
        for side in (-1, 1):
            streak = [offset(tip, face, -length * .25 * t, side * (2 + 6 * t)) for t in (0, .3, .7, 1)]
            self.ribbon(streak, 3, ROSE if returning else RUBY, alpha * .8)
        x, y = end
        self.ribbon(ellipse((x, y), (6 + 11 * progress, 3 + 6 * progress)), 2, ROSE, alpha, tapered=False)

    def strike(self, start, face, length, kind, progress, alpha, half_width):
        origin = start[0], start[1] - 8
        if kind == 'q':
            self.source('q_slash', offset(origin, face, length * .5, 0),
                        (length, 16), WIND, alpha, face, add=True)
            points = [offset(origin, face, length * t, 0) for t in (0, .25, .5, .75, 1)]
            self.ribbon(points, 3.6, WIND, alpha * .8)
            self.ribbon(points, 1.2, IVORY, alpha)
            return
        side = -1 if kind == 'attack2' else 1
        width = (half_width or 16) * .75
        points = [offset(origin, face, length * t, side * width * math.sin(t * 2.8 + progress))
                  for t in (0, .2, .43, .65, .81, 1)]
        self.ribbon(points, width * .6, RUBY if kind == 'attack2' else WIND, alpha * .86)
        self.ribbon(points, 1.3, ROSE if kind == 'attack2' else IVORY, alpha)
