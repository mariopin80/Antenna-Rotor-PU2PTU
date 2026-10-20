"""Mapa Tk com mosaicos OSM, cache e sobreposição RGBA de apontamento.
Toda rede/IO de mosaicos roda em duas threads; somente o Tk atualiza a tela.
"""
from collections import OrderedDict
from dataclasses import asdict
from io import BytesIO
import json
import math
import os
from pathlib import Path
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import webbrowser
from rotor_i18n import Translator, LANGUAGES

from PIL import Image, ImageDraw, ImageTk
from rotor_geo import (Station, number, locator_center, canonical_locator,
                       bearing_distance, destination, world_pixel, world_latlon,
                       screen_point, fit_zoom, cone_polygon)

BG = '#111820'
PANEL = '#1c2834'
FG = '#e5edf5'
MUTED = '#9dafc0'
TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
USER_AGENT = 'RotorPU2PTU/1.3 (Desktop antenna pointing map)'
CACHE_SECONDS = 7*24*60*60


def data_directory():
    parent = Path(os.environ['APPDATA']) if os.environ.get('APPDATA') else Path.home()/'.config'
    return parent/'RotorPU2PTU'


class SettingsStore:
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder is not None else data_directory()
        self.path = self.folder/'mapa.json'

    def load(self):
        default = {'station': None, 'radius': 200.0, 'opening': 60.0,
                   'opacity': .22, 'target_grid': '', 'language': 'pt'}
        try:
            d = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return default
        if not isinstance(d, dict):
            return default
        if d.get('language') in LANGUAGES:
            default['language'] = d['language']
        try:
            v = d.get('station')
            if isinstance(v, dict):
                default['station'] = Station.from_values(v.get('name',''),v.get('lat'),v.get('lon'),v.get('grid',''))
        except (TypeError, ValueError):
            pass
        for key, low, high in [('radius',1,3000), ('opening',1,360), ('opacity',.05,.6)]:
            try: default[key] = number(d.get(key,default[key]),low,high,key)
            except ValueError: pass
        try:
            if d.get('target_grid'): default['target_grid'] = canonical_locator(d['target_grid'])
        except ValueError:
            pass
        return default

    def save(self, d):
        values = dict(d)
        values['station'] = asdict(values['station']) if values.get('station') else None
        self.folder.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(self.path)


