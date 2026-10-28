# Hanka 3 (MG Projekt) + neighbourhood: parametric Blender build, exported straight to GLB.
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python hanka3/build.py
#
# Source: mgprojekt.com.pl/hanka-3 — usable 176.15 m², building 18.68 x 22.57 m, roof 30°,
# height 5.71 m (5.96 m with plinth), room height 2.70 m, walls: 24 cm aerated concrete + EPS + thin render.
# Plan geometry was measured from the published ground-floor plan at 35.39 px/m (both axes agree with the
# 6.49 / 5.70 / 6.49 and 5.54 / 2.64 / 10.09 / 4.30 m dimension chains).
#
# Plan coordinates (x, y) in metres: x from the west outer face, y from the back (north) outer face of the
# bedroom wing. Blender: X = x (east), Y = -y (north up), Z up. Front of the house faces south (road).
import bpy, bmesh, math, os, random
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, "textures")
OUT = os.path.join(ROOT, "hanka3.glb")

# ---------------- parameters ----------------
FFL = 0.25                      # finished floor (plinth 25 cm above terrain)
ROOM_H = 2.70
CEIL = FFL + ROOM_H             # flat ceilings
PLATE = 3.00                    # rafter underside at the outer wall face
TAN = math.tan(math.radians(30))
RT_V = 0.30                     # roof build-up measured vertically (rafter + battens + tiles)
OV = 0.50                       # eave overhang (horizontal)
VERGE = 0.30                    # gable verge
T_EXT = 0.45                    # 24 cm aerated concrete + 20 cm EPS + render (PL standard)
WT = PLATE + T_EXT * TAN + 0.02 # eave walls reach the roof underside at their inner face
HEAD = 2.25                     # window / external door head above FFL (all published windows are full height)
DOOR_H = 2.05                   # internal doorway (otwór 90 x 205 for an "80" leaf)

# wings (outer faces)
LW = (0.00, 6.49, 8.19, 18.28)      # living + kitchen wing
MB = (6.49, 12.21, 8.19, 16.28)     # entrance / dining block
RW = (12.21, 18.68, 0.00, 16.78)    # bedroom wing
CARPORT_Y1 = 22.35                  # carport + store under the bedroom-wing roof
LW_BACK = 5.24                      # living-wing roof runs on over the covered terrace (posts at y 5.54)

LW_RIDGE_X, LW_HS = 3.245, 3.245
RW_RIDGE_X, RW_HS = 15.445, 3.235
MB_RIDGE_Y, MB_HS = 12.235, 4.045

PLOT = (-8.0, 26.0, -10.0, 30.0)    # our plot (x0, x1, y0, y1); road along the south side
ROAD_Y = (30.6, 35.1)

random.seed(3)

# ---------------- scene ----------------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

COL = None
def coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

# ---------------- materials ----------------
MATS = {}
def srgb(r, g, b):
    f = lambda c: (c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b))

