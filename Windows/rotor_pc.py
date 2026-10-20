"""Rotor PU2PTU 1.3.0. Python 3.11+ / Tk / pySerial 3.5.
Controle de movimento no Arduino; Windows envia comandos e acompanha estado.
Execute --simular para experimentar sem hardware. Nao substitui ensaio real.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import math
import queue
import sys
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

from rotor_windows import configure_process, configure_window
from rotor_geo import Station, locator_center, bearing_distance, canonical_locator
from rotor_map import SettingsStore, MapPanel, StationPanel
from rotor_i18n import Translator, LANGUAGES, TEXT, flag_image
from PIL import ImageTk

PWM_LEVELS = (70, 90, 110, 140, 175, 220)

VERSION = "1.3.0"
FIRMWARE_VERSION = "1.2"
MODES = {0: "Parado", 1: "Botões físicos", 2: "Manual pelo computador",
         3: "Apontamento automático", 4: "Falha — pressione PARAR após corrigir", 5: "Configuração local"}
REASONS = {0: "Parada pelo operador", 1: "Alvo atingido", 2: "Limite de curso",
           3: "Comunicação interrompida", 4: "Leitura do sensor inválida",
           5: "Sem mudança de posição por 8 s", 6: "Tempo de movimento excedido",
           7: "Controle pelos botões físicos", 8: "Dois botões físicos pressionados", 9: "Configuração local"}
ERRORS = {"LOCAL": "Os botões físicos têm o controle. Solte-os para usar o PC.",
          "FAULT": "Falha no rotor. Corrija a causa e pressione PARAR.",
          "ANGLE": "Ângulo inválido: use de 0° a 360°.",
          "COMMAND": "Comando não reconhecido pelo firmware.",
          "LINE": "Uma linha serial inválida foi descartada."}
DIRECTIONS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S",
              "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
BG = "#111820"
PANEL = "#1c2834"
FG = "#e5edf5"
MUTED = "#9dafc0"
CYAN = "#5ed4ee"
GREEN = "#70dfae"
RED = "#ff757d"


def parse_angle(text: str) -> float:
    """Aceita vírgula decimal; rejeita NaN/infinito e valores fora do curso."""
    value = float(text.strip().replace(",", "."))
    if not math.isfinite(value) or not 0 <= value <= 360:
        raise ValueError("Informe um ângulo de 0° a 360°.")
    return value


@dataclass(frozen=True)
class Status:
    azimuth: float
    position: float
    bar: float
    mode: int
    direction: int
    pwm: int
    target: float | None
    limit: int
    reason: int

    @classmethod
    def parse(cls, line: str) -> Status:
        p = line.split(",")
        if len(p) != 10 or p[0] != "STAT":
            raise ValueError("Telemetria incompleta")
        az, pos, bar = map(float, p[1:4])
        mode, direction, pwm = map(int, p[4:7])
        target = None if p[7] == "NA" else float(p[7])
        limit, reason = map(int, p[8:10])
        values = (az, pos, bar) + (() if target is None else (target,))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Telemetria não finita")
        if not (0 <= az <= 360 and -20 <= pos <= 400 and 0 <= bar <= 100
                and mode in MODES and direction in (-1, 0, 1)
                and 0 <= pwm <= 255 and limit in (-1, 0, 1) and reason in REASONS):
            raise ValueError("Telemetria fora dos limites")
        if target is not None and not -5 <= target <= 365:
            raise ValueError("Alvo mecânico inválido")
        if (mode == 3) != (target is not None):
            raise ValueError("Alvo incompatível com o modo")
        return cls(az, pos, bar, mode, direction, pwm, target, limit, reason)


class SerialLink:
    """Somente esta thread usa a porta. Heartbeat depende do loop da janela.

    Não mantém JOG nem PING automaticamente: travamento da janela deixa
    expirar os prazos no Arduino. STOP limpa comandos pendentes.
    """
    def __init__(self, port: str):
        self.port = port
        self.events = queue.Queue(maxsize=128)
        self.pending: deque[tuple[float, str]] = deque()
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.verified = False
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _event(self, kind: str, payload=None):
        try:
            self.events.put_nowait((kind, payload))
        except queue.Full:
            self.quit.set()  # UI travada: para ao encerrar e deixa expirar o link.

    def send(self, command: str):
        if "\n" in command or "\r" in command or len(command) > 35:
            raise ValueError("Comando inválido")
        with self.lock:
            if command == "STOP":
                self.pending.clear()
                self.pending.append((time.monotonic(), command))
            elif self.verified and not self.quit.is_set():
                # Evita acumular renovações redundantes em uma conexão lenta.
                if command == "PING" or command.startswith("JOG,"):
                    self.pending = deque((t, c) for t, c in self.pending
                                         if c != command)
                if len(self.pending) >= 16:
                    self.pending.clear()
                    self.pending.append((time.monotonic(), "STOP"))
                    self.quit.set()
                else:
                    self.pending.append((time.monotonic(), command))

    def close(self):
        self.send("STOP")
        self.quit.set()

    def _worker(self):
        connection = None
        try:
            if serial is None:
                raise RuntimeError("serial_missing")
            connection = serial.Serial(self.port, 115200, timeout=0.03,
                                       write_timeout=0.15)
            self._event("opened")
            start = time.monotonic()
            hello_at = 0.0
            rx = bytearray()
            overflow = False
            last_status = start

            def write(command):
                payload = (command + "\n").encode("ascii")
                if connection.write(payload) != len(payload):
                    raise RuntimeError("serial_partial")

            while not self.quit.is_set():
                now = time.monotonic()
                if not self.verified:
                    if now - start > 6:
                        raise RuntimeError("firmware_timeout")
                    if now - hello_at >= 0.5:
                        write("STOP")
                        write("HELLO")
                        hello_at = now
                elif now - last_status > 1.0:
                    raise RuntimeError("telemetry_missing")
                with self.lock:
                    commands = list(self.pending)
                    self.pending.clear()
                for sent_at, command in commands:
                    if command == "STOP" or time.monotonic() - sent_at < 0.30:
                        write(command)
                data = connection.read(min(max(connection.in_waiting, 1), 256))
                for byte in data:
                    if byte == 10:
                        if not overflow and rx:
                            line = rx.decode("ascii", errors="strict").strip()
                            if line.startswith("BOOT,") and self.verified:
                                raise RuntimeError("board_reset")
                            elif line.startswith("ROTOR,"):
                                if line != "ROTOR,2,1.2":
                                    raise RuntimeError("firmware_incompatible")
                                if not self.verified:
                                    self.verified = True
                                    last_status = time.monotonic()
                                    write("STOP")
                                    self._event("identified", FIRMWARE_VERSION)
                            elif self.verified and line.startswith("STAT,"):
                                try:
                                    state = Status.parse(line)
                                except ValueError:
                                    pass  # Uma linha corrompida não renova a validade.
                                else:
                                    last_status = time.monotonic()
                                    self._event("status", state)
                            elif self.verified and line.startswith("SPEED,"):
                                if len(line) == 7 and line[6] in "123456":
                                    self._event("speed", int(line[6]))
                            elif self.verified and (line.startswith("ERR,") or
                                                    line.startswith("OK,")):
                                self._event("reply", line)
                        rx.clear()
                        overflow = False
                    elif byte != 13 and not overflow:
                        if len(rx) < 180:
                            rx.append(byte)
                        else:
                            overflow = True
                            rx.clear()
        except (OSError, ValueError, RuntimeError) as exc:
            self._event("error", str(exc))
        finally:
            self.verified = False
            if connection is not None:
                try:
                    connection.write(b"STOP\n")
                except (OSError, ValueError):
                    pass
                try:
                    connection.close()
                except OSError:
                    pass
            self._event("closed")


class DemoLink:
    """Prévia de interface independente; a validação do firmware usa o .ino real."""
    def __init__(self):
        self.events = queue.Queue()
        self.verified = True
        self.position = 125.0
        self.target = None
        self.direction = 0
        self.mode = 0
        self.reason = 0
        self.pwm = 0.0
        self.command_start = time.monotonic()
        self.last_tick = time.monotonic()
        self.last_ping = self.last_tick
        self.last_jog = self.last_tick
        self.closed = False
        self.speed_level = 6
        self.events.put(("identified", FIRMWARE_VERSION))
        self.events.put(("speed", self.speed_level))

    def send(self, command):
        now = time.monotonic()
        if command == "STOP":
            self.mode = self.direction = 0
            self.pwm = 0
            self.target = None
            self.reason = 0
        elif command == "PING":
            self.last_ping = now
        elif command == "SPEED?":
            self.events.put(("speed", self.speed_level))
        elif command.startswith("SPEED,"):
            if self.mode == 5:
                self.events.put(("reply", "ERR,CONFIG"))
            elif len(command) == 7 and command[6] in "123456":
                self.speed_level = int(command[6])
                self.pwm = min(self.pwm, PWM_LEVELS[self.speed_level-1])
                self.events.put(("speed", self.speed_level))
            else:
                self.events.put(("reply", "ERR,SPEED"))
        elif self.mode == 5:
            self.events.put(("reply", "ERR,CONFIG"))
        elif command.startswith("JOG,"):
            direction = -1 if command.endswith("L") else 1
            if self.mode != 2 or self.direction != direction:
                self.command_start = now
                self.pwm = 70
            self.direction = direction
            self.mode = 2
            self.reason = 0
            self.target = None
            self.last_jog = self.last_ping = now
        elif command.startswith("MOVE,"):
            az = parse_angle(command[5:]) % 360
            candidates = [az + 360*k for k in (-1, 0, 1)
                          if -4.09 <= az + 360*k <= 364.09]
            self.target = min(candidates, key=lambda p: abs(p - self.position))
            self.direction = 1 if self.target >= self.position else -1
            self.mode = 3
            self.reason = 0
            self.pwm = 70
            self.command_start = self.last_ping = now
            self.events.put(("reply", "OK,MOVE"))

    def tick(self):
        now = time.monotonic()
        dt = min(now - self.last_tick, .15)
        self.last_tick = now
        limit = -1 if self.position >= 368.18 else (1 if self.position <= -8.18 else 0)
        if self.mode in (2, 3):
            if now - self.last_ping > 1 or (self.mode == 2 and now - self.last_jog > .55):
                self.send("STOP")
                self.reason = 3
            elif (limit == -1 and self.direction == 1) or (limit == 1 and self.direction == -1):
                self.send("STOP")
                self.reason = 2
            elif self.mode == 3 and (abs(self.target - self.position) <= 1 or
                                     (self.target - self.position)*self.direction <= 0):
                self.send("STOP")
                self.reason = 1
            else:
                if self.mode == 2:
                    steps = (70, 90, 110, 140, 175, 220)
                    self.pwm = steps[min(self.speed_level-1, int((now-self.command_start)/.5))]
                else:
                    wanted = 70 + (PWM_LEVELS[self.speed_level-1]-70)*max(0, min(1, (abs(self.target-self.position)-1)/30))
                    change = 50*dt
                    self.pwm += max(-change, min(change, wanted-self.pwm))
                self.pwm = min(self.pwm, PWM_LEVELS[self.speed_level-1])
                self.position += self.direction*(self.pwm/220)*8*dt
        az = self.position % 360
        bar = max(0, min(100, (self.position+8.18)/376.36*100))
        self.events.put(("status", Status(az, self.position, bar, self.mode,
                          self.direction, int(self.pwm), self.target, limit, self.reason)))

    def close(self):
        self.send("STOP")
        self.closed = True
        self.verified = False


class RotorApp:
    def __init__(self, root: tk.Tk, simulate: bool = False, *, settings_dir=None, tile_store=None):
        self.root, self.simulate = root, simulate
        families = {str(f).casefold() for f in root.tk.call('font', 'families')}
        self.font_family = next((f for f in ('Segoe UI','DejaVu Sans','Liberation Sans','Helvetica')
                                 if f.casefold() in families), 'TkDefaultFont')
        self.settings_store = SettingsStore(settings_dir)
        self.map_settings = self.settings_store.load()
        self.t = Translator(self.map_settings['language'])
        self.tile_store = tile_store
        self.save_timer = None
        self.save_error = self.closing = False
        self.link = None
        self.ready = False
        self.jog = 0
        self.jog_source = None
        self.last_state = None
        self.last_rx = self.last_ping = self.last_jog = 0.0
        self.last_logged = self.last_error = None
        self.speed_level = self.pending_speed = None
        self.connection_state = 'disconnected'
        self.settings_open = False
        self.localized = []
        self.log_entries = deque(maxlen=100)
        self.grid_error = None
        self.port, self.angle = tk.StringVar(), tk.StringVar(value='180')
        self.connection_text, self.azimuth_text = tk.StringVar(), tk.StringVar(value='—°')
        self.cardinal_text, self.motion_text = tk.StringVar(), tk.StringVar()
        self.detail_text, self.target_text = tk.StringVar(), tk.StringVar()
        self.speed_value, self.speed_hint = tk.StringVar(), tk.StringVar()
        self.grid_destination = tk.StringVar(value=self.map_settings['target_grid'])
        self.grid_result = tk.StringVar()
        root.configure(bg=BG)
        root.geometry('1280x840'); root.minsize(980,720)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._build()
        self.set_window_icon()
        self.refresh_language()
        if self.grid_destination.get() and self.map_panel.station:
            self.calculate_grid(silent=True)
        self.refresh_ports()
        root.bind_all('<Escape>', self.stop)
        root.bind('<KeyPress-Left>', lambda e:self.key_start(e,-1))
        root.bind('<KeyPress-Right>', lambda e:self.key_start(e,1))
        root.bind('<KeyRelease-Left>', lambda e:self.key_release(e,-1))
        root.bind('<KeyRelease-Right>', lambda e:self.key_release(e,1))
        root.bind('<FocusOut>',self.focus_out)
        root.bind('<Unmap>',lambda e:self.release_jog() if e.widget is root else None)
        root.bind_all('<ButtonRelease-1>',self.mouse_release,add='+')
        self._update_enabled()
        root.after(50,self.tick)
        if simulate:root.after(100,self.toggle_connection)

    def _label(self,parent,key=None,variable=None,size=11,color=FG,**kw):
        widget=tk.Label(parent,text=self.t(key) if key else None,textvariable=variable,
                 bg=parent.cget('bg'),fg=color,font=(self.font_family,size),**kw)
        if key in TEXT:self.localized.append((widget,key))
        return widget

    def _button(self,parent,key,command=None,color=PANEL,**kw):
        widget=tk.Button(parent,text=self.t(key),command=command,bg=color,fg=FG,
                 activebackground='#344c61',activeforeground=FG,disabledforeground='#72808c',
                 bd=0,relief='flat',font=(self.font_family,9,'bold'),padx=3,pady=7,
                 cursor='hand2',**kw)
        if key in TEXT:self.localized.append((widget,key))
        return widget

    def _build(self):
        self.root.columnconfigure(0,weight=1);self.root.rowconfigure(0,weight=1)
        body=tk.Frame(self.root,bg=BG);body.grid(row=0,column=0,sticky='nsew')
        body.columnconfigure(1,weight=1);body.rowconfigure(0,weight=1)
        # 234 px = 60% dos 390 px da interface anterior. O texto nao alarga a coluna.
        self.left_panel=tk.Frame(body,bg=BG,width=234)
        self.left_panel.grid(row=0,column=0,sticky='ns');self.left_panel.grid_propagate(False)
        self.left_panel.columnconfigure(0,weight=1);self.left_panel.rowconfigure(0,weight=1)
        self.left_canvas=tk.Canvas(self.left_panel,bg=BG,bd=0,highlightthickness=0,width=234)
        self.left_canvas.grid(row=0,column=0,sticky='nsew')
        self.left_scroll=ttk.Scrollbar(self.left_panel,orient='vertical',command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=self.left_scroll.set)
        frame=tk.Frame(self.left_canvas,bg=BG,padx=12,pady=12)
        self.left_content=frame
        self.left_window=self.left_canvas.create_window(0,0,window=frame,anchor='nw')
        self.left_canvas.bind('<Configure>',self._resize_left)
        frame.bind('<Configure>',lambda e:self.root.after_idle(self._resize_left))
        self.right_host=tk.Frame(body,bg=BG)
        self.right_host.grid(row=0,column=1,sticky='nsew')
        self.right_host.columnconfigure(0,weight=1);self.right_host.rowconfigure(0,weight=1)
        self.map_panel=MapPanel(self.right_host,self.font_family,self.map_settings,self.map_changed,
                        self.edit_station,tile_store=self.tile_store,translator=self.t)
        self.map_panel.grid(row=0,column=0,sticky='nsew')
        self.station_panel=StationPanel(self.right_host,self.font_family,self.t,
                                      self.apply_station_settings,self.close_station)
        self.station_panel.grid(row=0,column=0,sticky='nsew');self.station_panel.grid_remove()
        self._label(frame,'ROTOR · PU2PTU',size=16,anchor='w').pack(fill='x')
        self._label(frame,'subtitle',size=10,color=MUTED,anchor='w',wraplength=208).pack(fill='x',pady=(0,9))
        connection=tk.Frame(frame,bg=BG);connection.pack(fill='x')
        self.combo=ttk.Combobox(connection,textvariable=self.port,state='readonly',width=7)
        self.combo.pack(side='left',fill='x',expand=True,padx=(0,5))
        self.refresh_button=self._button(connection,'↻',self.refresh_ports)
        self.refresh_button.pack(side='left',padx=(0,5))
        self.connect_button=self._button(connection,'connect',self.toggle_connection)
        self.connect_button.pack(side='left')
        self._label(frame,variable=self.connection_text,size=9,color=MUTED,anchor='w',
                    justify='left',wraplength=208).pack(fill='x',pady=(5,9))
        display=tk.Frame(frame,bg=PANEL,pady=6);display.pack(fill='x')
        self._label(display,'current_azimuth',size=10,color=MUTED).pack()
        self._label(display,variable=self.azimuth_text,size=42,color=CYAN).pack()
        self._label(display,variable=self.cardinal_text,size=13,color='#ffd375').pack()
        self.motion_label=self._label(display,variable=self.motion_text,size=10,color=GREEN,
                                      wraplength=196,justify='center')
        self.motion_label.pack(pady=(4,0))
        self.bar=tk.Canvas(frame,bg=BG,height=24,bd=0,highlightthickness=0)
        self.bar.pack(fill='x',pady=(9,0));self.bar.bind('<Configure>',lambda e:self.draw_bar())
        controls=tk.Frame(frame,bg=BG);controls.pack(fill='x',pady=(8,4))
        controls.columnconfigure((0,1,2),weight=1,uniform='buttons')
        self.left_button=self._button(controls,'left');self.left_button.grid(row=0,column=0,sticky='ew',padx=(0,3))
        self.stop_button=self._button(controls,'stop',self.stop,color='#963d4a');self.stop_button.grid(row=0,column=1,sticky='ew',padx=2)
        self.right_button=self._button(controls,'right');self.right_button.grid(row=0,column=2,sticky='ew',padx=(3,0))
        for button in (self.left_button,self.right_button):
            button.configure(font=(self.font_family,9),padx=1)
        for button,direction in ((self.left_button,-1),(self.right_button,1)):
            button.bind('<ButtonPress-1>',lambda e,d=direction:self.start_jog(d,'mouse'))
            button.bind('<Leave>',lambda e:self.release_jog() if self.jog_source=='mouse' else None)
        self._label(frame,'hold_hint',size=9,color=MUTED,wraplength=208,justify='left').pack(fill='x',pady=(0,8))
        self._label(frame,'max_speed',size=10,color=MUTED,anchor='w',wraplength=208).pack(fill='x')
        self.speed_combo=ttk.Combobox(frame,textvariable=self.speed_value,state='disabled',width=16)
        self.speed_combo.pack(fill='x',pady=(4,2));self.speed_combo.bind('<<ComboboxSelected>>',self.change_speed)
        self._label(frame,variable=self.speed_hint,size=9,color=MUTED,anchor='w',
                    wraplength=208,justify='left').pack(fill='x',pady=(0,6))
        self._label(frame,variable=self.target_text,size=10,color=MUTED,anchor='w',
                    wraplength=208,justify='left').pack(fill='x')
        target=tk.Frame(frame,bg=BG);target.pack(fill='x',pady=(5,8))
        self.entry=tk.Entry(target,textvariable=self.angle,font=(self.font_family,16),bg=PANEL,
                            fg=FG,insertbackground=FG,relief='flat',width=6)
        self.entry.pack(side='left',fill='x',expand=True,ipady=4,padx=(0,6));self.entry.bind('<Return>',self.move)
        self.move_button=self._button(target,'point',self.move,color='#23617a');self.move_button.pack(side='right')
        self._label(frame,'grid_label',color=MUTED,anchor='w',size=10,
                    wraplength=208,justify='left').pack(fill='x',pady=(3,2))
        grid=tk.Frame(frame,bg=BG);grid.pack(fill='x',pady=(2,4))
        self.grid_entry=tk.Entry(grid,textvariable=self.grid_destination,font=(self.font_family,12),
                    bg=PANEL,fg=FG,insertbackground=FG,relief='flat',width=7,
                    validate='key',validatecommand=(self.root.register(lambda v:len(v)<=6),'%P'))
        self.grid_entry.pack(side='left',fill='x',expand=True,ipady=4,padx=(0,6))
        self.grid_entry.bind('<Return>',lambda e:self.calculate_grid())
        self.calculate_button=self._button(grid,'calculate',self.calculate_grid);self.calculate_button.pack(side='right')
        self._label(frame,variable=self.grid_result,color='#ffd375',anchor='w',justify='left',
                    wraplength=208,size=10).pack(fill='x',pady=(0,4))
        actions=tk.Frame(frame,bg=BG);actions.pack(fill='x',pady=(0,7))
        self.grid_move_button=self._button(actions,'point_grid',self.move_grid,color='#23617a')
        self.grid_move_button.pack(fill='x')
        self.clear_grid_button=self._button(actions,'clear',self.clear_grid)
        self.clear_grid_button.pack(fill='x',pady=(3,0))
        self._label(frame,variable=self.detail_text,color=MUTED,anchor='w',justify='left',
                    wraplength=208,size=9).pack(fill='x')
        self.log=tk.Text(frame,height=2,width=1,bg=PANEL,fg=MUTED,bd=0,font=(self.font_family,9),
                         state='disabled',wrap='word')
        self.log.pack(fill='x',pady=(8,0))
        if self.simulate:self._label(frame,'simulation_hint',color='#ffd375',size=9,wraplength=208).pack(pady=(4,0))
        footer=tk.Frame(self.root,bg=BG,padx=12,pady=5);footer.grid(row=1,column=0,sticky='ew')
        self._label(footer,f'Rotor {VERSION} · Mario Pin – PU2PTU',size=9,color=MUTED).pack(side='left')
        flags=tk.Frame(footer,bg=BG);flags.pack(side='right')
        self.flag_buttons={};self.flag_photos=[];self.language_name=tk.StringVar()
        self._label(flags,variable=self.language_name,size=9,color=MUTED).pack(side='left',padx=(0,8))
        for language in LANGUAGES:
            photo=ImageTk.PhotoImage(flag_image(language),master=self.root);self.flag_photos.append(photo)
            wrapper=tk.Frame(flags,bg=BG);wrapper.pack(side='left',padx=3)
            button=tk.Button(wrapper,image=photo,command=lambda lang=language:self.set_language(lang),
                             bg=BG,activebackground=PANEL,bd=0,padx=3,pady=2,cursor='hand2',takefocus=True)
            button.pack()
            marker=tk.Frame(wrapper,height=2,bg=BG);marker.pack(fill='x')
            self.flag_buttons[language]=(button,marker)

    def _resize_left(self,event=None):
        if self.closing:return
        width=self.left_canvas.winfo_width()
        if width<=1:return
        self.left_canvas.itemconfigure(self.left_window,width=width)
        # A barra de rolagem também ocupa espaço: faça os textos quebrarem
        # dentro da largura útil, inclusive nas traduções mais compridas.
        def wrap_labels(parent):
            for child in parent.winfo_children():
                if isinstance(child,tk.Label) and int(child.cget('wraplength')):
                    child.configure(wraplength=max(1,width-24))
                wrap_labels(child)
        wrap_labels(self.left_content)
        required=self.left_content.winfo_reqheight()
        self.left_canvas.configure(scrollregion=(0,0,width,required))
        need=required>self.left_canvas.winfo_height()+2
        if need and not self.left_scroll.winfo_ismapped():self.left_scroll.grid(row=0,column=1,sticky='ns')
        elif not need and self.left_scroll.winfo_ismapped():self.left_scroll.grid_remove()

    def set_window_icon(self):
        configure_window(self.root)

    def set_language(self,language):
        if language not in LANGUAGES:return
        self.t.language=language
        self.refresh_language();self.map_changed()

    def refresh_language(self):
        self.root.title(f'Rotor — PU2PTU | {VERSION}'+(' | '+self.t('simulation') if self.simulate else ''))
        for widget,key in self.localized:widget.configure(text=self.t(key))
        self.language_name.set(LANGUAGES[self.t.language])
        for language,(_,marker) in self.flag_buttons.items():marker.configure(bg=CYAN if language==self.t.language else BG)
        self.speed_combo.configure(values=[self.t('speed_value',level=i) for i in range(1,7)])
        self._render_speed()
        self.map_panel.refresh_language();self.station_panel.refresh_language()
        self.connection_text.set(self.t(self.connection_state))
        if self.ready:self.connection_text.set(self.t('connected',port=self.t('simulation') if self.simulate else self.port.get(),version=FIRMWARE_VERSION))
        self._render_status();self._render_grid();self._render_log();self._update_enabled()

    def _render_speed(self):
        level=self.pending_speed[0] if self.pending_speed else self.speed_level
        self.speed_value.set(self.t('speed_value',level=level) if level else '—')
        self.speed_hint.set(self.t('speed_saving') if self.pending_speed else
                            ('' if self.speed_level else self.t('speed_wait')))

    def change_speed(self,event=None):
        level=self.speed_combo.current()+1
        if not self.ready or not self.link or not 1<=level<=6 or self.speed_combo.cget('state')=='disabled':
            self._render_speed();return
        if level==self.speed_level:return
        self.pending_speed=(level,time.monotonic())
        self.link.send(f'SPEED,{level}')
        self._render_speed();self._update_enabled()

    def apply_speed(self,level):
        if not 1<=level<=6:return
        self.speed_level=level
        if self.pending_speed and self.pending_speed[0]==level:
            self.pending_speed=None;self.log_message('speed_saved',level=level)
        self._render_speed();self._refresh_ready();self._update_enabled()

    def map_changed(self):
        if not hasattr(self,'map_panel') or self.closing:return
        if self.save_timer is not None:self.root.after_cancel(self.save_timer)
        self.save_timer=self.root.after(600,self.save_settings)

    def save_settings(self):
        self.save_timer=None
        values=self.map_panel.values()
        try:grid=canonical_locator(self.grid_destination.get()) if self.grid_destination.get().strip() else ''
        except ValueError:grid=''
        values.update(target_grid=grid,language=self.t.language)
        try:self.settings_store.save(values)
        except OSError:
            if not self.save_error:self.log_message('settings_save_error');self.save_error=True

    def edit_station(self):
        self.stop()
        self.station_panel.load(self.map_panel.station,self.map_panel.opening)
        self.settings_open=True
        self.map_panel.grid_remove();self.station_panel.grid()
        self.station_panel.name_entry.focus_set();self._update_enabled()

    def close_station(self):
        self.settings_open=False
        self.station_panel.grid_remove();self.map_panel.grid()
        self.map_panel.invalidate(True);self._update_enabled()

    def apply_station_settings(self,station,opening):
        self.map_panel.set_opening(opening)
        self.apply_station(station);self.close_station();self.save_settings()

    def apply_station(self,station):
        self.map_panel.set_station(station)
        if self.grid_destination.get().strip():self.calculate_grid(silent=True)
        else:self.grid_error=None;self._render_grid()
        self._update_enabled()

    def clear_grid(self):
        self.grid_destination.set('');self.grid_error=None
        self.map_panel.set_target(None);self._render_grid();self.map_changed()

    def _render_grid(self):
        if self.grid_error:self.grid_result.set(self.t.error(self.grid_error))
        elif self.map_panel.target:
            grid,_,_,azimuth,distance=self.map_panel.target
            self.grid_result.set(self.t('grid_result',grid=grid,azimuth=azimuth,distance=distance))
        else:self.grid_result.set(self.t('grid_prompt' if self.map_panel.station else 'grid_initial'))

    def calculate_grid(self,*,silent=False):
        if self.map_panel.station is None:
            if not silent:self.edit_station()
            return None
        try:
            grid=canonical_locator(self.grid_destination.get())
            target=self.map_panel.set_target(grid)
        except ValueError as exc:
            self.map_panel.set_target(None);self.grid_error=str(exc);self._render_grid()
            return None
        self.grid_error=None
        grid,_,_,azimuth,_=target
        self.grid_destination.set(grid);self.angle.set(f'{azimuth:.1f}')
        self._render_grid();self.map_changed()
        return azimuth

    def move_grid(self):
        if not self.ready or not self.link or self.grid_move_button.cget('state')=='disabled':return
        azimuth=self.calculate_grid()
        if azimuth is not None:self.angle.set(f'{azimuth:.3f}');self.move()

    def log_message(self,key,**values):
        self.log_entries.append((time.strftime('%H:%M:%S'),key,values));self._render_log()

    def _render_log(self):
        self.log.configure(state='normal');self.log.delete('1.0','end')
        for timestamp,key,values in self.log_entries:
            text=self.t.error(values['message']) if key=='_error' else self.t(key,**values)
            self.log.insert('end',timestamp+'  '+text+'\n')
        self.log.see('end');self.log.configure(state='disabled')

    def refresh_ports(self):
        if self.link is not None:return
        ports=['SIM'] if self.simulate else sorted(p.device for p in list_ports.comports()) if list_ports else []
        self.combo['values']=ports
        if self.port.get() not in ports:self.port.set(ports[0] if ports else '')
        self.connection_state='disconnected' if ports else 'no_ports'
        self.connection_text.set(self.t(self.connection_state))

    def toggle_connection(self):
        if self.link is not None:self.disconnect('disconnected');return
        if not self.port.get():messagebox.showinfo('COM',self.t('port_hint'));return
        if not self.simulate and serial is None:messagebox.showerror('Rotor',self.t('app_install_hint'));return
        self.last_state=None;self.last_logged=self.last_error=None
        self.ready=False;self.speed_level=self.pending_speed=None
        self.connection_state='connecting';self.connection_text.set(self.t('connecting'))
        self.detail_text.set(self.t('verifying'));self._render_speed()
        self.link=DemoLink() if self.simulate else SerialLink(self.port.get())
        self._update_enabled()

    def disconnect(self,key):
        if self.link:self.link.close()
        self.link=None;self.ready=False;self.jog=0;self.jog_source=None
        self.speed_level=self.pending_speed=None
        self.connection_state=key
        self.connection_text.set(self.t(key));self.azimuth_text.set('—°')
        self.last_state=None;self.map_panel.set_heading(None)
        self._render_status();self._render_speed();self.draw_bar();self._update_enabled()

    def _refresh_ready(self):
        valid=self.link is not None and self.link.verified and self.last_state is not None and self.speed_level is not None
        if valid and not self.ready:
            self.ready=True;self.connection_state='disconnected'
            self.connection_text.set(self.t('connected',port=self.t('simulation') if self.simulate else self.port.get(),version=FIRMWARE_VERSION))
            self.log_message('connection_established')

    def _update_enabled(self):
        connected=self.link is not None
        allow=(self.ready and self.last_state is not None and self.last_state.mode not in (1,4,5)
               and self.last_state.reason!=8 and not self.settings_open and not self.pending_speed)
        for widget in (self.left_button,self.right_button,self.move_button,self.grid_move_button):
            widget.configure(state='normal' if allow else 'disabled')
        if self.map_panel.station is None:self.grid_move_button.configure(state='disabled')
        self.stop_button.configure(state='normal' if connected else 'disabled')
        self.speed_combo.configure(state='readonly' if allow else 'disabled')
        self.connect_button.configure(text=self.t('disconnect' if connected else 'connect'))
        self.combo.configure(state='disabled' if connected else 'readonly')
        self.refresh_button.configure(state='disabled' if connected else 'normal')

    def start_jog(self,direction,source):
        if self.left_button.cget('state')=='disabled' or not self.ready or not self.link:return 'break'
        if self.jog and self.jog!=direction:self.release_jog();return 'break'
        if self.jog==direction:return 'break'
        self.jog,self.jog_source=direction,source
        self.link.send('JOG,L' if direction<0 else 'JOG,R');self.last_jog=time.monotonic()
        return 'break'

    def release_jog(self):
        if self.jog:
            self.jog=0;self.jog_source=None
            if self.link:self.link.send('STOP')

    def key_start(self,event,direction):
        if isinstance(self.root.focus_get(),(tk.Entry,ttk.Entry,ttk.Combobox,tk.Scale,ttk.Scale,tk.Text,tk.Spinbox,ttk.Spinbox)):
            return None
        return self.start_jog(direction,'keyboard')

    def key_release(self,event,direction):
        if self.jog_source=='keyboard' and self.jog==direction:self.release_jog();return 'break'

    def mouse_release(self,event):
        if self.jog_source=='mouse':self.release_jog()

    def focus_out(self,event):
        if self.closing:return
        def check():
            if not self.closing and self.root.focus_get() is None:self.release_jog()
        self.root.after(50,check)

    def stop(self,event=None):
        self.jog=0;self.jog_source=None
        if self.link:self.link.send('STOP');self.log_message('stop_requested')
        return 'break'

    def move(self,event=None):
        if not self.ready or not self.link or self.move_button.cget('state')=='disabled':return 'break'
        self.release_jog()
        try:value=parse_angle(self.angle.get())
        except ValueError:messagebox.showerror(self.t('target_label'),self.t('err_ANGLE'));return 'break'
        self.link.send(f'MOVE,{value:.3f}');self.log_message('move_requested',angle=value)
        return 'break'

    def draw_bar(self):
        self.bar.delete('all');width=max(100,self.bar.winfo_width())
        self.bar.create_rectangle(2,4,width-2,20,outline=MUTED,width=1)
        if self.last_state is not None:
            fraction=self.last_state.bar/100;x=5+fraction*(width-22)
            color=RED if fraction<.04 or fraction>.96 else GREEN
            self.bar.create_rectangle(x,7,x+12,17,fill=color,outline='')

    def _render_status(self):
        state=self.last_state
        if state is None:
            self.cardinal_text.set(self.t('no_telemetry' if self.link is None else 'waiting_rotor'))
            self.motion_text.set(self.t('mode_0'));self.target_text.set(self.t('target_label'))
            self.detail_text.set(self.t('select_port') if self.link is None else self.t('verifying'))
            return
        self.azimuth_text.set(f'{state.azimuth:05.1f}°')
        sector=int(((state.azimuth%360)+11.25)/22.5)%16
        directions=DIRECTIONS
        if self.t.language in ('pt','es'):directions=('N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO')
        elif self.t.language=='de':directions=('N','NNO','NO','ONO','O','OSO','SO','SSO','S','SSW','SW','WSW','W','WNW','NW','NNW')
        elif self.t.language=='ru':directions=('С','ССВ','СВ','ВСВ','В','ВЮВ','ЮВ','ЮЮВ','Ю','ЮЮЗ','ЮЗ','ЗЮЗ','З','ЗСЗ','СЗ','ССЗ')
        self.cardinal_text.set(directions[sector])
        arrows=''
        if state.direction:
            count=next((i for i,p in enumerate(PWM_LEVELS,1) if state.pwm<=p),6)
            arrows=('‹' if state.direction<0 else '›')*count
        self.motion_text.set(self.t(f'mode_{state.mode}')+('  '+arrows if arrows else ''))
        self.motion_label.configure(fg=RED if state.mode==4 or state.pwm>=220 else GREEN)
        self.target_text.set(self.t('active_target',target=state.target%360,remaining=abs(state.target-state.position))
                             if state.target is not None else self.t('target_label'))
        limit=self.t('left_limit' if state.limit==1 else 'right_limit' if state.limit==-1 else 'course_available')
        detail=self.t(f'reason_{state.reason}' if state.mode in (0,4) else f'mode_{state.mode}')
        self.detail_text.set(self.t('detail',detail=detail,limit=limit,pwm=state.pwm))

    def apply_status(self,state):
        self.last_state=state;self.last_rx=time.monotonic()
        self.map_panel.set_heading(state.azimuth);self._refresh_ready()
        if state.mode in (1,4,5) or state.mode==0 and state.reason in (2,3,8):self.jog=0;self.jog_source=None
        key=state.mode,state.reason,state.limit
        if key!=self.last_logged:
            if state.mode in (0,4) and state.reason!=0:self.log_message(f'reason_{state.reason}')
            self.last_logged=key
        self._render_status();self.draw_bar();self._update_enabled()

    def tick(self):
        if self.closing:return
        now=time.monotonic();link=self.link
        if link:
            if isinstance(link,DemoLink):link.tick()
            for _ in range(128):
                try:kind,payload=link.events.get_nowait()
                except queue.Empty:break
                if kind=='status':self.apply_status(payload)
                elif kind=='speed':self.apply_speed(payload)
                elif kind=='identified':self.log_message('identified',version=payload);self.last_ping=0.0
                elif kind=='reply' and payload.startswith('ERR,'):
                    code=payload.split(',',1)[1]
                    if code in ('LOCAL','FAULT','CONFIG'):self.jog=0;self.jog_source=None
                    if self.pending_speed and code in ('SPEED','CONFIG'):
                        self.pending_speed=None;self._render_speed();self._update_enabled()
                    if payload!=self.last_error:
                        self.log_message('err_'+code if 'err_'+code in TEXT else '_error',**({} if 'err_'+code in TEXT else {'message':payload}))
                        self.last_error=payload
                elif kind=='error':
                    self.log_message('_error',message=payload);self.disconnect('connection_error');break
                elif kind=='closed':self.disconnect('connection_closed');break
            if self.link is link:
                if self.last_state is not None and now-self.last_rx>.8:
                    self.log_message('telemetry_expired');self.disconnect('reason_3')
                else:
                    if link.verified and now-self.last_ping>=.2:link.send('PING');self.last_ping=now
                    if self.jog and self.ready and now-self.last_jog>=.15:
                        link.send('JOG,L' if self.jog<0 else 'JOG,R');self.last_jog=now
                    if self.pending_speed and now-self.pending_speed[1]>1.5:
                        self.pending_speed=None;self.log_message('speed_timeout')
                        # Falha de confirmacao encerra a conexao, nunca libera movimento
                        # com um limite que o operador pode acreditar ter sido aplicado.
                        self.disconnect('connection_error')
        self.root.after(50,self.tick)

    def close(self):
        self.closing=True;self.release_jog()
        if self.save_timer is not None:self.root.after_cancel(self.save_timer)
        self.save_settings();self.map_panel.close()
        link=self.link
        if link:link.close()
        deadline=time.monotonic()+.45
        def finish():
            if isinstance(link,SerialLink) and link.thread.is_alive() and time.monotonic()<deadline:self.root.after(20,finish)
            else:
                for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
                self.root.destroy()
        finish()


def main():
    parser = argparse.ArgumentParser(description="Rotor PU2PTU 1.3.0")
    parser.add_argument("--simular", action="store_true", help="Abre demonstração sem Arduino")
    args = parser.parse_args()
    configure_process()
    root = tk.Tk()
    RotorApp(root, args.simular)
    root.mainloop()


if __name__ == "__main__":
    main()
