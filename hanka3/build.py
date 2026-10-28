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
    img_mat("Deski_pionowe", "wooden_planks", 2.0, color=srgb(150, 114, 80), grain=0.55, rot=True)
    img_mat("Deski_poziome", "wooden_planks", 2.0, color=srgb(150, 114, 80), grain=0.55)
    img_mat("Podbitka", "wooden_planks", 2.0, color=srgb(168, 124, 84), grain=0.5)
    img_mat("Drewno_konstr", "fine_grained_wood", 1.2, color=srgb(176, 132, 90), grain=0.45)
    img_mat("Deski_taras", "wooden_planks", 1.5, color=srgb(140, 104, 74), grain=0.55)
    img_mat("Kamien", "stacked_stone_wall", 1.5, color=srgb(196, 178, 150), grain=0.6)
    img_mat("Podloga", "wood_floor", 2.0)
    img_mat("Plytki", "long_white_tiles", 1.2)
    img_mat("Trawa", "leafy_grass", 3.0, tint=(0.42, 0.62, 0.25))
    img_mat("Laka", "leafy_grass", 3.0, tint=(0.95, 0.98, 0.50))
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
    # vegetation: neutral bases, the hue comes from per-vertex colours
    flat_mat("Kora", (1, 1, 1), rough=0.95)
    flat_mat("Igliwie", (1, 1, 1), rough=0.85)
    flat_mat("Liscie", (1, 1, 1), rough=0.75)
    flat_mat("Liscie_krzew", (1, 1, 1), rough=0.75)
    flat_mat("Trawa_ozdobna", (1, 1, 1), rough=0.85)
    flat_mat("Lawenda", (1, 1, 1), rough=0.8)
    img_mat("Sciolka", "leafy_grass", 3.0, tint=(0.55, 0.52, 0.34))
    img_mat("Droga_ziemia", "sandy_gravel", 2.0, color=srgb(214, 196, 162), grain=0.6)
    img_mat("Zwir_bialy", "sandy_gravel", 1.0, color=srgb(222, 220, 214), grain=0.5)
    img_mat("Kora_mulcz", "sandy_gravel", 1.2, color=srgb(86, 56, 36), grain=0.6)
    img_mat("Cegla", "white_sandstone_bricks", 1.0, color=srgb(150, 76, 58), grain=0.5)
    flat_mat("Blacha_rabek", srgb(60, 64, 70), rough=0.4, metal=0.5)
    flat_mat("Inox", srgb(200, 200, 198), rough=0.25, metal=1.0)
    flat_mat("Swiatlo", srgb(255, 240, 210), rough=0.5)
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
    return r0 + r1

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

def door_leaf(op, name, la, lb, hinge_t, thick, zb, zt, side, mat, handles=False, glass=False, pull=False):
    """closed door leaf as its own object, origin on the hinge axis; extras.openAngle = signed swing (rad)
    that opens it towards `side`. Hardware is parented to the leaf so it swings with it."""
    t0 = op["t0"]
    lo, hi = (hinge_t - thick, hinge_t) if side > 0 else (hinge_t, hinge_t + thick)
    def box_at(bm, b0, b1, e0, e1, z_0, z_1):
        if op["along_x"]:
            bm_box(bm, (b0, -(t0 + e1), z_0), (b1, -(t0 + e0), z_1))
        else:
            bm_box(bm, (t0 + e0, -b1, z_0), (t0 + e1, -b0, z_1))
    leaf, hw, gl = bmesh.new(), bmesh.new(), bmesh.new()
    if glass:
        g0, g1 = la + 0.16, la + 0.30          # glass strip on the hinge side
        box_at(leaf, la, g0, lo, hi, zb, zt); box_at(leaf, g1, lb, lo, hi, zb, zt)
        box_at(leaf, g0, g1, lo, hi, zb, zb + 0.25); box_at(leaf, g0, g1, lo, hi, zt - 0.25, zt)
        box_at(gl, g0, g1, (lo + hi) / 2 - 0.006, (lo + hi) / 2 + 0.006, zb + 0.25, zt - 0.25)
    else:
        box_at(leaf, la, lb, lo, hi, zb, zt)
    zh = FFL + 1.02
    for face, out in ((lo, -1), (hi, 1)):
        if pull and out == -side:              # outside: 1.2 m stainless pull bar
            p = face + out * 0.07
            box_at(hw, lb - 0.13, lb - 0.10, min(face, p), max(face, p), FFL + 0.55, FFL + 1.75)
            continue
        if handles or pull:                    # rosette + lever towards the hinge
            r0, r1 = sorted((face, face + out * 0.012))
            box_at(hw, lb - 0.10, lb - 0.05, r0, r1, zh - 0.025, zh + 0.025)
            l0, l1 = sorted((face + out * 0.045, face + out * 0.065))
            box_at(hw, lb - 0.19, lb - 0.07, l0, l1, zh - 0.01, zh + 0.01)
            s0, s1 = sorted((face + out * 0.012, face + out * 0.065))
            box_at(hw, lb - 0.085, lb - 0.065, s0, s1, zh - 0.01, zh + 0.01)
    for zz in (zb + 0.25, zt - 0.25):          # hinges
        h0, h1 = (hinge_t - 0.012, hinge_t + 0.012)
        box_at(hw, la - 0.004, la + 0.012, min(h0, h1), max(h0, h1), zz - 0.06, zz + 0.06)
    hinge = Vector((la, -(t0 + hinge_t), 0.0)) if op["along_x"] else Vector((t0 + hinge_t, -la, 0.0))
    from mathutils import Matrix
    M = Matrix.Translation(-hinge)
    o = finish(name, leaf, mat); o.data.transform(M); o.location = hinge
    # +t is Blender -Y for walls along x, +X for walls along y (whose +a is Blender -Y)
    o["openAngle"] = (-1 if op["along_x"] else 1) * side * math.pi / 2
    for bm_, nm, m in ((hw, "Drzwi_okucia_" + name, "Inox"), (gl, "Drzwi_szyba_" + name, "Szklo")):
        if bm_.faces:
            c = finish(nm, bm_, m); c.data.transform(M); c.parent = o
        else:
            bm_.free()
    return o

def fill_openings():
    for i, op in enumerate(OPENINGS):
        n = f"{op['wall']}_{i}"
        a0, a1 = op["a0"], op["a1"]
        z0, z1 = FFL + op["sill"], FFL + op["head"]
        T = op["t1"] - op["t0"]
        kind = op["kind"]
        if kind == "open":
            continue
        if kind in ("door", "door_in"):
            side = 1 if kind == "door" else -1          # the leaf swings to the +t / -t side
            # adjustable frame (oscieznica regulowana): 3 cm lining + 7 cm architraves on both faces;
            # pieces only meet edge to edge so no two faces share a plane
            fr = [opening_box(op, a0, a0 + 0.03, 0.0, T, z0, z1 - 0.03, "f", None),
                  opening_box(op, a1 - 0.03, a1, 0.0, T, z0, z1 - 0.03, "f", None),
                  opening_box(op, a0, a1, 0.0, T, z1 - 0.03, z1, "f", None)]
            for e0, e1 in ((-0.012, 0.0), (T, T + 0.012)):
                fr += [opening_box(op, a0 - 0.07, a0 + 0.03, e0, e1, z0, z1 + 0.07, "f", None),
                       opening_box(op, a1 - 0.03, a1 + 0.07, e0, e1, z0, z1 + 0.07, "f", None),
                       opening_box(op, a0 + 0.03, a1 - 0.03, e0, e1, z1 - 0.03, z1 + 0.07, "f", None)]
            join(fr, f"Oscieznica_{n}", "Drzwi_wew")
            hinge_t = T - 0.03 if side > 0 else 0.03     # leaf sits in the rebate on the side it opens to
            door_leaf(op, f"Drzwi_skrzydlo_{n}", a0 + 0.032, a1 - 0.032, hinge_t, 0.04, z0 + 0.008, z1 - 0.034, side,
                      "Drzwi_wew", handles=True)
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
            # left leaf fixed, right leaf slid all the way behind it: the whole right half is open
            for la, lb, dd in ((a0 + fw, c, 0.0), (a0 + fw + 0.02, c + 0.02, 0.05)):
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
            # hinged leaf (closed), opening inwards; vertical glass strip, pull bar outside, lever inside
            side = 1 if outer_at_t0 else -1
            hinge_t = d1 + 0.005 if outer_at_t0 else d0 - 0.005
            door_leaf(op, f"Drzwi_wejsciowe_{n}", c - dw / 2 + 0.036, c + dw / 2 - 0.036, hinge_t, 0.07, zb + 0.005, z1 - fw - 0.005,
                      side, "Rama_okna", glass=True, pull=True)
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
    # corridor (korytarz 6.48 m2) runs north to the master bedroom: its door is in this wall
    wall("4", RW[0] + T, 16.42, 3.87, 3.99, c, [D(12.76, 13.66)], ext=False)
    wall("5", 13.76, 13.88, 3.99, 9.69, c, [D(5.85, 6.75), D(8.20, 9.05)], ext=False)
    wall("6", 13.88, RW[1] - T, 6.81, 6.93, c, ext=False)
    wall("8", 13.76, RW[1] - T, 9.69, 9.81, c, ext=False)
    wall("9", 13.76, 13.88, 9.81, 12.60, c, [D(9.90, 10.80)], ext=False)
    wall("10", 12.55, 13.76, 10.82, 10.94, c, ext=False)
    wall("11", 12.40, 12.55, LW[2] + T, 13.82, c, [O(8.75, 9.75), O(12.43, 13.82)], ext=False)
    wall("12", 12.55, RW[1] - T, 12.60, 12.72, c, [(12.80, 13.70, 0.0, DOOR_H, "door_in")], ext=False)   # leaf into the WC: the side corridor is only 1.10 m
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
    # near the eaves the roof underside drops below z_bot: clamp, or the outline folds over itself
    pts = [(x0, z_bot)] + [(x, max(under(x) + 0.03, z_bot + 0.01)) for x in xs] + [(x1, z_bot)]
    return prism(name, [(x, z) for x, z in pts], "y", -y1, -y0, mat)