class TileStore:
    """Somente tiles da vista atual, cache >=7 dias, UA estável, 2 workers daemon.

    Nenhuma pré-carga de cidades/regiões e nenhuma função de download offline.
    Redesenhar o cone não dispara novas requisições para tiles já carregados.
    """
    def __init__(self, folder=None, online=True, url_template=TILE_URL):
        self.folder = Path(folder) if folder is not None else data_directory()/'map_tiles'
        self.online = online
        self.url_template = url_template
        self.lock = threading.Lock()
        self.view = set()
        self.pending = set()
        self.memory = OrderedDict()
        self.failed = {}
        self.work = queue.Queue(maxsize=128)
        self.results = queue.Queue()
        self.quit = threading.Event()
        self.version = 0
        self.problem = ''
        self.threads = []
        for _ in range(2):
            thread = threading.Thread(target=self._worker,daemon=True)
            self.threads.append(thread)
            thread.start()

    def set_view(self, keys):
        with self.lock: self.view = set(keys)

    def path(self, key):
        z,x,y = key
        return self.folder/str(z)/str(x)/(str(y)+'.png')

    def get(self, key):
        if key in self.memory:
            self.memory.move_to_end(key)
            return self.memory[key]
        with self.lock:
            if key in self.view and key not in self.pending and time.monotonic()-self.failed.get(key,-1000) >= 30:
                self.pending.add(key)
                try:self.work.put_nowait(key)
                except queue.Full:self.pending.discard(key)
        return None

    def poll(self):
        for _ in range(64):
            try:key,img,error = self.results.get_nowait()
            except queue.Empty:break
            with self.lock:self.pending.discard(key)
            if img is not None:
                self.memory[key] = img
                self.memory.move_to_end(key)
                while len(self.memory) > 192:self.memory.popitem(last=False)
                self.version += 1
                if not error:self.problem = ''
            if error:
                self.problem = error
                self.failed[key] = time.monotonic()
                self.version += 1

    def _worker(self):
        while not self.quit.is_set():
            try:key = self.work.get(timeout=.25)
            except queue.Empty:continue
            with self.lock:visible = key in self.view
            if not visible:
                self.results.put((key,None,''));continue
            try:
                image,error = self._load(key)
            except Exception:
                image,error = None,'map_unavailable'
            if not self.quit.is_set():self.results.put((key,image,error))

    @staticmethod
    def decode(data):
        with Image.open(BytesIO(data)) as img:
            if img.size != (256,256):raise ValueError('Tile inválido')
            return img.convert('RGB')

    def _load(self, key):
        p = self.path(key)
        stale = None
        meta = {}
        try:
            stale = self.decode(p.read_bytes())
            try:meta = json.loads(p.with_suffix('.json').read_text())
            except (OSError,ValueError):pass
            if time.time()-p.stat().st_mtime < CACHE_SECONDS:
                return stale,''
        except (OSError,ValueError):
            pass
        if not self.online:
            return stale, 'map_offline' if stale is None else ''
        headers = {'User-Agent':USER_AGENT,'Accept':'image/png'}
        if meta.get('etag'):headers['If-None-Match'] = meta['etag']
        if meta.get('modified'):headers['If-Modified-Since'] = meta['modified']
        z,x,y = key
        req = Request(self.url_template.format(z=z,x=x,y=y),headers=headers)
        try:
            with urlopen(req,timeout=6) as response:
                data = response.read(2*1024*1024)
                img = self.decode(data)
                info = {'etag':response.headers.get('ETag',''),
                        'modified':response.headers.get('Last-Modified','')}
            try:
                p.parent.mkdir(parents=True,exist_ok=True)
                tmp = p.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(p)
                p.with_suffix('.json').write_text(json.dumps(info))
            except OSError:
                pass # Um cache sem permissão não impede a vista atual.
            return img,''
        except HTTPError as exc:
            if exc.code == 304 and stale is not None:
                try:p.touch()
                except OSError:pass
                return stale,''
            return stale,'map_unavailable'
        except (OSError,ValueError):
            return stale,'map_offline'

    def close(self):
        self.quit.set()
        with self.lock:self.view.clear()


