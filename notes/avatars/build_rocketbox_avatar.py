"""Build the teacher avatar (src/client/react/public/avatars/rocketbox_teacher.glb).

Converts a Microsoft Rocketbox avatar (MIT, github.com/microsoft/Microsoft-Rocketbox) into a TalkingHead-ready GLB:
the 3ds Max Biped rig is rebuilt as a Ready Player Me-named skeleton (hips at 1 m, RPM bone roll), facial bones are
folded into Head, and the shipped ARKit (AK_*) and viseme (AA_VI_*) blendshapes are renamed to ARKit / Oculus names
plus the extra mouthOpen, mouthSmile, eyesClosed, eyesLookUp and eyesLookDown keys. A soft smile is baked into
the rest shape (strength set by the REST_SCALE env var, default 2.2) so the avatar looks friendly when idle.
Optional outfit step: JEANS_TINT re-dyes the jeans (sRGB hex) and SHOES_GLB swaps the boots for the sneakers of
another GLB built by this script; the jeans are run down to the ankle to meet them.

Requirements (as used to build the committed GLB):
  - Blender 5.0.1
  - Rocketbox avatar folder, e.g. Assets/Avatars/Adults/Female_Adult_14 (Export/*_facial.fbx and Textures/*.tga)
  - for the committed GLB: REST_SCALE=2.2 JEANS_TINT=6584ad SHOES_GLB=<Sports_Female_02 built by this script>
  - talkinghead-addon.py from github.com/met4citizen/TalkingHead/tree/main/blender/MPFB, in <talkinghead_dir>

Run: Blender -b --python build_rocketbox_avatar.py -- <talkinghead_dir> <avatar_dir> <out.glb>
"""
import glob
import importlib.util
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
TH_DIR, AV_DIR, OUT = args[0], args[1], args[2]
TEX = os.path.join(AV_DIR, "Textures")

bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = glob.glob(os.path.join(AV_DIR, "Export", "*_facial.fbx"))[0]
bpy.ops.import_scene.fbx(filepath=fbx, automatic_bone_orientation=False)
src = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh = next(o for o in bpy.data.objects if o.type == "MESH")

# bake the FBX unit scale / axis rotation into the data so everything is in metres, Z up
for o in (src, mesh):
    o.select_set(True)
bpy.context.view_layer.objects.active = src
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# --- Rocketbox (3ds Max Biped) -> Ready Player Me bone names -----------------------------------
MAP = {"Pelvis": "Hips", "Spine": "Spine", "Spine1": "Spine1", "Spine2": "Spine2", "Neck": "Neck", "Head": "Head",
       "LEye": "LeftEye", "REye": "RightEye"}
for s, side in (("L", "Left"), ("R", "Right")):
    MAP.update({f"{s} Clavicle": f"{side}Shoulder", f"{s} UpperArm": f"{side}Arm", f"{s} Forearm": f"{side}ForeArm",
                f"{s} Hand": f"{side}Hand", f"{s} Thigh": f"{side}UpLeg", f"{s} Calf": f"{side}Leg",
                f"{s} Foot": f"{side}Foot", f"{s} Toe0": f"{side}ToeBase"})
    for i, finger in enumerate(("Thumb", "Index", "Middle", "Ring", "Pinky")):
        for j, suffix in enumerate(("", "1", "2")):
            MAP[f"{s} Finger{i}{suffix}"] = f"{side}Hand{finger}{j + 1}"
MAP = {"Bip01 " + k: v for k, v in MAP.items()}

PARENT = {"Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2", "Head": "Neck",
          "HeadTop_End": "Head", "LeftEye": "Head", "RightEye": "Head"}