def gable_along_y(name, x0, x1, y0, y1, under, z_bot, mat):
    ys = sorted(set([y0, y1] + ([MB_RIDGE_Y] if y0 < MB_RIDGE_Y < y1 else [])))
    pts = [(-y0, z_bot)] + [(-y, max(under(y) + 0.03, z_bot + 0.01)) for y in ys] + [(-y1, z_bot)]
    return prism(name, pts, "x", x0, x1, mat)

def house_infill():
    T = T_EXT
    # infills start exactly at the wall top (WT): an overlap leaves coplanar strips on both faces
    gs = [gable_along_x("Szczyt_LW_S", 0.0, LW[1], LW[3] - T, LW[3], lw_under, WT, None),
          # near the junction the entrance-block roof is the higher ceiling over this wall
          gable_along_x("Szczyt_LW_N", 0.0, LW[1], LW[2], LW[2] + T, lambda x: max(lw_under(x), mb_under(LW[2] + T)), WT, None),
          gable_along_x("Szczyt_RW_N", RW[0], RW[1], 0.0, T, rw_under, WT, None),
          gable_along_x("Szczyt_RW_S", RW[0], RW[1], RW[3] - T, RW[3], rw_under, WT, None),
          # vault closures: walls under the entrance-block roof
          gable_along_y("Nadproze_11", 12.40, 12.55, LW[2] + T, 13.82, mb_under, CEIL - 0.01, None),
          gable_along_y("Nadproze_15", 6.05, 6.27, 13.94, MB[3] - T, mb_under, CEIL - 0.01, None),
          pb("Nadproze_14", 6.05, 12.40, 13.82, 13.94, CEIL - 0.01, mb_under(13.82) + 0.03)]
    for g in gs:
        set_face_mats(g, wall_face_mat)
    # ceilings over flat rooms
    pb("Strop_RW_N", RW[0] + T, RW[1] - T, T, LW[2] + T, CEIL, CEIL + 0.05, "Tynk_wew")
    # slab edges end inside the walls above them, never flush with a wall face
    pb("Strop_RW_S", 12.475, RW[1] - T, LW[2] + T, RW[3] - T, CEIL, CEIL + 0.05, "Tynk_wew")
    pb("Strop_MB", 6.16, 12.40, 13.88, MB[3] - T, CEIL, CEIL + 0.05, "Tynk_wew")

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
        ("Korytarz_N", RW[0] + T, 13.76, 3.99, 8.62, "Podloga"),
        ("Sypialnia_2", 13.88, RW[1] - T, 6.93, 9.69, "Podloga"),
        ("Sypialnia_3", 13.88, RW[1] - T, 9.81, 12.60, "Podloga"),
        ("Korytarz", 12.55, 13.76, 8.64, 10.82, "Podloga"),
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
    lw_s = roof_y("r", LW_RIDGE_X, LW_HS, LW_BACK, LW[3] + VERGE)
    rw_s = roof_y("r", RW_RIDGE_X, RW_HS, -VERGE, CARPORT_Y1 + VERGE)
    lw_u = roof_y("r", LW_RIDGE_X, LW_HS, LW_BACK, LW[3] + VERGE, region="under")
    rw_u = roof_y("r", RW_RIDGE_X, RW_HS, -VERGE, CARPORT_Y1 + VERGE, region="under")
    mb_u = roof_x("r", MB_RIDGE_Y, MB_HS, LW_RIDGE_X, RW_RIDGE_X, region="under")
    # small boarded gables where the entrance-block roof rises above the wing ridges
    tips = []
    for x0, x1, reg in ((LW_RIDGE_X + 0.01, LW_RIDGE_X + 0.05, lw_r), (RW_RIDGE_X - 0.05, RW_RIDGE_X - 0.01, rw_r)):
        under = [(-(MB_RIDGE_Y - MB_HS - OV), PLATE - OV * TAN), (-MB_RIDGE_Y, PLATE + MB_HS * TAN), (-(MB_RIDGE_Y + MB_HS + OV), PLATE - OV * TAN)]
        # the slab ends here; this board wall closes the gap above the wing roof
        t = prism("Szczyt_MB", [(under[0][0], 0.0)] + under + [(under[2][0], 0.0)], "x", x0, x1, "Deski_poziome")
        cut_obj(t, reg)
        tips.append(t)
    t = join(tips, "Szczyt_MB_deski", "Deski_poziome")
    # boards face outwards (away from the entrance block), plaster faces the vault
    set_face_mats(t, lambda c, n: "Tynk_wew" if (n.x > 0.5 and c.x < 9) or (n.x < -0.5 and c.x > 9) else "Deski_poziome")
    # each roof loses what lies inside the space under the other roof: the slabs meet in valleys and the
    # vault ceiling is the upper envelope (cutting below the other's top would open holes where slabs overlap)
    cut_obj(lw, mb_u); cut_obj(rw, mb_u)
    # strict priority so no two slab faces share a plane: the entrance-block roof gives way below the wing
    # tops, the wing roofs give way below the entrance-block underside
    cut_obj(mb, lw_r); cut_obj(mb, rw_r)
    for r in (lw_r, rw_r, lw_u, rw_u, mb_u, lw_s, rw_s):
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
        # frame lining reaches 3 cm below the ceiling and 6 cm above the tiles: no face shares a roof plane
        fr += [prism("f", slope(y0, y1, -RT_V - 0.03, 0.06), "x", x0, x0 + 0.07),
               prism("f", slope(y0, y1, -RT_V - 0.03, 0.06), "x", x1 - 0.07, x1),
               prism("f", slope(y0, y0 + 0.07, -RT_V - 0.03, 0.06), "x", x0, x1),
               prism("f", slope(y1 - 0.07, y1, -RT_V - 0.03, 0.06), "x", x0, x1)]
        gl.append(prism("g", slope(y0 + 0.07, y1 - 0.07, -0.05, -0.03), "x", x0 + 0.07, x1 - 0.07))
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
    gutters_and_ridges()

# ---------------- shared geometry helpers (site + detail) ----------------
def nz(x, y, s=1.0):
    """cheap deterministic 2D noise in -1..1"""
    return (math.sin(x * 0.131 * s + 1.7) * math.cos(y * 0.117 * s - 0.6) * 0.6 +
            math.sin((x + y) * 0.071 * s + 2.3) * 0.3 + math.sin(x * 0.37 * s - y * 0.29 * s) * 0.1)

def slab(bm, p0, p1, w, z0a, z1a, z0b=None, z1b=None):
    """box-like slab between plan points p0 and p1 (x, y), width w; vertical extents may differ at each end"""
    z0b = z0a if z0b is None else z0b
    z1b = z1a if z1b is None else z1b
    (ax, ay), (bx, by) = p0, p1
    d = Vector((bx - ax, -(by - ay), 0))
    if d.length < 1e-6:
        return
    d.normalize()
    n = Vector((-d.y, d.x, 0)) * (w / 2)
    A, B = Vector((ax, -ay, 0)), Vector((bx, -by, 0))
    v = [bm.verts.new(p) for p in (A - n + Vector((0, 0, z0a)), B - n + Vector((0, 0, z0b)), B + n + Vector((0, 0, z0b)), A + n + Vector((0, 0, z0a)),
                                   A - n + Vector((0, 0, z1a)), B - n + Vector((0, 0, z1b)), B + n + Vector((0, 0, z1b)), A + n + Vector((0, 0, z1a)))]
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([v[i] for i in f])

