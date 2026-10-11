# sun position shared by the bake, the sky and the previews (ux/art-direction.md 3.1):
# latitude 37°, declination +19°, solar noon 12:00 so the sun sets at 19:00; local −X is the gate street = azimuth 294°.
# Other scenes (the road stops, F-10) set SCENE_MINUS_X_AZ to the azimuth of their own local −X.
import math, os
from mathutils import Vector
MINUTE = int(os.environ.get('PLAZA_BAKE_MINUTE', '1110'))       # 18:30
MINUS_X_AZ = float(os.environ.get('SCENE_MINUS_X_AZ', '294'))
def sun_local(minute=MINUTE):
    phi, dec = math.radians(37.0), math.radians(19.0)
    H = math.radians(15.0 * (minute / 60.0 - 12.0))
    se = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H)
    e = math.asin(se)
    ca = (math.sin(dec) - se * math.sin(phi)) / (math.cos(e) * math.cos(phi))
    A = math.acos(max(-1.0, min(1.0, ca)))
    if H > 0: A = 2 * math.pi - A
    d = A - math.radians(MINUS_X_AZ)
    return Vector((-math.cos(e) * math.cos(d), math.cos(e) * math.sin(d), math.sin(e))), math.degrees(e), math.degrees(A)
