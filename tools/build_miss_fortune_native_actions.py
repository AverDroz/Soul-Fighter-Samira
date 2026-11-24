"""Bake the local Miss Fortune rig into Isaac spritesheets using the companion renderer."""

import argparse
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import moderngl
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/samira/external'))
from model import GPURenderer, Model, YONE_VIEW
from mf_renderer import barrage_recoil
from mf_taunt_doll import TauntDoll

MOD = ROOT / 'src/samira-testroom/mod'
GLB = ROOT / 'assets/mf-local/mf.glb'
DEST = MOD / 'resources/gfx/mf'
VIEWPORT = (768, 768)
ORIGIN = (384, 490)
PAGE_SIZE = 1024
SUPERSAMPLE = 4.15
DIRECTIONS = 8
BARRAGE_INTERVAL = 6
LOOPS = {'idle', 'base_idle', 'run', 'strut_run_loop', 'r', 'joke_loop', 'taunt_loop', 'taunt_spam_loop',
         'dance_loop', 'recall_loop', 'homeguard'}
FRAME = dict(XScale='100', YScale='100', Delay='1', Visible='true', RedTint='255',
             GreenTint='255', BlueTint='255', AlphaTint='255', RedOffset='0',
             GreenOffset='0', BlueOffset='0', Rotation='0', Interpolated='false',
             XPosition='0', YPosition='0')


def render(frame, actor, doll, clip, direction, phase):
    yaw = math.tau * direction / DIRECTIONS
    frame.use()
    frame.clear(0, 0, 0, 0)
    actor.reset()
    recoil = None
    if clip == 'r':
        state = dict(mfBarrage=dict(start=0, interval=BARRAGE_INTERVAL), clock=phase * BARRAGE_INTERVAL)
        recoil = barrage_recoil(state, actor.model)
    source = 'taunt_loop' if clip == 'taunt_spam_loop' else clip
    actor.draw(source, phase, ORIGIN, VIEWPORT, yaw, .1, clip=source, anchor_root=True, world_offsets=recoil)
    if doll.actor is not None and source in ('taunt', 'taunt_loop', 'taunt_spam'):
        doll.reset()
        elapsed = actor.model.durations[source] * phase
        expression = None
        if clip == 'taunt_spam_loop':
            elapsed += actor.model.durations['taunt_spam']
            expression = 'taunt_spam'
        elif clip == 'taunt_loop':
            elapsed += actor.model.durations['taunt']
        doll.draw(dict(actionFrame=30 * elapsed, expression=expression, position=ORIGIN, screen=VIEWPORT),
                  actor, yaw, .1, source, phase)
        if doll.actor is None:
            raise RuntimeError('Failed to render the locally supplied taunt doll')
    if actor.ctx.error != 'GL_NO_ERROR':
        raise RuntimeError(f'GPU error for {clip}, direction {direction}, phase {phase}')

    pixels = np.frombuffer(frame.read(components=4), np.uint8)
    pixels = pixels.reshape(VIEWPORT[1], VIEWPORT[0], 4)[::-1]
    box = Image.fromarray(pixels[:, :, 3]).getbbox()
    if box is None and clip == 'respawn':
        events = actor.model.active_events(clip, phase)
        if any('Body' in event.get('mHideSubmeshList', ()) for event in events):
            return Image.new('RGBA', (2, 2)), (1, 1)
    if not box or not (0 < box[0] < box[2] < VIEWPORT[0] and 0 < box[1] < box[3] < VIEWPORT[1]):
        raise ValueError(f'Empty or clipped pose for {clip}, direction {direction}, phase {phase}: {box}')
    left, top, right, bottom = box
    # Include the common foot anchor even if the animated mesh leaves the ground.
    unit_box = (
        min(-1, math.floor((left - ORIGIN[0]) / SUPERSAMPLE) - 1),
        min(-1, math.floor((top - ORIGIN[1]) / SUPERSAMPLE) - 1),
        max(1, math.ceil((right - ORIGIN[0]) / SUPERSAMPLE) + 1),
        max(1, math.ceil((bottom - ORIGIN[1]) / SUPERSAMPLE) + 1),
    )
    left, top, right, bottom = unit_box
    crop = (round(ORIGIN[0] + left * SUPERSAMPLE), round(ORIGIN[1] + top * SUPERSAMPLE),
            round(ORIGIN[0] + right * SUPERSAMPLE), round(ORIGIN[1] + bottom * SUPERSAMPLE))
    if not (0 <= crop[0] < crop[2] <= VIEWPORT[0] and 0 <= crop[1] < crop[3] <= VIEWPORT[1]):
        raise ValueError(f'Insufficient supersample padding for {clip}, direction {direction}, phase {phase}')
    rgba = pixels[crop[1]:crop[3], crop[0]:crop[2]].copy()
    alpha = rgba[:, :, 3:4].astype(np.float32)
    rgba[:, :, :3] = np.clip(rgba[:, :, :3].astype(np.float32) * 255 / np.maximum(alpha, 1), 0, 255)
    image = Image.fromarray(rgba).resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    return image, (-left, -top)


