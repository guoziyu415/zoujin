# Plaza (from S7): physically based sky (Blender multiple-scattering model) for both the bake and the page.
# Renders the world through an equirect panoramic camera, checks the mapping against Blender's own
# environment lookup, scales the sky to a target horizontal irradiance and writes sky_sunset.hdr.
import bpy, math, sys, os
import numpy as np
from mathutils import Vector, Matrix
OUT = os.environ['PLAZA_OUT']  # work dir (build.sh sets it); nothing here is committed
ROT = Matrix.Rotation(math.radians(float(os.environ.get('SCENE_ROT_DEG', '144'))), 4, 'Z')   # as build_<scene>.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs(f'{OUT}/skytest', exist_ok=True)
from sunpos import sun_local
SUN_LOCAL, _E, _A = sun_local(); SUN_ELEV = math.radians(_E)
# SKY_SUN_ELEV_DEG: draw the sky for another sun height, same direction (the road's dawn river: the earth shadow and
# the pink band read only with the sun just below the horizon, homeward-road.md 1.5)
if os.environ.get('SKY_SUN_ELEV_DEG'):
    SUN_ELEV = math.radians(float(os.environ['SKY_SUN_ELEV_DEG']))
    print(f'sky drawn for {math.degrees(SUN_ELEV):.2f} deg instead')
print(f'sun at {_E:.2f} deg elevation, azimuth {_A:.1f}')
TARGET_E_SKY = float(os.environ.get('E_SKY', '0.9'))     # sky irradiance on a horizontal plane, same units as the lamp's 6.0
sd = (ROT @ SUN_LOCAL).normalized()
print('SUN_DIR_TO_SUN (blender)', tuple(round(c, 5) for c in sd))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
scene.cycles.samples = 16; scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'
scene.view_settings.exposure = 0; scene.view_settings.gamma = 1
cam_d = bpy.data.cameras.new('pano'); cam_d.type = 'PANO'
cam_d.panorama_type = 'EQUIRECTANGULAR'
cam = bpy.data.objects.new('pano', cam_d); scene.collection.objects.link(cam); scene.camera = cam
cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
world = bpy.data.worlds.new('World'); scene.world = world; world.use_nodes = True
N = world.node_tree.nodes; L = world.node_tree.links; bg = N['Background']

def render(w, h, path):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]   # row 0 = top
    bpy.data.images.remove(im)
    return a

def blender_equirect_dir(h, w):
    # Blender: u = -atan2(y, x) / 2pi + 0.5, v = atan2(z, hypot(x, y)) / pi + 0.5 (v=1 at the zenith)
    v = 1 - (np.arange(h) + 0.5) / h; u = (np.arange(w) + 0.5) / w
    el = (v - 0.5) * math.pi; az = -(u - 0.5) * 2 * math.pi
    E, A = np.meshgrid(el, az, indexing='ij')
    return np.stack([np.cos(E) * np.cos(A), np.cos(E) * np.sin(A), np.sin(E)], -1), E