def finish(name, bm, mat, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_obj(name, bm, mat)
    if smooth:
        for poly in o.data.polygons:
            poly.use_smooth = True
    return o

class Veg:
    """one bmesh + vertex-colour layer per vegetation kind (exported as COLOR_0, multiplies the material)"""
    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.color.new("Col")
    def paint(self, verts, fn):
        for v in verts:
            c = fn(v)
            for l in v.link_loops:
                l[self.col] = (c[0], c[1], c[2], 1.0)
    def done(self, name, mat, smooth=True):
        return finish(name, self.bm, mat, smooth)

def clump(veg, c, rx, ry, rz, base, sub=1, rough=0.22, shade=0.45):
    """organic foliage mass: noisy icosphere, darker underneath"""
    m = bmesh.ops.create_icosphere(veg.bm, subdivisions=sub, radius=1.0)
    k = random.uniform(0, 100)
    for v in m["verts"]:
        d = v.co.copy()
        f = 1.0 + rough * nz(d.x * 9 + k, d.y * 9 - k + d.z * 7)
        v.co = Vector((c[0] + d.x * rx * f, c[1] + d.y * ry * f, c[2] + d.z * rz * f))
    tint = random.uniform(0.85, 1.12)
    veg.paint(m["verts"], lambda v: tuple(min(1.0, b * tint * (1 - shade + shade * (0.5 + 0.5 * (v.co.z - c[2]) / rz))) for b in base))

def trunk(veg, x, y, z0, h, r0, r1, base, lean=(0.0, 0.0), segs=6):
    m = bmesh.ops.create_cone(veg.bm, cap_ends=False, segments=segs, radius1=r0, radius2=r1, depth=h)
    for v in m["verts"]:
        t = (v.co.z + h / 2) / h
        v.co = Vector((x + v.co.x + lean[0] * t * h, -y + v.co.y + lean[1] * t * h, z0 + v.co.z + h / 2))
    veg.paint(m["verts"], lambda v: base)

# ---------------- terrain ----------------
# our plot (survey): front 32.0 m on the track, left side 69.5 m, back 32.8 m, right side 76.7 m;
# both sides square to the front, so the back edge is skewed by 7.2 m
PLOT_POLY = [(-6.66, 30.0), (25.34, 30.0), (25.34, -46.7), (-6.66, -39.5)]
PLOT = (-6.66, 25.34, -46.7, 30.0)         # bounding box
HC = (9.34, 11.3)                          # house centre (plan)
UPHILL = (0.906, 0.423)                    # plan direction of the 2 m rise (true south-east on the photo)
PAD = (-2.5, 21.5, 3.0, 24.0)              # graded, level house pad
JUNCTION = (38.0, 34.0)
TRACKS = {
    "front": [(JUNCTION[0], 34.0), (10.0, 33.8), (-20.0, 34.2), (-36.0, 38.0), (-62.0, 48.0), (-120.0, 58.0), (-170.0, 62.0)],
    "north": [JUNCTION, (39.5, 6.0), (41.0, -20.0), (47.0, -45.0), (58.0, -72.0), (66.0, -110.0), (74.0, -205.0)],
    "south": [JUNCTION, (44.0, 60.0), (56.0, 100.0), (66.0, 185.0)],
    "east": [JUNCTION, (70.0, 29.0), (115.0, 22.0), (205.0, 26.0)],
}

def natural(x, y):
    s = (x - HC[0]) * UPHILL[0] + (y - HC[1]) * UPHILL[1]
    return 2.7 * math.tanh(s / 60.0) + 0.6 * nz(x, y, 0.35) + 0.15 * nz(x * 1.7, y * 1.9)

N0 = natural(*HC)

def in_plot(x, y):
    inside = False
    for (ax, ay), (bx, by) in zip(PLOT_POLY, PLOT_POLY[1:] + PLOT_POLY[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside

def plot_dist(x, y):
    best = 1e9
    for (ax, ay), (bx, by) in zip(PLOT_POLY, PLOT_POLY[1:] + PLOT_POLY[:1]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return 0.0 if in_plot(x, y) else best

def rect_dist(x, y, r):
    dx = max(r[0] - x, 0.0, x - r[1]); dy = max(r[2] - y, 0.0, y - r[3])
    return math.hypot(dx, dy)

def ground(x, y):
    t = rect_dist(x, y, PAD) / 9.0
    t = 0.0 if t <= 0 else (1.0 if t >= 1 else t * t * (3 - 2 * t))
    return (natural(x, y) - N0) * t

def smooth_path(pts, it=3):
    for _ in range(it):
        sm = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            sm += [(0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by), (0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by)]
        sm.append(pts[-1]); pts = sm
    return pts

def resample(pts, step=1.0):
    out = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay); n = max(1, int(L / step))
        out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(1, n + 1)]
    return out

TRACK_PTS = {k: resample(smooth_path(v), 1.0) for k, v in TRACKS.items()}

def near_track(x, y, clear):
    for pts in TRACK_PTS.values():
        for px, py in pts[::3]:
            if abs(px - x) < clear + 3 and abs(py - y) < clear + 3 and math.hypot(px - x, py - y) < clear:
                return True
    return False

LOTS = []          # (x0, x1, y0, y1) gardens of the neighbours: lawn, no wild trees
BACK_GATE = []     # the two posts of the gate to the forest (plan points)

def in_lot(x, y, m=0.0):
    return any(a - m < x < b + m and c - m < y < d + m for a, b, c, d in LOTS)

def forest_zone(x, y):
    # forest behind (north of) the long plot and along its west side; younger belt to the north-east
    return (x < -17 and y < 26) or (y < -56 and x < 33) or (34 < x < 84 and -60 < y < -14)

def terrain():
    x0, x1, y0, y1, st = -170.0, 210.0, -210.0, 190.0, 2.0
    nx_, ny_ = int((x1 - x0) / st), int((y1 - y0) / st)
    bm = bmesh.new(); col = bm.loops.layers.color.new("Col")
    vs = [[bm.verts.new((x0 + i * st, -(y0 + j * st), ground(x0 + i * st, y0 + j * st))) for i in range(nx_ + 1)] for j in range(ny_ + 1)]
    for j in range(ny_):
        for i in range(nx_):
            f = bm.faces.new([vs[j][i], vs[j + 1][i], vs[j + 1][i + 1], vs[j][i + 1]])
            cx, cy = x0 + (i + 0.5) * st, y0 + (j + 0.5) * st
            if in_plot(cx, cy) or in_lot(cx, cy):
                f.material_index = 1
            elif forest_zone(cx, cy):
                f.material_index = 2
            for l in f.loops:
                vx, vy = l.vert.co.x, -l.vert.co.y
                a = 0.5 + 0.5 * nz(vx * 0.6, vy * 0.6)
                b = 0.5 + 0.5 * nz(vx * 2.1 + 9, vy * 2.3 - 4)
                if f.material_index == 1:
                    c = (0.82 + 0.18 * a, 0.88 + 0.12 * b, 0.80 + 0.1 * a)
                elif f.material_index == 2:
                    c = (0.75 + 0.25 * a, 0.72 + 0.2 * a, 0.70 + 0.2 * b)
                else:   # dry meadow: yellow / green patches like the photo
                    c = (0.80 + 0.2 * a, 0.80 + 0.2 * b, 0.62 + 0.25 * b * (1 - a))
                l[col] = (c[0], c[1], c[2], 1.0)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new("Teren"); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Teren", me); COL.objects.link(o)
    for m in ("Laka", "Trawa", "Sciolka"):
        me.materials.append(MATS[m])
    for poly in me.polygons:
        poly.use_smooth = True

def drape_path(name, pts, width, off, mat):
    bm = bmesh.new(); rows = []
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]; b = pts[min(len(pts) - 1, i + 1)]
        d = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        n = Vector((-d.y, d.x)) * (width / 2)
        row = []
        for s_ in (-1.0, -0.5, 0.0, 0.5, 1.0):
            px, py = x + n.x * s_, y + n.y * s_
            row.append(bm.verts.new((px, -py, ground(px, py) + off)))
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new([r0[k], r1[k], r1[k + 1], r0[k + 1]])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0: f.normal_flip()
    return new_obj(name, bm, mat)

def drape_rect(name, x0, x1, y0, y1, off, mat, step=1.0):
    bm = bmesh.new()
    nx_, ny_ = max(1, int((x1 - x0) / step)), max(1, int((y1 - y0) / step))
    vs = [[bm.verts.new((x0 + (x1 - x0) * i / nx_, -(y0 + (y1 - y0) * j / ny_), ground(x0 + (x1 - x0) * i / nx_, y0 + (y1 - y0) * j / ny_) + off))
           for i in range(nx_ + 1)] for j in range(ny_ + 1)]
    for j in range(ny_):
        for i in range(nx_):
            bm.faces.new([vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0: f.normal_flip()
    return new_obj(name, bm, mat)

def tracks():
    # sandy two-track dirt roads with a grassy crown, as on the aerial photo
    for i, (k, pts) in enumerate(TRACK_PTS.items()):
        off = 0.04 + 0.008 * i      # tracks overlap at the junction: never at the same height
        drape_path(f"Droga_{k}", pts, 3.6, off, "Droga_ziemia")
        drape_path(f"Droga_srodek_{k}", pts, 0.9, off + 0.05, "Laka")

# ---------------- house: gutters, ridges, details ----------------
def gutters_and_ridges():
    bm = bmesh.new()
    zg = PLATE - OV * TAN - 0.06
    ex_l, ex_r = LW[0] - OV - 0.07, RW[1] + OV + 0.07
    runs = [((ex_l, LW_BACK), (ex_l, LW[3] + VERGE)), ((ex_r, -VERGE), (ex_r, CARPORT_Y1 + VERGE)),
            ((LW[1] + OV + 0.07, LW_BACK), (LW[1] + OV + 0.07, MB[2] - OV)), ((LW[1] + OV + 0.07, MB[3] + OV), (LW[1] + OV + 0.07, LW[3] + VERGE)),
            ((RW[0] - OV - 0.07, -VERGE), (RW[0] - OV - 0.07, MB[2] - OV)), ((RW[0] - OV - 0.07, RW[3] + OV), (RW[0] - OV - 0.07, CARPORT_Y1 + VERGE)),
            ((LW[1] + OV, MB[2] - OV - 0.07), (RW[0] - OV, MB[2] - OV - 0.07)), ((LW[1] + OV, MB[3] + OV + 0.07), (RW[0] - OV, MB[3] + OV + 0.07))]
    for (ax, ay), (bx, by) in runs:
        cyl(bm, (ax, -ay, zg), (bx, -by, zg), 0.065, 10)        # 125 mm half-round gutter (closed for simplicity)
    for x, y in ((ex_l, LW[2] + 0.3), (ex_l, LW[3] - 0.3), (ex_r, 0.4), (ex_r, RW[3] - 0.4), (ex_r, CARPORT_Y1 - 0.2),
                 (RW[0] - OV - 0.07, MB[3] + OV + 0.07), (LW[1] + OV + 0.07, MB[2] - OV - 0.07)):
        cyl(bm, (x, -y, zg), (x, -y, 0.02), 0.045, 10)          # 90 mm downpipe
    finish("Rynny", bm, "Blacha_grafit", True)
    # ridge caps (gasiory)
    rb = bmesh.new()
    top_lw = PLATE + LW_HS * TAN + RT_V - 0.02
    top_rw = PLATE + RW_HS * TAN + RT_V - 0.02
    top_mb = PLATE + MB_HS * TAN + RT_V - 0.02
    # caps stop 2 cm short of the verges so their end discs never sit on the barge-board plane
    # wing caps break where the entrance-block roof rises over the wing ridge (else they hang in the vault)
    gap = (MB_RIDGE_Y - 0.9, MB_RIDGE_Y + 0.9)
    for x, top, y0, y1 in ((LW_RIDGE_X, top_lw, LW_BACK + 0.02, LW[3] + VERGE - 0.02), (RW_RIDGE_X, top_rw, -VERGE + 0.02, CARPORT_Y1 + VERGE - 0.02)):
        for a, b in ((y0, gap[0]), (gap[1], y1)):
            cyl(rb, (x, -a, top), (x, -b, top), 0.12, 10)
    cyl(rb, (LW_RIDGE_X + 0.03, -MB_RIDGE_Y, top_mb), (RW_RIDGE_X - 0.03, -MB_RIDGE_Y, top_mb), 0.12, 10)
    finish("Gasiory", rb, "Dachowka_grafit", True)

def vboards(bm, axis, a0, a1, plane, out, z0, z1, w=0.12, gap=0.016, t=0.022, off=0.012):
    """vertical boards on a wall face. axis 'x': face at plan y=plane, out = -1 (north) / +1 (south)"""
    a = a0
    while a + 0.03 < a1:
        b = min(a + w, a1)
        p0 = plane + out * off; p1 = plane + out * (off + t)
        lo, hi = sorted((p0, p1))
        if axis == "x":
            bm_box(bm, (a, -hi, z0), (b, -lo, z1))
        else:
            bm_box(bm, (lo, -b, z0), (hi, -a, z1))
        a = b + gap

def gable_hboards(bm, x0, x1, ridge, peak, y_face, out, z_from, h=0.125, gap=0.012, t=0.022):
    """horizontal boards filling a 30 deg gable triangle above z_from (face at plan y = y_face)"""
    z = z_from
    p0 = y_face + out * 0.012; p1 = y_face + out * 0.034
    lo, hi = sorted((p0, p1))
    while z < peak - 0.05:
        zt = min(z + h, peak)
        half = (peak - zt) / TAN
        a, b = max(x0, ridge - half), min(x1, ridge + half)
        if b - a > 0.05:
            bm_box(bm, (a, -hi, z), (b, -lo, zt))
        z = zt + gap

def lamp(bm_body, bm_glow, x, y, z, out_axis, out):
    """wall sconce: graphite body, glowing underside"""
    if out_axis == "y":
        y0, y1 = sorted((y, y + out * 0.12))
        bm_box(bm_body, (x - 0.06, -y1, z), (x + 0.06, -y0, z + 0.22))
        bm_box(bm_glow, (x - 0.045, -(y1 - 0.015), z - 0.006), (x + 0.045, -(y0 + 0.015), z + 0.001))
    else:
        x0_, x1_ = sorted((x, x + out * 0.12))
        bm_box(bm_body, (x0_, -(y + 0.06), z), (x1_, -(y - 0.06), z + 0.22))
        bm_box(bm_glow, (x0_ + 0.015, -(y + 0.045), z - 0.006), (x1_ - 0.015, -(y - 0.045), z + 0.001))

def house_details():
    T = T_EXT
    # chimney (stone) with the fireplace inside and the outdoor grill on the terrace side
    pb("Komin", 5.00, 6.05, 7.83, 8.62, 0.0, 6.25, "Kamien")
    pb("Komin_czapa", 4.95, 6.10, 7.78, 8.67, 6.25, 6.32, "Beton_grafit")
    fl = bmesh.new()
    for x in (5.3, 5.75):
        cyl(fl, (x, -8.22, 6.32), (x, -8.22, 6.62), 0.09, 10)
    finish("Komin_wyloty", fl, "Blacha_grafit", True)
    pb("Kominek", 4.90, 6.05, LW[2] + T, 9.05, FFL, FFL + 1.15, "Kamien")
    pb("Kominek_palenisko", 5.15, 5.80, 9.05, 9.06, FFL + 0.35, FFL + 0.95, "Palenisko")
    pb("Grill_palenisko", 5.15, 5.90, 7.82, 7.83, 0.95, 1.55, "Palenisko")
    # larch cladding: real boards on battens (vertical on walls, horizontal in the gables)
    bm = bmesh.new()
    vboards(bm, "x", 0.0, 2.23, LW[3], +1, FFL, PLATE)
    vboards(bm, "x", RW[0] + 0.45, 15.60, 0.0, -1, FFL, PLATE)
    vboards(bm, "y", 0.45, 1.95, RW[0], -1, FFL, PLATE)
    vboards(bm, "y", 3.76, 5.79, RW[0], -1, FFL, PLATE)
    finish("Deski_elewacja", bm, "Deski_pionowe")
    gb = bmesh.new()
    gable_hboards(gb, LW[0], LW[1], LW_RIDGE_X, PLATE + LW_HS * TAN, LW[3], +1, PLATE)
    gable_hboards(gb, LW[0], LW[1], LW_RIDGE_X, PLATE + LW_HS * TAN, LW[2], -1, PLATE)
    gable_hboards(gb, RW[0], RW[1], RW_RIDGE_X, PLATE + RW_HS * TAN, 0.0, -1, PLATE)
    gable_hboards(gb, RW[0], RW[1], RW_RIDGE_X, PLATE + RW_HS * TAN, CARPORT_Y1, +1, PLATE)
    finish("Szczyt_deski", gb, "Deski_poziome")
    pb("Kamien_wejscie", 10.65, RW[0] - 0.02, MB[3], MB[3] + 0.03, FFL - 0.03, WT, "Kamien")
    pb("Kamien_kominek_sciana", 4.40, 5.00, LW[2] - 0.03, LW[2], 0.0, PLATE, "Kamien")
    # covered terrace: joists + 140 mm deck boards with 6 mm gaps, two posts, open king-post truss
    pb("Taras_konstrukcja", 0.0, RW[0], 4.84, LW[2] - 0.01, 0.0, FFL - 0.06, "Beton_grafit")
    db = bmesh.new()
    y = 4.84
    while y < LW[2] - 0.02:
        bm_box(db, (0.0, -min(y + 0.14, LW[2]), FFL - 0.058), (RW[0], -y, FFL - 0.03))
        y += 0.146
    finish("Taras_deski", db, "Deski_taras")
    posts = [pb("s", 0.66, 0.91, 5.54, 5.79, FFL - 0.03, 2.55), pb("s", 6.58, 6.83, 5.54, 5.79, FFL - 0.03, 2.55)]
    join(posts, "Slupy_taras", "Biel")
    tr = [pb("b", 0.40, 7.05, 5.52, 5.81, 2.55, 2.85),
          pb("b", LW_RIDGE_X - 0.08, LW_RIDGE_X + 0.08, 5.58, 5.75, 2.85, lw_under(LW_RIDGE_X))]
    rafter = lambda xa, xb: prism("r", [(xa, lw_under(xa) - 0.20), (xb, lw_under(xb) - 0.20), (xb, lw_under(xb)), (xa, lw_under(xa))], "y", -5.75, -5.58)
    tr += [rafter(-0.3, LW_RIDGE_X), rafter(LW_RIDGE_X, LW[1] + 0.3)]
    for sx in (-1, 1):
        xa, xb = LW_RIDGE_X + sx * 0.08, LW_RIDGE_X + sx * 1.9
        za, zb = 2.85, lw_under(xb) - 0.20
        tr.append(prism("st", [(xa, za), (xb, zb - 0.16), (xb, zb), (xa, za + 0.16)], "y", -5.75, -5.58))
    join(tr, "Wiazar_taras", "Drewno_konstr")
    # entrance podest, step and planters
    pb("Podest_wejscie", LW[1], RW[0], MB[3], 19.20, 0.0, FFL - 0.03, "Plyty_beton")
    pb("Podest_stopien", 7.40, 11.00, 19.20, 19.55, 0.0, (FFL - 0.03) / 2, "Plyty_beton")
    for x in (6.45, 10.95):
        pb("Donica", x, x + 0.80, 18.70, 19.15, FFL - 0.03, FFL + 0.42, "Beton_grafit")
    # entrance hardware: stainless pull bar, house number
    pb("Klamka_wejscie", 8.86, 8.89, 16.20, 16.23, FFL + 0.70, FFL + 1.80, "Inox")
    pb("Numer_domu", 11.00, 11.40, MB[3] + 0.03, MB[3] + 0.04, 1.85, 2.05, "Blacha_grafit")
    # carport: open glulam frame (posts, beams, exposed rafters) next to the board-clad store
    cp = [pb("s", RW[0], RW[0] + 0.14, CARPORT_Y1 - 0.14, CARPORT_Y1, 0.05, 2.80),
          pb("s", RW[0], RW[0] + 0.14, 19.50, 19.64, 0.05, 2.80),
          pb("b", RW[0], 16.30, CARPORT_Y1 - 0.14, CARPORT_Y1, 2.80, PLATE),
          pb("b", RW[0], RW[0] + 0.14, RW[3], CARPORT_Y1, 2.80, PLATE)]
    yy = RW[3] + 0.4
    while yy < CARPORT_Y1 - 0.3:
        for xa, xb in ((RW[0], RW_RIDGE_X), (RW_RIDGE_X, 16.30)):
            cp.append(prism("r", [(xa, rw_under(xa) - 0.16), (xb, rw_under(xb) - 0.16), (xb, rw_under(xb)), (xa, rw_under(xa))], "y", -(yy + 0.08), -yy))
        yy += 0.8
    join(cp, "Wiata_konstrukcja", "Drewno_konstr")
    store = [pb("w", 16.30, 16.47, RW[3], 17.80, 0.0, 3.05), pb("w", 16.30, 16.47, 18.79, CARPORT_Y1, 0.0, 3.05),
             pb("w", 16.30, 16.47, 17.80, 18.79, 2.30, 3.05),
             pb("w", 18.31, 18.48, RW[3], CARPORT_Y1, 0.0, 3.05), pb("w", 16.47, 18.31, CARPORT_Y1 - 0.17, CARPORT_Y1, 0.0, 3.05)]
    join(store, "Wiata_pom_gosp", "Tynk_elewacja")
    pb("Wiata_pom_strop", 16.47, 18.31, RW[3], CARPORT_Y1 - 0.17, 2.60, 2.64, "Podbitka")
    sb = bmesh.new()
    vboards(sb, "y", RW[3], 17.80, 16.30, -1, 0.05, 3.0)
    vboards(sb, "y", 18.79, CARPORT_Y1, 16.30, -1, 0.05, 3.0)
    vboards(sb, "y", 17.80, 18.79, 16.30, -1, 2.30, 3.0)
    vboards(sb, "y", RW[3], CARPORT_Y1, 18.48, +1, 0.05, 3.0)
    vboards(sb, "x", 16.30, 18.48, CARPORT_Y1, +1, 0.05, 3.0)
    finish("Wiata_deski", sb, "Deski_pionowe")
    # plank door to the store, hinged, opening out into the carport
    door_leaf(dict(t0=16.30, along_x=False), "Wiata_drzwi", 17.84, 18.75, 0.0, 0.04, 0.06, 2.27, -1, "Deski_pionowe", handles=True)
    pb("Wiata_posadzka", RW[0], 16.30, RW[3], 22.57, 0.0, 0.05, "Kostka_szara")
    pb("Wiata_pom_posadzka", 16.47, 18.31, RW[3], CARPORT_Y1 - 0.17, 0.0, 0.05, "Beton")
    # wall sconces (glow after dusk)
    body, glow = bmesh.new(), bmesh.new()
    lamp(body, glow, 7.95, MB[3], 2.05, "y", +1)
    lamp(body, glow, 10.95, MB[3] + 0.03, 2.05, "y", +1)    # on the stone
    for x in (1.2, 5.4, 8.0, 10.6):
        lamp(body, glow, x, LW[2], 2.25, "y", -1)
    lamp(body, glow, 14.3, RW[3], 2.25, "y", +1)
    lamp(body, glow, RW[0], 4.8, 2.25, "x", -1)
    lamp(body, glow, 16.30, 19.2, 2.25, "x", -1)
    finish("Kinkiety", body, "Blacha_grafit")
    finish("Kinkiety_swiatlo", glow, "Swiatlo")
    # 50 cm white-gravel strip (opaska) with steel edging round the walls facing the lawn
    gv, ed = bmesh.new(), bmesh.new()
    for x0, x1, y0, y1 in ((-0.5, 0.0, LW[2], LW[3]), (RW[1], RW[1] + 0.5, 0.0, RW[3]), (RW[0], RW[1] + 0.5, -0.5, 0.0),
                           (-0.5, 6.05, LW[3], LW[3] + 0.5), (RW[0] - 0.5, RW[0], 0.0, 4.84)):
        bm_box(gv, (x0, -y1, 0.0), (x1, -y0, 0.035))
    finish("Opaska_zwir", gv, "Zwir_bialy")

# ---------------- plot: paths, fence, lights, garden ----------------
def plot():
    y1 = PLOT_POLY[0][1]
    drape_rect("Podjazd", 12.0, 16.5, 22.57, 32.0, 0.05, "Kostka_szara")
    slabs = bmesh.new()
    def slab_at(xa, xb, ya, yb):
        g = [ground(xa, ya), ground(xb, ya), ground(xa, yb), ground(xb, yb)]
        bm_box(slabs, (xa, -yb, min(g) - 0.04), (xb, -ya, max(g) + 0.03))
    y = 19.7
    while y + 0.45 < y1 + 1.5:
        slab_at(8.60, 10.20, y, y + 0.45); y += 0.72
    for i in range(6):
        yy = 4.5 - i * 0.72
        slab_at(8.0, 9.6, yy - 0.45, yy)
    finish("Sciezka_plyty", slabs, "Plyty_beton")
    lamps = bmesh.new()
    for x, y in [(7.9, 21.2), (10.9, 21.2), (7.9, 24.4), (10.9, 24.4), (7.9, 27.6), (10.9, 27.6), (7.6, 3.4), (10.0, 0.6)]:
        g = ground(x, y)
        cyl(lamps, (x, -y, g - 0.05), (x, -y, g + 0.60), 0.06, 12)
    finish("Slupki_LED", lamps, "Lampa_LED", True)
    # mailbox by the wicket
    pb("Skrzynka_slupek", 7.6, 7.68, 30.25, 30.33, ground(7.6, 30.3) - 0.1, ground(7.6, 30.3) + 1.0, "Ogrodzenie")
    pb("Skrzynka", 7.48, 7.80, 30.10, 30.36, ground(7.6, 30.3) + 1.0, ground(7.6, 30.3) + 1.38, "Ogrodzenie")
    fence()
    garden()

def fence():
    x0, x1, y1 = PLOT_POLY[0][0], PLOT_POLY[1][0], PLOT_POLY[0][1]
    H = 1.73      # 1730 mm 3D panels; the invisible collision wall below is 2.6 m so it cannot be jumped
    gate, wicket = (11.9, 16.6), (8.9, 10.0)
    base, posts, slats, wires, kol = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    def spans(a, b, step):
        n = max(1, round(abs(b - a) / step))
        return [a + (b - a) * i / n for i in range(n + 1)]
    # front: graphite block base following the slope, block posts, horizontal aluminium slats
    for a, b in ((x0, wicket[0]), (wicket[1], gate[0]), (gate[1], x1)):
        xs = spans(a, b, 2.6)
        for i, px in enumerate(xs):
            g = ground(px, y1)
            bm_box(posts, (px - 0.12, -(y1 + 0.12), g - 0.3), (px + 0.12, -(y1 - 0.12), g + 1.82))
        for pa, pb_ in zip(xs, xs[1:]):
            ga, gb = ground(pa, y1), ground(pb_, y1)
            slab(base, (pa, y1), (pb_, y1), 0.20, ga - 0.3, ga + 0.40, gb - 0.3, gb + 0.40)
            for k in range(9):
                z = 0.50 + k * 0.135
                slab(slats, (pa + 0.12, y1), (pb_ - 0.12, y1), 0.04, ga + z, ga + z + 0.10, gb + z, gb + z + 0.10)
            slab(kol, (pa, y1), (pb_, y1), 0.24, ga, ga + 2.6, gb, gb + 2.6)
    g = ground(gate[1], y1)
    for k in range(9):     # sliding gate parked open behind the eastern span
        z = 0.50 + k * 0.135
        slab(slats, (gate[1] + 0.1, y1 - 0.28), (gate[1] + 0.1 + (gate[1] - gate[0]), y1 - 0.28), 0.04, g + z, g + z + 0.10)
        slab(slats, (wicket[0] + 0.04, y1 - 0.1), (wicket[0] + 0.04, y1 - 1.1), 0.04, g + z, g + z + 0.10)   # wicket swung in
    # sides and back: 1.53 m 3D welded-mesh panels on posts with a 20 cm concrete underpinning
    # back fence gets a 1.2 m gate to the forest: split that run around the opening
    (bax, bay), (bbx, bby) = PLOT_POLY[3], PLOT_POLY[2]
    blen = math.hypot(bbx - bax, bby - bay)
    t0, t1 = 0.5 - 0.6 / blen, 0.5 + 0.6 / blen
    g0 = (bax + (bbx - bax) * t0, bay + (bby - bay) * t0)
    g1 = (bax + (bbx - bax) * t1, bay + (bby - bay) * t1)
    BACK_GATE.extend([g0, g1])
    for (ax, ay), (bx, by) in ((PLOT_POLY[3], PLOT_POLY[0]), (PLOT_POLY[2], PLOT_POLY[1]), (PLOT_POLY[3], g0), (g1, PLOT_POLY[2])):
        L = math.hypot(bx - ax, by - ay); n = max(1, round(L / 2.5))
        pts = [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n + 1)]
        for px, py in pts:
            g = ground(px, py)
            bm_box(posts, (px - 0.03, -(py + 0.03), g - 0.3), (px + 0.03, -(py - 0.03), g + H + 0.05))
        for (pa, qa), (pb_, qb) in zip(pts, pts[1:]):
            ga, gb = ground(pa, qa), ground(pb_, qb)
            slab(base, (pa, qa), (pb_, qb), 0.05, ga - 0.2, ga + 0.2, gb - 0.2, gb + 0.2)
            slab(kol, (pa, qa), (pb_, qb), 0.1, ga, ga + 2.6, gb, gb + 2.6)
            m = int(math.hypot(pb_ - pa, qb - qa) / 0.2)
            for i in range(m + 1):
                t = i / m
                px, py = pa + (pb_ - pa) * t, qa + (qb - qa) * t
                g = ga + (gb - ga) * t
                cyl(wires, (px, -py, g + 0.22), (px, -py, g + H), 0.0025, 4)
            for z in (0.26, 0.30, 0.78, 0.82, 1.24, 1.28, H - 0.04, 1.62):
                cyl(wires, (pa, -qa, ga + z), (pb_, -qb, gb + z), 0.0025, 4)
    # the forest gate leaf, swung open into the garden (mesh panel like the fence)
    (gx, gy), (hx, hy) = g0, g1
    nx_, ny_ = -(hy - gy), (hx - gx)             # inward normal (towards the house)
    L = math.hypot(nx_, ny_); nx_, ny_ = nx_ / L, ny_ / L
    if (HC[0] - gx) * nx_ + (HC[1] - gy) * ny_ < 0:
        nx_, ny_ = -nx_, -ny_
    gz = ground(gx, gy)
    tip = (gx + nx_ * 1.15, gy + ny_ * 1.15)
    for z in (0.15, 0.6, 1.05, 1.5, H - 0.02):
        cyl(wires, (gx, -gy, gz + z), (tip[0], -tip[1], gz + z), 0.004, 4)
    for k in range(7):
        t = k / 6
        px, py = gx + nx_ * 1.15 * t, gy + ny_ * 1.15 * t
        cyl(wires, (px, -py, gz + 0.12), (px, -py, gz + H), 0.003 if 0 < k < 6 else 0.02, 4)
    finish("Ogrodzenie_podmurowka", base, "Beton_grafit")
    finish("Ogrodzenie_slupki", posts, "Ogrodzenie")
    finish("Ogrodzenie_sztachety", slats, "Ogrodzenie")
    finish("Ogrodzenie_panele", wires, "Ogrodzenie")
    finish("Kolizja_ogrodzenie", kol, "Kolizja")

GREEN_PINE = (0.30, 0.42, 0.24)
GREEN_SPRUCE = (0.22, 0.36, 0.22)
GREEN_LEAF = (0.42, 0.56, 0.26)
GREEN_SHRUB = (0.34, 0.48, 0.24)
BARK_PINE = (0.52, 0.42, 0.34)
BARK_DARK = (0.38, 0.30, 0.24)

def grass_tuft(veg, x, y, h, base, blades=9, spread=0.10):
    z0 = ground(x, y)
    for k in range(blades):
        a = random.uniform(0, 2 * math.pi); lean = random.uniform(0.2, 0.55) * h
        hh = h * random.uniform(0.7, 1.1)
        dx, dy = math.cos(a), math.sin(a)
        px, py = x + dx * random.uniform(0, spread), -y + dy * random.uniform(0, spread)
        w = 0.012
        v0 = veg.bm.verts.new((px - dy * w, py + dx * w, z0 - 0.02))
        v1 = veg.bm.verts.new((px + dy * w, py - dx * w, z0 - 0.02))
        v2 = veg.bm.verts.new((px + dx * lean * 0.45 - dy * w * 0.6, py + dy * lean * 0.45 + dx * w * 0.6, z0 + hh * 0.6))
        v3 = veg.bm.verts.new((px + dx * lean * 0.45 + dy * w * 0.6, py + dy * lean * 0.45 - dx * w * 0.6, z0 + hh * 0.6))
        v4 = veg.bm.verts.new((px + dx * lean, py + dy * lean, z0 + hh))
        f1 = veg.bm.faces.new([v0, v1, v3, v2]); f2 = veg.bm.faces.new([v2, v3, v4])
        tint = random.uniform(0.85, 1.1)
        for f in (f1, f2):
            for l in f.loops:
                t = (l.vert.co.z - z0) / max(hh, 0.01)
                l[veg.col] = tuple(min(1.0, b * tint * (0.55 + 0.45 * t)) for b in base) + (1.0,)

def spruce(veg_t, veg_c, x, y, h, base=GREEN_SPRUCE):
    z0 = ground(x, y)
    trunk(veg_t, x, y, z0 - 0.1, h * 0.95, 0.04 + h * 0.012, 0.02, BARK_DARK)
    tiers = max(4, int(h / 0.45))
    for i in range(tiers):
        t = i / tiers
        r = (1 - t) * h * 0.30 + 0.12
        zc = z0 + h * 0.08 + t * h * 0.88
        m = bmesh.ops.create_cone(veg_c.bm, cap_ends=True, segments=12, radius1=r, radius2=0.0, depth=h * 0.22)
        for j, v in enumerate(m["verts"]):
            if v.co.z < 0:     # jagged, drooping tier edge
                k = 0.72 if j % 2 else 1.0
                v.co.x *= k; v.co.y *= k; v.co.z -= 0.08 * k
            v.co += Vector((x, -y, zc + h * 0.11))
        shade = 0.55 + 0.45 * t
        veg_c.paint(m["verts"], lambda v, s_=shade: tuple(b * s_ * random.uniform(0.9, 1.08) for b in base))

def pine(veg_t, veg_c, x, y, h, detail=False):
    z0 = ground(x, y)
    lean = (random.uniform(-0.03, 0.03), random.uniform(-0.03, 0.03))
    trunk(veg_t, x, y, z0 - 0.15, h * 0.88, 0.16 + h * 0.007, 0.06, BARK_PINE, lean)
    top_x, top_y = x + lean[0] * h * 0.85, y - lean[1] * h * 0.85
    for k in range(random.randint(3, 4)):
        a = random.uniform(0, 2 * math.pi); r = random.uniform(0.4, 1.5)
        cz = z0 + h * random.uniform(0.70, 0.93)
        clump(veg_c, (top_x + math.cos(a) * r, -top_y + math.sin(a) * r, cz),
              random.uniform(1.4, 2.4), random.uniform(1.4, 2.4), random.uniform(0.8, 1.2), GREEN_PINE, 2 if detail else 1)

def birch(veg_t, veg_c, x, y, h, detail=False):
    z0 = ground(x, y)
    trunk(veg_t, x, y, z0 - 0.1, h * 0.8, 0.12, 0.04, (0.92, 0.90, 0.86))
    for k in range(5):
        a = random.uniform(0, 2 * math.pi); r = random.uniform(0.3, 1.3)
        clump(veg_c, (x + math.cos(a) * r, -y + math.sin(a) * r, z0 + h * random.uniform(0.55, 0.9)),
              random.uniform(1.0, 1.7), random.uniform(1.0, 1.7), random.uniform(1.0, 1.6), GREEN_LEAF, 2 if detail else 1, rough=0.3)

def shrub(veg, x, y, s, base=GREEN_SHRUB):
    z0 = ground(x, y)
    for k in range(3):
        a = random.uniform(0, 2 * math.pi)
        clump(veg, (x + math.cos(a) * s * 0.4, -y + math.sin(a) * s * 0.4, z0 + s * random.uniform(0.35, 0.6)),
              s * random.uniform(0.5, 0.75), s * random.uniform(0.5, 0.75), s * random.uniform(0.4, 0.6), base, 2)

# ---------------- impostor cards (Poly Haven trees / plants baked by impostors.py) ----------------
import json
IMP_DIR = os.path.join(ROOT, "impostors")
IMP = json.load(open(os.path.join(IMP_DIR, "impostors.json")))
CARDS = {}

def card(name, x, y, s=1.0):
    CARDS.setdefault(name, []).append((x, y, s, random.uniform(0, math.pi)))

def imp_mat(name):
    key = f"Karta_{name}"
    if key not in MATS:
        m = bpy.data.materials.new(key); m.use_nodes = True
        nt = m.node_tree; b = nt.nodes["Principled BSDF"]
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(IMP_DIR, f"{name}.png"), check_existing=True)
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
        b.inputs["Roughness"].default_value = 0.9
        m.surface_render_method = "DITHERED"
        MATS[key] = m
    return key

def build_cards():
    """each instance = VIEWS crossed vertical cards; normals bend outwards and up so the flat
    cards shade like a crown. Trees also get an invisible trunk collider."""
    kol = bmesh.new()
    for name, inst in CARDS.items():
        meta = IMP[name]; V = meta["views"]; w, h = meta["w"], meta["h"]
        verts, faces, uvs, nrm = [], [], [], []
        for x, y, s_, yaw in inst:
            z0 = ground(x, y) - 0.06 * s_
            hw, hh = w * s_ / 2, h * s_
            for k in range(V):
                a = yaw + math.pi * k / V
                dx, dy = math.cos(a) * hw, math.sin(a) * hw
                b = len(verts)
                verts += [(x - dx, -y - dy, z0), (x + dx, -y + dy, z0), (x + dx, -y + dy, z0 + hh), (x - dx, -y - dy, z0 + hh)]
                faces.append((b, b + 1, b + 2, b + 3))
                u0, u1 = k / V, (k + 1) / V
                uvs += [(u0, 0), (u1, 0), (u1, 1), (u0, 1)]
                for sx, t in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
                    nrm.append(Vector((sx * math.cos(a), sx * math.sin(a), 0.35 + 0.5 * t)).normalized())
            if h * s_ > 4:
                cyl(kol, (x, -y, z0), (x, -y, z0 + 3.0), 0.22 * s_, 6)
        me = bpy.data.meshes.new(f"Las_{name}")
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        for li, uv in enumerate(uvs):
            uvl.data[li].uv = uv
        me.normals_split_custom_set(nrm)
        o = bpy.data.objects.new(f"Las_{name}", me); COL.objects.link(o)
        me.materials.append(MATS[imp_mat(name)])
        o["keep_uv"] = 1
    CARDS.clear()
    if kol.verts:
        finish("Kolizja_las", kol, "Kolizja")
    else:
        kol.free()

def deadwood(points):
    """real Poly Haven dead trunk and dry branches, decimated, placed as copies sharing one mesh"""
    made = {}
    for asset, ratio in (("dead_tree_trunk", 0.04), ("dry_branches_medium_01", 0.2)):
        path = os.path.join(ROOT, "assets_src", asset, f"{asset}_1k.blend")
        if not os.path.exists(path):
            continue
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(asset)][:1]
        o = dst.objects[0]
        for img in bpy.data.images:
            if img.filepath.startswith("//textures"):
                img.filepath = os.path.join(ROOT, "assets_src", asset, img.filepath[2:]); img.reload()
        COL.objects.link(o)
        m = o.modifiers.new("dec", "DECIMATE"); m.ratio = ratio
        apply_mods(o)
        made[asset] = o
    for i, (x, y) in enumerate(points):
        src = made.get("dead_tree_trunk" if i % 3 == 0 else "dry_branches_medium_01")
        if not src:
            continue
        o = src.copy(); COL.objects.link(o)
        o.location = (x, -y, ground(x, y) + 0.05)
        o.rotation_euler = (0, 0, random.uniform(0, 2 * math.pi))
        o.name = f"Martwe_drewno_{i}"
        o["keep_uv"] = 1
    for o in made.values():
        bpy.data.objects.remove(o, do_unlink=True)     # the copies keep the shared mesh