for side in ("Left", "Right"):
    PARENT.update({f"{side}Shoulder": "Spine2", f"{side}Arm": f"{side}Shoulder", f"{side}ForeArm": f"{side}Arm",
                   f"{side}Hand": f"{side}ForeArm", f"{side}UpLeg": "Hips", f"{side}Leg": f"{side}UpLeg",
                   f"{side}Foot": f"{side}Leg", f"{side}ToeBase": f"{side}Foot", f"{side}Toe_End": f"{side}ToeBase"})
    for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        PARENT[f"{side}Hand{finger}1"] = f"{side}Hand"
        for j in (2, 3, 4):
            PARENT[f"{side}Hand{finger}{j}"] = f"{side}Hand{finger}{j - 1}"

# joint positions from the source rest pose
heads = {MAP[b.name]: src.matrix_world @ b.head_local for b in src.data.bones if b.name in MAP}
src_head = src.data.bones["Bip01 Head"]
head_len = (src_head.tail_local - src_head.head_local).length
# end joints the Biped rig lacks: extend each chain by its last segment
heads["HeadTop_End"] = heads["Head"] + Vector((0, 0, max(head_len, 0.18)))
for side in ("Left", "Right"):
    for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        a, b = heads[f"{side}Hand{finger}2"], heads[f"{side}Hand{finger}3"]
        heads[f"{side}Hand{finger}4"] = b + (b - a) * 0.8
    toe, foot = heads[f"{side}ToeBase"], heads[f"{side}Foot"]
    fwd = Vector((toe.x - foot.x, toe.y - foot.y, 0)).normalized()
    heads[f"{side}Toe_End"] = toe + fwd * 0.07

CHILD = {"Hips": "Spine", "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Neck", "Neck": "Head",
         "Head": "HeadTop_End"}
for side in ("Left", "Right"):
    CHILD.update({f"{side}Shoulder": f"{side}Arm", f"{side}Arm": f"{side}ForeArm", f"{side}ForeArm": f"{side}Hand",
                  f"{side}Hand": f"{side}HandMiddle1", f"{side}UpLeg": f"{side}Leg", f"{side}Leg": f"{side}Foot",
                  f"{side}Foot": f"{side}ToeBase", f"{side}ToeBase": f"{side}Toe_End"})
    for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        for j in (1, 2, 3):
            CHILD[f"{side}Hand{finger}{j}"] = f"{side}Hand{finger}{j + 1}"

# --- build the new armature -----------------------------------------------------------------------
arm_data = bpy.data.armatures.new("Armature")
arm = bpy.data.objects.new("Armature", arm_data)
bpy.context.collection.objects.link(arm)
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
for name, h in heads.items():
    b = eb.new(name)
    b.head = h
    if name in CHILD:
        b.tail = heads[CHILD[name]]
    elif name.endswith("Eye"):
        b.tail = h + Vector((0, -0.03, 0))
    else:  # leaf bones (_End, finger tips): continue the parent's direction
        p = heads[PARENT[name]]
        d = (h - p).normalized() if (h - p).length > 1e-5 else Vector((0, 0, 1))
        b.tail = h + d * 0.02
for name, p in PARENT.items():
    eb[name].parent = eb[p]
bpy.ops.object.mode_set(mode="OBJECT")

# --- move the skin weights over: renamed groups, facial/helper bones folded into Head ----------
vg = mesh.vertex_groups
fold = {}
for g in vg:
    if g.name in MAP:
        fold[g.index] = MAP[g.name]
    elif g.name.startswith("Bip01"):
        b = src.data.bones.get(g.name)
        under_head = b is not None and "Bip01 Head" in [a.name for a in b.parent_recursive]
        fold[g.index] = "Head" if under_head else "Hips"  # facial bones are replaced by the blendshapes
print("FOLDED", sorted((g.name, fold[g.index]) for g in vg if g.name not in MAP and g.index in fold))
targets = {n: vg.new(name="_" + n) for n in set(fold.values())}
for v in mesh.data.vertices:
    acc = {}
    for ge in v.groups:
        if ge.group in fold:
            acc[fold[ge.group]] = acc.get(fold[ge.group], 0.0) + ge.weight
    for n, w in acc.items():
        targets[n].add([v.index], w, "REPLACE")