def collect_poses(only=None):
    with moderngl.create_standalone_context(require=330) as ctx:
        color = ctx.texture(VIEWPORT, 4)
        depth = ctx.depth_renderbuffer(VIEWPORT)
        frame = ctx.framebuffer([color], depth)
        actor = GPURenderer(ctx, Model(GLB, hero='mf'))
        actor.model.pixel_scale = .9
        actor.view = YONE_VIEW
        doll = TauntDoll(ctx, GLB)
        if (GLB.parent / 'taunt-doll/doll.glb').is_file() and doll.actor is None:
            raise RuntimeError('Could not load the locally supplied taunt doll')
        try:
            r_preview = actor.model.rig_events.get('states', {}).get('r_preview', {})
            durations = dict(actor.model.durations)
            if doll.actor is not None and 'taunt_spam' in durations and 'taunt_loop' in durations:
                durations['taunt_spam_loop'] = durations['taunt_loop']
            if only:
                if only not in durations:
                    raise ValueError(f'Unknown native animation clip: {only}')
                durations = {only: durations[only]}
            for clip, duration in durations.items():
                pulse_pose = clip == 'r' and r_preview.get('mode') == 'hold_terminal_pose'
                count = BARRAGE_INTERVAL if pulse_pose else min(32, max(2, math.ceil(duration * 15 - .0001)))
                looping = clip in LOOPS or (clip == 'dance' and 'dance_loop' not in durations)
                divisor = max(1, count if looping else count - 1)
                samples = [
                    [render(frame, actor, doll, clip, direction, index / divisor) for index in range(count)]
                    for direction in range(DIRECTIONS)
                ]
                print(f'{clip}: {count} frames x {DIRECTIONS} directions', flush=True)
                yield clip, BARRAGE_INTERVAL / 30 if pulse_pose else duration, looping, samples
        finally:
            doll.close()
            actor.close()
            frame.release()
            depth.release()
            color.release()


def new_document(clip, page):
    actor = ET.Element('AnimatedActor')
    ET.SubElement(actor, 'Info', Version='1', Fps='30')
    content = ET.SubElement(actor, 'Content')
    sheets = ET.SubElement(content, 'Spritesheets')
    ET.SubElement(sheets, 'Spritesheet', Path=f'actions-{page}.png', Id='0')
    layers = ET.SubElement(content, 'Layers')
    ET.SubElement(layers, 'Layer', Name='Body', Id='0', SpritesheetId='0')
    ET.SubElement(content, 'Nulls')
    ET.SubElement(content, 'Events')
    return actor, ET.SubElement(actor, 'Animations', DefaultAnimation=f'{clip}0')


def add_animation(animations, clip, direction, looping, samples, crops):
    animation = ET.SubElement(animations, 'Animation', Name=f'{clip}{direction}',
                              FrameNum=str(len(samples)), Loop=str(looping).lower())
    root = ET.SubElement(animation, 'RootAnimation')
    ET.SubElement(root, 'Frame', FRAME | dict(Delay=str(len(samples))))
    layer = ET.SubElement(ET.SubElement(animation, 'LayerAnimations'), 'LayerAnimation',
                         LayerId='0', Visible='true')
    for (image, pivot), (x, y) in zip(samples, crops, strict=True):
        attributes = dict(XCrop=x, YCrop=y, Width=image.width, Height=image.height,
                          XPivot=pivot[0], YPivot=pivot[1])
        ET.SubElement(layer, 'Frame', FRAME | {key: str(value) for key, value in attributes.items()})
    ET.SubElement(animation, 'NullAnimations')
    ET.SubElement(animation, 'Triggers')