# 1. mapping check: the panoramic render of an environment texture must equal the texture itself
# (S7 used a downloaded HDRI here; a synthetic one with a lopsided bright blob checks the same thing)
_tw, _th = 512, 256
_yy, _xx = np.mgrid[0:_th, 0:_tw].astype(np.float32)
_test = 0.2 + 0.6 * (_yy / _th) + 6.0 * np.exp(-(((_xx - 140) / 18) ** 2 + ((_yy - 80) / 12) ** 2))
_test = _test + 2.0 * np.exp(-(((_xx - 400) / 40) ** 2 + ((_yy - 190) / 25) ** 2))
_img = bpy.data.images.new('maptest', _tw, _th, float_buffer=True, alpha=False)
_img.pixels = np.concatenate([np.repeat(_test[::-1, :, None], 3, -1), np.ones((_th, _tw, 1), np.float32)], -1).ravel()
env = N.new('ShaderNodeTexEnvironment'); env.image = _img
L.new(env.outputs['Color'], bg.inputs['Color'])
pano = render(256, 128, f'{OUT}/skytest/check.exr')
src = np.array(env.image.pixels[:], dtype=np.float32).reshape(env.image.size[1], env.image.size[0], 4)[::-1, :, :3]
sh, sw = src.shape[:2]
srcs = src.reshape(128, sh // 128, 256, sw // 256, 3).mean((1, 3))
lp, ls = np.log1p(pano.mean(-1)), np.log1p(srcs.mean(-1))
corr = np.corrcoef(lp.ravel(), ls.ravel())[0, 1]
flip = np.corrcoef(lp.ravel(), ls[:, ::-1].ravel())[0, 1]
print(f'mapping check: corr {corr:.4f} (mirrored {flip:.4f})')
assert corr > 0.97, 'panoramic camera does not match the environment mapping'

# 2. the sky
N.remove(env)
sky = N.new('ShaderNodeTexSky'); sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_disc = False
sky.sun_elevation = SUN_ELEV
sky.altitude = 0
sky.air_density = 1.0; sky.aerosol_density = float(os.environ.get('AEROSOL', '2.5')); sky.ozone_density = 1.0
az_sun = math.atan2(sd.y, sd.x)
# find sun_rotation so the brightest sky lands at the sun azimuth (the convention differs between sky models)
best = None
for rot in (math.pi / 2 - az_sun, az_sun - math.pi / 2, -az_sun, az_sun, math.pi / 2 + az_sun):
    sky.sun_rotation = rot % (2 * math.pi)
    L.new(sky.outputs['Color'], bg.inputs['Color'])
    p = render(128, 64, f'{OUT}/skytest/rot.exr')
    lum = p.mean(-1); lum[32:] = 0
    i, j = np.unravel_index(np.argmax(lum), lum.shape)
    d, _ = blender_equirect_dir(64, 128)
    az_b = math.atan2(d[i, j][1], d[i, j][0])
    err = abs((math.degrees(az_b - az_sun) + 180) % 360 - 180)    # azimuth only: without the disc the glow peaks below the sun
    print(f'sun_rotation {math.degrees(rot) % 360:.1f} -> brightest sky {err:.1f} deg of azimuth from the lamp')
    if best is None or err < best[0]: best = (err, rot)
assert best[0] < 8, 'could not align the sky sun with the lamp'
sky.sun_rotation = best[1] % (2 * math.pi)
W, H = int(os.environ.get('SKY_W', '1024')), int(os.environ.get('SKY_H', '512'))
p = render(W, H, f'{OUT}/skytest/sky.exr')
d, E = blender_equirect_dir(H, W)
dw = (2 * math.pi / W) * (math.pi / H) * np.cos(E)
up = E > 0
e_h = float((p.mean(-1) * np.sin(E) * dw)[up].sum())
k = TARGET_E_SKY / e_h
p *= k
print(f'horizontal sky irradiance {e_h:.4f} at strength 1 -> scale {k:.5f}')
# below the horizon the model is black; fill it with a dim warm ground bounce so reflections are not void
horizon = p[H // 2 - 2:H // 2].mean(0)
p[H // 2:] = horizon[None] * 0.25
im = bpy.data.images.new('sky', W, H, float_buffer=True, alpha=False)
im.pixels = np.concatenate([p[::-1], np.ones((H, W, 1), np.float32)], -1).ravel()
im.filepath_raw = f'{OUT}/sky_sunset.hdr'; im.file_format = 'HDR'; im.save()
# preview + horizon colour for the page's fog
pv = p / (1 + p); pv = (np.clip(pv, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
from PIL import Image
Image.fromarray(pv).save(f'{OUT}/skytest/sky_preview.png')
away = [abs(((math.degrees(-((j + 0.5) / W - 0.5) * 2 * math.pi) - math.degrees(az_sun) + 180) % 360) - 180) > 60 for j in range(W)]
hz = p[H // 2 - int(H * 4 / 180):H // 2, np.array(away)].mean((0, 1))
print('horizon (away from sun) linear rgb', [round(float(c), 4) for c in hz], 'sun-side', [round(float(c), 3) for c in p[H // 2 - 6:H // 2, :].max((0, 1))])
print('sky done')
