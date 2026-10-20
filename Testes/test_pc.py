"""Testes locais: parser e transporte real por porta pseudo-terminal Linux.
Execute: python3 -m unittest discover -s Testes -v (na raiz do pacote).
"""
import importlib.util
import math
import os
from pathlib import Path
import queue
import sys
import threading
import time
import unittest

source = Path(__file__).resolve().parents[1] / 'Windows' / 'rotor_pc.py'
sys.path.insert(0, str(source.parent))
spec = importlib.util.spec_from_file_location('rotor_pc', source)
pc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pc
spec.loader.exec_module(pc)


class InputTests(unittest.TestCase):
    def test_angles(self):
        for value, expected in [('0',0), ('360',360), (' 135,5 ',135.5), ('90.25',90.25)]:
            self.assertEqual(pc.parse_angle(value), expected)
        for value in ('nan', 'inf', '-1', '361', '', 'x', '1,2,3'):
            with self.assertRaises(ValueError): pc.parse_angle(value)

    def test_frames(self):
        s = pc.Status.parse('STAT,359.0,-1.0,2.0,3,-1,70,-1.0,0,0')
        self.assertEqual(s.target, -1)
        self.assertEqual(s.direction, -1)
        s = pc.Status.parse('STAT,0.0,360.0,97.0,0,0,0,NA,0,1')
        self.assertIsNone(s.target)
        bad = ('STAT,nan,1,2,0,0,0,NA,0,0',
               'STAT,120,120,40,9,0,0,NA,0,0',
               'STAT,120,120,101,0,0,0,NA,0,0',
               'STAT,120,120,40,3,1,70,NA,0,0',
               'STAT,120,120,40,0,0,0,180,0,0', 'STAT,0,0')
        for value in bad:
            with self.assertRaises(ValueError): pc.Status.parse(value)

    def test_demo_move_stop(self):
        link = pc.DemoLink()
        link.position = 358
        link.send('MOVE,0')
        self.assertEqual(link.target, 360)
        link.send('STOP')
        self.assertEqual(link.mode, 0)
        self.assertEqual(link.pwm, 0)

    def test_queue_stop_priority(self):
        # Testa a caixa de comandos sem abrir porta.
        link = object.__new__(pc.SerialLink)
        from collections import deque
        link.pending = deque()
        link.lock = threading.Lock()
        link.quit = threading.Event()
        link.verified = True
        link.send('MOVE,200')
        link.send('JOG,R')
        link.send('PING')
        link.send('STOP')
        self.assertEqual([s for _,s in link.pending], ['STOP'])


@unittest.skipUnless(os.name == 'posix' and pc.serial is not None, 'Requer PTY Linux e pySerial')
class TransportTests(unittest.TestCase):
    def setUp(self):
        import pty
        self.master, self.slave = pty.openpty()
        self.link = pc.SerialLink(os.ttyname(self.slave))
        self.stop_event = threading.Event()
        self.commands = []
        self.thread = threading.Thread(target=self.device, daemon=True)
        self.thread.start()

    def device(self):
        import select
        buf = bytearray()
        last_frame = 0
        identified = False
        while not self.stop_event.is_set():
            ready, _, _ = select.select([self.master], [], [], .02)
            if ready:
                try: data = os.read(self.master, 512)
                except OSError: return
                buf.extend(data)
                while b'\n' in buf:
                    line, _, rest = buf.partition(b'\n')
                    buf = bytearray(rest)
                    cmd = line.decode('ascii',errors='ignore').strip()
                    self.commands.append(cmd)
                    if cmd == 'HELLO':
                        # Inicializacao pode ter identidade duplicada, como no Uno.
                        os.write(self.master, b'BOOT,1.2\nROTOR,2,1.2\nSPEED,6\nROTOR,2,1.2\n')
                        identified = True
                    elif cmd == 'SPEED?':
                        os.write(self.master,b'SPEED,6\n')
                    elif cmd.startswith('SPEED,'):
                        os.write(self.master,b'OK,SPEED\n'+cmd.encode()+b'\n')
            if identified and time.monotonic()-last_frame > .1:
                os.write(self.master, b'STAT,120.0,120.0,34.1,0,0,0,NA,0,0\n')
                last_frame = time.monotonic()

    def wait_event(self, desired, timeout=2):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            try: kind,payload = self.link.events.get(timeout=.05)
            except queue.Empty: continue
            if kind == 'error': self.fail(payload)
            if kind == desired: return payload
        self.fail('Evento não recebido: '+desired)

    def tearDown(self):
        self.link.close()
        self.link.thread.join(timeout=1)
        self.stop_event.set()
        self.thread.join(timeout=1)
        os.close(self.master)
        os.close(self.slave)

    def test_handshake_and_stop(self):
        self.wait_event('identified')
        s = self.wait_event('status')
        self.assertEqual(s.azimuth, 120)
        self.link.send('MOVE,180.000')
        time.sleep(.1)
        self.link.send('STOP')
        time.sleep(.15)
        self.assertIn('MOVE,180.000',self.commands)
        self.assertIn('STOP',self.commands)
        self.assertNotIn('PING',self.commands)  # worker nao cria heartbeat proprio.

    def test_speed_round_trip(self):
        self.wait_event('identified')
        self.assertEqual(self.wait_event('speed'),6)
        self.link.send('SPEED,3')
        self.assertEqual(self.wait_event('speed'),3)
        self.assertIn('SPEED,3',self.commands)

    def test_board_reset_disconnects(self):
        self.wait_event('identified')
        self.wait_event('status')
        os.write(self.master,b'BOOT,1.2\nROTOR,2,1.2\n')
        end=time.monotonic()+1
        error=None
        while time.monotonic()<end:
            try: kind,payload=self.link.events.get(timeout=.05)
            except queue.Empty: continue
            if kind=='error': error=payload;break
        self.assertIsNotNone(error)
        self.assertEqual(error,'board_reset')

    def test_partial_frame_and_no_heartbeat(self):
        self.wait_event('identified')
        self.wait_event('status')
        self.stop_event.set();self.thread.join(timeout=1)
        os.write(self.master,b'STAT,10.0,10.0,4.8,0,0,0,NA,0')
        time.sleep(.04)
        os.write(self.master,b',0\n')
        end=time.monotonic()+.5
        found=False
        while time.monotonic()<end:
            try: kind,payload=self.link.events.get(timeout=.05)
            except queue.Empty: continue
            if kind=='status' and payload.azimuth==10:found=True;break
        self.assertTrue(found)
        self.assertNotIn('PING',self.commands)


if __name__ == '__main__': unittest.main()