def img_mat(name, folder, tile, tint=(1, 1, 1), rough=1.0, rot=False, color=None, grain=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    uv = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1)
    if rot:
        mp.inputs["Rotation"].default_value[2] = math.pi / 2
    nt.links.new(uv.outputs["UV"], mp.inputs[0])
    def tex(fname, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(os.path.join(TEX, folder, fname), check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs[0], n.inputs[0])
        return n
    d = tex("diff.jpg", False)
    if color is not None:
        # exact palette colour: texture only modulates brightness, baked once to gray_<grain>.png
        gpath = os.path.join(TEX, folder, f"gray_{int(grain * 100)}.png")
        if not os.path.exists(gpath):
            import numpy as np
            src = d.image; w_, h_ = src.size
            px = np.empty(w_ * h_ * 4, dtype=np.float32); src.pixels.foreach_get(px); px = px.reshape(-1, 4)
            lum = px[:, 0] * 0.2126 + px[:, 1] * 0.7152 + px[:, 2] * 0.0722
            v = np.clip(1 - grain + grain * lum / (float(lum.mean()) or 0.5), 0, 1) * 0.999
            o = np.stack([v, v, v, np.ones_like(v)], 1).ravel()
            g = bpy.data.images.new(f"gray_{folder}_{int(grain * 100)}", w_, h_, float_buffer=False)
            g.colorspace_settings.name = "Non-Color"; g.pixels.foreach_set(o)
            g.filepath_raw = gpath; g.file_format = "PNG"; g.save()
            bpy.data.images.remove(g)
        d.image = bpy.data.images.load(gpath, check_existing=True)
        d.image.colorspace_settings.name = "Non-Color"
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs["A"].default_value = (*color, 1)
        nt.links.new(d.outputs[0], mix.inputs["B"])
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    elif tint != (1, 1, 1):
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(d.outputs[0], mix.inputs["A"])
        mix.inputs["B"].default_value = (*tint, 1)
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    else:
        nt.links.new(d.outputs[0], bsdf.inputs["Base Color"])
    r = tex("rough.jpg", True)
    if rough != 1.0:
        mth = nt.nodes.new("ShaderNodeMath"); mth.operation = "MULTIPLY"; mth.inputs[1].default_value = rough
        nt.links.new(r.outputs[0], mth.inputs[0]); nt.links.new(mth.outputs[0], bsdf.inputs["Roughness"])
    else:
        nt.links.new(r.outputs[0], bsdf.inputs["Roughness"])
    nrm = tex("nor.jpg", True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    MATS[name] = m
    return m

def flat_mat(name, color, rough=0.5, metal=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    if alpha < 1:
        m.surface_render_method = "BLENDED"
    MATS[name] = m
    return m

def make_materials():
    img_mat("Tynk_elewacja", "white_plaster_02", 3.0, color=srgb(240, 238, 233), grain=0.12, rough=0.9)
    img_mat("Cokol", "white_plaster_02", 3.0, color=srgb(70, 72, 75), grain=0.2, rough=0.9)
    img_mat("Dachowka_grafit", "grey_roof_tiles_02", 2.0, color=srgb(52, 54, 57), grain=0.5, rough=0.95)
    img_mat("Dachowka_czerwona", "grey_roof_tiles_02", 2.0, color=srgb(150, 62, 44), grain=0.5, rough=0.7)
    img_mat("Dachowka_pomaranczowa", "grey_roof_tiles_02", 2.0, color=srgb(196, 92, 48), grain=0.5, rough=0.7)
    img_mat("Dachowka_ciemna", "grey_roof_tiles_02", 2.0, color=srgb(62, 66, 74), grain=0.5, rough=0.7)
    img_mat("Deski_pionowe", "wooden_planks", 2.0, color=srgb(128, 90, 62), grain=0.55, rot=True)
    img_mat("Deski_poziome", "wooden_planks", 2.0, color=srgb(128, 90, 62), grain=0.55)
    img_mat("Podbitka", "wooden_planks", 2.0, color=srgb(168, 124, 84), grain=0.5)
    img_mat("Drewno_konstr", "fine_grained_wood", 1.2, color=srgb(176, 132, 90), grain=0.45)
    img_mat("Deski_taras", "wooden_planks", 1.5, color=srgb(140, 104, 74), grain=0.55)
    img_mat("Kamien", "stacked_stone_wall", 1.5, color=srgb(196, 178, 150), grain=0.6)
    img_mat("Podloga", "wood_floor", 2.0)
    img_mat("Plytki", "long_white_tiles", 1.2)
    img_mat("Trawa", "leafy_grass", 3.0, tint=(0.42, 0.62, 0.25))
    img_mat("Laka", "leafy_grass", 3.0, tint=(0.66, 0.74, 0.32))
    img_mat("Droga_zwir", "sandy_gravel", 2.0, color=srgb(196, 184, 164), grain=0.6)
    img_mat("Kostka_szara", "concrete_pavers_02", 1.6, color=srgb(170, 168, 164), grain=0.5)
    img_mat("Plyty_beton", "patterned_concrete_pavers_03", 2.0, color=srgb(196, 194, 188), grain=0.4)
    flat_mat("Tynk_wew", srgb(236, 234, 228), rough=0.9)
    flat_mat("Biel", srgb(245, 245, 242), rough=0.5)
    flat_mat("Rama_okna", srgb(56, 60, 64), rough=0.45)
    flat_mat("Szklo", (0.05, 0.07, 0.08), rough=0.03, alpha=0.35)
    flat_mat("Blacha_grafit", srgb(52, 56, 60), rough=0.35, metal=0.5)
    flat_mat("Prog", srgb(90, 90, 88), rough=0.6)
    flat_mat("Beton", srgb(150, 150, 146), rough=0.9)
    flat_mat("Beton_grafit", srgb(70, 72, 74), rough=0.8)
    flat_mat("PV", srgb(18, 26, 48), rough=0.15, metal=0.3)
    flat_mat("Ogrodzenie", srgb(52, 56, 60), rough=0.4, metal=0.5)
    flat_mat("Drzwi_wew", srgb(236, 232, 224), rough=0.5)
    flat_mat("Palenisko", (0.02, 0.02, 0.02), rough=0.9)
    flat_mat("Lampa_LED", (0.05, 0.05, 0.05), rough=0.4, metal=0.6)
    flat_mat("Kolizja", (1, 0, 1), rough=1.0)
    flat_mat("Kora", (0.14, 0.09, 0.06), rough=0.9)
    flat_mat("Kora_sosna", srgb(104, 78, 60), rough=0.9)
    flat_mat("Igliwie", srgb(38, 62, 34), rough=0.85)
    flat_mat("Liscie", srgb(70, 92, 40), rough=0.75)
    flat_mat("Liscie_krzew", srgb(48, 78, 40), rough=0.75)
    flat_mat("Trawa_ozdobna", srgb(186, 170, 120), rough=0.8)
    flat_mat("Lawenda", srgb(130, 105, 170), rough=0.8)
    flat_mat("Hortensja", srgb(238, 236, 228), rough=0.8)
    flat_mat("Sciana_sasiad", srgb(236, 234, 226), rough=0.9)
    flat_mat("Sciana_sasiad_bez", srgb(222, 206, 178), rough=0.9)
    flat_mat("Okno_sasiad", srgb(30, 36, 44), rough=0.1)

# ---------------- mesh helpers ----------------
def new_obj(name, bm, mat=None, col=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    (col or COL).objects.link(o)
    if mat:
        o.data.materials.append(MATS[mat])
    return o

def bm_box(bm, a, b):
    (x0, y0, z0), (x1, y1, z1) = a, b
    v = [bm.verts.new(p) for p in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]]
    for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
        bm.faces.new([v[i] for i in f])

def wbox(name, a, b, mat=None):
    """box in Blender coords"""
    bm = bmesh.new()
    bm_box(bm, [min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)])
    return new_obj(name, bm, mat)

def pb(name, x0, x1, y0, y1, z0, z1, mat=None):
    """box in plan coords (y from the back) -> Blender"""
    return wbox(name, (x0, -y1, z0), (x1, -y0, z1), mat)

def prism(name, pts2d, axis, t0, t1, mat=None):
    """Extrude polygon (u, z) along Blender axis 'x' (u = Blender Y) or 'y' (u = Blender X), t0..t1."""
    bm = bmesh.new()
    P = (lambda u, z, t: (t, u, z)) if axis == "x" else (lambda u, z, t: (u, t, z))
    a = [bm.verts.new(P(u, z, t0)) for u, z in pts2d]
    b = [bm.verts.new(P(u, z, t1)) for u, z in pts2d]
    n = len(pts2d)
    bm.faces.new(a[::-1]); bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], b[j], b[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_obj(name, bm, mat)

def cyl(bm, p0, p1, r, verts=8):
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0
    rot = ax.to_track_quat("Z", "Y")
    angs = [2 * math.pi * i / verts for i in range(verts)]
    r0 = [bm.verts.new(p0 + rot @ Vector((r * math.cos(a), r * math.sin(a), 0))) for a in angs]
    r1 = [bm.verts.new(p0 + rot @ Vector((r * math.cos(a), r * math.sin(a), ax.length))) for a in angs]
    for i in range(verts):
        j = (i + 1) % verts
        bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
    bm.faces.new(r0[::-1]); bm.faces.new(r1)

def blob(bm, c, rx, ry, rz, sub=1):
    m = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    for v in m["verts"]:
        jit = 0.85 + 0.3 * random.random()
        v.co = Vector((c[0] + v.co.x * rx * jit, c[1] + v.co.y * ry * jit, c[2] + v.co.z * rz * jit))

def cone(bm, c, r, h, segs=8):
    m = bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=0.0, depth=h)
    for v in m["verts"]:
        v.co += Vector((c[0], c[1], c[2] + h / 2))

def join(objs, name, mat=None):
    objs = [o for o in objs if o]
    if not objs:
        return None
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy(); tmp.transform(o.matrix_world)
        bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    keep = objs[0]
    for o in objs[1:]:
        me = o.data; bpy.data.objects.remove(o, do_unlink=True)
        if me.users == 0: bpy.data.meshes.remove(me)
    keep.matrix_world.identity()
    bm.to_mesh(keep.data); bm.free()
    keep.name = name
    if mat:
        keep.data.materials.clear(); keep.data.materials.append(MATS[mat])
    return keep

def mesh_obj(name, build, mat):
    bm = bmesh.new(); build(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_obj(name, bm, mat)

def apply_mods(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    old = o.data; o.modifiers.clear(); o.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)

def cut_obj(o, cutter):
    m = o.modifiers.new("Cut", "BOOLEAN")
    m.operation = "DIFFERENCE"; m.object = cutter; m.solver = "EXACT"
    apply_mods(o)

def remove(o):
    me = o.data; bpy.data.objects.remove(o, do_unlink=True)
    if me and me.users == 0: bpy.data.meshes.remove(me)

def planar_uv(o, rot=False):
    """World-metre planar UVs per face (tangent = horizontal, bitangent = up-slope). GLB-safe."""
    me = o.data
    if not me.polygons:
        return
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active.data
    mw = o.matrix_world
    up = Vector((0, 0, 1))
    for poly in me.polygons:
        n = (mw.to_3x3() @ poly.normal).normalized()
        if abs(n.z) > 0.985:
            t, b = Vector((1, 0, 0)), Vector((0, 1, 0))
        else:
            t = up.cross(n).normalized(); b = n.cross(t).normalized()
        for li in poly.loop_indices:
            p = mw @ me.vertices[me.loops[li].vertex_index].co
            u, v = p.dot(t), p.dot(b)
            uvl[li].uv = (v, u) if rot else (u, v)

def set_face_mats(o, pick):
    """pick(center, normal) -> material name; rebuilds the slot list."""
    names = []
    picks = []
    for p in o.data.polygons:
        n = pick(o.matrix_world @ p.center, (o.matrix_world.to_3x3() @ p.normal).normalized())
        if n not in names:
            names.append(n)
        picks.append(names.index(n))
    o.data.materials.clear()
    for n in names:
        o.data.materials.append(MATS[n])
    for p, i in zip(o.data.polygons, picks):
        p.material_index = i

# ---------------- house footprint ----------------
def in_house(x, y):
    for x0, x1, y0, y1 in (LW, MB, RW):
        if x0 < x < x1 and y0 < y < y1:
            return True
    return False

def wall_face_mat(c, n):
    if abs(n.z) > 0.5:
        return "Tynk_wew"
    p = c + n * 0.03
    if in_house(p.x, -p.y):
        return "Tynk_wew"
    return "Cokol" if c.z < FFL - 1e-3 else "Tynk_elewacja"

# ---------------- walls with openings ----------------
WALLS, OPENINGS = [], []

def wall(name, x0, x1, y0, y1, top, ops=(), ext=True, out=None):
    """Wall box split around openings. ops: (a0, a1, sill, head, kind) along the long axis.
    kind: win | fix | hs | entry | door | open. out: N/S/E/W outward side (external walls)."""
    along_x = (x1 - x0) >= (y1 - y0)
    def seg(a0, a1, z0, z1, mat_name=None):
        if a1 - a0 < 1e-4 or z1 - z0 < 1e-4:
            return None
        if along_x:
            return pb("w", a0, a1, y0, y1, z0, z1, mat_name)
        return pb("w", x0, x1, a0, a1, z0, z1, mat_name)
    A0, A1 = (x0, x1) if along_x else (y0, y1)
    parts, cur = [], A0
    split = [0.0, FFL, top] if ext else [0.0, top]
    for a0, a1, sill, head, kind in sorted(ops):
        for z0, z1 in zip(split, split[1:]):
            parts.append(seg(cur, a0, z0, z1))
        if sill > 0:
            for z0, z1 in zip([0.0, FFL], [FFL, FFL + sill]):
                parts.append(seg(a0, a1, z0, z1))
        else:
            thr = seg(a0, a1, 0.0, FFL, "Prog")
            thr.name = f"Prog_{name}"
        if FFL + head < top:
            parts.append(seg(a0, a1, FFL + head, top))
        OPENINGS.append(dict(wall=name, along_x=along_x, a0=a0, a1=a1, t0=(y0 if along_x else x0),
                             t1=(y1 if along_x else x1), sill=sill, head=head, kind=kind, out=out, ext=ext))
        cur = a1
    for z0, z1 in zip(split, split[1:]):
        parts.append(seg(cur, A1, z0, z1))
    o = join(parts, ("Sciana_" if ext else "Sciana_wew_") + name)
    set_face_mats(o, wall_face_mat)
    WALLS.append(o)
    return o

def opening_box(op, a0, a1, d0, d1, z0, z1, name, mat):
    """box inside an opening; d measured across the wall from t0 (plan)"""
    t0 = op["t0"]
    if op["along_x"]:
        return pb(name, a0, a1, t0 + d0, t0 + d1, z0, z1, mat)
    return pb(name, t0 + d0, t0 + d1, a0, a1, z0, z1, mat)

def fill_openings():
    for i, op in enumerate(OPENINGS):
        n = f"{op['wall']}_{i}"
        a0, a1 = op["a0"], op["a1"]
        z0, z1 = FFL + op["sill"], FFL + op["head"]
        T = op["t1"] - op["t0"]
        kind = op["kind"]
        if kind == "open":
            continue
        if kind == "door":
            # adjustable frame (oscieznica) wrapping the wall + leaf opened 90 deg into the +t side
            fr = [opening_box(op, a0, a0 + 0.06, -0.015, T + 0.015, z0, z1, "f", None),
                  opening_box(op, a1 - 0.06, a1, -0.015, T + 0.015, z0, z1, "f", None),
                  opening_box(op, a0, a1, -0.015, T + 0.015, z1 - 0.06, z1, "f", None)]
            join(fr, f"Oscieznica_{n}", "Drzwi_wew")
            lw = a1 - a0 - 0.12
            if op["along_x"]:
                leaf = pb(f"Drzwi_skrzydlo_{n}", a0 + 0.06, a0 + 0.10, op["t1"] + 0.02, op["t1"] + 0.02 + lw, z0 + 0.01, z1 - 0.07, "Drzwi_wew")
            else:
                leaf = pb(f"Drzwi_skrzydlo_{n}", op["t1"] + 0.02, op["t1"] + 0.02 + lw, a0 + 0.06, a0 + 0.10, z0 + 0.01, z1 - 0.07, "Drzwi_wew")
            continue
        # external joinery sits in the masonry, just behind the 20 cm EPS layer
        outer_at_t0 = op["out"] in ("N", "W")
        d0 = 0.20 if outer_at_t0 else T - 0.28
        d1 = d0 + 0.08
        fw = 0.07
        parts, glass = [], []
        F = lambda b0, b1, e0, e1, zz0, zz1: parts.append(opening_box(op, b0, b1, e0, e1, zz0, zz1, "f", None))
        G = lambda b0, b1, zz0, zz1, dd=0.0: glass.append(opening_box(op, b0, b1, d0 + 0.035 + dd, d0 + 0.045 + dd, zz0, zz1, "g", None))
        F(a0, a1, d0, d1, z1 - fw, z1)
        F(a0, a0 + fw, d0, d1, z0, z1)
        F(a1 - fw, a1, d0, d1, z0, z1)
        F(a0, a1, d0, d1, z0, z0 + 0.03 if kind in ("hs", "entry") else z0 + fw)
        zb = z0 + (0.03 if kind in ("hs", "entry") else fw)
        if kind == "hs":
            c = (a0 + a1) / 2; w2 = (a1 - a0 - 2 * fw) / 2
            # left leaf fixed, right leaf slid half-way behind it so the terrace is reachable
            for la, lb, dd in ((a0 + fw, c, 0.0), (c - w2 / 2, c + w2 / 2, 0.05)):
                sw = 0.09
                for b0, b1, zz0, zz1 in ((la, lb, zb, zb + sw), (la, lb, z1 - fw - sw, z1 - fw), (la, la + sw, zb, z1 - fw), (lb - sw, lb, zb, z1 - fw)):
                    parts.append(opening_box(op, b0, b1, d0 - 0.01 + dd, d0 + 0.06 + dd, zz0, zz1, "f", None))
                G(la + sw, lb - sw, zb + sw, z1 - fw - sw, dd)
        elif kind == "entry":
            # door 1.10 m with side lights; leaf open 90 deg inwards
            c = (a0 + a1) / 2; dw = 1.10
            for b in (c - dw / 2 - 0.035, c + dw / 2 - 0.035):
                F(b, b + 0.07, d0, d1, z0, z1)
            G(a0 + fw, c - dw / 2 - 0.035, zb, z1 - fw)
            G(c + dw / 2 + 0.035, a1 - fw, zb, z1 - fw)
            inward = op["t1"] if outer_at_t0 else op["t0"]
            sgn = 1 if outer_at_t0 else -1
            lf0 = inward + sgn * 0.02
            if op["along_x"]:
                ys = sorted((lf0, lf0 + sgn * (dw - 0.08)))
                pb(f"Drzwi_wejsciowe_{n}", c - dw / 2 + 0.035, c - dw / 2 + 0.105, ys[0], ys[1], zb, z1 - fw, "Rama_okna")
        else:   # win / fix: one mullion from 1.5 m
            w = a1 - a0
            if w >= 1.5:
                c = (a0 + a1) / 2
                F(c - 0.04, c + 0.04, d0, d1, z0, z1)
                G(a0 + fw, c - 0.04, zb, z1 - fw); G(c + 0.04, a1 - fw, zb, z1 - fw)
            else:
                G(a0 + fw, a1 - fw, zb, z1 - fw)
        join(parts, f"Okno_rama_{n}", "Rama_okna")
        join(glass, f"Szyba_{n}", "Szklo")

# ---------------- house: walls ----------------
def house_walls():
    W = lambda a0, a1, kind="win": (a0, a1, 0.0, HEAD, kind)
    D = lambda a0, a1: (a0, a1, 0.0, DOOR_H, "door")
    O = lambda a0, a1: (a0, a1, 0.0, DOOR_H, "open")
    T = T_EXT
    # external
    wall("LW_W", 0.00, T, LW[2], LW[3], WT, [W(12.86, 14.67)], out="W")
    wall("Tyl", T, RW[0], LW[2], LW[2] + T, WT, [W(1.75, 4.75, "hs"), W(7.86, 10.85, "hs")], out="N")
    wall("LW_S", T, LW[1], LW[3] - T, LW[3], WT, [W(2.23, 5.14, "fix")], out="S")
    wall("LW_E", 6.05, LW[1], MB[3], LW[3] - T, WT, out="E")
    wall("MB_S", 6.05, RW[0], MB[3] - T, MB[3], WT, [W(6.70, 7.85, "fix"), W(8.15, 10.55, "entry")], out="S")
    wall("RW_W_front", RW[0], RW[0] + T, MB[3] - T, RW[3], WT, out="W")
    wall("RW_S", RW[0] + T, RW[1], RW[3] - T, RW[3], WT, out="S")
    wall("RW_E", RW[1] - T, RW[1], 0.0, RW[3] - T, WT,
         [W(1.24, 2.01), W(5.26, 6.02), W(7.60, 9.10), W(10.48, 11.98), W(13.37, 14.89)], out="E")
    wall("RW_N", RW[0], RW[1] - T, 0.0, T, WT, [W(15.71, 16.42)], out="N")
    wall("RW_W", RW[0], RW[0] + T, T, LW[2] + T, WT, [W(1.95, 3.76), W(5.79, 7.60)], out="W")
    # internal (12 cm partitions, 24 cm where the plan shows load-bearing)
    c = CEIL
    wall("1", 16.42, 16.54, T, 2.89, c, [D(1.40, 2.30)], ext=False)
    wall("2", 16.54, RW[1] - T, 2.77, 2.89, c, ext=False)
    wall("3", 16.42, 16.54, 2.89, 6.81, c, [D(2.95, 3.85)], ext=False)
    wall("4", 13.76, 16.42, 3.87, 3.99, c, ext=False)
    wall("5", 13.76, 13.88, 3.99, 9.69, c, [D(5.85, 6.75), D(8.20, 9.05)], ext=False)
    wall("6", 13.88, RW[1] - T, 6.81, 6.93, c, ext=False)
    wall("7", RW[0] + T, 13.76, 8.50, 8.62, c, [D(12.76, 13.66)], ext=False)
    wall("8", 13.76, RW[1] - T, 9.69, 9.81, c, ext=False)
    wall("9", 13.76, 13.88, 9.81, 12.60, c, [D(9.90, 10.80)], ext=False)
    wall("10", 12.40, 13.76, 10.82, 10.94, c, ext=False)
    wall("11", 12.40, 12.55, LW[2] + T, 13.82, c, [O(8.75, 9.75), O(12.43, 13.82)], ext=False)
    wall("12", 12.55, RW[1] - T, 12.60, 12.72, c, [D(12.80, 13.70)], ext=False)
    wall("13", 14.27, 14.38, 13.94, RW[3] - T, c, ext=False)
    wall("14", 6.05, 14.38, 13.82, 13.94, c, [D(8.90, 9.80)], ext=False)
    wall("15", 6.05, 6.27, 13.94, MB[3] - T, c, [D(14.55, 15.45)], ext=False)
    wall("16", 7.97, 8.09, 13.94, MB[3] - T, c, [D(14.55, 15.45)], ext=False)
    wall("17", 10.65, 10.77, 13.94, MB[3] - T, c, [D(14.55, 15.45)], ext=False)
    wall("18", 12.43, 12.66, 13.94, MB[3] - T, c, [D(14.55, 15.45)], ext=False)

# roof undersides (plan coords)
def lw_under(x): return PLATE + (LW_HS - abs(x - LW_RIDGE_X)) * TAN
def rw_under(x): return PLATE + (RW_HS - abs(x - RW_RIDGE_X)) * TAN
def mb_under(y): return PLATE + (MB_HS - abs(y - MB_RIDGE_Y)) * TAN

def gable_along_x(name, x0, x1, y0, y1, under, z_bot, mat, step=None):
    """wall infill between y0..y1 (thickness) whose top follows under(x) over x0..x1 (+3 cm into the roof)"""
    # sampled so the top can follow a max() of two roofs
    n = max(2, int((x1 - x0) / 0.1))
    xs = sorted(set([x0 + (x1 - x0) * i / n for i in range(n + 1)] + [x for x in (LW_RIDGE_X, RW_RIDGE_X) if x0 < x < x1]))
    pts = [(x0, z_bot)] + [(x, under(x) + 0.03) for x in xs] + [(x1, z_bot)]
    return prism(name, [(x, z) for x, z in pts], "y", -y1, -y0, mat)

def gable_along_y(name, x0, x1, y0, y1, under, z_bot, mat):
    ys = sorted(set([y0, y1] + ([MB_RIDGE_Y] if y0 < MB_RIDGE_Y < y1 else [])))
    pts = [(-y0, z_bot)] + [(-y, under(y) + 0.03) for y in ys] + [(-y1, z_bot)]
    return prism(name, pts, "x", x0, x1, mat)

def house_infill():
    T = T_EXT
    gs = [gable_along_x("Szczyt_LW_S", 0.0, LW[1], LW[3] - T, LW[3], lw_under, WT - 0.1, None),
          # near the junction the entrance-block roof is the higher ceiling over this wall
          gable_along_x("Szczyt_LW_N", 0.0, LW[1], LW[2], LW[2] + T, lambda x: max(lw_under(x), mb_under(LW[2] + T)), WT - 0.1, None),
          gable_along_x("Szczyt_RW_N", RW[0], RW[1], 0.0, T, rw_under, WT - 0.1, None),
          gable_along_x("Szczyt_RW_S", RW[0], RW[1], RW[3] - T, RW[3], rw_under, WT - 0.1, None),
          # vault closures: walls under the entrance-block roof
          gable_along_y("Nadproze_11", 12.40, 12.55, LW[2] + T, 13.82, mb_under, CEIL - 0.01, None),
          gable_along_y("Nadproze_15", 6.05, 6.27, 13.94, MB[3] - T, mb_under, CEIL - 0.01, None),
          pb("Nadproze_14", 6.05, 12.40, 13.82, 13.94, CEIL - 0.01, mb_under(13.82) + 0.03)]
    for g in gs:
        set_face_mats(g, wall_face_mat)
    # ceilings over flat rooms
    pb("Strop_RW_N", RW[0] + T, RW[1] - T, T, LW[2] + T, CEIL, CEIL + 0.05, "Tynk_wew")
    pb("Strop_RW_S", 12.40, RW[1] - T, LW[2] + T, RW[3] - T, CEIL, CEIL + 0.05, "Tynk_wew")
    pb("Strop_MB", 6.05, 12.40, 13.82, MB[3] - T, CEIL, CEIL + 0.05, "Tynk_wew")

def house_floors():
    T = T_EXT
    rooms = [  # name, x0, x1, y0, y1, finish
        ("Salon", T, 6.05, LW[2] + T, 13.82, "Podloga"),
        ("Kuchnia", T, 6.05, 13.82, LW[3] - T, "Plytki"),
        ("Jadalnia", 6.05, 12.40, LW[2] + T, 13.82, "Podloga"),
        ("Spizarnia", 6.27, 7.97, 13.94, MB[3] - T, "Plytki"),
        ("Przedsionek", 8.09, 10.65, 13.94, MB[3] - T, "Plytki"),
        ("Szatnia", 10.77, 12.43, 13.94, MB[3] - T, "Plytki"),
        ("Sypialnia_1", RW[0] + T, 16.42, T, 3.87, "Podloga"),
        ("Lazienka_1", 16.54, RW[1] - T, T, 2.77, "Plytki"),
        ("Garderoba", 16.54, RW[1] - T, 2.89, 6.81, "Podloga"),
        ("Lazienka_2", 13.88, 16.42, 3.99, 6.81, "Plytki"),
        ("Hol_sypialni", RW[0] + T, 13.76, 3.87, 8.50, "Podloga"),
        ("Sypialnia_2", 13.88, RW[1] - T, 6.93, 9.69, "Podloga"),
        ("Sypialnia_3", 13.88, RW[1] - T, 9.81, 12.60, "Podloga"),
        ("Korytarz", 12.55, 13.76, 8.62, 10.82, "Podloga"),
        ("WC", 12.55, 13.76, 10.94, 12.60, "Plytki"),
        ("Korytarz_2", 12.55, 14.38, 12.72, 13.82, "Podloga"),
        ("Gabinet", 14.38, RW[1] - T, 12.72, RW[3] - T, "Podloga"),
        ("Pom_gosp", 12.66, 14.27, 13.94, RW[3] - T, "Plytki"),
    ]
    for name, x0, x1, y0, y1, mat in rooms:
        if x1 - x0 > 1e-3 and y1 - y0 > 1e-3:
            pb(f"Podloga_{name}", x0, x1, y0, y1, 0.0, FFL, mat)

# ---------------- roofs ----------------
def roof_section(hs, ov, region=None):
    """cross-section (u from ridge, z) of a 30 deg slab; region "top" / "under" = the volume below that surface"""
    zb = PLATE - ov * TAN
    zr = PLATE + hs * TAN
    if region is None:
        return [(-hs - ov, zb), (0.0, zr), (hs + ov, zb), (hs + ov, zb + RT_V), (0.0, zr + RT_V), (-hs - ov, zb + RT_V)]
    d = RT_V if region == "top" else 0.0
    return [(-hs - ov, -5.0), (hs + ov, -5.0), (hs + ov, zb + d), (0.0, zr + d), (-hs - ov, zb + d)]

def roof_y(name, ridge_x, hs, y0, y1, region=None):
    """ridge along plan y (Blender Y): extrude section over Blender Y -y1..-y0"""
    return prism(name, [(ridge_x + u, z) for u, z in roof_section(hs, OV, region)], "y", -y1, -y0)

def roof_x(name, ridge_y, hs, x0, x1, region=None):
    return prism(name, [(-(ridge_y + u), z) for u, z in roof_section(hs, OV, region)], "x", x0, x1)

def bisect(o, planes):
    bm = bmesh.new(); bm.from_mesh(o.data)
    for co, no in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    bm.to_mesh(o.data); bm.free()

def roof_face_mat(c, n):
    if n.z > 0.3:
        return "Dachowka_grafit"
    if n.z < -0.3:
        return "Tynk_wew" if in_house(c.x, -c.y) else "Podbitka"
    return "Biel"   # fascia / barge boards

def mb_top(y): return mb_under(y) + RT_V

def roofs():
    lw = roof_y("Dach_LW", LW_RIDGE_X, LW_HS, LW_BACK, LW[3] + VERGE)
    rw = roof_y("Dach_RW", RW_RIDGE_X, RW_HS, -VERGE, CARPORT_Y1 + VERGE)
    mb = roof_x("Dach_MB", MB_RIDGE_Y, MB_HS, LW_RIDGE_X, RW_RIDGE_X)
    lw_r = roof_y("r", LW_RIDGE_X, LW_HS, LW_BACK, LW[3] + VERGE, region="top")
    rw_r = roof_y("r", RW_RIDGE_X, RW_HS, -VERGE, CARPORT_Y1 + VERGE, region="top")
    lw_u = roof_y("r", LW_RIDGE_X, LW_HS, LW_BACK, LW[3] + VERGE, region="under")
    rw_u = roof_y("r", RW_RIDGE_X, RW_HS, -VERGE, CARPORT_Y1 + VERGE, region="under")
    mb_u = roof_x("r", MB_RIDGE_Y, MB_HS, LW_RIDGE_X, RW_RIDGE_X, region="under")
    # small boarded gables where the entrance-block roof rises above the wing ridges
    tips = []
    for x0, x1, reg in ((LW_RIDGE_X, LW_RIDGE_X + 0.04, lw_r), (RW_RIDGE_X - 0.04, RW_RIDGE_X, rw_r)):
        under = [(-(MB_RIDGE_Y - MB_HS - OV), PLATE - OV * TAN), (-MB_RIDGE_Y, PLATE + MB_HS * TAN), (-(MB_RIDGE_Y + MB_HS + OV), PLATE - OV * TAN)]
        # the slab ends here; this board wall closes the gap above the wing roof
        t = prism("Szczyt_MB", [(under[0][0], 0.0)] + under + [(under[2][0], 0.0)], "x", x0, x1, "Deski_poziome")
        cut_obj(t, reg)
        tips.append(t)
    join(tips, "Szczyt_MB_deski", "Deski_poziome")
    # each roof loses what lies inside the space under the other roof: the slabs meet in valleys and the
    # vault ceiling is the upper envelope (cutting below the other's top would open holes where slabs overlap)
    cut_obj(lw, mb_u); cut_obj(rw, mb_u)
    cut_obj(mb, lw_u); cut_obj(mb, rw_u)
    for r in (lw_r, rw_r, lw_u, rw_u, mb_u):
        remove(r)
    # roof windows over the dining hall (2 x 78 x 140, front slope)
    rwins = []
    for cx in (8.78, 9.98):
        y0, y1 = MB_RIDGE_Y + 0.8, MB_RIDGE_Y + 0.8 + 1.40 * math.cos(math.radians(30))
        hole = pb("h", cx - 0.39, cx + 0.39, y0, y1, 0.0, 9.0)
        cut_obj(mb, hole); remove(hole)
        rwins.append((cx, y0, y1))
    planes = [((x, 0, 0), (1, 0, 0)) for x in (LW[0], LW[1], RW[0], RW[1])] + \
             [((0, -y, 0), (0, 1, 0)) for y in (0.0, LW[2], MB[3], RW[3], LW[3])]
    for r in (lw, rw, mb):
        bisect(r, planes)
        set_face_mats(r, roof_face_mat)
    # roof-window frames and glass, set in the slab
    def slope(y0, y1, d0, d1):
        return [(-y0, mb_top(y0) + d0), (-y1, mb_top(y1) + d0), (-y1, mb_top(y1) + d1), (-y0, mb_top(y0) + d1)]
    fr, gl = [], []
    for cx, y0, y1 in rwins:
        x0, x1 = cx - 0.39, cx + 0.39
        fr += [prism("f", slope(y0, y1, -RT_V, 0.06), "x", x0, x0 + 0.07),
               prism("f", slope(y0, y1, -RT_V, 0.06), "x", x1 - 0.07, x1),
               prism("f", slope(y0, y0 + 0.07, -RT_V, 0.06), "x", x0, x1),
               prism("f", slope(y1 - 0.07, y1, -RT_V, 0.06), "x", x0, x1)]
        gl.append(prism("g", slope(y0 + 0.07, y1 - 0.07, -0.02, 0.0), "x", x0 + 0.07, x1 - 0.07))
    join(fr, "Okno_dachowe_rama", "Rama_okna")
    join(gl, "Okno_dachowe_szyba", "Szklo")
    # PV on the garden slope (2 rows x 4, as in the published rear elevation)
    pv = []
    for row in range(2):
        y1 = MB_RIDGE_Y - 0.6 - row * 1.75
        y0 = y1 - 1.65 * math.cos(math.radians(30))
        for i in range(4):
            x0 = 7.25 + i * 1.08
            pv.append(prism("p", [(-y0, mb_top(y0) + 0.06), (-y1, mb_top(y1) + 0.06), (-y1, mb_top(y1) + 0.10), (-y0, mb_top(y0) + 0.10)],
                            "x", x0, x0 + 1.02))
    join(pv, "Panele_PV", "PV")
    # gutters + downpipes on the outer eaves
    g = []
    zg0, zg1 = PLATE - OV * TAN - 0.10, PLATE - OV * TAN + 0.04
    ex_l, ex_r = LW[0] - OV, RW[1] + OV
    g.append(pb("g", ex_l - 0.12, ex_l, LW_BACK, LW[3] + VERGE, zg0, zg1))
    g.append(pb("g", ex_r, ex_r + 0.12, -VERGE, CARPORT_Y1 + VERGE, zg0, zg1))
    for y0, y1 in ((LW_BACK, MB[2] - OV), (MB[3] + OV, LW[3] + VERGE)):
        g.append(pb("g", LW[1] + OV, LW[1] + OV + 0.12, y0, y1, zg0, zg1))
    for y0, y1 in ((-VERGE, MB[2] - OV), (RW[3] + OV, CARPORT_Y1 + VERGE)):
        g.append(pb("g", RW[0] - OV - 0.12, RW[0] - OV, y0, y1, zg0, zg1))
    for y in (MB[2] - OV - 0.12, MB[3] + OV):
        g.append(pb("g", LW[1] + OV, RW[0] - OV, y, y + 0.12, zg0, zg1))
    for x, y in ((ex_l - 0.10, LW[2] + 0.2), (ex_l - 0.10, LW[3] - 0.3), (ex_r + 0.02, 0.3), (ex_r + 0.02, RW[3] - 0.3),
                 (ex_r + 0.02, CARPORT_Y1 - 0.2), (RW[0] - OV - 0.10, MB[3] + OV + 0.02)):
        g.append(pb("g", x, x + 0.08, y, y + 0.08, 0.0, zg0))
    join(g, "Rynny", "Blacha_grafit")

# ---------------- house: details ----------------
def house_details():
    T = T_EXT
    # chimney (stone) with the fireplace inside and the outdoor grill on the terrace side
    pb("Komin", 5.00, 6.05, 7.83, 8.62, 0.0, 6.25, "Kamien")
    pb("Komin_czapa", 4.95, 6.10, 7.78, 8.67, 6.25, 6.32, "Beton_grafit")
    pb("Kominek", 4.90, 6.05, LW[2] + T, 9.05, FFL, FFL + 1.15, "Kamien")
    pb("Kominek_palenisko", 5.15, 5.80, 9.05, 9.06, FFL + 0.35, FFL + 0.95, "Palenisko")
    # cladding: vertical boards / stone, 2 cm proud of the render
    Kx = lambda name, x0, x1, y, side, z0, z1, mat: pb(name, x0, x1, (y - 0.02) if side == "N" else y, y if side == "N" else y + 0.02, z0, z1, mat)
    Ky = lambda name, x, y0, y1, side, z0, z1, mat: pb(name, (x - 0.02) if side == "W" else x, x if side == "W" else x + 0.02, y0, y1, z0, z1, mat)
    clad = [Kx("c", 0.0, 2.23, LW[3], "S", FFL, PLATE, None),
            Kx("c", RW[0] + 0.45, 15.60, 0.0, "N", FFL, PLATE, None),
            Ky("c", RW[0], T + 0.0, 1.95, "W", FFL, PLATE, None),
            Ky("c", RW[0], 3.76, 5.79, "W", FFL, PLATE, None)]
    join(clad, "Deski_elewacja", "Deski_pionowe")
    # gable triangles in boards (front living wing, rear bedroom wing, terrace gable)
    def tri_x(x0, x1, y, side, under):
        y0, y1 = (y - 0.02, y) if side == "N" else (y, y + 0.02)
        return gable_along_x("t", x0, x1, y0, y1, lambda x: under(x) - 0.03, PLATE, None)
    tris = [tri_x(LW[0], LW[1], LW[3], "S", lw_under), tri_x(LW[0], LW[1], LW[2], "N", lw_under),
            tri_x(RW[0], RW[1], 0.0, "N", rw_under), tri_x(RW[0], RW[1], CARPORT_Y1, "S", rw_under)]
    join(tris, "Szczyt_deski", "Deski_poziome")
    pb("Kamien_wejscie", 10.65, RW[0], MB[3], MB[3] + 0.03, 0.0, WT, "Kamien")
    pb("Kamien_kominek_sciana", 4.40, 5.00, LW[2] - 0.03, LW[2], 0.0, PLATE, "Kamien")
    # covered terrace: deck, two posts, open truss under the living-wing roof
    pb("Taras_deski", 0.0, RW[0], 4.84, LW[2], 0.0, FFL - 0.03, "Deski_taras")
    posts = [pb("s", 0.66, 0.91, 5.54, 5.79, FFL - 0.03, 2.55), pb("s", 6.58, 6.83, 5.54, 5.79, FFL - 0.03, 2.55)]
    join(posts, "Slupy_taras", "Biel")
    tr = [pb("b", 0.40, 7.05, 5.52, 5.81, 2.55, 2.85),                       # tie beam
          pb("b", LW_RIDGE_X - 0.08, LW_RIDGE_X + 0.08, 5.58, 5.75, 2.85, lw_under(LW_RIDGE_X))]   # king post
    rafter = lambda xa, xb: prism("r", [(xa, lw_under(xa) - 0.20), (xb, lw_under(xb) - 0.20), (xb, lw_under(xb)), (xa, lw_under(xa))], "y", -5.75, -5.58)
    tr += [rafter(-0.3, LW_RIDGE_X), rafter(LW_RIDGE_X, LW[1] + 0.3)]
    for sx in (-1, 1):   # struts from the king-post foot to the rafters
        xa, xb = LW_RIDGE_X + sx * 0.08, LW_RIDGE_X + sx * 1.9
        za, zb = 2.85, lw_under(xb) - 0.20
        tr.append(prism("st", [(xa, za), (xb, zb - 0.16), (xb, zb), (xa, za + 0.16)], "y", -5.75, -5.58))
    join(tr, "Wiazar_taras", "Drewno_konstr")
    # entrance podest, step and planters
    pb("Podest_wejscie", 6.05, RW[0], MB[3], 19.20, 0.0, FFL - 0.03, "Plyty_beton")
    pb("Podest_stopien", 7.40, 11.00, 19.20, 19.55, 0.0, (FFL - 0.03) / 2, "Plyty_beton")
    for x in (6.45, 10.95):
        pb("Donica", x, x + 0.80, 18.70, 19.15, FFL - 0.03, FFL + 0.42, "Beton_grafit")
    # carport: corner post + beams, store (pom. gosp. 9.65 m2) clad in boards
    cp = [pb("s", RW[0], RW[0] + 0.24, CARPORT_Y1 - 0.24, CARPORT_Y1, 0.0, 2.75),
          pb("b", RW[0], 16.30, CARPORT_Y1 - 0.24, CARPORT_Y1, 2.75, PLATE),
          pb("b", RW[0], RW[0] + 0.24, RW[3], CARPORT_Y1, 2.75, PLATE)]
    join(cp, "Wiata_konstrukcja", "Drewno_konstr")
    store = [pb("w", 16.30, 16.47, RW[3], 17.80, 0.0, 3.05), pb("w", 16.30, 16.47, 18.79, CARPORT_Y1, 0.0, 3.05),
             pb("w", 16.30, 16.47, 17.80, 18.79, 2.30, 3.05),
             pb("w", 18.31, 18.48, RW[3], CARPORT_Y1, 0.0, 3.05), pb("w", 16.47, 18.31, CARPORT_Y1 - 0.17, CARPORT_Y1, 0.0, 3.05)]
    join(store, "Wiata_pom_gosp", "Deski_pionowe")
    pb("Wiata_drzwi", 16.33, 16.44, 17.82, 18.77, 0.03, 2.28, "Deski_pionowe")
    pb("Wiata_posadzka", RW[0], 16.30, RW[3], 22.57, 0.0, 0.05, "Kostka_szara")
    pb("Wiata_pom_posadzka", 16.47, 18.31, RW[3], CARPORT_Y1 - 0.17, 0.0, 0.05, "Beton")

# ---------------- plot: lawn, paths, fence, lights ----------------
def plot():
    x0, x1, y0, y1 = PLOT
    pb("Trawnik_dzialka", x0, x1, y0, y1, 0.0, 0.03, "Trawa")
    pb("Podjazd", 12.0, 16.5, 22.57, y1 + 0.6, 0.0, 0.05, "Kostka_szara")
    # stepping slabs: gate -> entrance and terrace -> garden
    slabs = []
    for i in range(14):
        y = 19.7 + i * 0.75
        if y + 0.45 > y1 + 0.5:
            break
        slabs.append(pb("p", 8.60, 10.20, y, y + 0.45, 0.0, 0.06))
    for i in range(5):
        y = 4.5 - i * 0.75
        slabs.append(pb("p", 8.0, 9.6, y - 0.45, y, 0.0, 0.06))
    join(slabs, "Sciezka_plyty", "Plyty_beton")
    # LED bollards along the front path and by the terrace
    lamps = []
    for x, y in [(7.9, 21.0), (10.9, 21.0), (7.9, 24.0), (10.9, 24.0), (7.9, 27.0), (10.9, 27.0), (7.6, 4.0), (10.0, 2.0)]:
        cy_ = -y
        bm_ = bmesh.new(); cyl(bm_, (x, cy_, 0.0), (x, cy_, 0.60), 0.06, 12)
        lamps.append(new_obj("l", bm_))
    join(lamps, "Slupki_LED", "Lampa_LED")
    fence()
    garden_plants()

def fence():
    x0, x1, y0, y1 = PLOT
    H = 1.53
    # front: graphite block base + horizontal aluminium slats; sliding gate parked open behind the fence
    gate = (11.9, 16.6); wicket = (8.9, 10.0)
    front, slats = [], []
    xs = [x0, wicket[0], wicket[1], gate[0], gate[1], x1]
    for a, b in ((x0, wicket[0]), (wicket[1], gate[0]), (gate[1], x1)):
        front.append(pb("f", a, b, y1 - 0.12, y1 + 0.12, 0.0, 0.40))
        n = max(1, round((b - a) / 2.6))
        for i in range(n + 1):
            px = a + (b - a) * i / n
            front.append(pb("f", px - 0.12 if i else px, px + 0.12 if i < n else px, y1 - 0.12, y1 + 0.12, 0.0, 1.60))
        for k in range(8):
            z = 0.50 + k * 0.135
            slats.append(pb("s", a, b, y1 - 0.02, y1 + 0.02, z, z + 0.10))
    for k in range(8):   # open sliding gate, parked behind the eastern span
        z = 0.50 + k * 0.135
        slats.append(pb("s", gate[1] + 0.1, gate[1] + 0.1 + (gate[1] - gate[0]), y1 - 0.30, y1 - 0.26, z, z + 0.10))
    for k in range(8):   # wicket leaf swung inwards
        z = 0.50 + k * 0.135
        slats.append(pb("s", wicket[0] + 0.02, wicket[0] + 0.06, y1 - (wicket[1] - wicket[0]) - 0.1, y1 - 0.1, z, z + 0.10))
    join(front, "Ogrodzenie_podmurowka", "Beton_grafit")
    join(slats, "Ogrodzenie_sztachety", "Ogrodzenie")
    # sides and back: 3D welded-mesh panels on posts, 20 cm concrete underpinning
    runs = [((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)), ((x0, y0), (x1, y0))]
    wires, base, posts = [], [], []
    for (ax, ay), (bx, by) in runs:
        vert = ax == bx
        L = abs(by - ay) if vert else abs(bx - ax)
        P = lambda s, d, z0, z1, w=0.003: (pb("w", ax - w, ax + w, min(ay, by) + s - d, min(ay, by) + s + d, z0, z1) if vert
                                          else pb("w", min(ax, bx) + s - d, min(ax, bx) + s + d, ay - w, ay + w, z0, z1))
        base.append(P(L / 2, L / 2, 0.0, 0.20, 0.03))
        n = int(L / 2.5)
        for i in range(n + 1):
            posts.append(P(L * i / n, 0.03, 0.0, H + 0.05, 0.03))
        s = 0.0
        while s <= L:
            wires.append(P(s, 0.0025, 0.20, H))
            s += 0.20
        for z in (0.25, 0.75, 1.25, H - 0.02):
            wires.append(P(L / 2, L / 2, z, z + 0.006))
            wires.append(P(L / 2, L / 2, z + 0.05, z + 0.056))
    join(base, "Ogrodzenie_podmurowka_panel", "Beton")
    join(posts, "Ogrodzenie_slupki", "Ogrodzenie")
    join(wires, "Ogrodzenie_panele", "Ogrodzenie")
    # hidden collision walls (thin wires let wall probes slip through)
    kol = [pb("k", x0 - 0.05, x0 + 0.05, y0, y1, 0.0, 1.6), pb("k", x1 - 0.05, x1 + 0.05, y0, y1, 0.0, 1.6),
           pb("k", x0, x1, y0 - 0.05, y0 + 0.05, 0.0, 1.6)]
    for a, b in ((x0, wicket[0]), (wicket[1], gate[0]), (gate[1], x1)):
        kol.append(pb("k", a, b, y1 - 0.12, y1 + 0.12, 0.0, 1.6))
    join(kol, "Kolizja_ogrodzenie", "Kolizja")

def garden_plants():
    grass, lav, hyd, shrub = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    def tuft(bm, x, y, h):
        for k in range(7):
            a = k * 2 * math.pi / 7
            m = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.02, radius2=0.002, depth=h)
            for v in m["verts"]:
                v.co += Vector((x + 0.08 * math.cos(a), -y + 0.08 * math.sin(a), h / 2))
    for x in (6.9, 7.4, 11.4, 11.9):
        for y in (20.0, 21.6, 23.2, 24.8, 26.4):
            if random.random() < 0.8:
                tuft(grass, x + random.uniform(-0.15, 0.15), y, random.uniform(0.6, 0.9))
    for i in range(10):
        blob(lav, (0.4 + i * 0.55, -(LW[3] + 0.6), 0.25), 0.28, 0.28, 0.22)
        blob(hyd, (19.4, -(1.0 + i * 1.5), 0.45), 0.45, 0.45, 0.45)
    for x, y in ((-6.0, 2.0), (-5.0, -6.0), (24.0, -6.0), (24.5, 4.0), (-6.5, 26.0), (24.5, 27.0)):
        blob(shrub, (x, -y, 0.9), 1.0, 1.0, 0.9)
    for bm, nm, m in ((grass, "Trawy_ozdobne", "Trawa_ozdobna"), (lav, "Lawenda", "Lawenda"),
                      (hyd, "Hortensje", "Hortensja"), (shrub, "Krzewy_dzialka", "Liscie_krzew")):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        new_obj(nm, bm, m)

# ---------------- neighbourhood ----------------
def road_strip(name, pts, width, z, mat):
    # Chaikin-smoothed polyline -> flat strip
    for _ in range(3):
        sm = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            sm += [(0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by), (0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by)]
        sm.append(pts[-1]); pts = sm
    bm = bmesh.new(); left, right = [], []
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(len(pts) - 1, i + 1)]
        d = Vector((b[0] - a[0], -(b[1] - a[1]), 0)).normalized()
        n = Vector((-d.y, d.x, 0)) * width / 2
        left.append(bm.verts.new((x + n.x, -y + n.y, z))); right.append(bm.verts.new((x - n.x, -y - n.y, z)))
    for i in range(len(pts) - 1):
        bm.faces.new([right[i], right[i + 1], left[i + 1], left[i]])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0: f.normal_flip()
    return new_obj(name, bm, mat)

