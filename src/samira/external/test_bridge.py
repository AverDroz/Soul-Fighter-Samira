import json,tempfile,unittest
from pathlib import Path
from bridge import parse,Tail,PREFIX

def state(seq,ms,x=100,kind='Walk',phase=.2):
    return {'version':1,'active':True,'seq':seq,'time':ms,'screen':[640,480],
            'position':[x,100],'face':[1,0],'kind':kind,'phase':phase,'clock':ms*.03,'fx':[]}
def line(value):return ('[INFO] - Lua Debug: '+PREFIX+json.dumps(value)+'\n').encode()

class BridgeTests(unittest.TestCase):
    def test_heartsteel_target_motion_and_contact_share_delayed_clock(self):
        tail=Tail(Path('missing-test-log'));tail.received=1;tail.interval=.1
        tail.previous=dict(state(1,100),heartsteel=[dict(key='e',stage=6,age=6,position=[100,100])])
        tail.latest=dict(state(2,200),heartsteel=[dict(key='e',stage=6,age=9,position=[120,100])],heartsteelHits=[dict(age=0,position=[120,100])])
        s=tail.sample(1.05)
        self.assertAlmostEqual(s['heartsteel'][0]['age'],7.5)
        self.assertAlmostEqual(s['heartsteel'][0]['position'][0],110)
        self.assertEqual(s['heartsteelHits'],[])
        self.assertEqual(tail.sample(1.11)['heartsteelHits'][0]['age'],0)

    def test_captured_room_scroll_interpolates_without_changing_visibility(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'log';p.touch();tail=Tail(p)
            for seq,x in ((1,137),(2,140)):
                with p.open('ab') as f:f.write(line(dict(state(seq,seq*100,x),presentation=2,transition=True,renderCaptured=True,room=3)))
                tail.poll(1+seq*.1)
            self.assertIsNotNone(tail.previous)
            self.assertAlmostEqual(tail.sample(1.25)['position'][0],138.5)
            with p.open('ab') as f:f.write(line(dict(state(3,300,143),presentation=2,transition=True,renderCaptured=True,room=4)))
            tail.poll(1.3)
            self.assertIsNone(tail.previous,'no interpolation across unrelated room epochs')
            self.assertEqual(tail.sample(1.3)['position'][0],143)

    def test_validate(self):
        self.assertIsNone(parse('normal log line'));self.assertIsNone(parse(PREFIX+'broken'))
        self.assertIsNone(parse(PREFIX+json.dumps(dict(state(1,1),screen=[0,0]))))
        self.assertIsNone(parse(PREFIX+json.dumps(dict(state(1,1),position=[float('nan'),0]))))
        self.assertFalse(parse(PREFIX+'{"version":1,"active":false}')['active'])
    def test_tail_interpolation_stale_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'log.txt';p.write_bytes(line(state(0,0)))
            tail=Tail(p);tail.poll(1);self.assertIsNone(tail.sample(1)) # no old game replay
            content=line(state(1,100,100))
            with p.open('ab') as f:f.write(content[:40])
            tail.poll(1);self.assertIsNone(tail.sample(1))
            with p.open('ab') as f:f.write(content[40:])
            tail.poll(1);self.assertEqual(tail.sample(1)['position'],[100,100])
            with p.open('ab') as f:f.write(line(state(2,200,120,phase=.4)))
            tail.poll(1.1);sample=tail.sample(1.15)
            self.assertAlmostEqual(sample['position'][0],110);self.assertAlmostEqual(sample['phase'],.3)
            self.assertIsNone(tail.sample(1.7))
            p.write_bytes(line({'version':1,'active':False}));tail.poll(2);self.assertIsNone(tail.sample(2))
            with p.open('ab') as f:f.write(line(state(1,300,500)))
            tail.poll(3);self.assertEqual(tail.sample(3)['position'][0],500)
    def test_pause_and_impact_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'log.txt';p.touch();tail=Tail(p)
            a=state(1,100,phase=.2);b=state(2,200,phase=.6)
            a.update(kind='Q1',cast={'stage':1,'age':15,'impact':18,'duration':24})
            b.update(kind='Q1',cast={'stage':1,'age':18,'impact':18,'duration':24},fx=[{'age':0}])
            with p.open('ab') as f:f.write(line(a))
            tail.poll(1)
            with p.open('ab') as f:f.write(line(b))
            tail.poll(1.1);self.assertEqual(tail.sample(1.1)['fx'],[])
            self.assertEqual(tail.sample(1.21)['fx'][0]['age'],0)
            b.update(seq=3,time=300,paused=True)
            with p.open('ab') as f:f.write(line(b))
            tail.poll(1.3);self.assertTrue(tail.sample(1.3)['paused'])
    def test_clip_change_and_nonlooping_death(self):
        tail=Tail(Path('missing-test-log'))
        tail.previous=dict(state(1,100,phase=.95),kind='Death',looping=False)
        tail.latest=dict(state(2,200,phase=1),kind='Death',looping=False)
        tail.received=1;tail.interval=.1
        self.assertEqual(tail.sample(1.2)['phase'],1,'death must hold its final pose, not wrap to zero')
        tail.previous=dict(state(1,100,phase=.9),clip='Dance_Windup')
        tail.latest=dict(state(2,200,phase=.05),clip='Dance_Loop',looping=True)
        self.assertEqual(tail.sample(1.01)['phase'],.05,'different clips must not interpolate unrelated phase values')

    def test_room_transition_never_interpolates_old_coordinates(self):
        for change in ({'room':2},{'session':'new'},{'transition':True},{'screen':[800,600]},{'paused':True},{'occluded':True}):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as folder:
                p=Path(folder)/'log.txt';p.touch();tail=Tail(p)
                first=dict(state(1,100,580),room=1,session='old',transition=False)
                second=dict(first,**dict(state(2,133,40),**change))
                with p.open('ab') as f:f.write(line(first))
                tail.poll(1)
                with p.open('ab') as f:f.write(line(second))
                tail.poll(1.033)
                self.assertIsNone(tail.previous)
                self.assertEqual(tail.sample(1.033)['position'][0],40)
                third=dict(second,seq=3,time=166,position=[44,100],transition=False,paused=False,occluded=False)
                with p.open('ab') as f:f.write(line(third))
                tail.poll(1.066)
                if change.get('transition') or change.get('paused') or change.get('occluded'):
                    self.assertEqual(tail.sample(1.066)['position'][0],44,'reveal must start at the new position')

    def test_missile_tether_and_new_cast_timelines(self):
        tail=Tail(Path('missing-test-log'));tail.received=1;tail.interval=.1
        tail.previous=dict(state(1,100),bolt=dict(origin=[100,100],position=[150,100]),cast=dict(kind='W',age=9))
        tail.latest=dict(state(2,200),bolt=dict(origin=[100,100],position=[190,100]),cast=dict(kind='RStart',age=1))
        sample=tail.sample(1.05)
        self.assertAlmostEqual(sample['bolt']['position'][0],170)
        self.assertEqual(sample['cast']['age'],1,'new R must not inherit previous W cast age')
        self.assertEqual(sample['packetClock'],6,'cooldown remaining stays associated with original simulation tick')
        tail.latest['bolt']['origin']=[300,100]
        self.assertEqual(tail.sample(1)['bolt']['position'][0],190,'new missile must not interpolate an old missile')

    def test_walking_during_sheathing_wraps_continuously(self):
        tail=Tail(Path('missing-test-log'));tail.received=1;tail.interval=.1
        tail.previous=dict(state(1,100,kind='Sheathe'),locomotion=dict(kind='Walk',phase=.95))
        tail.latest=dict(state(2,200,kind='Sheathe'),locomotion=dict(kind='Walk',phase=.15))
        self.assertAlmostEqual(tail.sample(1.05)['locomotion']['phase'],.05)

if __name__=='__main__':unittest.main()
