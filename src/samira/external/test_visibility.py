import tempfile,unittest,json
from pathlib import Path
from visibility import layers
from bridge import Tail
from test_bridge import state,line
from status import Status

class VisibilityTests(unittest.TestCase):
    def test_persistent_presentation_and_bounded_heartbeat(self):
        tail=Tail(Path('missing-test-log'));tail.received=1
        tail.latest=dict(state(1,100),presentation=2,transition=True,paused=True,hudVisible=True)
        tail.settle_until=4
        packet=tail.sample(3)
        self.assertEqual(layers(packet),(True,True))
        self.assertEqual(packet['position'],[100,100])
        self.assertEqual(packet['phase'],.2,'stalled telemetry holds pose instead of running an old action')
        self.assertEqual(packet['heartbeatTime'],2100)
        self.assertEqual(layers(dict(packet,occluded=True,hudVisible=False)),(False,False))
        self.assertIsNone(tail.sample(4.01),'actual disconnect still releases ownership')
        tail.latest={'active':False}
        self.assertIsNone(tail.sample(1.01),'explicit off is immediate')

    def test_rooms_keep_hud_but_loading_and_pause_do_not(self):
        for paused in (False,True):
            self.assertEqual(layers(dict(transition=True,occluded=True,paused=paused,hudVisible=True)),(False,True))
        for flags in (dict(occluded=True,hudVisible=False),dict(paused=True,hudVisible=False)):
            self.assertEqual(layers(flags),(False,False))
        self.assertEqual(layers(dict(hudVisible=True)),(True,True))

    def test_late_room_notification_never_sweeps_across_room(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'log';path.touch();tail=Tail(path)
            for seq,x in enumerate((580,40,42),1):
                with path.open('ab') as f:f.write(line(dict(state(seq,seq*33,x),hudVisible=True)))
                tail.poll(seq/30)
                if seq==2:
                    packet=tail.sample(seq/30)
                    self.assertIsNone(tail.previous);self.assertEqual(layers(packet),(False,True))
                    self.assertEqual(packet['position'][0],40)
            self.assertEqual(layers(tail.sample(.21)),(True,True))

    def test_hud_only_ack_does_not_claim_actor(self):
        with tempfile.TemporaryDirectory() as folder:
            status=Status(folder);status.write(dict(session='s',room=2,time=100),True,visible=False,hud_visible=True)
            ack=json.loads((Path(folder)/'save1.dat').read_text())
            self.assertTrue(ack['ready']);self.assertTrue(ack['hudVisible']);self.assertFalse(ack['visible'])
            status.hidden(dict(session='s',room=2,time=133))
            ack=json.loads((Path(folder)/'save1.dat').read_text())
            self.assertFalse(ack['hudVisible']);self.assertTrue(ack['ready'])

    def test_blocking_room_load_keeps_only_hud_for_bounded_time(self):
        tail=Tail(Path('missing-test-log'));tail.received=1
        tail.latest=dict(state(1,100),transition=True,hudVisible=True)
        self.assertEqual(layers(tail.sample(2)),(False,True))
        self.assertIsNone(tail.sample(3.1))

if __name__=='__main__':unittest.main()