def garden():
    trunks, crowns, leaves, shrubs, grass, lav, lavf, mulch = Veg(), Veg(), Veg(), Veg(), Veg(), Veg(), Veg(), bmesh.new()
    # mulched beds: along the living-wing front (lavender) and both sides of the entrance path (grasses)
    for x0, x1, y0, y1 in ((0.0, 6.0, LW[3] + 0.5, LW[3] + 1.6), (6.9, 8.2, 19.8, 28.8), (10.6, 11.9, 19.8, 28.8)):
        bm_box(mulch, (x0, -y1, -0.05), (x1, -y0, max(ground(x0, y1), ground(x1, y1)) + 0.04))
    finish("Rabaty_kora", mulch, "Kora_mulcz")
    for i in range(11):
        x, y = 0.4 + i * 0.52, LW[3] + 1.05
        z0 = ground(x, y) + 0.04
        for k in range(14):   # lavender: grey-green stems with purple spikes
            a = random.uniform(0, 2 * math.pi); r = random.uniform(0.0, 0.18)
            px, py = x + math.cos(a) * r, y + math.sin(a) * r
            h = random.uniform(0.35, 0.5)
            stem = cyl(lav.bm, (px, -py, z0), (px + math.cos(a) * 0.08, -py + math.sin(a) * 0.08, z0 + h), 0.006, 3)
            lav.paint(stem, lambda v: (0.5, 0.58, 0.45))
            m = bmesh.ops.create_cone(lavf.bm, cap_ends=True, segments=5, radius1=0.022, radius2=0.008, depth=0.10)
            for v in m["verts"]:
                v.co += Vector((px + math.cos(a) * 0.08, -py + math.sin(a) * 0.08, z0 + h + 0.03))
            lavf.paint(m["verts"], lambda v: (random.uniform(0.45, 0.6), random.uniform(0.38, 0.48), random.uniform(0.75, 0.9)))
    for x in (7.2, 7.8, 11.0, 11.6):          # ornamental grass along the entrance path
        for y in (20.3, 21.9, 23.5, 25.1, 26.7, 28.3):
            card("grass_b", x + random.uniform(-0.15, 0.15), y, random.uniform(3.2, 4.0))
    for x, y, s_ in ((-4.8, -6.0, 1.6), (-4.6, 4.0, 1.2), (23.4, -8.0, 1.5), (23.5, 3.0, 1.3), (-4.8, 27.6, 1.4),
                     (23.4, 27.6, 1.2), (20.5, 26.0, 1.0), (-4.5, -30.0, 1.5), (23.0, -36.0, 1.4), (10.0, -20.0, 1.1)):
        card("fir_sap", x, y, s_ * 1.2)        # dwarf conifers
    for x, y in ((-3.5, -4.5), (22.5, -4.0), (22.0, 8.0), (2.0, -24.0), (17.0, -30.0), (8.0, -36.0)):
        card("pine_b", x, y, random.uniform(0.45, 0.55))
    (ax, ay), (bx, by) = PLOT_POLY[3], PLOT_POLY[2]
    for k in range(24):   # young fir hedge along the back fence, clear of the forest gate
        t = (k + 0.5) / 24
        if abs(t - 0.5) < 0.07:
            continue
        card("fir_sap", ax + (bx - ax) * t, ay + (by - ay) * t + 0.9, random.uniform(2.0, 2.4))
    for v in (trunks, crowns, leaves, shrubs, grass):
        v.bm.free()
    lav.done("Lawenda_lodygi", "Trawa_ozdobna", smooth=False)
    lavf.done("Lawenda", "Lawenda")