class StationPanel(tk.Frame):
    """Configuracao na janela principal; nenhum Toplevel ou grab modal."""
    def __init__(self, parent, font, translator, apply, cancel):
        super().__init__(parent, bg=BG, padx=24, pady=16)
        self.t, self.font = translator, font
        self.apply_callback, self.cancel_callback = apply, cancel
        self.localized = []
        self.name = tk.StringVar()
        self.mode = tk.StringVar(value='coords')
        self.lat, self.lon = tk.StringVar(), tk.StringVar()
        self.grid_value, self.opening_value = tk.StringVar(), tk.StringVar()
        self.error_text = tk.StringVar()
        self.last_error = None
        box = tk.Frame(self, bg=BG)
        box.pack(fill='both', expand=True)
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)
        def label(key, row, *, color=MUTED, size=11, column=0, span=2):
            w=tk.Label(box,text=self.t(key),bg=BG,fg=color,font=(font,size),
                       anchor='w',justify='left',wraplength=650)
            w.grid(row=row,column=column,columnspan=span,sticky='ew',pady=(7,3))
            self.localized.append((w,key));return w
        def entry(var,row,column=0,span=2):
            w=tk.Entry(box,textvariable=var,bg=PANEL,fg=FG,insertbackground=FG,
                       relief='flat',font=(font,12),width=20)
            w.grid(row=row,column=column,columnspan=span,sticky='ew',ipady=6,padx=(0,10))
            w.bind('<Return>',lambda e:self.commit())
            return w
        label('station_title',0,color=FG,size=18)
        label('station_name',1);self.name_entry=entry(self.name,2)
        for row,mode,key in ((3,'coords','coords_mode'),(4,'grid','grid_mode')):
            w=tk.Radiobutton(box,text=self.t(key),variable=self.mode,value=mode,
                    command=self.update_mode,bg=BG,fg=FG,selectcolor=PANEL,
                    activebackground=BG,activeforeground=FG,font=(font,11),anchor='w')
            w.grid(row=row,column=0,columnspan=2,sticky='w',pady=(8,2))
            self.localized.append((w,key))
        label('latitude',5,column=0,span=1);label('longitude',5,column=1,span=1)
        self.lat_entry=entry(self.lat,6,column=0,span=1)
        self.lon_entry=entry(self.lon,6,column=1,span=1)
        label('station_grid',7);self.grid_entry=entry(self.grid_value,8)
        self.grid_entry.configure(validate='key',validatecommand=(self.register(lambda v:len(v)<=6),'%P'))
        label('latitude_hint',9,size=10)
        label('beam_label',10,color=FG);self.opening_entry=entry(self.opening_value,11,column=0,span=1)
        label('beam_hint',12,size=10)
        tk.Label(box,textvariable=self.error_text,bg=BG,fg='#ff757d',font=(font,10),
                 anchor='w',justify='left',wraplength=650).grid(row=13,column=0,columnspan=2,sticky='ew',pady=(8,0))
        buttons=tk.Frame(box,bg=BG);buttons.grid(row=14,column=0,columnspan=2,sticky='ew',pady=(12,0))
        for key,callback,side in [('cancel',cancel,'left'),('apply_station',self.commit,'right')]:
            w=tk.Button(buttons,text=self.t(key),command=callback,bg=PANEL if side=='left' else '#23617a',
                        fg=FG,activebackground='#344c61',activeforeground=FG,
                        bd=0,padx=12,pady=8,font=(font,11))
            w.pack(side=side);self.localized.append((w,key))

    def load(self, station, opening):
        self.name.set(station.name if station else 'PU2PTU')
        self.mode.set('grid' if station and station.grid else 'coords')
        self.lat.set(f'{station.lat:.6f}' if station else '')
        self.lon.set(f'{station.lon:.6f}' if station else '')
        self.grid_value.set(station.grid if station else '')
        self.opening_value.set(f'{opening:g}')
        self.error_text.set('');self.last_error=None
        self.update_mode()

    def refresh_language(self):
        for widget,key in self.localized:widget.configure(text=self.t(key))
        if self.last_error:self.error_text.set(self.t.error(self.last_error))

    def update_mode(self):
        coords=self.mode.get()=='coords'
        self.lat_entry.configure(state='normal' if coords else 'disabled')
        self.lon_entry.configure(state='normal' if coords else 'disabled')
        self.grid_entry.configure(state='disabled' if coords else 'normal')

    def commit(self):
        try:
            station=Station.from_values(self.name.get(),self.lat.get(),self.lon.get(),
                         self.grid_value.get() if self.mode.get()=='grid' else '')
            opening=number(self.opening_value.get(),1,360,'Abertura do feixe')
        except ValueError as exc:
            self.last_error=str(exc);self.error_text.set(self.t.error(exc));return False
        self.last_error=None;self.error_text.set('')
        self.apply_callback(station,opening)
        return True