def write_clip(clip, actor):
    ET.indent(actor)
    ET.ElementTree(actor).write(DEST / f'action-{clip}.anm2', encoding='utf-8', xml_declaration=True)


def pack_clip(samples, occupied):
    # A clip stays on one page, so each animation needs just one visible layer.
    shelves = [list(shelf) for shelf in occupied]
    result = [[] for direction in samples]
    poses = sorted(
        ((image.height, image.width, direction, index)
         for direction, frames in enumerate(samples) for index, (image, _) in enumerate(frames)),
        reverse=True,
    )
    for height, width, direction, index in poses:
        match = next((shelf for shelf in shelves if shelf[1] >= height + 2 and shelf[2] + width + 2 <= PAGE_SIZE), None)
        if match is None:
            y = sum(shelf[1] for shelf in shelves)
            if y + height + 2 > PAGE_SIZE:
                return None
            match = [y, height + 2, 0]
            shelves.append(match)
        result[direction].append((index, (match[2] + 1, match[0] + 1)))
        match[2] += width + 2
    return shelves, [[crop for _, crop in sorted(row)] for row in result]


def write_assets(poses, only=None):
    documents = {}
    pages = []
    shelves = []
    metadata = []
    namespace = f'{only}-' if only else ''
    for clip, duration, looping, samples in poses:
        for page, occupied in enumerate(shelves):
            layout = pack_clip(samples, occupied)
            if layout is not None:
                break
        else:
            page = len(pages)
            layout = pack_clip(samples, [])
            if layout is None:
                raise ValueError(f'{clip} exceeds a {PAGE_SIZE}-pixel page')
            pages.append(Image.new('RGBA', (PAGE_SIZE, PAGE_SIZE)))
            shelves.append([])
        shelves[page], crops = layout
        actor, animations = new_document(clip, f'{namespace}{page}')
        documents[clip] = actor
        for direction, (frames, frame_crops) in enumerate(zip(samples, crops, strict=True)):
            add_animation(animations, clip, direction, looping, frames, frame_crops)
            for (image, _), crop in zip(frames, frame_crops, strict=True):
                pages[page].paste(image, crop)
        metadata.append((clip, duration, len(samples[0])))

    DEST.mkdir(parents=True, exist_ok=True)
    for page, (image, occupied) in enumerate(zip(pages, shelves, strict=True)):
        width = max(shelf[2] for shelf in occupied)
        height = sum(shelf[1] for shelf in occupied)
        image.crop((0, 0, width, height)).save(DEST / f'actions-{namespace}{page}.png')
    for clip, actor in documents.items():
        write_clip(clip, actor)
    if not only:
        for stale in DEST.glob('action-*.anm2'):
            if stale.stem.removeprefix('action-') not in documents:
                stale.unlink()
        for stale in DEST.glob('actions-*.png'):
            if stale.stem.removeprefix('actions-').isdigit() and int(stale.stem.removeprefix('actions-')) >= len(pages):
                stale.unlink()
        (DEST / 'actions.anm2').unlink(missing_ok=True)
    for suffix, field in [('frames', 2), ('times', 1)]:
        lines = [f'    {entry[0]} = {entry[field]:.9g},' for entry in metadata]
        target = MOD / f'miss_fortune_sprite_{suffix}.lua'
        if only:
            original = target.read_text(encoding='utf-8').splitlines()
            lines = [line for line in original[2:-1] if not line.strip().startswith(f'{only} =')] + lines
        target.write_text(
            '-- Generated by tools/build_miss_fortune_native_actions.py\nreturn {\n'
            + '\n'.join(lines) + '\n}\n', encoding='utf-8')
    print(f'Wrote {len(metadata)} clips to {len(pages)} atlas pages', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', help='Bake one clip and leave all other atlas pages intact.')
    args = parser.parse_args()
    write_assets(collect_poses(args.clip), args.clip)
