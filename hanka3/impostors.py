# Bake Poly Haven trees into impostor atlases (3 views side by side, transparent background).
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python hanka3/impostors.py
# Needs hanka3/assets_src/ (see fetch_assets.py). Writes hanka3/impostors/<name>.png + impostors.json.
import bpy, os, json, math
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "assets_src")
OUT = os.path.join(ROOT, "impostors")
VIEWS = 3
RES_Y = 1024

TREES = [
    ("pine_a", "pine_tree_01", "pine_tree_01_a_LOD1"),
    ("pine_b", "pine_tree_01", "pine_tree_01_b_LOD1"),
    ("fir_a", "fir_tree_01", "fir_tree_01_a_LOD1"),
    ("fir_b", "fir_tree_01", "fir_tree_01_b_LOD1"),
    ("fir_c", "fir_tree_01", "fir_tree_01_c_LOD1"),
    ("pine_sap", "pine_sapling_small", "pine_sapling_small_a"),
    ("fir_sap", "fir_sapling", "fir_sapling_a"),
    ("fern", "fern_02", "fern_02_b"),
    ("grass", "grass_medium_01", "grass_medium_01_geonodes_large_a_LOD0"),
    ("grass_b", "grass_medium_01", "grass_medium_01_geonodes_large_b_LOD0"),
]


def append(asset, obj_name):
    path = os.path.join(SRC, asset, f"{asset}_1k.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [obj_name]
    o = dst.objects[0]
    bpy.context.scene.collection.objects.link(o)
    # appended images keep paths relative to the source .blend
    for img in bpy.data.images:
        if img.filepath.startswith("//"):
            img.filepath = os.path.join(SRC, asset, img.filepath[2:])
            img.reload()
    return o


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.eevee.taa_render_samples = 32
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 1.0          # even sky light: albedo with soft occlusion, relit in the app
    sc.world = w
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def bake(name, asset, obj_name, meta):
    sc, cam = setup_scene()
    o = append(asset, obj_name)
    # matrix_world of a freshly appended object is still identity here; its own TRS is what renders
    bb = [o.matrix_basis @ Vector(c) for c in o.bound_box]
    x0, x1 = min(v.x for v in bb), max(v.x for v in bb)
    y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
    z0, z1 = min(v.z for v in bb), max(v.z for v in bb)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h = (z1 - z0) * 1.02
    w = max(x1 - x0, y1 - y0) * 1.05
    # keep the atlas within 2048 px wide (low, wide plants would otherwise blow up)
    ry = min(RES_Y, int(2048 / VIEWS * h / w) // 8 * 8)
    rx = max(64, int(round(ry * w / h / 8)) * 8)
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    cam.data.ortho_scale = max(h, w)
    tiles = []
    for k in range(VIEWS):
        a = math.pi * k / VIEWS
        d = Vector((math.sin(a), -math.cos(a), 0.0))
        cam.location = Vector((cx, cy, z0 + h / 2)) + d * 60
        cam.rotation_euler = (math.pi / 2, 0, a)
        f = os.path.join(OUT, f"_{name}_{k}.png")
        sc.render.filepath = f
        bpy.ops.render.render(write_still=True)
        tiles.append(f)
    import numpy as np
    imgs = [bpy.data.images.load(f) for f in tiles]
    arrs = [np.array(i.pixels[:], dtype=np.float32).reshape(ry, rx, 4) for i in imgs]
    atlas = np.concatenate(arrs, axis=1)
    out = bpy.data.images.new(name, rx * VIEWS, ry, alpha=True)
    out.pixels.foreach_set(atlas.ravel())
    out.filepath_raw = os.path.join(OUT, f"{name}.png")
    out.file_format = "PNG"
    out.save()
    for f in tiles:
        os.remove(f)
    meta[name] = {"w": w, "h": h, "views": VIEWS, "ox": cx - (x0 + x1) / 2, "z0": z0}
    print("BAKED", name, f"{w:.1f} x {h:.1f} m", rx * VIEWS, "x", ry)


os.makedirs(OUT, exist_ok=True)
meta_path = os.path.join(OUT, "impostors.json")
meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
for name, asset, obj in TREES:
    if name in meta and os.path.exists(os.path.join(OUT, f"{name}.png")):
        continue
    bake(name, asset, obj, meta)
    json.dump(meta, open(meta_path, "w"), indent=1)
