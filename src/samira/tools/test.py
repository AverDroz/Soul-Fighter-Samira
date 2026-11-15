from pathlib import Path
import sys,json,xml.etree.ElementTree as ET
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
from lupa.lua54 import LuaRuntime,lua_type
lua=LuaRuntime(unpack_returned_tuples=True);loaded={}
def include(name):
    if name not in loaded:loaded[name]=lua.execute((ROOT/'mod'/f'{name.replace(".","/")}.lua').read_text(encoding='utf-8'))
    return loaded[name]
lua.globals().include=include
def plain(value):
    if lua_type(value)!='table':return value
    keys=list(value.keys())
    if keys and set(keys)==set(range(1,len(keys)+1)):return [plain(value[i]) for i in range(1,len(keys)+1)]
    return {k:plain(v) for k,v in value.items()}
lua.globals().testJsonEncode=lambda value:json.dumps(plain(value))
lua.globals().testJsonDecode=lambda text:lua.table_from(json.loads(text),recursive=True)
lua.execute("package.preload['json']=function()return {encode=testJsonEncode,decode=testJsonDecode}end")
for p in (ROOT/'mod').rglob('*.lua'):lua.compile(p.read_text(encoding='utf-8'),name=str(p))
for p in sorted((ROOT/'tests').glob('*.lua')):lua.execute(p.read_text(encoding='utf-8'),name=str(p))
count=0
for p in (ROOT/'mod').rglob('*.anm2'):
    root=ET.parse(p);sheets={s.get('Id'):Image.open(p.parent/s.get('Path')) for s in root.findall('Content/Spritesheets/Spritesheet')}
    layers={l.get('Id'):sheets[l.get('SpritesheetId')] for l in root.findall('Content/Layers/Layer')}
    for anim in root.findall('Animations/Animation'):
        count+=1
        for tag in ['RootAnimation','LayerAnimations','NullAnimations','Triggers']:assert anim.find(tag) is not None
        for layer in anim.findall('LayerAnimations/LayerAnimation'):
            im=layers[layer.get('LayerId')]
            for frame in layer:
                a=frame.attrib;x,y,w,h=[int(a[k]) for k in ['XCrop','YCrop','Width','Height']]
                assert x>=0 and y>=0 and x+w<=im.width and y+h<=im.height,(p,a)
                bounds=im.crop((x,y,x+w,y+h)).getbbox()
                assert bounds or p.stem=='experience_arc' and x==0 and y==0,(p,anim.get('Name'),'empty frame')
                if w>1 and p.parent.name=='samira':assert bounds[0]>0 and bounds[1]>0 and bounds[2]<w and bounds[3]<h,(p,anim.get('Name'),'clipped frame')
players=ET.parse(ROOT/'mod/content/players.xml')
import wave
sound_names=set()
sounds=ET.parse(ROOT/'mod/content/sounds.xml').getroot()
for sound in sounds.findall('sound'):
    assert sound.get('name') not in sound_names;sound_names.add(sound.get('name'))
    for sample in sound.findall('sample'):
        with wave.open(str(ROOT/'mod/resources'/sounds.get('root')/sample.get('path'))) as audio:
            assert audio.getnframes()>0 and audio.getnchannels() in (1,2)
assert len(sound_names)==125
for name in ('vo_attack','vo_en_attack'):
    originals=sounds.find(f"./sound[@name='Samira {name}']").findall('sample')
    assert len(originals)==21
    for index,sample in enumerate(originals,1):
        alias=sounds.find(f"./sound[@name='Samira {name}_{index:02d}']")
        assert alias is not None and len(alias.findall('sample'))==1
        assert alias.find('sample').get('path')==sample.get('path')
for name,path in {'vo_boss':'vo_attack_06.wav','vo_en_boss':'en/File0074.wav'}.items():
    entry=sounds.find(f"./sound[@name='Samira {name}']")
    assert entry is not None and len(entry.findall('sample'))==1
    assert entry.find('sample').get('path')==path,'boss intro must use the exact original quote'
assert 'Samira heartsteel_hit' in sound_names
assert {'Samira vo_en_'+name for name in ('q1','q2','q3','w','e','r','death','joke','taunt','laugh','move','attack','kill','move_long','r_ready')}<=sound_names
assert all(f'Samira vo_en_r_{i:02d}' in sound_names for i in range(1,9))
english=json.loads((ROOT/'reference/english-voice-manifest.json').read_text(encoding='utf-8'))
import hashlib
optimization_path=ROOT/'reference/asset-optimization.json'
optimized=json.loads(optimization_path.read_text(encoding='utf8'))['files'] if optimization_path.exists() else {}
for relative,record in optimized.items():
    asset=ROOT/'mod'/relative
    assert hashlib.sha256(asset.read_bytes()).hexdigest()==record['sha256'],('optimized asset changed',relative)
    if record['kind']=='voice-pcm16-32000':
        with wave.open(str(asset)) as audio:
            assert audio.getsampwidth()==2 and audio.getcomptype()=='NONE'
            assert audio.getnchannels()==record['channels'] and audio.getframerate()==record['rate']==32000
            assert audio.getnframes()==record['frames']
            assert abs(audio.getnframes()/audio.getframerate()-record['source_frames']/record['source_rate'])<=1/32000
