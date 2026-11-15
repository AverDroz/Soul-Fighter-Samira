"""Pack a small emergency actor from existing baked frames; no new rendering."""
from pathlib import Path
import copy,xml.etree.ElementTree as ET
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'mod/resources/gfx/samira'
root=ET.parse(ROOT/'idle.anm2').getroot()
root.find('Content/Spritesheets/Spritesheet').set('Path','fallback.png')
animations=root.find('Animations');animations.clear();animations.set('DefaultAnimation','Idle0')
tiles=[];packed_frames=[]
for kind,samples in [('Idle',[0,28]),('Walk',[0,8,16,24]),('Attack',[0,20,38]),('Death',[20,45,59])]:
    source=ET.parse(ROOT/(kind.lower()+'.anm2'));image=Image.open(ROOT/(kind.lower()+'.png'))
    for direction in range(8):
        anim=copy.deepcopy(source.find(f"Animations/Animation[@Name='{kind}{direction}']"))
        anim.set('FrameNum',str(len(samples)))
        anim.find('RootAnimation/Frame').set('Delay',str(len(samples)))
        layer=anim.find('LayerAnimations/LayerAnimation');frames=list(layer);layer.clear();layer.set('LayerId','0');layer.set('Visible','true')
        for sample in samples:
            frame=copy.deepcopy(frames[min(sample,len(frames)-1)]);a=frame.attrib
            x,y,w,h=[int(a[k]) for k in ('XCrop','YCrop','Width','Height')]
            tile=image.crop((x,y,x+w,y+h)).resize((w//2,h//2),Image.Resampling.LANCZOS)
            for name in ('Width','Height','XPivot','YPivot','XPosition','YPosition'):
                if name in a:a[name]=str(round(float(a[name])/2))
            padded=Image.new('RGBA',(tile.width+4,tile.height+4));padded.paste(tile,(2,2));tile=padded
            for name in ('Width','Height'):a[name]=str(int(a[name])+4)
            for name in ('XPivot','YPivot'):a[name]=str(int(a[name])+2)
            a.update(Delay='1',XCrop=str(len(tiles)%8*(w//2)),YCrop=str(len(tiles)//8*(h//2)))
            layer.append(frame);tiles.append(tile);packed_frames.append(frame)
        animations.append(anim)
tw=max(im.width for im in tiles);th=max(im.height for im in tiles)
atlas=Image.new('RGBA',(tw*8,th*((len(tiles)+7)//8)))
for i,tile in enumerate(tiles):
    atlas.paste(tile,(i%8*tw,i//8*th));packed_frames[i].set('XCrop',str(i%8*tw));packed_frames[i].set('YCrop',str(i//8*th))
atlas.save(ROOT/'fallback.png',optimize=True)
ET.indent(root);ET.ElementTree(root).write(ROOT/'fallback.anm2',encoding='utf-8',xml_declaration=True)
print('Fallback:',len(tiles),'frames,',round((ROOT/'fallback.png').stat().st_size/1024),'KiB')
