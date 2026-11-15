import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from status import Status

class StatusTests(unittest.TestCase):
    def test_renderer_heartbeat_can_renew_held_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            status=Status(folder)
            status.write(dict(session='s',time=100,heartbeatTime=2100),True,True)
            payload=json.loads((status.folder/'save1.dat').read_text())
            self.assertEqual(payload['time'],2100)
            self.assertTrue(payload['ready'])

    def test_intentional_hide_retains_only_a_rendered_session(self):
        with tempfile.TemporaryDirectory() as folder:
            status=Status(folder);state={'session':'run-1','time':100}
            status.hidden(state)
            self.assertFalse(status.ready,'no takeover until the first frame has actually rendered')
            status.write(state,True,True)
            for paused,transition in [(True,False),(True,True),(False,True)]:
                state=dict(state,time=state['time']+300,paused=paused,transition=transition)
                with patch('status.time.perf_counter',return_value=status.last+.3):status.hidden(state)
                payload=json.loads((status.folder/'save1.dat').read_text())
                self.assertTrue(payload['ready']);self.assertEqual(payload['time'],state['time'])
            status.hidden(dict(state,session='new-run'))
            self.assertFalse(status.ready,'new session still waits for a rendered frame')
            status.write(state,True,True);status.hidden(None)
            self.assertFalse(status.ready,'stale/missing telemetry is a real disconnect')
    def test_slots_stop_and_file_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            status=Status(Path(folder)/'samira_external_link')
            state={'session':'run-1','time':123456}
            self.assertTrue(status.write(state,True,True))
            for slot in (1,2,3):
                data=json.loads((status.folder/f'save{slot}.dat').read_text())
                self.assertEqual(data,dict(version=1,session='run-1',time=123456,ready=True,capabilities={'combat':1,'hud':1,'shop':1},visible=True,hudVisible=True,room=None))
            self.assertTrue(status.write(force=True))
            self.assertFalse(json.loads((status.folder/'save1.dat').read_text())['ready'])
            with patch('status.os.replace',side_effect=PermissionError('reader lock')):
                self.assertFalse(status.write(state,True,True))
            self.assertTrue(status.write(state,True,True),'next update retries rather than killing the renderer')

if __name__=='__main__':unittest.main()
