"""Rotor PU2PTU 1.2.1. Python 3.11+ / Tk / pySerial 3.5.
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
from rotor_map import SettingsStore, MapPanel, StationDialog

VERSION = "1.2.1"
FIRMWARE_VERSION = "1.1"
MODES = {0: "Parado", 1: "Botões físicos", 2: "Manual pelo computador",
         3: "Apontamento automático", 4: "Falha — pressione PARAR após corrigir"}
REASONS = {0: "Parada pelo operador", 1: "Alvo atingido", 2: "Limite de curso",
           3: "Comunicação interrompida", 4: "Leitura do sensor inválida",
           5: "Sem mudança de posição por 8 s", 6: "Tempo de movimento excedido",
           7: "Controle pelos botões físicos", 8: "Dois botões físicos pressionados"}
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
                raise RuntimeError("pySerial ausente. Execute INSTALAR.bat.")
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
                    raise RuntimeError("Escrita serial incompleta")

            while not self.quit.is_set():
                now = time.monotonic()
                if not self.verified:
                    if now - start > 6:
                        raise RuntimeError("O rotor não respondeu com firmware 1.1. "
                                           "Confira a COM e grave o novo .ino.")
                    if now - hello_at >= 0.5:
                        write("STOP")
                        write("HELLO")
                        hello_at = now
                elif now - last_status > 1.0:
                    raise RuntimeError("Sem telemetria. Confira o cabo USB e a alimentação.")
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
                                raise RuntimeError("Arduino reiniciou durante a conexão. "
                                                   "Conecte novamente.")
                            elif line.startswith("ROTOR,"):
                                if line != "ROTOR,1,1.1":
                                    raise RuntimeError("Firmware incompatível: " + line)
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
        self.events.put(("identified", FIRMWARE_VERSION))

    def send(self, command):
        now = time.monotonic()
        if command == "STOP":
            self.mode = self.direction = 0
            self.pwm = 0
            self.target = None
            self.reason = 0
        elif command == "PING":
            self.last_ping = now
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
                    self.pwm = steps[min(5, int((now-self.command_start)/.5))]
                else:
                    wanted = 70 + 150*max(0, min(1, (abs(self.target-self.position)-1)/30))
                    change = 50*dt
                    self.pwm += max(-change, min(change, wanted-self.pwm))
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
        self.root = root
        families = {str(f).casefold() for f in root.tk.call("font", "families")}
        self.font_family = next((f for f in ("Segoe UI", "DejaVu Sans", "Liberation Sans",
                                  "Helvetica", "Bitstream Charter")
                                 if f.casefold() in families), "TkDefaultFont")
        self.simulate = simulate
        self.settings_store = SettingsStore(settings_dir)
        self.map_settings = self.settings_store.load()
        self.save_timer = None
        self.save_error = False
        self.tile_store = tile_store
        self.link = None
        self.ready = False
        self.jog = 0
        self.jog_source = None
        self.last_state = None
        self.last_rx = 0.0
        self.last_ping = 0.0
        self.last_jog = 0.0
        self.last_logged = None
        self.last_error = None
        self.closing = False
        root.title(f"Rotor — PU2PTU | {VERSION}" + (" | SIMULAÇÃO" if simulate else ""))
        root.configure(bg=BG)
        root.geometry("1280x800")
        root.minsize(1040, 700)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.port = tk.StringVar()
        self.angle = tk.StringVar(value="180")
        self.connection_text = tk.StringVar(value="Desconectado")
        self.azimuth_text = tk.StringVar(value="—°")
        self.cardinal_text = tk.StringVar(value="AGUARDANDO ROTOR")
        self.motion_text = tk.StringVar(value="Parado")
        self.detail_text = tk.StringVar(value="Selecione a porta COM e conecte.")
        self.target_text = tk.StringVar(value="Novo apontamento (0° a 360°)")
        self.grid_destination = tk.StringVar(value=self.map_settings["target_grid"])
        self.grid_result = tk.StringVar(value="Defina a estação e calcule o destino.")
        self._build()
        self.set_window_icon()
        if self.grid_destination.get() and self.map_panel.station:
            self.calculate_grid(silent=True)
        root.update_idletasks()
        required_height = max(700, root.winfo_reqheight())
        root.minsize(1040, min(required_height, 790))
        root.geometry(f"1280x{max(780, min(required_height, 880))}")
        self.refresh_ports()
        root.bind_all("<Escape>", self.stop)
        root.bind("<KeyPress-Left>", lambda e: self.key_start(e, -1))
        root.bind("<KeyPress-Right>", lambda e: self.key_start(e, 1))
        root.bind("<KeyRelease-Left>", lambda e: self.key_release(e, -1))
        root.bind("<KeyRelease-Right>", lambda e: self.key_release(e, 1))
        root.bind("<FocusOut>", self.focus_out)
        root.bind("<Unmap>", lambda e: self.release_jog() if e.widget is root else None)
        # Detecta botão do mouse perdido sem disparar JOG indefinidamente.
        root.bind_all("<ButtonRelease-1>", self.mouse_release, add="+")
        self._update_enabled()
        root.after(50, self.tick)
        if simulate:
            root.after(100, self.toggle_connection)

    def _label(self, parent, text=None, variable=None, size=11, color=FG, **kw):
        return tk.Label(parent, text=text, textvariable=variable, bg=parent.cget("bg"),
                        fg=color, font=(self.font_family, size), **kw)

    def _button(self, parent, text, command=None, color=PANEL, **kw):
        return tk.Button(parent, text=text, command=command, bg=color, fg=FG,
                         activebackground="#344c61", activeforeground=FG,
                         disabledforeground="#72808c", bd=0, relief="flat",
                         font=(self.font_family, 10, "bold"), padx=10, pady=7,
                         cursor="hand2", **kw)

    def _build(self):
        layout = tk.Frame(self.root, bg=BG)
        layout.pack(fill="both", expand=True)
        layout.columnconfigure(0, minsize=390)
        layout.columnconfigure(1, weight=1, minsize=600)
        layout.rowconfigure(0, weight=1)
        frame = tk.Frame(layout, bg=BG, padx=18, pady=14)
        frame.grid(row=0, column=0, sticky="nsew")
        self.map_panel = MapPanel(layout, self.font_family, self.map_settings,
                                 self.map_changed, self.edit_station, tile_store=self.tile_store)
        self.map_panel.grid(row=0, column=1, sticky="nsew")
        self._label(frame, "ROTOR · PU2PTU", size=20, color=FG, anchor="w").pack(fill="x")
        self._label(frame, "Controle de azimute  •  USB", color=MUTED,
                    anchor="w").pack(fill="x", pady=(0, 12))
        connection = tk.Frame(frame, bg=BG)
        connection.pack(fill="x")
        self.combo = ttk.Combobox(connection, textvariable=self.port, state="readonly", width=10)
        self.combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.refresh_button = self._button(connection, "Atualizar", self.refresh_ports)
        self.refresh_button.pack(side="left", padx=(0, 8))
        self.connect_button = self._button(connection, "Conectar", self.toggle_connection)
        self.connect_button.pack(side="left")
        self._label(frame, variable=self.connection_text, color=MUTED, anchor="w").pack(fill="x", pady=(6, 12))
        display = tk.Frame(frame, bg=PANEL, pady=8)
        display.pack(fill="x")
        self._label(display, "AZIMUTE ATUAL", size=10, color=MUTED).pack()
        self._label(display, variable=self.azimuth_text, size=42, color=CYAN).pack()
        self._label(display, variable=self.cardinal_text, size=13, color="#ffd375").pack()
        self.motion_label = self._label(display, variable=self.motion_text, color=GREEN)
        self.motion_label.pack(pady=(6, 0))
        labels = tk.Frame(frame, bg=BG)
        labels.pack(fill="x", pady=(12, 2))
        self._label(labels, "LIMITE ESQUERDO", size=9, color=MUTED).pack(side="left")
        self._label(labels, "LIMITE DIREITO", size=9, color=MUTED).pack(side="right")
        self.bar = tk.Canvas(frame, bg=BG, height=24, bd=0, highlightthickness=0)
        self.bar.pack(fill="x")
        self.bar.bind("<Configure>", lambda e: self.draw_bar())
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill="x", pady=(12, 4))
        controls.columnconfigure((0, 1, 2), weight=1, uniform="buttons")
        self.left_button = self._button(controls, "< ESQ")
        self.left_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stop_button = self._button(controls, "PARAR", self.stop, color="#963d4a")
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.right_button = self._button(controls, "DIR >")
        self.right_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        for button, direction in ((self.left_button, -1), (self.right_button, 1)):
            button.bind("<ButtonPress-1>", lambda e, d=direction: self.start_jog(d, "mouse"))
            button.bind("<Leave>", lambda e: self.release_jog() if self.jog_source == "mouse" else None)
        self._label(frame, "Mantenha pressionado para girar · Esc para parar", size=9,
                    color=MUTED).pack(pady=(0, 12))
        self._label(frame, variable=self.target_text, anchor="w", color=MUTED).pack(fill="x")
        target_row = tk.Frame(frame, bg=BG)
        target_row.pack(fill="x", pady=(6, 8))
        self.entry = tk.Entry(target_row, textvariable=self.angle, font=(self.font_family, 16),
                              bg=PANEL, fg=FG, insertbackground=FG, relief="flat", width=10)
        self.entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 10))
        self.entry.bind("<Return>", self.move)
        self.move_button = self._button(target_row, "APONTAR", self.move, color="#23617a")
        self.move_button.pack(side="right")
        self._label(frame, "Destino por grid locator (até 6 caracteres)", color=MUTED,
                    anchor="w", size=10).pack(fill="x", pady=(6, 2))
        grid_row = tk.Frame(frame, bg=BG)
        grid_row.pack(fill="x", pady=(2, 4))
        self.grid_entry = tk.Entry(grid_row, textvariable=self.grid_destination,
                    font=(self.font_family, 13), bg=PANEL, fg=FG, insertbackground=FG,
                    width=10, validate="key", validatecommand=(self.root.register(lambda value: len(value) <= 6), "%P"))
        self.grid_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        self.grid_entry.bind("<Return>", lambda e: self.calculate_grid())
        self.calculate_button = self._button(grid_row, "Calcular", self.calculate_grid)
        self.calculate_button.pack(side="left", padx=(0, 5))
        self.clear_grid_button = self._button(grid_row, "Limpar", self.clear_grid)
        self.clear_grid_button.pack(side="left")
        self._label(frame, variable=self.grid_result, color="#ffd375", anchor="w", justify="left",
                    wraplength=345, size=10).pack(fill="x", pady=(0, 4))
        self.grid_move_button = self._button(frame, "APONTAR PARA O GRID", self.move_grid, color="#23617a")
        self.grid_move_button.pack(fill="x", pady=(0, 7))
        self._label(frame, variable=self.detail_text, color=MUTED, anchor="w",
                    justify="left", wraplength=345, size=10).pack(fill="x")
        self.log = tk.Text(frame, height=3, width=38, bg=PANEL, fg=MUTED, bd=0,
                           font=(self.font_family, 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(12, 0))
        if self.simulate:
            self._label(frame, "SIMULAÇÃO — nenhum motor conectado", color="#ffd375", size=9).pack(pady=(4, 0))

    def set_window_icon(self):
        configure_window(self.root)

    def map_changed(self):
        if not hasattr(self, "map_panel") or self.closing:
            return
        if self.save_timer is not None:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(600, self.save_settings)

    def save_settings(self):
        self.save_timer = None
        values = self.map_panel.values()
        try:
            grid = canonical_locator(self.grid_destination.get()) if self.grid_destination.get().strip() else ""
        except ValueError:
            grid = ""
        values["target_grid"] = grid
        try:
            self.settings_store.save(values)
        except OSError:
            if not self.save_error:
                self.log_message("Não foi possível salvar as configurações do mapa.")
                self.save_error = True

    def edit_station(self):
        self.release_jog()
        StationDialog(self.root, self.map_panel.station, self.font_family, self.apply_station)

    def apply_station(self, station):
        self.map_panel.set_station(station)
        if self.grid_destination.get().strip():
            self.calculate_grid(silent=True)
        else:
            self.grid_result.set("Digite o grid do destino e clique em Calcular.")
        self._update_enabled()

    def clear_grid(self):
        self.grid_destination.set("")
        self.grid_result.set("Digite o grid do destino e clique em Calcular.")
        self.map_panel.set_target(None)
        self.map_changed()

    def calculate_grid(self, *, silent=False):
        if self.map_panel.station is None:
            if not silent:
                messagebox.showinfo("Estação", "Configure a localização da estação no mapa.")
            return None
        try:
            grid = canonical_locator(self.grid_destination.get())
            target = self.map_panel.set_target(grid)
        except ValueError as exc:
            self.map_panel.set_target(None)
            self.grid_result.set(str(exc))
            if not silent:
                messagebox.showerror("Grid locator", str(exc))
            return None
        grid, lat, lon, azimuth, distance = target
        self.grid_destination.set(grid)
        self.grid_result.set(f"{grid} (centro) · {azimuth:.1f}° · {distance:.1f} km")
        self.angle.set(f"{azimuth:.1f}")
        self.map_changed()
        return azimuth

    def move_grid(self):
        if not self.ready or self.link is None or self.grid_move_button.cget("state") == "disabled":
            return
        azimuth = self.calculate_grid()
        if azimuth is None:
            return
        # Um clique explícito envia MOVE; calcular ou alterar estação não movimenta.
        self.angle.set(f"{azimuth:.3f}")
        self.move()

    def log_message(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S") + "  " + text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 100:
            self.log.delete("1.0", "2.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh_ports(self):
        if self.link is not None:
            return
        if self.simulate:
            ports = ["SIMULAÇÃO"]
        else:
            ports = [p.device for p in list_ports.comports()] if list_ports else []
            ports.sort()
        self.combo["values"] = ports
        if self.port.get() not in ports:
            self.port.set(ports[0] if ports else "")
        if not ports:
            self.connection_text.set("Nenhuma porta COM encontrada — conecte o cabo USB.")

    def toggle_connection(self):
        if self.link is not None:
            self.disconnect("Desconectado")
            return
        if not self.port.get():
            messagebox.showinfo("Porta COM", "Conecte o Arduino e atualize a lista de portas.")
            return
        if not self.simulate and serial is None:
            messagebox.showerror("Instalação", "Execute INSTALAR.bat para instalar o pySerial.")
            return
        self.last_state = None
        self.last_logged = self.last_error = None
        self.ready = False
        self.connection_text.set("Conectando — aguardando o Arduino iniciar…")
        self.detail_text.set("Confirmando firmware e leitura de posição.")
        self.link = DemoLink() if self.simulate else SerialLink(self.port.get())
        self._update_enabled()

    def disconnect(self, text):
        if self.link:
            self.link.close()
        self.link = None
        self.ready = False
        self.jog = 0
        self.jog_source = None
        self.connection_text.set(text)
        self.azimuth_text.set("—°")
        self.cardinal_text.set("SEM TELEMETRIA")
        self.motion_text.set("Parado / conexão encerrada")
        self.target_text.set("Novo apontamento (0° a 360°)")
        self.last_state = None
        self.map_panel.set_heading(None)
        self.draw_bar()
        self._update_enabled()

    def _update_enabled(self):
        connected = self.link is not None
        allow = self.ready and (self.last_state is not None and
                self.last_state.mode not in (1, 4) and self.last_state.reason != 8)
        state = "normal" if allow else "disabled"
        for widget in (self.left_button, self.right_button, self.move_button, self.grid_move_button):
            widget.configure(state=state)
        if self.map_panel.station is None:
            self.grid_move_button.configure(state="disabled")
        self.stop_button.configure(state="normal" if connected else "disabled")
        self.connect_button.configure(text="Desconectar" if connected else "Conectar")
        self.combo.configure(state="disabled" if connected else "readonly")
        self.refresh_button.configure(state="disabled" if connected else "normal")

    def start_jog(self, direction, source):
        if self.left_button.cget("state") == "disabled" or not self.ready or not self.link:
            return "break"
        if self.jog and self.jog != direction:
            # Não muda direção com dois comandos simultâneos.
            self.release_jog()
            return "break"
        if self.jog == direction:
            return "break"  # auto-repeat do teclado não reinicia a rampa.
        self.jog, self.jog_source = direction, source
        self.last_jog = 0.0
        self.link.send("JOG,L" if direction < 0 else "JOG,R")
        self.last_jog = time.monotonic()
        return "break"

    def release_jog(self):
        if self.jog:
            self.jog = 0
            self.jog_source = None
            if self.link:
                self.link.send("STOP")

    def key_start(self, event, direction):
        if isinstance(self.root.focus_get(), (tk.Entry, ttk.Combobox, tk.Scale,
                                             ttk.Scale, tk.Text, tk.Spinbox, ttk.Spinbox)):
            return None
        return self.start_jog(direction, "keyboard")

    def key_release(self, event, direction):
        if self.jog_source == "keyboard" and self.jog == direction:
            self.release_jog()
            return "break"

    def mouse_release(self, event):
        if self.jog_source == "mouse":
            self.release_jog()

    def focus_out(self, event):
        if self.closing:
            return
        def check():
            if not self.closing and self.root.focus_get() is None:
                self.release_jog()
        self.root.after(50, check)

    def stop(self, event=None):
        self.jog = 0
        self.jog_source = None
        if self.link:
            self.link.send("STOP")
            self.log_message("Parada solicitada.")
        return "break"

    def move(self, event=None):
        if not self.ready or not self.link or self.move_button.cget("state") == "disabled":
            return "break"
        self.release_jog()
        try:
            value = parse_angle(self.angle.get())
        except ValueError:
            messagebox.showerror("Ângulo", "Informe um ângulo de 0° a 360°.")
            return "break"
        self.link.send(f"MOVE,{value:.3f}")
        self.log_message(f"Apontamento solicitado: {value:g}°.")
        return "break"

    def draw_bar(self):
        self.bar.delete("all")
        width = max(100, self.bar.winfo_width())
        self.bar.create_rectangle(2, 4, width-2, 20, outline=MUTED, width=1)
        if self.last_state is not None:
            fraction = self.last_state.bar/100
            x = 5 + fraction*(width-22)
            color = RED if fraction < .04 or fraction > .96 else GREEN
            self.bar.create_rectangle(x, 7, x+12, 17, fill=color, outline="")

    def apply_status(self, state):
        self.last_state = state
        self.map_panel.set_heading(state.azimuth)
        self.last_rx = time.monotonic()
        if not self.ready:
            self.ready = True
            self.connection_text.set(f"{'Simulação' if self.simulate else self.port.get()} · Firmware 1.1 · conectado")
            self.log_message("Conexão estabelecida; comandos habilitados.")
        self.azimuth_text.set(f"{state.azimuth:05.1f}°")
        sector = int(((state.azimuth % 360)+11.25)/22.5) % 16
        self.cardinal_text.set(DIRECTIONS[sector])
        if state.mode in (1, 4) or (state.mode == 0 and state.reason in (2, 3, 8)):
            self.jog = 0
            self.jog_source = None  # não envia STOP sobre comando físico.
        arrows = ""
        if state.direction:
            count = next((i for i, p in enumerate((70, 90, 110, 140, 175, 220), 1)
                          if state.pwm <= p), 6)
            arrows = ("<" if state.direction < 0 else ">")*count
        self.motion_text.set(MODES[state.mode] + (f"  {arrows}" if arrows else ""))
        self.motion_label.configure(fg=RED if state.mode == 4 or state.pwm >= 220 else GREEN)
        if state.target is not None:
            self.target_text.set(f"Alvo ativo: {state.target % 360:.1f}° · faltam {abs(state.target-state.position):.1f}°")
        else:
            self.target_text.set("Novo apontamento (0° a 360°)")
        limit_text = "Limite esquerdo" if state.limit == 1 else ("Limite direito" if state.limit == -1 else "Curso disponível")
        detail = REASONS[state.reason] if state.mode in (0, 4) else MODES[state.mode]
        self.detail_text.set(f"{detail} · {limit_text} · PWM {state.pwm}/255")
        key = state.mode, state.reason, state.limit
        if key != self.last_logged:
            if state.mode in (0, 4) and state.reason != 0:
                self.log_message(REASONS[state.reason])
            self.last_logged = key
        self.draw_bar()
        self._update_enabled()

    def tick(self):
        if self.closing:
            return
        now = time.monotonic()
        link = self.link
        if link:
            if isinstance(link, DemoLink):
                link.tick()
            for _ in range(128):
                try:
                    kind, payload = link.events.get_nowait()
                except queue.Empty:
                    break
                if kind == "status":
                    self.apply_status(payload)
                elif kind == "identified":
                    self.log_message("Firmware 1.1 identificado.")
                    self.last_ping = 0.0
                elif kind == "reply" and payload.startswith("ERR,"):
                    code = payload.split(",", 1)[1]
                    if code in ("LOCAL", "FAULT"):
                        self.jog = 0
                        self.jog_source = None
                    if payload != self.last_error:
                        self.log_message(ERRORS.get(code, payload))
                        self.last_error = payload
                elif kind == "error":
                    self.log_message(payload)
                    self.detail_text.set(payload)
                    self.disconnect("Erro de conexão")
                    break
                elif kind == "closed":
                    self.disconnect("Conexão encerrada")
                    break
            if self.link is link:
                if self.ready and now - self.last_rx > .8:
                    self.log_message("Telemetria expirou; parada solicitada.")
                    self.detail_text.set("Confira o cabo USB e conecte novamente.")
                    self.disconnect("Comunicação interrompida")
                else:
                    if link.verified and now - self.last_ping >= .2:
                        link.send("PING")
                        self.last_ping = now
                    if self.jog and self.ready and now - self.last_jog >= .15:
                        link.send("JOG,L" if self.jog < 0 else "JOG,R")
                        self.last_jog = now
        self.root.after(50, self.tick)

    def close(self):
        self.closing = True
        self.release_jog()
        if self.save_timer is not None:
            self.root.after_cancel(self.save_timer)
        self.save_settings()
        self.map_panel.close()
        link = self.link
        if link:
            link.close()
        # Dá ao worker até 450 ms para escrever STOP; o Arduino tem prazo próprio.
        deadline = time.monotonic() + .45
        def finish():
            if (isinstance(link, SerialLink) and link.thread.is_alive()
                    and time.monotonic() < deadline):
                self.root.after(20, finish)
            else:
                # Cancela callbacks Tk pendentes antes de destruir a janela.
                for timer in self.root.tk.call("after", "info"):
                    self.root.after_cancel(timer)
                self.root.destroy()
        finish()


def main():
    parser = argparse.ArgumentParser(description="Rotor PU2PTU 1.2.1")
    parser.add_argument("--simular", action="store_true", help="Abre demonstração sem Arduino")
    args = parser.parse_args()
    configure_process()
    root = tk.Tk()
    RotorApp(root, args.simular)
    root.mainloop()


if __name__ == "__main__":
    main()