# ---------------- neighbourhood ----------------
class Capture:
    def __enter__(self):
        self.before = set(COL.objects); return self
    def __exit__(self, *a):
        self.objs = [o for o in COL.objects if o not in self.before]

def nhouse(i, cx, cy, rot, w, d, wall_h, pitch, roof_mat, wall_mat, frame_mat="Rama_okna",
           cross=False, garage=False, dormers=0, lot=None):
    """a believable neighbour: plinth, walls, real-looking windows with sills, roof with overhangs,
    fascia, gutters, ridge cap, chimney, entrance canopy; built axis-aligned then rotated into place"""
    hw, hd = w / 2, d / 2
    corners = [(cx + sx * hw, cy + sy * hd) for sx in (-1, 1) for sy in (-1, 1)]
    zb = min(ground(*c) for c in corners) - 0.3
    ffl = max(ground(*c) for c in corners) + 0.35
    t = math.tan(math.radians(pitch))
    with Capture() as cap:
        pb(f"Sasiad_{i}_cokol", cx - hw, cx + hw, cy - hd, cy + hd, zb, ffl, "Cokol")
        pb(f"Sasiad_{i}_sciany", cx - hw, cx + hw, cy - hd, cy + hd, ffl, ffl + wall_h, wall_mat)
        eave = ffl + wall_h
        sec = [(-(cy - hd - 0.6), eave - 0.6 * t), (-cy, eave + hd * t), (-(cy + hd + 0.6), eave - 0.6 * t),
               (-(cy + hd + 0.6), eave - 0.6 * t + 0.28), (-cy, eave + hd * t + 0.28), (-(cy - hd - 0.6), eave - 0.6 * t + 0.28)]
        prism(f"Sasiad_{i}_dach", sec, "x", cx - hw - 0.45, cx + hw + 0.45, roof_mat)   # noqa
        fas = [prism("f", [(-(cy + s * (hd + 0.6)), eave - 0.6 * t - 0.02), (-(cy + s * (hd + 0.6)), eave - 0.6 * t + 0.28),
                           (-(cy + s * (hd + 0.63)), eave - 0.6 * t + 0.28), (-(cy + s * (hd + 0.63)), eave - 0.6 * t - 0.02)],
                     "x", cx - hw - 0.45, cx + hw + 0.45) for s in (-1, 1)]
        join(fas, f"Sasiad_{i}_deska_czolowa", "Biel")
        gab = []
        for s in (-1, 1):
            x_in = cx + s * (hw - 0.3)
            x_out = cx + s * hw
            lo, hi = sorted((x_in, x_out))
            # starts exactly at the eave: an overlap would leave a coplanar strip with the wall face
            gab.append(prism("g", [(-(cy - hd), eave), (-cy, eave + hd * t - 0.02), (-(cy + hd), eave)], "x", lo, hi))
        join(gab, f"Sasiad_{i}_szczyty", wall_mat)
        rb = bmesh.new()
        cyl(rb, (cx - hw - 0.43, -cy, eave + hd * t + 0.26), (cx + hw + 0.43, -cy, eave + hd * t + 0.26), 0.11, 8)
        for s in (-1, 1):
            yy = cy + s * (hd + 0.70)
            cyl(rb, (cx - hw - 0.43, -yy, eave - 0.6 * t - 0.05), (cx + hw + 0.43, -yy, eave - 0.6 * t - 0.05), 0.06, 8)
        finish(f"Sasiad_{i}_rynny", rb, "Blacha_grafit", True)
        pb(f"Sasiad_{i}_komin", cx + hw * 0.35, cx + hw * 0.35 + 0.55, cy - 0.9, cy - 0.35, eave, eave + hd * t + 1.0, "Cegla")
        # windows: frame, recessed glass, sill; ground floor + (if tall) first floor; gable attic windows
        fr, gl, sl = bmesh.new(), bmesh.new(), bmesh.new()
        def win(a, z0, ww, hh, face, s):
            if face == "y":
                y0 = cy + s * hd
                p0, p1 = sorted((y0, y0 + s * 0.05))
                bm_box(fr, (a - ww / 2, -p1, z0), (a + ww / 2, -p0, z0 + hh))
                q0, q1 = sorted((y0 + s * 0.05, y0 + s * 0.06))
                bm_box(gl, (a - ww / 2 + 0.07, -q1, z0 + 0.07), (a + ww / 2 - 0.07, -q0, z0 + hh - 0.07))
                r0, r1 = sorted((y0, y0 + s * 0.14))
                bm_box(sl, (a - ww / 2 - 0.04, -r1, z0 - 0.04), (a + ww / 2 + 0.04, -r0, z0))
            else:
                x0_ = cx + s * hw
                p0, p1 = sorted((x0_, x0_ + s * 0.05))
                bm_box(fr, (p0, -(a + ww / 2), z0), (p1, -(a - ww / 2), z0 + hh))
                q0, q1 = sorted((x0_ + s * 0.05, x0_ + s * 0.06))
                bm_box(gl, (q0, -(a + ww / 2 - 0.07), z0 + 0.07), (q1, -(a - ww / 2 + 0.07), z0 + hh - 0.07))
                r0, r1 = sorted((x0_, x0_ + s * 0.14))
                bm_box(sl, (r0, -(a + ww / 2 + 0.04), z0 - 0.04), (r1, -(a - ww / 2 - 0.04), z0))
        floors = [ffl + 0.9] + ([ffl + 3.7] if wall_h > 5 else [])
        for zf in floors:
            n = max(2, int(w / 3.2))
            for k in range(n):
                a = cx - hw + w * (k + 0.5) / n
                for s in (-1, 1):
                    if not (zf == ffl + 0.9 and s > 0 and abs(a - cx) < 1.0):
                        win(a, zf, 1.2 if k % 2 else 1.5, 1.45, "y", s)
            for s in ((-1,) if garage else (-1, 1)):   # the garage covers the +x wall
                win(cy, zf, 1.0, 1.4, "x", s)
        for s in (-1, 1):   # attic window in each gable (above the garage roof)
            win(cy, eave + 0.3, 0.9, 1.1, "x", s)
        finish(f"Sasiad_{i}_okna_ramy", fr, frame_mat)
        finish(f"Sasiad_{i}_okna_szyby", gl, "Okno_sasiad")
        finish(f"Sasiad_{i}_parapety", sl, "Blacha_grafit")
        # front door + canopy (front = +y side, towards the street)
        pb(f"Sasiad_{i}_drzwi", cx - 0.55, cx + 0.55, cy + hd, cy + hd + 0.05, ffl + 0.01, ffl + 2.15, "Rama_okna")
        pb(f"Sasiad_{i}_daszek", cx - 1.2, cx + 1.2, cy + hd, cy + hd + 1.2, ffl + 2.5, ffl + 2.62, "Blacha_grafit")
        pb(f"Sasiad_{i}_schodek", cx - 1.0, cx + 1.0, cy + hd, cy + hd + 1.0, zb, ffl - 0.02, "Plyty_beton")
        for k in range(dormers):   # roof windows on the street slope
            a = cx - hw + w * (k + 0.5) / dormers
            y0_, y1_ = cy + 0.8, cy + 2.0
            prism(f"Sasiad_{i}_okno_dach", [(-y0_, eave + (hd - 0.8) * t + 0.30), (-y1_, eave + (hd - 2.0) * t + 0.30),
                                             (-y1_, eave + (hd - 2.0) * t + 0.36), (-y0_, eave + (hd - 0.8) * t + 0.36)], "x", a - 0.4, a + 0.4, "Okno_sasiad")
        if garage:
            gx0 = cx + hw
            pb(f"Sasiad_{i}_garaz", gx0, gx0 + 3.6, cy - hd + 1.0, cy + hd, zb, ffl + 2.6, wall_mat)
            pb(f"Sasiad_{i}_garaz_dach", gx0 - 0.1, gx0 + 3.8, cy - hd + 0.9, cy + hd + 0.2, ffl + 2.6, ffl + 2.8, "Blacha_grafit")
            pb(f"Sasiad_{i}_garaz_brama", gx0 + 0.4, gx0 + 3.2, cy + hd, cy + hd + 0.04, ffl - 0.3, ffl + 2.1, "Blacha_grafit")
    # rotate everything about the house centre
    if rot:
        from mathutils import Matrix
        M = Matrix.Translation((cx, -cy, 0)) @ Matrix.Rotation(math.radians(rot), 4, "Z") @ Matrix.Translation((-cx, cy, 0))
        for o in cap.objs:
            o.data.transform(M)
    if lot:
        LOTS.append(lot)

