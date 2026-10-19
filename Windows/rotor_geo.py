"""Geometria independente da interface. Azimutes verdadeiros, WGS84."""
from dataclasses import dataclass
import math
import re
from geographiclib.geodesic import Geodesic

TILE_SIZE = 256
MAX_LAT = 85.0


def number(value, minimum, maximum, label):
    try:
        result = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        raise ValueError(f'{label}: informe um número de {minimum:g} a {maximum:g}.')
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f'{label}: informe um número de {minimum:g} a {maximum:g}.')
    return result


def locator_center(text):
    """Centro do Maidenhead de 2, 4 ou 6 caracteres; sem geocodificação online."""
    grid = str(text).strip().upper()
    if not re.fullmatch(r'[A-R]{2}(?:[0-9]{2}(?:[A-X]{2})?)?', grid):
        raise ValueError('Grid inválido. Use 2, 4 ou 6 caracteres, como GG66 ou GG66dr.')
    lon = -180 + (ord(grid[0])-65)*20
    lat = -90 + (ord(grid[1])-65)*10
    dx, dy = 20.0, 10.0
    if len(grid) >= 4:
        lon += int(grid[2])*2
        lat += int(grid[3])
        dx, dy = 2.0, 1.0
    if len(grid) == 6:
        lon += (ord(grid[4])-65)/12
        lat += (ord(grid[5])-65)/24
        dx, dy = 1/12, 1/24
    return lat+dy/2, lon+dx/2


def canonical_locator(text):
    grid = str(text).strip().upper()
    locator_center(grid)
    return grid[:4] + grid[4:].lower()


@dataclass(frozen=True)
class Station:
    name: str
    lat: float
    lon: float
    grid: str = ''

    @classmethod
    def from_values(cls, name, lat=None, lon=None, grid=''):
        name = str(name).strip()[:40] or 'Estação'
        if grid:
            grid = canonical_locator(grid)
            lat, lon = locator_center(grid)
        lat = number(lat, -MAX_LAT, MAX_LAT, 'Latitude do mapa')
        lon = number(lon, -180, 180, 'Longitude')
        return cls(name, lat, lon, grid)


def bearing_distance(lat1, lon1, lat2, lon2):
    g = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    if not math.isfinite(g['s12']) or g['s12'] < 1:
        raise ValueError('Destino coincide com a estação; escolha outro grid.')
    return g['azi1'] % 360, g['s12']/1000


def destination(lat, lon, bearing, km):
    g = Geodesic.WGS84.Direct(lat, lon, bearing, km*1000)
    return g['lat2'], g['lon2']


def world_pixel(lat, lon, zoom):
    lat = max(-85.05112878, min(85.05112878, lat))
    scale = TILE_SIZE * 2**zoom
    sine = math.sin(math.radians(lat))
    return ((lon+180)/360*scale,
            (0.5-math.log((1+sine)/(1-sine))/(4*math.pi))*scale)


def world_latlon(x, y, zoom):
    scale = TILE_SIZE * 2**zoom
    return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/scale)))), (x/scale*360-180+180)%360-180


def screen_point(lat, lon, station, zoom, width, height):
    x, y = world_pixel(lat, lon, zoom)
    cx, cy = world_pixel(station.lat, station.lon, zoom)
    span = TILE_SIZE*2**zoom
    dx = (x-cx+span/2)%span-span/2
    return width/2+dx, height/2+y-cy


def fit_zoom(station, radius_km, width, height):
    """Zoom fracionário: círculo geodésico de referência cabe na janela."""
    cx, cy = world_pixel(station.lat, station.lon, 0)
    xx, yy = .0001, .0001
    for az in range(0, 360, 15):
        lat, lon = destination(station.lat, station.lon, az, radius_km)
        x, y = world_pixel(lat, lon, 0)
        xx = max(xx, abs((x-cx+128)%256-128))
        yy = max(yy, abs(y-cy))
    factor = min(max(width-70, 20)/(2*xx), max(height-70, 20)/(2*yy))
    return max(1.0, min(18.0, math.log2(factor)))


def cone_polygon(station, azimuth, opening, radius_km, zoom, width, height):
    """Setor geodésico; opening é a abertura TOTAL entre limites a −3 dB."""
    points = [(width/2, height/2)]
    count = max(12, int(math.ceil(opening/2)))
    for i in range(count+1):
        az = azimuth-opening/2 + opening*i/count
        lat, lon = destination(station.lat, station.lon, az, radius_km)
        points.append(screen_point(lat, lon, station, zoom, width, height))
    return points
