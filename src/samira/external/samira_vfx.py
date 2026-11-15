"""Render Soul Fighter visuals from the Lua combat snapshot."""

import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from canvas import Canvas, FS, VS
from client_vfx import ClientParticles


PROJECTILES = {"attack": "BA_Projectile", "q": "Q_Projectile"}
IMPACTS = {
    "attack": "BA_Tar", "q": "Q_Tar", "qmelee": "Q_Melee_Tar",
    "w": "W_tar", "e": "E_dash_hit", "r": "R_Tar",
    "melee": "BA_Melee_One_Tar", "eq": "E_Q_Buffer_Target",
}
# Calibrated against the source mesh extents and the visible leading edge
# of each texture. The hit radius itself comes from Lua, in logical pixels.
CLIENT_RADIUS = {
    "W_Zone": 430, "W_CircleCut": 400, "R_Range_Indicator_Self": 345,
    "Q_Melee_AOE": 535, "BA_Melee_One": 663,
}


def direction(vector, fallback=(1, 0)):
    x, y = vector
    length = math.hypot(x, y)
    return (x / length, y / length) if length else tuple(fallback)


def towards(start, end, fallback):
    return direction((end[0] - start[0], end[1] - start[1]), fallback)


def draw_ready_glow(canvas, width, height, clock):
    depth = min(14 + 2 * math.sin(clock * 3.4), min(width, height) / 4)
    pulse = .218 + .032 * math.sin(clock * 4.9)
    rings = []
    for inset in (0, depth * .38, depth):
        rings.append(((inset, inset), (width - inset, inset),
                      (width - inset, height - inset), (inset, height - inset)))

    def at(ring, side, portion):
        start, end = ring[side], ring[(side + 1) % 4]
        return tuple(a + (b - a) * portion for a, b in zip(start, end))

    def colors(position, side):
        flicker = math.sin(clock * 5.2 + side * 1.65 + position * 15)
        warmth = .5 + .5 * math.sin(clock * 3.1 - side * .9 + position * 21 + .7 * flicker)
        glow = (1, .18 + .24 * warmth, .045 + .075 * warmth)
        alpha = pulse * (.90 + .10 * flicker)
        return ((*glow, alpha), (*glow, alpha * .43), (*glow, 0))

    # Miter the sides so the four edge gradients never stack at the corners.
    segments = 12
    for side in range(4):
        previous = colors(0, side)
        for segment in range(segments):
            start, end = segment / segments, (segment + 1) / segments
            current = colors(end, side)
            for level, (outer, inner) in enumerate(zip(rings, rings[1:])):
                canvas.polygon(
                    (at(outer, side, start), at(outer, side, end),
                     at(inner, side, end), at(inner, side, start)),
                    (previous[level], current[level], current[level + 1], previous[level + 1]),
                )
            previous = current