def neighbour_garden(i, lot, trees_n, veg, hedge=False):
    x0, x1, y0, y1 = lot
    for k in range(trees_n):
        x, y = random.uniform(x0 + 2, x1 - 2), random.uniform(y0 + 2, y1 - 2)
        if random.random() < 0.5:
            card("pine_b", x, y, random.uniform(0.45, 0.65))
        else:
            card("fir_c", x, y, random.uniform(0.35, 0.5))
    if hedge:   # conifer hedge along the street side
        x = x0 + 0.6
        while x < x1 - 0.6:
            card("fir_sap", x, y1 - 0.6, random.uniform(1.8, 2.2)); x += 0.7

def neighbourhood():
    LOTS.extend([(-44.0, -12.0, 44.0, 68.0), (40.0, 128.0, -132.0, -52.0)])
    terrain()
    tracks()
    veg = {"t": Veg(), "c": Veg(), "l": Veg()}
    # the new house south-west of the plot (photo: steep standing-seam roof, white walls, big glazing)
    nhouse("SW", -28.0, 55.0, 15, 13.0, 9.0, 3.1, 45, "Blacha_rabek", "Sciana_sasiad", cross=True, dormers=2)
    neighbour_garden("SW", (-44.0, -12.0, 44.0, 68.0), 3, veg)
    drape_rect("Sasiad_SW_podjazd", -26.0, -22.0, 40.0, 50.0, 0.04, "Kostka_szara")
    # houses beyond the tree belt to the north-east
    for k, (x, y, rot, w, d, wh, p, rm, wm, gar, dm) in enumerate([
            (58.0, -66.0, 10, 11.0, 9.5, 3.2, 40, "Dachowka_czerwona", "Sciana_sasiad", True, 0),
            (82.0, -74.0, -5, 12.0, 10.0, 5.8, 35, "Dachowka_ciemna", "Sciana_sasiad", False, 0),
            (106.0, -66.0, 20, 10.5, 9.0, 3.3, 42, "Dachowka_pomaranczowa", "Sciana_sasiad_bez", False, 2),
            (66.0, -104.0, 0, 11.5, 9.0, 3.2, 40, "Dachowka_grafit", "Sciana_sasiad", True, 2),
            (96.0, -110.0, 8, 12.0, 9.5, 3.4, 38, "Dachowka_czerwona", "Sciana_sasiad_bez", False, 0)]):
        nhouse(f"NE{k}", x, y, rot, w, d, wh, p, rm, wm, garage=gar, dormers=dm)
        neighbour_garden(f"NE{k}", (x - 11, x + 11, y - 13, y + 11), 2, veg, hedge=(k % 2 == 0))
    trees(veg)