NEIGHBOURS = [
    # x, y (plan, centre), w (along x), d, eave, pitch, roof, wall, gable along x?
    (38.0, 12.0, 12.0, 10.0, 5.9, 35, "Dachowka_ciemna", "Sciana_sasiad", True),     # finished house next door
    (-44.0, 20.0, 11.0, 9.5, 3.4, 40, "Dachowka_grafit", "Sciana_sasiad", False),
    (-46.0, -4.0, 12.0, 10.0, 3.6, 38, "Dachowka_grafit", "Sciana_sasiad", True),
    (-44.0, -30.0, 10.0, 9.0, 3.3, 40, "Dachowka_ciemna", "Sciana_sasiad", False),
    (4.0, 46.0, 6.0, 9.0, 2.6, 40, "Dachowka_pomaranczowa", "Sciana_sasiad_bez", False),   # small orange-roof cottage
    (62.0, -14.0, 11.0, 9.0, 3.2, 40, "Dachowka_czerwona", "Sciana_sasiad", True),
    (80.0, 22.0, 12.0, 9.0, 3.4, 38, "Dachowka_ciemna", "Sciana_sasiad", False),
    (64.0, 44.0, 10.0, 10.0, 3.2, 40, "Dachowka_czerwona", "Sciana_sasiad_bez", True),
    (98.0, -10.0, 11.0, 10.0, 3.3, 40, "Dachowka_pomaranczowa", "Sciana_sasiad", True),
    (104.0, 30.0, 12.0, 9.0, 3.6, 35, "Dachowka_grafit", "Sciana_sasiad", False),
    (86.0, -40.0, 10.0, 9.0, 3.2, 40, "Dachowka_czerwona", "Sciana_sasiad", True),
]

