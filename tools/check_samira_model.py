"""Validate the imported rig and attachment boundaries without launching Isaac."""
from pathlib import Path
import json,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/samira/external'))
from model import Model,CLIPS,MAX_BONES

model=Model(ROOT/'src/samira/reference/source/model.glb')
assert len(model.joints)==133 and len(model.tracks)==89
assert MAX_BONES>=len(model.joints)
assert not (set(CLIPS.values())-set(model.tracks))
samples=0
for clip in model.tracks:
    for phase in (0,.25,.5,.75,1):
        matrices=model.matrices(model.sample(clip,phase),clip,phase)
        assert np.isfinite(matrices).all(),(clip,phase)
        samples+=1

def world(action,phase):
    skin=model.matrices(model.sample(action,phase),action,phase)
    return {model.nodes[node]['name']:skin[i]@np.linalg.inv(model.ibm[i])
            for i,node in enumerate(model.joints)}

# Check the actual attachment result, not only event names or JSON parsing.
for action,phase,pairs in [
    ('W',.5,[('Sword','Sword_R_Hand_Snap'),('Pistol','Pistol_R_Holster_Snap')]),
    ('E',0,[('Sword','Sword_World_Snap'),('Revolver','Revolver_L_Holster_Snap')]),
    ('E',1,[('Sword','Sword_R_Hand_Snap')]),
    ('Death',.5,[('Sword','Sword_World_Snap'),('Pistol','Pistol_World_Snap')])]:
    transforms=world(action,phase)
    for source,target in pairs:
        assert np.allclose(transforms[source],transforms[target],atol=.001),(action,source,target)
assert not model.visibility('Q',0)['Revolver_Blur']
assert model.visibility('Q',1)['Revolver_Blur']
assert model.visibility('E',0)['Revolver']
assert not model.visibility('E',1)['Revolver']
root=model.node_names['Root'];start=model.sample('E',0)[0][root]
for phase in np.linspace(0,1,21):
    original=model.sample('E',phase);anchored=model.anchor_motion(original,'E')
    assert np.allclose(anchored[0][root,[0,2]],start[[0,2]])
    assert anchored[0][root,1]==original[0][root,1], 'E must preserve authored jump height'
report={'result':'passed','animations':89,'bones':133,'bindings':len(CLIPS),
        'finite_pose_samples':samples,'attachment_and_visibility_boundaries':'passed',
        'scope':'CPU rig validation; does not validate gameplay or all LoL animation graph features'}
out=ROOT/'docs/model-check-result.json'
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report))