for g in list(vg):
    if not g.name.startswith("_"):
        vg.remove(g)
for g in vg:
    g.name = g.name[1:]
print("GROUPS", len(vg))

for m in list(mesh.modifiers):
    if m.type == "ARMATURE":
        mesh.modifiers.remove(m)
mw = mesh.matrix_world.copy()
mesh.parent = arm
mesh.matrix_world = mw
mod = mesh.modifiers.new("Armature", "ARMATURE")
mod.object = arm
bpy.data.objects.remove(src, do_unlink=True)
mesh.name = mesh.data.name = "Avatar"

# --- TalkingHead fixes: hips at 1 m, RPM bone roll -----------------------------------------------
spec = importlib.util.spec_from_file_location("th_addon", os.path.join(TH_DIR, "talkinghead-addon.py"))
th = importlib.util.module_from_spec(spec)
spec.loader.exec_module(th)
bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
th.scale_character([arm])
th.fix_bone_axes([arm], th.BONE_AXES_DATA_A)
bpy.ops.object.mode_set(mode="OBJECT")
for o in (arm, mesh):
    o.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# --- shape keys: ARKit + Oculus viseme names, plus the extra RPM ones --------------------------
kb = mesh.data.shape_keys.key_blocks
VIS = {"Sil": "sil", "KK": "kk"}
for k in list(kb):
    n = k.name
    if n.startswith("AK_"):
        base = n.split("_", 2)[2]
        k.name = base[0].lower() + base[1:]
    elif n.startswith("AA_VI_"):
        base = n.split("_", 3)[3]
        k.name = "viseme_" + VIS.get(base, base)
    elif n != "Basis":
        mesh.shape_key_remove(k)


def mix(name, parts):
    basis = kb["Basis"].data
    new = mesh.shape_key_add(name=name, from_mix=False)
    for i, p in enumerate(new.data):
        d = Vector()
        for src_name in parts:
            d += kb[src_name].data[i].co - basis[i].co
        p.co = basis[i].co + d


mix("mouthOpen", ["jawOpen"])
mix("mouthSmile", ["mouthSmileLeft", "mouthSmileRight"])
mix("eyesClosed", ["eyeBlinkLeft", "eyeBlinkRight"])
mix("eyesLookUp", ["eyeLookUpLeft", "eyeLookUpRight"])
mix("eyesLookDown", ["eyeLookDownLeft", "eyeLookDownRight"])
for k in kb:
    k.value = 0.0  # exported as the default morph weights; plain three.js viewers (the avatar picker) use them
print("KEYS", len(kb), [k.name for k in kb])

# --- friendly resting face: bake a soft smile into the rest shape --------------------------------
# Adding the same offset to every key (Basis included) keeps all blendshape deltas unchanged.
REST_SCALE = float(os.environ.get("REST_SCALE", "2.2"))
REST = {"mouthSmileLeft": 0.30, "mouthSmileRight": 0.30, "cheekSquintLeft": 0.15, "cheekSquintRight": 0.15,
        "eyeSquintLeft": 0.12, "eyeSquintRight": 0.12, "browOuterUpLeft": 0.10, "browOuterUpRight": 0.10}
basis = [p.co.copy() for p in kb["Basis"].data]
offset = [Vector() for _ in basis]
for name, w in REST.items():
    for i, p in enumerate(kb[name].data):
        offset[i] += (p.co - basis[i]) * w * REST_SCALE
for k in kb:
    for i, p in enumerate(k.data):
        p.co += offset[i]


# --- materials: rebuild from the Rocketbox textures -------------------------------------------
def img(stem, non_color=False):
    i = bpy.data.images.load(os.path.join(TEX, stem + ".tga"))
    if non_color:
        i.colorspace_settings.name = "Non-Color"
    return i


