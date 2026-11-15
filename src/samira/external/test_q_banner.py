"""Regression: normal Q owns banner tracks; passive leg mixing preserves them."""
from pathlib import Path
import json
from overlay import Windows,create_window,glfw,Model,GPURenderer,ROOT,np,Image
from model import CLIPS

def main():
    m=Model(ROOT/'reference/source/model.glb')
    old=Model(ROOT/'reference/model-before-ground-q-0766.glb')
    banner=[i for i,n in enumerate(m.nodes) if 'Banner' in n.get('name','')]
    assert CLIPS['Q1']=='aatrox_ground_q1' and CLIPS['Q3']=='aatrox_ground_q3'
    assert CLIPS['RQ1']=='Q1_Ult' and CLIPS['RQ3']=='Q3_Ult'
    for clip in ('aatrox_ground_q1','aatrox_ground_q3'):
        tracked={(n,p) for n,p,*_ in m.tracks[clip]}
        assert all((n,p) in tracked for n in banner for p in ('translation','rotation','scale'))
    # Adding animations must not change existing mesh, texture or action data.
    assert np.array_equal(m.vertices,old.vertices)
    for name in old.tracks:
        for phase in (0,.5,1):
            assert all(np.array_equal(a,b) for a,b in zip(m.sample(name,phase),old.sample(name,phase))),name
    passive=[n for n in m.tracks if 'passive' in n.lower()]
    preserved=sorted(set(range(len(m.nodes)))-set(m.leg_nodes))
    for clip in passive:
        for phase in np.linspace(0,1,9):
            pose=m.sample(clip,phase);walk=m.sample('Passive_Run',.3)
            mixed=m.moving_pose(clip,phase,dict(kind='Passive_Run',phase=.3))
            for base,actual,legs in zip(pose,mixed,walk):
                assert np.array_equal(base[preserved],actual[preserved]),clip
                assert np.array_equal(legs[m.leg_nodes],actual[m.leg_nodes]),clip
    Windows();window,ctx=create_window(False)
    try:
        renderer=GPURenderer(ctx,m)
        fbo=ctx.framebuffer([ctx.texture((400,400),4)],ctx.depth_renderbuffer((400,400)))
        fbo.use();ctx.viewport=(0,0,400,400)
        sheet=Image.new('RGBA',(1200,800))
        examples=[('Q1_Ult',.48,None),('Q3_Ult',.424,None),('Q1_INTO_PASSIVE_RUN',.3,True),
                  ('aatrox_ground_q1',.72,None),('aatrox_ground_q3',.72,None),('Q1_INTO_PASSIVE_RUN',.3,False)]
        for i,(clip,phase,bad_mix) in enumerate(examples):
            renderer.kind=None;renderer.pose=None;renderer.previous=None
            ctx.clear(.08,.07,.07,1)
            locomotion=dict(kind='Passive_Run',phase=.6) if bad_mix is not None else None
            if bad_mix:
                pose=m.sample(clip,phase);walk=m.sample('Passive_Run',.6)
                for part,legs in zip(pose,walk):part[m.walk_nodes]=legs[m.walk_nodes]
                current=m.moving_pose;m.moving_pose=lambda *args:pose
                try:renderer.draw('Idle',phase,(55,95),(110,110),.3,1/30,clip=clip)
                finally:m.moving_pose=current
            else:renderer.draw('Idle',phase,(55,95),(110,110),.3,1/30,clip=clip,locomotion=locomotion)
            ctx.finish()
            sheet.paste(Image.frombytes('RGBA',fbo.size,fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM),((i%3)*400,(i//3)*400))
        sheet.save(ROOT/'reference/q-banner-0766-comparison.png')
        for clip in ('aatrox_ground_q1','aatrox_ground_q3','Q1_Ult','Q3_Ult',*passive):
            for phase in np.linspace(0,1,11):
                ctx.clear(0,0,0,0)
                renderer.draw('Idle',phase,(55,95),(110,110),.3,1/30,clip=clip,
                    ultimate=clip.endswith('_Ult'),locomotion=dict(kind='Passive_Run',phase=.3) if clip in passive else None)
        ctx.finish();assert ctx.error=='GL_NO_ERROR'
        report=dict(original_clips_unchanged=len(old.tracks),new_normal_q_banner_tracks_complete=True,
            passive_clips_tested=len(passive),passive_samples_per_clip=9,upper_body_and_banner_preserved=True,
            leg_motion_preserved=True,gpu_error=ctx.error,live_game_test=False)
        (ROOT/'reference/q-banner-0766-test.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report))
    finally:glfw.destroy_window(window);glfw.terminate()
if __name__=='__main__':main()
