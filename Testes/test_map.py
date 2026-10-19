import json
import math
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Windows'))
from rotor_geo import *
from rotor_map import SettingsStore, TileStore, USER_AGENT, CACHE_SECONDS
from PIL import Image


class GeometryTests(unittest.TestCase):
    def test_locator_known(self):
        lat,lon = locator_center('gg66DR')
        self.assertAlmostEqual(lat,-23.2708333333)
        self.assertAlmostEqual(lon,-47.7083333333)
        self.assertEqual(locator_center('GG66'),(-23.5,-47.0))
        self.assertEqual(locator_center('GG'),(-25.0,-50.0))
        self.assertEqual(canonical_locator(' gg66DR '),'GG66dr')

    def test_locator_invalid(self):
        for grid in ('','GG6','GG66d','GG66dra','SS66aa','GG66yy','GG6Xdr','12ABCD','GG-66'):
            with self.assertRaises(ValueError):locator_center(grid)

    def test_station(self):
        s=Station.from_values('PU2PTU','-23,2','-47,7')
        self.assertEqual(s.lat,-23.2)
        self.assertEqual(s.lon,-47.7)
        s=Station.from_values('PU2PTU',grid='GG66dr')
        self.assertAlmostEqual(s.lat,locator_center('GG66dr')[0])
        for lat,lon in [('nan','0'),('86','0'),('0','181')]:
            with self.assertRaises(ValueError):Station.from_values('x',lat,lon)

    def test_cardinal_bearings(self):
        for target,expected in [((1,0),0),((0,1),90),((-1,0),180),((0,-1),270)]:
            az,km=bearing_distance(0,0,*target)
            self.assertAlmostEqual(az,expected,places=7)
            self.assertGreater(km,100)
        with self.assertRaises(ValueError):bearing_distance(0,0,0,0)

    def test_official_geodesic_example(self):
        # Exemplo de referência GeographicLib: Wellington -> Salamanca.
        az,km=bearing_distance(-41.32,174.81,40.96,-5.50)
        self.assertAlmostEqual(km,19959.679267,places=5)
        self.assertAlmostEqual(az,161.067669986,places=6)

    def test_projection_roundtrip(self):
        for lat,lon in [(0,0),(-23.27,-47.7),(80,179.9),(-80,-179.9)]:
            x,y=world_pixel(lat,lon,7.35)
            a,b=world_latlon(x,y,7.35)
            self.assertAlmostEqual(a,lat,places=7)
            self.assertAlmostEqual(b,lon,places=7)

    def test_north_wrap_beam_total_width(self):
        station=Station('s',0,0)
        pts=cone_polygon(station,0,60,200,8,800,600)
        self.assertEqual(pts[0],(400,300))
        self.assertLess(pts[1][0],400)
        self.assertGreater(pts[-1][0],400)
        for pt in (pts[1],pts[-1]):
            cx,cy=world_pixel(0,0,8)
            lat,lon=world_latlon(cx+pt[0]-400,cy+pt[1]-300,8)
            az,km=bearing_distance(0,0,lat,lon)
            self.assertAlmostEqual(km,200,places=6)
            self.assertAlmostEqual(min(az,360-az),30,places=6)

    def test_dateline_and_center(self):
        s=Station('s',0,179.8)
        self.assertEqual(screen_point(0,179.8,s,8,800,600),(400,300))
        lat,lon=destination(0,179.8,90,100)
        x,y=screen_point(lat,lon,s,8,800,600)
        self.assertGreater(x,400)
        self.assertLess(x,800)

    def test_scale_fits_circle(self):
        for s in (Station('BR',-23,-47),Station('Fiji',-16,179.9),Station('N',65,20)):
            for radius in (10,200,1000):
                z=fit_zoom(s,radius,800,600)
                for az in range(0,360,15):
                    p=destination(s.lat,s.lon,az,radius)
                    x,y=screen_point(*p,s,z,800,600)
                    self.assertTrue(20<x<780 and 20<y<580,(s,radius,x,y))


class StorageTests(unittest.TestCase):
    def test_settings_persist(self):
        with tempfile.TemporaryDirectory() as f:
            store=SettingsStore(f)
            d=store.load()
            self.assertIsNone(d['station'])
            d.update(station=Station.from_values('PU2PTU',grid='GG66dr'),opening=48.,opacity=.25,target_grid='GG67aa')
            store.save(d)
            new=store.load()
            self.assertEqual(new['station'],d['station'])
            self.assertEqual(new['opening'],48)
            self.assertEqual(new['target_grid'],'GG67aa')
            store.path.write_text('{bad json')
            self.assertIsNone(store.load()['station'])

    def test_corrupt_settings(self):
        with tempfile.TemporaryDirectory() as f:
            store=SettingsStore(f)
            store.folder.mkdir(exist_ok=True)
            store.path.write_text(json.dumps({'station':{'lat':999,'lon':0},'opacity':'nan','opening':0}))
            d=store.load()
            self.assertIsNone(d['station'])
            self.assertEqual(d['opacity'],.22)
            self.assertEqual(d['opening'],60)

    def test_tile_cache_without_network(self):
        with tempfile.TemporaryDirectory() as f:
            tiles=TileStore(f,online=True)
            try:
                key=(3,4,5);p=tiles.path(key);p.parent.mkdir(parents=True)
                Image.new('RGB',(256,256),'white').save(p)
                with patch('rotor_map.urlopen',side_effect=AssertionError('network used')):
                    img,err=tiles._load(key)
                self.assertEqual(img.getpixel((0,0)),(255,255,255))
                self.assertEqual(err,'')
                self.assertEqual(CACHE_SECONDS,604800)
            finally:tiles.close()

    def test_tile_http_identity_and_conditional(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory() as f:
            tiles=TileStore(f)
            try:
                key=(3,4,5);p=tiles.path(key);p.parent.mkdir(parents=True)
                Image.new('RGB',(256,256),'white').save(p)
                p.with_suffix('.json').write_text(json.dumps({'etag':'test-etag'}))
                import os
                os.utime(p,(0,0))
                received=[]
                def mock_url(req,timeout):
                    received.append(dict(req.header_items()))
                    from urllib.error import HTTPError
                    raise HTTPError(req.full_url,304,'Not modified',{},None)
                with patch('rotor_map.urlopen',mock_url):img,err=tiles._load(key)
                self.assertIsNotNone(img)
                self.assertEqual(received[0]['User-agent'],USER_AGENT)
                self.assertEqual(received[0]['If-none-match'],'test-etag')
                self.assertNotIn('Cache-control',received[0])
            finally:tiles.close()

    def test_failed_network_keeps_cached_tile(self):
        with tempfile.TemporaryDirectory() as f:
            tiles=TileStore(f)
            try:
                key=(3,4,5);p=tiles.path(key);p.parent.mkdir(parents=True)
                Image.new('RGB',(256,256),'white').save(p)
                import os
                os.utime(p,(0,0))
                with patch('rotor_map.urlopen',side_effect=OSError('offline')):
                    img,err=tiles._load(key)
                self.assertIsNotNone(img)
                self.assertIn('rede',err)
            finally:tiles.close()


if __name__=='__main__':unittest.main()