class CombatCanvas(Canvas):
    """The shared quad batch with the small ASCII font this HUD needs."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.program = ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.buffer = ctx.buffer(reserve=2**16, dynamic=True)
        self.vao = ctx.vertex_array(self.program, [(self.buffer, "2f 2f 4f", "position", "uv", "tint")])
        self.textures = {}
        self.vertices = []
        self.batch = None
        self.draw_calls = 0
        self.add("white", Image.new("RGBA", (1, 1), "white"))
        chars = "QWERDCBAS-.0123456789?"
        font = ImageFont.load_default(size=48)
        self.font_size = (64 * len(chars), 80)
        atlas = Image.new("RGBA", self.font_size)
        painter = ImageDraw.Draw(atlas)
        self.glyphs = {}
        for i, char in enumerate(chars):
            x = i * 64
            painter.text((x + 3, 3), char, font=font, fill="white", anchor="lt")
            self.glyphs[char] = (x, 0, font.getlength(char))
        self.add("font", atlas)

    def sprite(self, name, point, size, color=(1, 1, 1, 1), face=(1, 0), add=False):
        x, y = point
        dx, dy = face
        half_width, half_height = size[0] / 2, size[1] / 2
        corners = [
            (x + u * dx - v * dy, y + u * dy + v * dx)
            for u, v in ((-half_width, -half_height), (half_width, -half_height),
                         (half_width, half_height), (-half_width, half_height))
        ]
        self.polygon(corners, color, name, [(0, 0), (1, 0), (1, 1), (0, 1)],
                     add=add, brightness=add)


class SoulFighterVFX:
    """Translate logical screen positions into source particle playback."""

    def __init__(self, ctx, root):
        root = Path(root)
        self.client = ClientParticles(ctx, root=root, bundle="soul-fighter")
        self.canvas = CombatCanvas(ctx)
        assets = {Path(name).stem: info for name, info in self.client.manifest.items()}
        sources = {
            "attack": "samira_skin30_ba_dot",
            "q": "samira_skin30_q_missile_head_2",
            "attack-trail": "samira_skin30_ba_trail_flame",
            "q-trail": "samira_skin30_q_trail_sharp",
            "muzzle": "samira_skin30_q_muzzle_flash",
        }
        for role, asset in sources.items():
            if asset in assets:
                self.canvas.load(role, root / assets[asset]["file"])
        self.can_projectiles = all(
            kind in self.canvas.textures and name in self.client.systems
            for kind, name in PROJECTILES.items()
        )
        for key in "qwer":
            icon = root / "icons" / f"{key}.png"
            if icon.is_file():
                self.canvas.load("icon-" + key, icon)
        target_icon = root / "icons" / "target.png"
        if target_icon.is_file():
            self.canvas.load("target", target_icon, crop=True)
        self.reset()

    def reset(self):
        self.client.reset()
        self.projectile_birth = {}

    def begin(self, state):
        self.clock = time.monotonic()
        self.screen = tuple(state["screen"])
        self.visual = state.get("visual") or {}
        self.axis = tuple(self.visual.get("ground") or state.get("ground") or (1, 1))
        self.client.begin(self.screen, self.axis, self.clock)
        self.canvas.begin(self.screen)
        self.events = self.visual.get("events") or []
        skills = self.visual.get("skills")
        if skills is None:
            skill = self.visual.get("skill")
            skills = [skill] if skill else []
        self.skills = {skill["kind"]: skill for skill in skills}
        self.projectiles = self.visual.get("projectiles") or []
        self.projectile_birth = {
            p["id"]: self.projectile_birth.get(p["id"], self.clock)
            for p in self.projectiles
        }

    def draw(self, name, age, position, face, units, event_key, **options):
        if name in self.client.systems:
            self.client.draw(name, age, position, face, units, key=event_key, **options)

    def ground(self, state):
        actor, face = state["position"], state["face"]
        marker = self.canvas
        target = self.visual.get("target")
        if target and "target" in marker.textures:
            marker.sprite("target", target, (24, 16), (1, .65, .6, .92))
            marker.flush()

        for kind, name in (("w", "W_Zone"), ("r", "R_Range_Indicator_Self")):
            skill = self.skills.get(kind)
            if not skill:
                continue
            event = next((e for e in reversed(self.events) if e["kind"] == kind), {})
            radius = skill.get("radius") or event.get("radius", 0)
            if radius > 0:
                age = skill["age"]
                duration = skill["duration"]
                opacity = min(1, max(0, (duration - age) / .12))
                # The R range boundary is visible on the opening packet,
                # before its first burst, using the current Lua radius.
                zone_age = max(.06, age) if kind == "r" else age
                self.draw(name, zone_age, actor, face, self.radius_scale(name, radius),
                          (kind, "zone"), children=False, opacity=opacity)

        for event in self.events:
            if event["kind"] != "eq" or event["age"] >= .65:
                continue
            target = event.get("target")
            if not target:
                continue
            origin = event["position"]
            path = tuple((end - start) / axis for start, end, axis in zip(origin, target, self.axis))
            length = math.hypot(*path)
            if length > 0:
                # The original scrape covers -700..0 in its local forward
                # direction. Anchor it at the measured dash endpoint.
                self.draw("Q_EBufferCast", event["age"], target, direction(path),
                          length / 700, event["id"], children=False)

    def radius_scale(self, name, radius):
        # Axis X is already incorporated in the transmitted logical radius.
        return radius / (CLIENT_RADIUS[name] * self.axis[0]) if radius > 0 else .17

    @staticmethod
    def socket(sockets, name, point, face):
        return sockets.get(name, (point[0] + 8 * face[0], point[1] + 8 * face[1] - 12))

    def draw_events(self, state, sockets):
        actor = state["position"]
        dash = self.skills.get("eq") or self.skills.get("e")
        for event in self.events:
            kind = event["kind"]
            key = event["id"]
            age = event["age"]
            point = event["position"]
            face = direction(event.get("direction", state["face"]), state["face"])
            target = event.get("target")
            radius = event.get("radius", 0)
            if kind in ("attack", "q") and age < .23:
                muzzle = self.socket(sockets, "pistol" if kind == "attack" else "revolver", point, face)
                if target:
                    face = towards(point, target, face)
                # BA emitters were authored inside the moving missile with a
                # downward offset. Rebase the source effect at the actual socket.
                emitter_origin = (muzzle[0], muzzle[1] - 60 * .19 * .819152) if kind == "attack" else muzzle
                self.draw("BA_Muzzle" if kind == "attack" else "Q_Muzzle",
                          age, emitter_origin, face, .19, key)
                # The source plane can be edge-on. Its original texture also
                # reads as a flash in screen space while the gun is horizontal.
                if age < .15 and "muzzle" in self.canvas.textures:
                    anchor = (muzzle[0] + 5 * face[0], muzzle[1] + 5 * face[1])
                    tint = (1, .65, .27) if kind == "attack" else (.45, .70, 1)
                    self.canvas.sprite("muzzle", anchor, (9, 16), (*tint, 1 - age / .15),
                                       (-face[1], face[0]), add=True)
                    self.canvas.flush()
            elif kind == "qmelee" and age < .65:
                self.melee_q(age, point, face, radius, key)
            elif kind == "melee" and age < .65:
                # The basic attack swipe uses the reverse local forward axis.
                name = "BA_Melee_One"
                self.draw(name, age, point, (-face[0], -face[1]),
                          self.radius_scale(name, radius), key, opacity=.85)
            elif kind == "w" and age < .55 and ("w" in self.skills or "r" not in self.skills):
                # Each cut hits once at its event position. The separate W zone follows the actor.
                self.draw("W_CircleCut", age, point, face, self.radius_scale("W_CircleCut", radius), key)
            elif kind == "e" and age < .65:
                head = actor if dash else target or point
                duration = dash["duration"] if dash else 7 / 30
                dash_speed = math.dist(point, target) / (duration * .13) if target else 0
                trail = "E_R_Dash_Trail" if "r" in self.skills else "E_DashTrail"
                self.draw(trail, age, head, face, .13, key,
                          moving_speed=dash_speed, moving_duration=duration, opacity=.72)
            elif kind == "r" and age < .20:
                self.ultimate_burst(event, sockets, face)
            elif kind == "block" and age < .35:
                self.draw("W_Missile_Block_Beam", age, point, face, .14, key)
            elif kind == "hit" and age < .42:
                source = event.get("source", "attack")
                self.draw(IMPACTS.get(source, "BA_Tar"), age, point, face, .15, key,
                          opacity=.68 if source == "r" else .9)

    def melee_q(self, age, point, screen_face, radius, key):
        name = "Q_Melee_AOE"
        units = self.radius_scale(name, radius)
        gx, gy = self.axis
        # The shader applies the ground projection after rotation. Lua's
        # event direction is already projected, so undo it before rotating.
        face = direction((screen_face[0] / gx, screen_face[1] / gy))
        # Fit the authored crescent to Isaac's melee cone in ground space.
        # The offset applies to the artwork inside a cone anchored at the actor.
        self.draw(name, age, point, face, units, key, opacity=.85 * min(1, age * 30),
                  effect_shape=(.55, 1.5, 75), fan_bounds=(CLIENT_RADIUS[name], .55))

    def ultimate_burst(self, event, sockets, face):
        age = event["age"]
        point = event["position"]
        radius = event.get("radius", 0)
        key = event["id"]
        angle = math.atan2(face[1], face[0])
        for index, color in enumerate(("Blue", "Red")):
            rotation = angle + index * math.pi
            aim = (math.cos(rotation), math.sin(rotation))
            muzzle = self.socket(sockets, "pistol" if index == 0 else "revolver", point, aim)
            self.draw(f"R_Gun_{color}_Muzzle", age, muzzle, aim, .18, key)
            distance = radius * min(1, age / .14)
            bullet = (muzzle[0] + aim[0] * distance, muzzle[1] + aim[1] * distance)
            self.draw(f"R_Mis_Gun_{color}", age, bullet, aim, .11, key, opacity=.78)

    def draw_projectiles(self):
        if not self.can_projectiles:
            return
        for projectile in self.projectiles:
            kind = projectile["kind"]
            if kind not in PROJECTILES:
                continue
            point = projectile["position"]
            velocity = projectile["velocity"]
            face = direction(velocity)
            key = projectile["id"]
            age = self.clock - self.projectile_birth[key]
            units = .14 if kind == "attack" else .13
            # Only the native tear owns its position. Source sprites remain
            # visible after one-shot particles time out (e.g. a stationary tear).
            if age < .39:
                self.draw(PROJECTILES[kind], age, point, face, units,
                          ("projectile", key), children=False, opacity=.65)
            trail = kind + "-trail"
            length = min(32, math.hypot(*velocity) * 1.7)
            if trail in self.canvas.textures and length > 2:
                tail = (point[0] - face[0] * length / 2, point[1] - face[1] * length / 2)
                self.canvas.sprite(trail, tail, (length, 7 if kind == "q" else 4),
                                   (1, 1, 1, .72), face, add=True)
            if kind == "attack":
                self.canvas.sprite(kind, point, (13, 7), (1, .8, .54, 1), face, add=True)
            else:
                # Its opaque head sits a quarter of the way down the
                # original vertical texture. Align that head to the tear.
                center = (point[0] - 5.5 * face[0], point[1] - 5.5 * face[1])
                self.canvas.sprite(kind, center, (15, 22), (.63, .80, 1, 1),
                                   (-face[1], face[0]), add=True)
            self.canvas.flush()

    def hud(self):
        cooldowns = self.visual.get("cooldowns")
        style = self.visual.get("style")
        ready = bool(style and style.get("ready"))
        canvas = self.canvas
        width, height = self.screen
        now = getattr(self, "clock", 0)
        if ready:
            draw_ready_glow(canvas, width, height, now)
        if not cooldowns:
            if ready:
                canvas.flush()
            return
        x = width / 2 - 45
        y = height - (50 if width < 556 else 24)
        charge = self.visual.get("charge") or {}
        if charge.get("visible"):
            progress = max(0, min(1, charge.get("progress", 0)))
            canvas.rect(x, y - 10, 90, 7, (.067, .052, .10, .96))
            color = (1, .67, .20, 1) if progress >= 1 else (.54, .75, 1, 1)
            canvas.rect(x + 1, y - 9, 88 * progress, 5, color)
        rank = max(0, min(6, int(style.get("rank", 0)))) if style is not None else None
        ultimate_locked = rank is not None and rank < 6
        for key in "qwer":
            cooldown = max(0, cooldowns.get(key, 0))
            locked = key == "r" and ultimate_locked
            icon = "icon-" + key
            canvas.rect(x, y, 19, 19, (.067, .052, .10, .92))
            if icon in canvas.textures:
                canvas.rect(x + 1, y + 1, 17, 17, (1, 1, 1, .36 if cooldown or locked else .9), icon)
            if cooldown:
                canvas.text(str(math.ceil(cooldown)), x + 9.5, y + 3, 14, center=True)
            if not cooldown or key == "r":
                canvas.rect(x + 1, y + 10.5, 7.5, 7.5, (.04, .03, .07, .85))
                canvas.text(key.upper(), x + 4.75, y + 11.5, 8, center=True)
            x += 23.5
        if style is not None:
            x, y = math.floor(x + 1), math.floor(y - 5)
            color = (1, .83, .48, 1) if ready else (1, .58, .39, 1) if rank else (.8, .73, .75, 1)
            canvas.rect(x, y, 39, 28, color if ready else (.56, .34, .36, 1))
            canvas.rect(x + 1, y + 1, 37, 26, (.067, .052, .10, 1))
            if rank != getattr(self, "hud_rank", None):
                self.hud_rank = rank
                self.hud_rank_at = now
            age = max(0, 1 - (now - self.hud_rank_at) / .20)
            canvas.text("-EDCBAS"[rank], x + 12, y + 3, 21 + 3 * age * age, color, center=True)
            remaining = style.get("remaining", 0)
            if rank and remaining > 0:
                canvas.text(str(math.ceil(remaining)), x + 29, y + 7, 12, color, center=True)
            for pip in range(6):
                canvas.rect(x + 3 + 5.6 * pip, y + 22, 5, 3, color if pip < rank else (.33, .23, .25, 1))
        canvas.flush()

    def foreground(self, state, sockets):
        self.draw_events(state, sockets or {})
        self.draw_projectiles()
        self.hud()
