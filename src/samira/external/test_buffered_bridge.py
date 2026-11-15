"""Slow log I/O cannot stall render sampling or mix room snapshots."""
import json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from bridge import Tail,BufferedTail
from test_bridge import state,line


class BufferedBridgeTests(unittest.TestCase):
    def wait_for(self,predicate):
        deadline=time.perf_counter()+2
        while not predicate():
            if time.perf_counter()>deadline:self.fail('reader did not publish')
            time.sleep(.002)

    def test_blocked_io_keeps_sampling_and_original_stale_policy(self):
        entered=threading.Event();release=threading.Event();durations=[]
        def blocked(tail,now=None):
            entered.set();release.wait(2)
        with patch.object(Tail,'poll',blocked):
            reader=BufferedTail('missing-test-log')
            try:
                self.assertTrue(entered.wait(1))
                # Publish a previous acknowledged room, then block the reader.
                tail=reader._tail;tail.latest=dict(state(1,100),presentation=2,hudVisible=True)
                tail.received=1;reader._publish()
                for _ in range(2000):
                    start=time.perf_counter();sample=reader.sample(1.1)
                    durations.append((time.perf_counter()-start)*1000)
                    self.assertEqual(sample['seq'],1)
                self.assertIsNone(reader.sample(4.1),'stalls cannot extend the stale-data lease')
                self.assertFalse(release.is_set())
                self.assertLess(max(durations),50,'render sampling must not wait for file I/O')
                print(json.dumps({'blocked_reader_samples':len(durations),'sample_max_ms':max(durations),
                                  'sample_mean_ms':sum(durations)/len(durations)}))
            finally:release.set();reader.close()
            self.assertFalse(reader._thread.is_alive())

    def test_real_append_partial_lines_room_change_and_truncate(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'log.txt';path.write_bytes(line(state(0,0)))
            reader=BufferedTail(path)
            try:
                self.assertIsNone(reader.sample(),'old log must not be replayed')
                with path.open('ab') as f:f.write(line(state(1,100)))
                self.wait_for(lambda:reader.count==1)
                first=reader._view
                packet=line(dict(state(2,200,120),room=2))
                with path.open('ab') as f:f.write(packet[:35])
                time.sleep(.025);self.assertEqual(reader.count,1)
                with path.open('ab') as f:f.write(packet[35:])
                self.wait_for(lambda:reader.count==2)
                sample=reader.sample()
                self.assertEqual(sample['room'],2);self.assertEqual(sample['position'],[120,100])
                self.assertEqual(first.latest['seq'],1,'published views cannot be mutated by new reads')
                path.write_bytes(line({'version':1,'active':False}))
                self.wait_for(lambda:reader.count==3);self.assertIsNone(reader.sample())
            finally:reader.close()

    def test_published_sample_is_identical_to_sync_interpolation(self):
        tail=Tail('missing-test-log');tail.received=1;tail.interval=.1
        tail.previous=state(1,100,100,phase=.2);tail.latest=state(2,200,120,phase=.4)
        reader=object.__new__(BufferedTail);reader._tail=tail;reader._error=None;reader._publish()
        for at in (1,1.025,1.05,1.1,1.4,1.6):self.assertEqual(reader.sample(at),tail.sample(at))

    def test_worker_failures_are_visible_to_supervisor(self):
        with patch.object(Tail,'poll',side_effect=ValueError('test failure')):
            reader=BufferedTail('missing-test-log')
            try:
                self.wait_for(lambda:reader._error is not None)
                with self.assertRaisesRegex(RuntimeError,'log reader failed'):reader.sample()
            finally:reader.close()


if __name__=='__main__':unittest.main()
