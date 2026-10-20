"""Teste Tk opcional. Ative ROTOR_TEST_UI=1 com display disponível.
Windows PowerShell: $env:ROTOR_TEST_UI='1'; py -3 -m unittest discover -s Testes -v
"""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Windows'))


@unittest.skipUnless(os.environ.get('ROTOR_TEST_UI')=='1','Teste visual opcional; ative ROTOR_TEST_UI=1')
class UserInterfaceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='win32','Consulta WM_GETICON exige Windows')
    def test_windows_title_icons(self):
        import ctypes
        import tkinter as tk
        from rotor_windows import configure_window
        root=tk.Tk()
        try:
            configure_window(root)
            end=time.monotonic()+.4
            while time.monotonic()<end:
                root.update();time.sleep(.01)
            self.assertTrue(hasattr(root,'_rotor_native_icons'))
            native=root._rotor_native_icons
            hwnd=native.user.GetAncestor(root.winfo_id(),2)
            for kind,expected in enumerate(native.handles):
                actual=native.user.SendMessageW(hwnd,0x7F,kind,0)  # WM_GETICON
                self.assertEqual(actual,expected)
        finally:
            root.destroy()

    def test_map_grid_and_motor_controls(self):
        import tkinter as tk
        from rotor_pc import RotorApp,Status
        from rotor_geo import Station,locator_center,bearing_distance,destination,screen_point
        from rotor_map import TileStore
        from PIL import ImageTk
        with tempfile.TemporaryDirectory() as folder:
            root=tk.Tk()
            errors=[]
            root.report_callback_exception=lambda *exc:errors.append(exc)
            tiles=TileStore(Path(folder)/'tiles',online=False)
            app=RotorApp(root,simulate=True,settings_dir=folder,tile_store=tiles)
            def pump(seconds):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    root.update();time.sleep(.01)
            try:
                pump(.4)
                self.assertTrue(app.ready)
                app.apply_station(Station.from_values('PU2PTU',grid='GG66dr'))
                app.grid_destination.set('GG67aa')
                az=app.calculate_grid()
                expected,_=bearing_distance(*locator_center('GG66dr'),*locator_center('GG67aa'))
                self.assertAlmostEqual(az,expected)
                self.assertEqual(app.link.mode,0)
                app.move_grid();self.assertEqual(app.link.mode,3)
                app.stop();self.assertEqual(app.link.mode,0)
                app.start_jog(-1,'mouse');self.assertEqual(app.link.mode,2)
                app.right_button.event_generate('<ButtonRelease-1>');root.update()
                self.assertEqual(app.link.mode,0)
                # As setas nos campos e no controle de opacidade não iniciam JOG.
                opacity_scale=next(w for row in app.map_panel.winfo_children() for w in row.winfo_children() if isinstance(w,tk.Scale))
                for widget in (app.grid_entry,app.station_panel.opening_entry,app.map_panel.radius_combo,opacity_scale):
                    widget.focus_force();root.update()
                    app.key_start(None,-1)
                    self.assertEqual(app.link.mode,0)
                app.map_panel.set_opening(48);app.map_panel.radius_var.set('200')
                app.map_panel.apply_scale();app.map_panel.change_opacity('24')
                app.apply_status(Status(325,325,88.5,0,0,0,None,0,0))
                root.update_idletasks();app.map_panel.redraw()
                lat,lon=destination(app.map_panel.station.lat,app.map_panel.station.lon,335,100)
                x,y=screen_point(lat,lon,app.map_panel.station,app.map_panel.zoom,
                                 app.map_panel.canvas.winfo_width(),app.map_panel.canvas.winfo_height())
                x,y=round(x),round(y)
                before=app.map_panel.base.getpixel((x,y))
                after=ImageTk.getimage(app.map_panel.photo).getpixel((x,y))
                expected=tuple(round(a*.76+b*.24) for a,b in zip(before,(22,133,237)))
                self.assertLessEqual(max(abs(a-b) for a,b in zip(after,expected)),2)
                app.save_settings()
                saved=app.settings_store.load()
                self.assertEqual(saved['station'].grid,'GG66dr')
                self.assertEqual(saved['target_grid'],'GG67aa')
                app.grid_destination.set('')
                app.apply_station(Station.from_values('Outra estação','-23','-47'))
                self.assertIsNone(app.map_panel.target)
                app.disconnect('Desconectado')
                self.assertIsNone(app.map_panel.azimuth)
                self.assertFalse(errors)
            finally:
                app.close()
                try:root.update()
                except tk.TclError:pass

    def test_inline_settings_languages_and_speed(self):
        import tkinter as tk
        from rotor_pc import RotorApp,Status
        from rotor_geo import Station
        from rotor_map import TileStore
        from rotor_i18n import LANGUAGES
        with tempfile.TemporaryDirectory() as folder:
            root=tk.Tk();errors=[]
            root.report_callback_exception=lambda *exc:errors.append(exc)
            app=RotorApp(root,simulate=True,settings_dir=folder,
                         tile_store=TileStore(Path(folder)/'tiles',online=False))
            def pump(seconds=.15):
                end=time.monotonic()+seconds
                while time.monotonic()<end:root.update();time.sleep(.005)
            try:
                pump(.3);self.assertTrue(app.ready)
                app.apply_station(Station.from_values('PU2PTU',grid='GG66dr'))
                self.assertEqual(app.speed_level,6)
                app.speed_combo.current(2);app.change_speed()
                self.assertEqual(app.move_button.cget('state'),'disabled')
                pump();self.assertEqual(app.speed_level,3)
                self.assertIsNone(app.pending_speed)
                app.start_jog(1,'mouse');self.assertEqual(app.link.mode,2)
                app.edit_station();self.assertEqual(app.link.mode,0)
                pump();self.assertTrue(app.settings_open)
                self.assertEqual(app.left_button.cget('state'),'disabled')
                self.assertFalse(any(isinstance(w,tk.Toplevel) for w in root.winfo_children()))
                self.assertEqual(app.station_panel.winfo_toplevel(),root)
                self.assertFalse(app.map_panel.winfo_ismapped())
                app.station_panel.opening_value.set('361')
                self.assertFalse(app.station_panel.commit())
                self.assertTrue(app.station_panel.error_text.get())
                app.station_panel.opening_value.set('45')
                for language in LANGUAGES:
                    app.set_language(language);pump(.05)
                    self.assertEqual(app.stop_button.cget('text'),app.t('stop'))
                    self.assertEqual(app.station_panel.opening_value.get(),'45')
                    self.assertFalse(errors)
                self.assertTrue(app.station_panel.commit());pump()
                self.assertFalse(app.settings_open)
                self.assertEqual(app.map_panel.opening,45)
                self.assertEqual(app.settings_store.load()['language'],'ru')
                self.assertEqual(app.link.mode,0)
                app.apply_status(Status(120,120,34,5,0,0,None,0,9))
                self.assertEqual(app.left_button.cget('state'),'disabled')
                self.assertEqual(str(app.speed_combo.cget('state')),'disabled')
                self.assertEqual(app.stop_button.cget('state'),'normal')
                root.update_idletasks()
                self.assertEqual(app.left_panel.winfo_width(),234)
                self.assertGreater(app.map_panel.winfo_width(),900)
                self.assertFalse(errors)
            finally:
                app.close()
                try:root.update()
                except tk.TclError:pass


if __name__=='__main__':unittest.main()