def trees(veg):
    def blocked(x, y, clear=4.0):
        if plot_dist(x, y) < 4.0:
            return True
        return near_track(x, y, clear) or in_lot(x, y, 1.0)
    placed = tries = 0
    edge_pts = []
    while placed < 1100 and tries < 30000:
        tries += 1
        x, y = random.uniform(-165, 205), random.uniform(-205, 60)
        if not forest_zone(x, y) or blocked(x, y):
            continue
        edge = min(abs(x + 17), abs(y + 56)) if x < 33 else abs(y + 14)
        if random.random() > 0.35 + 0.65 * math.exp(-edge / 45.0):
            continue   # denser along the edges you see, thinner deep inside
        r = random.random()
        if 34 < x < 84:      # the younger mixed belt
            card(random.choice(("fir_b", "fir_c", "pine_b")), x, y, random.uniform(0.5, 0.85))
        elif r < 0.7:
            card(random.choice(("pine_a", "pine_b")), x, y, random.uniform(0.85, 1.2))
        else:
            card(random.choice(("fir_a", "fir_b", "fir_c")), x, y, random.uniform(0.8, 1.15))
        if edge < 12:
            edge_pts.append((x, y))
        placed += 1
    # ferns and deadwood along the forest edges
    for x, y in edge_pts:
        for _ in range(random.randint(1, 3)):
            fx, fy = x + random.uniform(-3, 3), y + random.uniform(-3, 3)
            if forest_zone(fx, fy) and not blocked(fx, fy, 2.0):
                card("fern", fx, fy, random.uniform(1.0, 1.6))
    deadwood([p for p in random.sample(edge_pts, min(18, len(edge_pts)))])
    # young pines / firs in the meadow south and between plot and forest
    for _ in range(260):
        x, y = random.uniform(-40, 110), random.uniform(38, 150)
        if random.random() < 0.3:
            x, y = random.uniform(-16, -9), random.uniform(-20, 40)
        if blocked(x, y, 3.0):
            continue
        for _k in range(random.randint(1, 4)):
            card(random.choice(("pine_sap", "fir_sap")), x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5), random.uniform(0.8, 2.6))
    # meadow grass clumps around the plot and the tracks
    for _ in range(2600):
        x, y = random.uniform(-40, 80), random.uniform(-60, 80)
        if plot_dist(x, y) < 0.5 or near_track(x, y, 2.3) or in_lot(x, y) or forest_zone(x, y):
            continue
        card(random.choice(("grass", "grass_b")), x, y, random.uniform(2.4, 3.8))
    for v in veg.values():
        v.bm.free()