def neighbour(i, x, y, w, d, eave, pitch, roof_mat, wall_mat, along_x):
    hw, hd = w / 2, d / 2
    pb(f"Sasiad_{i}_trawnik", x - hw - 6, x + hw + 6, y - hd - 8, y + hd + 8, 0.0, 0.03, "Trawa")
    pb(f"Sasiad_{i}_sciany", x - hw, x + hw, y - hd, y + hd, 0.0, eave, wall_mat)
    t = math.tan(math.radians(pitch))
    if along_x:
        sec = [(-(y - hd - 0.5), eave - 0.5 * t), (-y, eave + hd * t), (-(y + hd + 0.5), eave - 0.5 * t),
               (-(y + hd + 0.5), eave - 0.5 * t + 0.3), (-y, eave + hd * t + 0.3), (-(y - hd - 0.5), eave - 0.5 * t + 0.3)]
        r = prism(f"Sasiad_{i}_dach", sec, "x", x - hw - 0.4, x + hw + 0.4, roof_mat)
        gx = [(x - hw, -1), (x + hw, 1)]
        tri = lambda xx, s: prism("t", [(-(y - hd), eave), (-y, eave + hd * t), (-(y + hd), eave)], "x", xx - (0.0 if s > 0 else 0.01), xx + (0.01 if s > 0 else 0.0))
        join([tri(xx, s) for xx, s in gx], f"Sasiad_{i}_szczyty", wall_mat)
    else:
        sec = [(x - hw - 0.5, eave - 0.5 * t), (x, eave + hw * t), (x + hw + 0.5, eave - 0.5 * t),
               (x + hw + 0.5, eave - 0.5 * t + 0.3), (x, eave + hw * t + 0.3), (x - hw - 0.5, eave - 0.5 * t + 0.3)]
        r = prism(f"Sasiad_{i}_dach", sec, "y", -(y + hd + 0.4), -(y - hd - 0.4), roof_mat)
        tri = lambda yy, s: prism("t", [(x - hw, eave), (x, eave + hw * t), (x + hw, eave)], "y", -yy - (0.01 if s > 0 else 0.0), -yy + (0.0 if s > 0 else 0.01))
        join([tri(y - hd, -1), tri(y + hd, 1)], f"Sasiad_{i}_szczyty", wall_mat)
    # windows / door 2 cm proud of each facade
    win = []
    floors = [0.9] + ([3.6] if eave > 5 else [])
    for zf in floors:
        for k in range(int(w // 3)):
            wx = x - hw + 1.5 + k * 3.0
            for yy, s in ((y - hd, -1), (y + hd, 1)):
                win.append(pb("w", wx - 0.6, wx + 0.6, yy - 0.02 if s < 0 else yy, yy if s < 0 else yy + 0.02, zf, zf + 1.4))
        for k in range(int(d // 3)):
            wy = y - hd + 1.5 + k * 3.0
            for xx, s in ((x - hw, -1), (x + hw, 1)):
                win.append(pb("w", xx - 0.02 if s < 0 else xx, xx if s < 0 else xx + 0.02, wy - 0.6, wy + 0.6, zf, zf + 1.4))
    win.append(pb("w", x - 0.5, x + 0.5, y + hd, y + hd + 0.02, 0.0, 2.1))
    join(win, f"Sasiad_{i}_okna", "Okno_sasiad")
    pb(f"Sasiad_{i}_komin", x + hw * 0.4, x + hw * 0.4 + 0.5, y - 0.25, y + 0.25, eave, eave + max(hw, hd) * t + 1.0, "Beton_grafit")

SIDE_ROAD = [(-26.0, 60.0), (-26.0, 32.85), (-26.0, 0.0), (-22.0, -28.0), (-8.0, -50.0),
             (20.0, -60.0), (55.0, -62.0), (75.0, -50.0), (80.0, -20.0), (78.0, 10.0)]

def near_road(x, y, clear):
    for (ax, ay), (bx, by) in zip(SIDE_ROAD, SIDE_ROAD[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        if math.hypot(x - ax - t * dx, y - ay - t * dy) < clear:
            return True
    return False

def neighbourhood():
    pb("Teren_laka", -220.0, 220.0, -220.0, 220.0, -0.03, 0.0, "Laka")
    road_strip("Droga_glowna", [(-120.0, 32.85), (-30.0, 32.85), (60.0, 32.85), (130.0, 34.0)], 4.5, 0.045, "Droga_zwir")
    road_strip("Droga_boczna", SIDE_ROAD, 4.2, 0.035, "Droga_zwir")
    for i, n in enumerate(NEIGHBOURS):
        neighbour(i, *n)
    # hedges (tuja) around the orange-roof cottage, as in the photo
    hedge = bmesh.new()
    for k in range(18):
        blob(hedge, (-4.0 + k * 0.9, -38.5, 1.3), 0.55, 0.55, 1.4)
        blob(hedge, (-4.0 + k * 0.9, -55.5, 1.3), 0.55, 0.55, 1.4)
    new_obj("Zywoplot_tuje", hedge, "Liscie_krzew")
    trees()

def trees():
    trunks, crowns, leafy, scrub = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    def pine(x, y, h):
        # Scots pine: bare trunk, wide flat-topped crown in the top third
        cyl(trunks, (x, -y, -0.05), (x, -y, h * 0.85), 0.16 + h * 0.008, 6)
        for k in range(3):
            blob(crowns, (x + random.uniform(-1.2, 1.2), -y + random.uniform(-1.2, 1.2), h * (0.70 + 0.09 * k)),
                 2.2 + random.random(), 2.2 + random.random(), 1.3, 1)
    def birch(x, y, h):
        cyl(trunks, (x, -y, -0.05), (x, -y, h * 0.65), 0.14, 6)
        blob(leafy, (x, -y, h * 0.72), 2.2, 2.2, h * 0.35, 1)
    def taken(x, y):
        if PLOT[0] - 3 < x < PLOT[1] + 3 and PLOT[2] - 3 < y < PLOT[3] + 6:
            return True
        if ROAD_Y[0] - 3 < y < ROAD_Y[1] + 3:
            return True
        if near_road(x, y, 6.0):
            return True
        for nx, ny, w, d, *_ in NEIGHBOURS:
            if abs(x - nx) < w / 2 + 9 and abs(y - ny) < d / 2 + 10:
                return True
        return False
    n = 0
    while n < 700:   # pine forest behind (north) and to the west, as in the photos
        x, y = random.uniform(-160, 150), random.uniform(-170, -32)
        if y > -64 and -20 < x < 72:
            y -= 30
        if taken(x, y):
            continue
        pine(x, y, random.uniform(14, 22)); n += 1
    for _ in range(140):
        x, y = random.uniform(-160, -60), random.uniform(-32, 120)
        if not taken(x, y):
            pine(x, y, random.uniform(13, 20))
    for _ in range(60):
        x, y = random.uniform(-20, 140), random.uniform(-30, 80)
        if not taken(x, y):
            (birch if random.random() < 0.5 else pine)(x, y, random.uniform(9, 15))
    for _ in range(110):   # young pine scrub in the meadow south of the road
        x, y = random.uniform(-15, 50), random.uniform(38, 95)
        if not taken(x, y):
            cone(scrub, (x, -y, 0.0), random.uniform(0.5, 1.0), random.uniform(1.0, 2.6), 7)
    for bm, nm, m in ((trunks, "Drzewa_pnie", "Kora_sosna"), (crowns, "Drzewa_korony", "Igliwie"),
                      (leafy, "Drzewa_liscie", "Liscie"), (scrub, "Mlode_sosny", "Igliwie")):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        new_obj(nm, bm, m)

# ---------------- build ----------------
def build():
    global COL
    reset()
    COL = coll("Hanka3")
    make_materials()
    house_walls()
    fill_openings()
    house_infill()
    house_floors()
    roofs()
    house_details()
    plot()
    neighbourhood()
    for o in COL.objects:
        if o.type == "MESH":
            planar_uv(o, rot=any(m and m.name == "Deski_pionowe" for m in o.data.materials))
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True)
    print("EXPORTED", OUT, len(COL.objects), "objects")

build()