class MapPanel(tk.Frame):
    def __init__(self, parent, font, settings, on_change, on_edit_station, *, tile_store=None, translator=None):
        super().__init__(parent,bg=BG,padx=12,pady=14)
        self.font, self.t = font, translator or Translator()
        self.localized=[]
        self.on_change = on_change
        self.station = settings['station']
        self.opening = settings['opening']
        self.opacity = settings['opacity']
        self.radius = settings['radius']
        self.target = self.azimuth = None
        self.zoom = 6.0
        self.tiles = tile_store if tile_store is not None else TileStore()
        self.photo = self.base = self.base_key = self.last_draw = None
        self.last_retry = time.monotonic()
        self.closed = False
        self.dirty = True
        self.timer = None
        self.radius_var = tk.StringVar(value=f'{self.radius:g}')
        self.opening_var = tk.StringVar(value=f'{self.opening:g}')
        self.station_text = tk.StringVar()
        self.state_text = tk.StringVar(value=self.t('map_wait'))
        self.target_text = tk.StringVar(value='')
        self.opacity_var = tk.DoubleVar(value=self.opacity*100)
        self.opacity_text = tk.StringVar()
        self.columnconfigure(0,weight=1);self.rowconfigure(3,weight=1)
        def label(parent,key,**kw):
            widget=tk.Label(parent,text=self.t(key),bg=BG,fg=MUTED,font=(font,10),**kw)
            self.localized.append((widget,key));return widget
        def button(parent,key,callback):
            widget=tk.Button(parent,text=self.t(key),command=callback,bg=PANEL,fg=FG,
                  activebackground='#344c61',activeforeground=FG,font=(font,10),bd=0,padx=10,pady=7)
            self.localized.append((widget,key));return widget
        head=tk.Frame(self,bg=BG);head.grid(row=0,column=0,sticky='ew')
        title=label(head,'map_title');title.configure(fg=FG,font=(font,15,'bold'));title.pack(side='left')
        self.station_button=button(head,'station_settings',on_edit_station);self.station_button.pack(side='right')
        tk.Label(self,textvariable=self.station_text,bg=BG,fg=MUTED,font=(font,10),anchor='w').grid(row=1,column=0,sticky='ew',pady=(5,10))
        controls=tk.Frame(self,bg=BG);controls.grid(row=2,column=0,sticky='ew',pady=(0,8))
        label(controls,'radius').pack(side='left',padx=(0,6))
        self.radius_combo=ttk.Combobox(controls,textvariable=self.radius_var,width=7,
                        values=('10','25','50','100','200','400','800','1600'))
        self.radius_combo.pack(side='left',padx=(0,8))
        self.radius_combo.bind('<<ComboboxSelected>>',lambda e:self.apply_scale())
        self.radius_combo.bind('<Return>',lambda e:self.apply_scale())
        button(controls,'apply',self.apply_scale).pack(side='left')
        for text,factor in (('+',.5),('−',2)):
            tk.Button(controls,text=text,command=lambda f=factor:self.zoom_by(f),bg=PANEL,fg=FG,
                font=(font,11,'bold'),bd=0,padx=8,pady=4).pack(side='right',padx=(4,0))
        self.canvas=tk.Canvas(self,bg='#edf1ef',width=640,height=430,bd=0,highlightthickness=0)
        self.canvas.grid(row=3,column=0,sticky='nsew')
        self.image_id=self.canvas.create_image(0,0,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.invalidate(True))
        self.canvas.bind('<MouseWheel>',lambda e:self.zoom_by(.5 if e.delta>0 else 2))
        self.canvas.bind('<Button-4>',lambda e:self.zoom_by(.5))
        self.canvas.bind('<Button-5>',lambda e:self.zoom_by(2))
        footer=tk.Frame(self,bg=BG);footer.grid(row=4,column=0,sticky='ew',pady=(7,0))
        tk.Label(footer,textvariable=self.opacity_text,bg=BG,fg=MUTED,font=(font,9)).pack(side='left')
        self.opacity_scale=tk.Scale(footer,from_=5,to=60,orient='horizontal',variable=self.opacity_var,
                 command=self.change_opacity,showvalue=False,length=135,bg=BG,fg=FG,
                 highlightthickness=0,troughcolor=PANEL,bd=0)
        self.opacity_scale.pack(side='left',padx=(5,12))
        attribution=tk.Label(footer,text='© OpenStreetMap contributors',bg=BG,fg='#8ccde9',font=(font,9),cursor='hand2')
        attribution.pack(side='right')
        attribution.bind('<Button-1>',lambda e:webbrowser.open('https://www.openstreetmap.org/copyright'))
        tk.Label(self,textvariable=self.state_text,bg=BG,fg=MUTED,font=(font,9),anchor='w').grid(row=5,column=0,sticky='ew',pady=(3,0))
        tk.Label(self,textvariable=self.target_text,bg=BG,fg='#ffd375',font=(font,9),anchor='w').grid(row=6,column=0,sticky='ew',pady=(3,0))
        self.refresh_language()
        self.timer=self.after(100,self.poll)

    def refresh_language(self):
        for widget,key in self.localized:widget.configure(text=self.t(key))
        self.opacity_text.set(self.t('opacity',value=self.opacity*100))
        self.refresh_station_label()
        self.invalidate()

    def set_opening(self, opening):
        self.opening=number(opening,1,360,'Abertura do feixe')
        self.opening_var.set(f'{self.opening:g}')
        self.invalidate();self.on_change()

    def refresh_station_label(self):
        s = self.station
        self.station_text.set(f'{s.name} · {s.lat:.5f}, {s.lon:.5f}' + (f' · {s.grid}' if s.grid else '')
                              if s else self.t('station_prompt'))

    def values(self):
        return {'station':self.station,'radius':self.radius,'opening':self.opening,'opacity':self.opacity}

    def set_station(self, station):
        self.station = station
        self.target = None
        self.refresh_station_label()
        self.invalidate(True)
        self.on_change()

    def apply_scale(self):
        try:
            radius = number(self.radius_var.get(),1,3000,'Raio')
            opening = self.opening
        except ValueError as exc:
            messagebox.showerror(self.t('map_title'),self.t.error(exc),parent=self);return
        self.radius,self.opening = radius,opening
        self.radius_var.set(f'{radius:g}');self.opening_var.set(f'{opening:g}')
        self.invalidate(True)
        self.on_change()

    def zoom_by(self, factor):
        self.radius = max(1,min(3000,self.radius*factor))
        self.radius_var.set(f'{self.radius:g}')
        self.invalidate(True)
        self.on_change()
        return 'break'

    def change_opacity(self, value):
        try:opacity = float(value)/100
        except ValueError:return
        self.opacity = max(.05,min(.6,opacity))
        self.opacity_text.set(self.t('opacity',value=self.opacity*100))
        self.invalidate()
        self.on_change()

    def set_heading(self, value):
        value = None if value is None else value%360
        if value != self.azimuth:
            self.azimuth = value
            self.invalidate()

    def set_target(self, grid=None):
        self.target = None
        if grid and self.station:
            lat,lon = locator_center(grid)
            bearing,km = bearing_distance(self.station.lat,self.station.lon,lat,lon)
            self.target = (canonical_locator(grid),lat,lon,bearing,km)
        self.invalidate()
        return self.target

    def invalidate(self, base=False):
        self.dirty = True
        if base:self.base_key = None

    def poll(self):
        if self.closed:return
        self.tiles.poll()
        if getattr(self, 'missing', 0) and time.monotonic()-self.last_retry > 30:
            self.last_retry = time.monotonic()
            self.invalidate(True)
        if self.tiles.version != self.last_draw:self.dirty = True
        if self.dirty:
            self.redraw()
            self.dirty = False
            self.last_draw = self.tiles.version
        self.timer = self.after(100,self.poll)

    def basemap(self,w,h):
        station = self.station
        self.zoom = fit_zoom(station,self.radius,w,h)
        key = (station.lat,station.lon,self.radius,w,h,self.tiles.version)
        if key == self.base_key:return self.base
        level = int(math.floor(self.zoom))
        factor = 2**(self.zoom-level)
        cx,cy = world_pixel(station.lat,station.lon,level)
        left,top = cx-w/(2*factor),cy-h/(2*factor)
        x0,x1 = math.floor(left/256),math.floor((left+w/factor)/256)
        y0,y1 = math.floor(top/256),math.floor((top+h/factor)/256)
        keys = {(level,x%(2**level),y) for x in range(x0,x1+1) for y in range(y0,y1+1) if 0<=y<2**level}
        self.tiles.set_view(keys)
        mosaic = Image.new('RGB',((x1-x0+1)*256,(y1-y0+1)*256),'#edf1ef')
        draw = ImageDraw.Draw(mosaic)
        missing = 0
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):
                tile = self.tiles.get((level,x%(2**level),y)) if 0<=y<2**level else None
                xy = ((x-x0)*256,(y-y0)*256)
                if tile is not None:mosaic.paste(tile,xy)
                else:
                    missing += 1
                    draw.rectangle((xy[0],xy[1],xy[0]+255,xy[1]+255),outline='#d6dfdc')
        self.missing = missing
        self.base = mosaic.transform((w,h),Image.Transform.AFFINE,
                    (1/factor,0,left-x0*256,0,1/factor,top-y0*256),resample=Image.Resampling.BILINEAR)
        self.base_key = key
        return self.base

    def redraw(self):
        w,h = max(200,self.canvas.winfo_width()),max(200,self.canvas.winfo_height())
        self.canvas.delete('annotation')
        if self.station is None:
            image = Image.new('RGB',(w,h),'#e8efed')
            self.canvas.create_text(w/2,h/2,text=self.t('map_no_station'),
                      justify='center',font=(self.font,15),fill='#435b63',tags='annotation')
            self.state_text.set(self.t('station_prompt'))
            self.target_text.set(self.t('beam_label'))
        else:
            image = self.basemap(w,h).convert('RGBA')
            overlay = Image.new('RGBA',(w,h),(0,0,0,0));draw = ImageDraw.Draw(overlay)
            center = (w/2,h/2)
            if self.azimuth is not None:
                points = cone_polygon(self.station,self.azimuth,self.opening,self.radius,self.zoom,w,h)
                draw.polygon(points,fill=(22,133,237,int(255*self.opacity)))
                draw.line(points+[center],fill=(12,104,205,200),width=2)
                lat,lon = destination(self.station.lat,self.station.lon,self.azimuth,self.radius)
                tip = screen_point(lat,lon,self.station,self.zoom,w,h)
                draw.line([center,tip],fill=(0,106,220,240),width=2)
            image = Image.alpha_composite(image,overlay).convert('RGB')
            if self.target:
                grid,lat,lon,bearing,km = self.target
                path = [center]
                for i in range(1,33):
                    p = destination(self.station.lat,self.station.lon,bearing,min(km,self.radius)*i/32)
                    path.append(screen_point(*p,self.station,self.zoom,w,h))
                flat = [n for point in path for n in point]
                self.canvas.create_line(*flat,fill='#b15b03',width=2,dash=(6,5),tags='annotation')
                x,y = screen_point(lat,lon,self.station,self.zoom,w,h)
                visible = 12<x<w-12 and 12<y<h-12
                if visible:
                    self.canvas.create_oval(x-5,y-5,x+5,y+5,fill='#ffa43c',outline='#553000',width=2,tags='annotation')
                    self.canvas.create_text(x+10,y-10,text=grid,anchor='w',fill='#663300',font=(self.font,11,'bold'),tags='annotation')
                self.target_text.set(self.t('map_target',grid=grid,bearing=bearing,distance=km))
            else:self.target_text.set(self.t('beam_label'))
            self.canvas.create_oval(w/2-6,h/2-6,w/2+6,h/2+6,fill='#07596f',outline='white',width=2,tags='annotation')
            self.canvas.create_text(w/2+11,h/2+13,text=self.station.name,anchor='w',fill='#13383e',font=(self.font,10,'bold'),tags='annotation')
            self.canvas.create_text(20,20,text='N ↑',fill='#153b43',font=(self.font,15,'bold'),tags='annotation')
            # Barra de escala local por distância geodésica entre pixels.
            lat1,lon1 = world_latlon(*world_pixel(self.station.lat,self.station.lon,self.zoom),self.zoom)
            px,py = world_pixel(self.station.lat,self.station.lon,self.zoom)
            lat2,lon2 = world_latlon(px+100,py,self.zoom)
            _,km100 = bearing_distance(lat1,lon1,lat2,lon2)
            exponent = 10**math.floor(math.log10(km100))
            nice = max(v*exponent for v in (1,2,5) if v*exponent<=km100)
            length = 100*nice/km100
            self.canvas.create_rectangle(10,h-43,145,h-8,fill='white',outline='',tags='annotation')
            self.canvas.create_line(20,h-18,20+length,h-18,fill='#203c40',width=3,tags='annotation')
            self.canvas.create_text(20,h-30,text=f'{nice:g} km',anchor='w',fill='#203c40',font=(self.font,10),tags='annotation')
            heading = self.t('map_heading',angle=self.azimuth) if self.azimuth is not None else self.t('cone_hidden')
            self.state_text.set(self.t('map_state',heading=heading,opening=self.opening,radius=self.radius))
            if self.missing:
                self.state_text.set(self.state_text.get()+' · '+self.t(self.tiles.problem or 'loading_map'))
        self.photo = ImageTk.PhotoImage(image,master=self.canvas)
        self.canvas.itemconfigure(self.image_id,image=self.photo)
        self.canvas.tag_lower(self.image_id)

    def close(self):
        self.closed = True
        if self.timer:
            try:self.after_cancel(self.timer)
            except tk.TclError:pass
        self.tiles.close()