# ---------------- checks ----------------
SOLID_SKIP = ("Igliwie", "Liscie", "Liscie_krzew", "Trawa_ozdobna", "Lawenda", "Szklo_none")

def solid_bvh(bounds=None):
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    for o in COL.objects:
        if o.type != "MESH" or any(m and m.name in SOLID_SKIP for m in o.data.materials):
            continue
        if "openAngle" in o or (o.parent and "openAngle" in o.parent):
            continue      # doors are opened in-game (E / tap)
        if bounds:
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            if max(v.x for v in bb) < bounds[0] or min(v.x for v in bb) > bounds[1] or \
               max(-v.y for v in bb) < bounds[2] or min(-v.y for v in bb) > bounds[3]:
                continue
        tmp = o.data.copy(); tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    return BVHTree.FromBMesh(bm)

def check_walk():
    """flood-fill the house at 10 cm from the front podest with a 0.28 m body (probe heights 0.5-1.75 m
    above the floor) and list every room whose centre it cannot reach"""
    B = (-1.0, 20.0, -1.0, 23.0)
    bvh = solid_bvh(B)
    st, r = 0.1, 0.28
    nx_, ny_ = int((B[1] - B[0]) / st), int((B[3] - B[2]) / st)
    def free(i, j):
        x, y = B[0] + i * st, B[2] + j * st
        for dz in (0.5, 1.0, 1.45):      # the in-game probes: knee to shoulder (door heads stay clear)
            loc, nrm, idx, dist = bvh.find_nearest(Vector((x, -y, FFL + dz)), r)
            if loc is not None:
                return False
        return True
    start = (int((9.35 - B[0]) / st), int((17.5 - B[2]) / st))
    seen = {start}; q = [start]
    while q:
        i, j = q.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if 0 <= n[0] < nx_ and 0 <= n[1] < ny_ and n not in seen and free(*n):
                seen.add(n); q.append(n)
    bad = []
    for o in COL.objects:
        if o.name.startswith("Podloga_"):
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            cx = sum(v.x for v in bb) / 8; cy = -sum(v.y for v in bb) / 8
            ij = (int(round((cx - B[0]) / st)), int(round((cy - B[2]) / st)))
            near = any((ij[0] + a, ij[1] + b) in seen for a in range(-4, 5) for b in range(-4, 5))
            if not near:
                bad.append(o.name)
    print("WALK", "all rooms reachable" if not bad else "UNREACHABLE: " + ", ".join(bad), f"({len(seen)} cells)")

DBG = {}
def check_coplanar():
    """same-facing faces of different objects lying in one plane and overlapping = z-fighting"""
    bpy.context.view_layer.update()     # copies placed by location only need fresh world matrices
    Q = 0.002
    buckets = {}
    names = []
    for oi, o in enumerate(COL.objects):
        names.append(o.name)
        if o.type != "MESH" or o.name.startswith(("Teren", "Kolizja", "Trawa_laka", "Drzewa", "Swierki", "Ogrod_", "Krzewy")):
            continue
        mw = o.matrix_world; rot = mw.to_3x3()
        for p in o.data.polygons:
            if p.area < 1e-4:
                continue
            n = (rot @ p.normal).normalized(); c = mw @ p.center
            if n.z < -0.9 and c.z < ground(c.x, -c.y) + 0.05:
                continue        # buried bottoms are never seen
            d = n.dot(c)
            key = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d / Q))
            vs = [mw @ o.data.vertices[v].co for v in p.vertices]
            buckets.setdefault(key, []).append((oi, vs, n))
    pairs = {}
    for key, lst in buckets.items():
        cand = lst + buckets.get(key[:3] + (key[3] + 1,), [])
        if len(cand) < 2:
            continue
        n = lst[0][2]
        a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
        u = n.cross(a).normalized(); w = n.cross(u)
        bb = [(min(v.dot(u) for v in vs), max(v.dot(u) for v in vs), min(v.dot(w) for v in vs), max(v.dot(w) for v in vs)) for _, vs, _ in cand]
        for i in range(len(lst)):
            for j in range(i + 1, len(cand)):
                if cand[i][0] == cand[j][0]:
                    continue
                A, Bb = bb[i], bb[j]
                ox = min(A[1], Bb[1]) - max(A[0], Bb[0]); oy = min(A[3], Bb[3]) - max(A[2], Bb[2])
                if ox > 0.01 and oy > 0.01:
                    k = tuple(sorted((names[cand[i][0]], names[cand[j][0]])))
                    if k not in pairs:
                        DBG[k] = (tuple(round(c, 2) for c in n), round(key[3] * Q, 3), [tuple(round(c, 2) for c in v) for v in cand[i][1][:3]], [tuple(round(c, 2) for c in v) for v in cand[j][1][:3]])
                    pairs[k] = pairs.get(k, 0.0) + ox * oy
    top = sorted(pairs.items(), key=lambda kv: -kv[1])
    print("COPLANAR", len(top), "pairs")
    for (a, b), area in top[:60]:
        print(f"  {area:7.3f}  {a} ~ {b}   {DBG.get((a, b), '')}")

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
    neighbourhood()      # registers neighbour lots before the plot's garden scatter
    plot()
    build_cards()
    for o in COL.objects:
        if o.type == "MESH" and not o.get("keep_uv"):
            planar_uv(o, rot=any(m and m.name == "Deski_pionowe" for m in o.data.materials))
    check_walk()
    check_coplanar()
    for o in COL.objects:
        cols = o.data.color_attributes if o.type == "MESH" else []
        if "Col" in cols:     # our layer must be the only (and active) one: it becomes COLOR_0
            for a in [a for a in cols if a.name != "Col"]:
                cols.remove(a)
            cols.active_color = cols["Col"]
            cols.render_color_index = 0
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                              export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_extras=True)
    print("EXPORTED", OUT, len(COL.objects), "objects")

build()