for m in mesh.data.materials:
    part = m.name.split("_", 1)[1]  # f002_body -> body
    prefix = m.name.split("_", 1)[0]
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = img(f"{prefix}_{part}_color")
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.0
    if part == "opacity":  # hair cards, lashes, brows
        nt.links.new(col.outputs["Alpha"], bsdf.inputs["Alpha"])
        bsdf.inputs["Roughness"].default_value = 0.7
        m.surface_render_method = "BLENDED"
        m.use_backface_culling = False
        continue
    nrm_path = os.path.join(TEX, f"{prefix}_{part}_normal.tga")
    if os.path.exists(nrm_path):
        nrm = nt.nodes.new("ShaderNodeTexImage")
        nrm.image = img(f"{prefix}_{part}_normal", True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.55 if part == "head" else 0.75

# --- outfit: lighter jeans wash, and sneakers from another Rocketbox avatar instead of boots ------
# Rocketbox avatars share one UV layout and skeleton, so the donor's shoes fit after aligning the feet.
SHOES_GLB = os.environ.get("SHOES_GLB", "")  # a GLB built by this script, e.g. from Sports_Female_02
JEANS_TINT = os.environ.get("JEANS_TINT", "")  # sRGB hex of the denim wash, e.g. "8fa9c9"


def body_islands(obj):
    """UV islands of the body material as (face indices, min z, max z).

    The Rocketbox body is one connected mesh, so garments are told apart by their UV islands: two faces are
    neighbours only if they share an edge with the same UVs on both sides.
    """
    me = obj.data
    body = next(i for i, m in enumerate(me.materials) if m.name.endswith("_body"))
    uv = me.uv_layers.active.data
    edge_faces = {}
    for p in me.polygons:
        if p.material_index != body:
            continue
        loops = list(p.loop_indices)
        for a, b in zip(loops, loops[1:] + loops[:1]):
            ends = sorted(((me.loops[a].vertex_index, tuple(round(c, 4) for c in uv[a].uv)),
                           (me.loops[b].vertex_index, tuple(round(c, 4) for c in uv[b].uv))))
            edge_faces.setdefault(tuple(ends), []).append(p.index)
    face_edges = {}
    for ek, fs in edge_faces.items():
        for f in fs:
            face_edges.setdefault(f, []).append(ek)
    seen, out = set(), []
    for p in me.polygons:
        if p.material_index != body or p.index in seen:
            continue
        stack, isl = [p.index], []
        seen.add(p.index)
        while stack:
            f = stack.pop()
            isl.append(f)
            for ek in face_edges[f]:
                for g in edge_faces[ek]:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        zs = [me.vertices[v].co.z for f in isl for v in me.polygons[f].vertices]
        out.append((isl, min(zs), max(zs)))
    return out


def uv_mask(obj, faces, w, h, grow=3):
    """Boolean (h, w) texture mask covering the UVs of the given faces."""
    mask = np.zeros((h, w), bool)
    uv = obj.data.uv_layers.active.data
    for f in faces:
        pts = [uv[li].uv * Vector((w, h)) for li in obj.data.polygons[f].loop_indices]
        for t in range(1, len(pts) - 1):
            (ax, ay), (bx, by), (cx, cy) = pts[0], pts[t], pts[t + 1]
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            x0, x1 = int(max(min(ax, bx, cx), 0)), int(min(max(ax, bx, cx) + 1, w - 1))
            y0, y1 = int(max(min(ay, by, cy), 0)), int(min(max(ay, by, cy) + 1, h - 1))
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
            l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
            mask[y0:y1 + 1, x0:x1 + 1] |= (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
    for _ in range(grow):  # cover the island borders so no dark seam is left behind
        mask = mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    return mask


if SHOES_GLB or JEANS_TINT:
    import bmesh
    import numpy as np
    islands = body_islands(mesh)
    legs = [faces for faces, z0, z1 in islands if z0 < 0.3 and z1 > 0.9]  # the two jeans legs
    boots = [f for faces, z0, z1 in islands if z1 < 0.25 for f in faces]

if JEANS_TINT:
    body_mat = next(m for m in mesh.data.materials if m.name.endswith("_body"))
    image = next(n.image for n in body_mat.node_tree.nodes if n.type == "TEX_IMAGE" and "color" in n.image.name)
    w, h = image.size
    px = np.empty(w * h * 4, np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    m = uv_mask(mesh, [f for faces in legs for f in faces], w, h)
    lum = px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    tint = np.array([int(JEANS_TINT[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    # keep the denim's own fades and seams, re-dyed to the new wash
    dyed = np.clip(tint * (lum / lum[m].mean())[..., None] ** 0.8, 0, 1)
    px[..., :3][m] = dyed[m]
    image.pixels.foreach_set(px.ravel())
    image.pack()
    print("JEANS recoloured %d px" % m.sum())

if SHOES_GLB:
    # run the jeans down to the ankle, where the boot shafts used to cover them
    leg_verts = {v for faces in legs for f in faces for v in mesh.data.polygons[f].vertices}
    z_hem = min(mesh.data.vertices[v].co.z for v in leg_verts)
    Z0, Z1 = 0.045, 0.40
    for coords in [k.data for k in kb] + [mesh.data.vertices]:
        for v in leg_verts:
            co = coords[v].co
            if co.z < Z1:
                co.z = Z0 + (co.z - z_hem) * (Z1 - Z0) / (Z1 - z_hem)
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in boots], context="FACES")
    bmesh.update_edit_mesh(mesh.data)
    bpy.ops.object.mode_set(mode="OBJECT")

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SHOES_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    d_arm = next(o for o in new if o.type == "ARMATURE")
    d_mesh = next(o for o in new if o.type == "MESH")
    d_mesh.shape_key_clear()
    d_mesh.data.transform(d_mesh.matrix_world)
    d_mesh.parent = None
    d_mesh.matrix_world.identity()
    d_mesh.modifiers.clear()
    d_mesh.data.uv_layers.active.name = mesh.data.uv_layers.active.name  # join merges UV layers by name
    keep = {f for faces, z0, z1 in body_islands(d_mesh) if z1 < 0.12 for f in faces}  # uppers + soles
    shift = {}
    for side in ("Left", "Right"):
        t = arm.matrix_world @ arm.data.bones[side + "Foot"].head_local
        d = d_arm.matrix_world @ d_arm.data.bones[side + "Foot"].head_local
        shift[side] = Vector((t.x - d.x, t.y - d.y, 0))
    sign_left = 1 if (arm.matrix_world @ arm.data.bones["LeftFoot"].head_local).x > 0 else -1
    bpy.ops.object.select_all(action="DESELECT")
    d_mesh.select_set(True)
    bpy.context.view_layer.objects.active = d_mesh
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(d_mesh.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    for v in bm.verts:
        v.co += shift["Left" if v.co.x * sign_left > 0 else "Right"]
    bmesh.update_edit_mesh(d_mesh.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    print("SHOES kept %d faces, shift L %s R %s" % (len(keep), tuple(shift["Left"]), tuple(shift["Right"])))
    for o in new:
        if o is not d_mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    d_mesh.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.join()

for p in mesh.data.polygons:
    p.use_smooth = True

hips = arm.matrix_world @ arm.pose.bones["Hips"].head
head = arm.matrix_world @ arm.pose.bones["Head"].head
print("BONES hips_z=%.3f head_z=%.3f nbones=%d verts=%d"
      % (hips.z, head.z, len(arm.data.bones), len(mesh.data.vertices)))

bpy.ops.object.select_all(action="DESELECT")
for o in (arm, mesh):
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_animations=False,
                          export_morph=True, export_skins=True, export_image_format="WEBP", export_image_quality=85,
                          export_vertex_color="NONE")  # FBX vertex colours would tint the textures in three.js
print("EXPORTED", OUT, os.path.getsize(OUT))