for samples in english['events'].values():
    for sample in samples:
        asset=ROOT/'mod/resources/sfx/samira/en'/sample['file']
        record=optimized.get(asset.relative_to(ROOT/'mod').as_posix())
        if record:
            assert record['kind']=='voice-pcm16-32000' and record['source_sha256']==sample['sha256'],'compressed voice must derive from the verified supplied English voice'
        else:
            assert hashlib.sha256(asset.read_bytes()).hexdigest()==sample['sha256'],'supplied English voice must remain unchanged'
assert {'Samira vo_move_long','Samira vo_r_ready'}<=sound_names
assert all(f'Samira vo_r_{i:02d}' in sound_names for i in range(1,9))
assert {'Samira death','Samira vo_death','Samira dance_loop','Samira attack_hit','Samira r_music','Samira ui_open','Samira ui_level','Samira passive_hit'}<=sound_names
music=ET.parse(ROOT/'mod/content/music.xml').getroot()
track=music.find("./track[@name='Samira World Ender']")
assert track is not None and track.get('loop')=='true'
with wave.open(str(ROOT/'mod/resources'/music.get('root')/track.get('path'))) as bgm:
    assert bgm.getnchannels()==2 and bgm.getframerate()==48000 and abs(bgm.getnframes()/48000-59.405)<.01
for p in players.findall('player'):
    for field in ['skin','portrait','nameimage']:assert (ROOT/'mod/resources/gfx/samira'/p.get(field)).exists()
assert count==549,('missing animations',count)
# The native character registration is read before floor baking, unlike Lua
# pre-render edits. Keep it scoped to Samira, with no visible button anchors.
native_tutorial=ET.parse(ROOT/'mod/content/gfx/controls.anm2')
assert native_tutorial.find('Animations').get('DefaultAnimation')=='Samira'
assert [a.get('Name') for a in native_tutorial.findall('Animations/Animation')]==['Samira']
for tag in ['LayerAnimation','NullAnimation']:
    for node in native_tutorial.findall('.//'+tag):
        assert node.get('Visible')=='false'
        assert all(f.get('Visible')=='false' and f.get('AlphaTint')=='0' for f in node.findall('Frame'))
floor_tutorial=ET.parse(ROOT/'mod/resources/gfx/samira/branding/controls.anm2')
assert floor_tutorial.find('.//LayerAnimation/Frame').get('YPosition')=='-30'
shader=ET.parse(ROOT/'mod/content/shaders.xml')
assert not shader.findall('shader'), 'room must retain its native render viewport'
print(f'Lua 5.4 syntax, {count} animations, sprite crops and character registration passed')

for p in (ROOT/'mod/resources/gfx/samira').glob('*.smooth.json'):
    import json
    d=json.loads(p.read_text());assert d['frames']/d['duration']>=30-1e-5,(p,'less than 30 samples/sec')
print('All 21 action clips sampled at >=30 frames per second')

import json,numpy as np,time
rig=include('scripts.samira_skeleton');reference=json.loads((ROOT/'reference/skeleton-reference.json').read_text())
for name,blend in [('idle',0),('walk',1)]:
    d=rig.data()['clips'][name]['duration'];v=rig.vertices(d*.25 if name=='idle' else 0,d*.25 if name=='walk' else 0,blend)
    result=np.array([[v[i][j] for j in range(1,4)] for i in range(1,len(v)+1)])
    error=np.abs(result-np.array(reference[name])).max();assert error<.01,(name,error) # 30 Hz local-key approximation: under 0.24 rendered world pixels
    print(f'Live skinning vs original GLB {name}: max vertex error {error:.6f}')
a=rig.vertices(.8,.8,.499);b=rig.vertices(.8,.8,.501)
assert max(abs(a[i][j]-b[i][j]) for i in range(1,len(a)+1) for j in range(1,4))<.02,'blend must be continuous'
print('Idle/walk bone blending continuity passed')

start=time.perf_counter()
for i in range(30):rig.vertices(i/30,i/30,.5)
print(f'Offline Lua bone+skin CPU mean: {(time.perf_counter()-start)*1000/30:.2f}ms (no game/GPU drawing)')
