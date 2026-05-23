import math
import os
import pathlib
import struct
from zipfile import ZipFile
import bmesh
import bpy
import json
from Crypto.Cipher import AES

from mathutils import Matrix,Vector,Quaternion

versions = [
    20158017,
    20160310,
    20181101,
    20250501
]


print("get")

def write_obj(objects, output_path):
    """
    Writes mesh data to .obj files based on the provided objects dictionary.

    Args:
    - objects (dict): Dictionary containing object and mesh data.
    - output_path (str): Path to the directory where the .obj files will be written.
    """
    
    for object_name, meshes in objects.items():
        for mesh_name, mesh_data in meshes.items():
            file_name = f"{output_path}/{object_name}_{mesh_name}.obj"
            
            # Extract the directory from the file path
            directory = os.path.dirname(file_name)  
            
            # If the directory does not exist, create it
            if not os.path.exists(directory):
                os.makedirs(directory)    
            
            positions = mesh_data["positions"]
            uvs = mesh_data["uvs"]
            normals = mesh_data["normals"]
            faces = mesh_data["faces"]
            
            with open(file_name, 'w', encoding='utf-8') as obj_file:
                for position in positions:
                    obj_file.write("v %f %f %f\n" % (position[0], position[1], position[2]))
                for uv in uvs:
                    obj_file.write("vt %f %f\n" % (uv[0], uv[1]))
                for normal in normals:
                    obj_file.write("vn %f %f %f\n" % (normal[0], normal[1], normal[2])) 

                for face in faces:
                    obj_file.write("f %i/%i/%i %i/%i/%i %i/%i/%i\n" % (face[0]+1, face[0]+1, face[0]+1, face[1]+1, face[1]+1, face[1]+1, face[2]+1, face[2]+1, face[2]+1)) 

def get_geometries(data,a_mesh_length):
    """
    Extracts mesh geometries from binary data.

    Args:
    - data (io.BufferedReader): Binary data stream.

    Returns:
    Tuple containing positions, uvs, normals, and faces.
    """
    positions = []
    uvs = []
    normals = []
    faces = []
    face_groups_idx = []

# Get mesh data
    # Fixed by @pabl_06
    mesh_length = struct.unpack('i', data.read(4))[0]
    if mesh_length > 0:
        for i in range(mesh_length):
            positions.append(list(struct.unpack("<3f", data.read(12))))

            if a_mesh_length < 32:
                # Map vertex format: xyz(12) + uv(8), no normals
                normals.append([0.0, 0.0, 1.0])
                uvs.append(list(struct.unpack("<2f", data.read(8))))
                if a_mesh_length > 20:
                    data.read(a_mesh_length - 20)
            elif a_mesh_length == 48:
                normals.append(list(struct.unpack("<3f", data.read(12))))
                data.read(16)
                uvs.append(list(struct.unpack("<2f", data.read(8))))
            else:
                normals.append(list(struct.unpack("<3f", data.read(12))))
                uvs.append(list(struct.unpack("<2f", data.read(8))))
                if a_mesh_length > 32:
                    data.read(a_mesh_length - 32)

        faces_count = struct.unpack('i', data.read(4))[0]
        for i in range(0, faces_count, 3):
            faces.append([i, i+1, i+2])

        for i in range(faces_count):
            face_groups_idx.append(list(struct.unpack("<i", data.read(4)))[0])

        return positions, uvs, normals, faces, face_groups_idx

patterns = ["geometries", "skin", "sikn", "geom"]
key = b'\x2a\xb5\x11\xf4\x77\x97\x7d\x25\xcf\x6f\x7a\x8a\xe0\x49\xa1\x25'

def to_obj(file_path, directory, clear_scene=True):
    """
    Reads an EZ file, extracts mesh data, and writes .obj files.

    Args:
    - file_path (str): Path to the input EZ file.

    Returns:
    True if successful, False otherwise.
    """
    
    root = {}

    bones = {}

    bone_names = []

    objects = {}
    can_be_opened = False
    
    geometrie_offset = 0   
    file_name = os.path.basename(file_path).split(".")[0].strip()

    parent_name = ""

    animations = {}

    mesh_names = {}

    aura = {}
    
    with open(file_path, 'rb') as file:
        ver = struct.unpack("<i",  file.read(4))[0]
        file.seek(0)
        # Read the first 600 bytes of the file (crank-a-kai ymds can have the pattern further in)
        data = file.read(600)

        for pattern in patterns:
            # Find all occurrences of the text in the data
            positions = [pos for pos in range(len(data)) if data.startswith(pattern.encode(), pos)]
            
            if positions:
                geometrie_offset = positions[0] - 8
                can_be_opened = True
                break
        
        print(can_be_opened)
        
             
        if can_be_opened:
            file.seek(geometrie_offset)
            meshes_count = struct.unpack("<i", file.read(4))[0]

            for i in range(meshes_count):
                a_mesh_length = 0
                mesh_name = "unnamed_mesh_" + str(i)
                mesh_lentgh = struct.unpack("<i", file.read(4))[0]
                
                if mesh_lentgh == 1:
                    file.read(4)
                    object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                    a_mesh_length = struct.unpack("<i", file.read(4))[0]
                else:
                    mesh_name = file.read(mesh_lentgh).decode()
                    loop_count = struct.unpack("<i", file.read(4))[0]
                    if loop_count == 1:
                        file.read(8)
                        object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                        a_mesh_length = struct.unpack("<i", file.read(4))[0]
                    else:
                        for i in range(loop_count-1):
                            file.read(8)
                            sub_object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                            a_mesh_length = struct.unpack("<i", file.read(4))[0]
                            sub_result = get_geometries(file, a_mesh_length)
                            if sub_result is not None:
                                sub_pos, sub_uvs, sub_normals, sub_faces, sub_fg = sub_result
                                if sub_object_name not in objects:
                                    objects[sub_object_name] = {}
                                if mesh_name not in objects[sub_object_name]:
                                    objects[sub_object_name][mesh_name] = {}
                                objects[sub_object_name][mesh_name].setdefault("positions", []).extend(sub_pos)
                                objects[sub_object_name][mesh_name].setdefault("uvs", []).extend(sub_uvs)
                                objects[sub_object_name][mesh_name].setdefault("normals", []).extend(sub_normals)
                                objects[sub_object_name][mesh_name].setdefault("faces", []).extend(sub_faces)
                                objects[sub_object_name][mesh_name].setdefault("face_groups_idx", []).extend(sub_fg)
                                objects[sub_object_name][mesh_name]["bone_names"] = []
                                objects[sub_object_name][mesh_name]["face_groups"] = []
                        file.read(8)
                        object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                        a_mesh_length = struct.unpack("<i", file.read(4))[0]
                    
                positions, uvs, normals, faces, face_groups_idx = get_geometries(file,a_mesh_length)
                
                if object_name not in objects:
                    objects[object_name] = {}

                if mesh_name not in objects[object_name]:
                    objects[object_name][mesh_name] = {}

                objects[object_name][mesh_name].setdefault("positions", []).extend(positions)
                objects[object_name][mesh_name].setdefault("uvs", []).extend(uvs)
                objects[object_name][mesh_name].setdefault("normals", []).extend(normals)
                objects[object_name][mesh_name].setdefault("faces", []).extend(faces)
                objects[object_name][mesh_name].setdefault("face_groups_idx", []).extend(face_groups_idx)
                objects[object_name][mesh_name]["bone_names"] = []
                objects[object_name][mesh_name]["face_groups"] = []

                

            for i in range(struct.unpack("<i", file.read(4))[0]):
                object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                # object_nameの座標があるか確認（仮）
                tmp = file.tell()
                bone_length = struct.unpack("<i", file.read(4))[0]
                if(bone_length > 100):
                    file.seek(tmp)
                    file.read(64)
                    bone_length = struct.unpack("<i", file.read(4))[0]
                # object_name here may be a geometry block name (e.g. "geometries_3") rather
                # than an object name. Collect ALL objects that contain it as a mesh key.
                affected = [(pname, mname)
                            for pname, meshes in objects.items()
                            for mname in meshes
                            if mname == object_name or pname == object_name]

                # Read bone names and matrices once
                skin_bone_names = []
                for j in range(bone_length):
                    bone_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                    skin_bone_names.append(bone_name)
                    bone = list(struct.unpack("<%df" % 16, file.read(64)))
                    rotation_matrix = Matrix([
                        [bone[0],bone[1],bone[2],bone[3]],
                        [bone[4],bone[5],bone[6],bone[7]],
                        [bone[8],bone[9],bone[10],bone[11]],
                        [bone[12],bone[13],bone[14],bone[15]]
                    ])
                    bones[bone_name] = {"matrix": rotation_matrix}

                # Read face groups once
                skin_face_groups = []
                for j in range(struct.unpack("<i", file.read(4))[0]):
                    tmp = {"bone_idx": [], "weight": []}
                    for k in range(struct.unpack("<i", file.read(4))[0]):
                        tmp["bone_idx"].append(struct.unpack("<i", file.read(4))[0])
                        tmp["weight"].append(struct.unpack("<f", file.read(4))[0])
                    skin_face_groups.append(tmp)

                # Apply to every object that shares this geometry block
                for pname, mname in affected:
                    objects[pname][mname]["bone_names"] = skin_bone_names
                    objects[pname][mname]["face_groups"] = skin_face_groups

            for i in range(struct.unpack("<i", file.read(4))[0]): # bones
                bone_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                next_bone_name_length = struct.unpack("<i", file.read(4))[0]
                if next_bone_name_length != 0:
                    next_bone_name = file.read(next_bone_name_length).decode()
                else:
                    next_bone_name = None

                has_mesh_ref = struct.unpack("<i", file.read(4))[0]
                if has_mesh_ref != 0:
                    geom_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                else:
                    geom_name = None
                list(struct.unpack("<%df" % 10, file.read(40)))

                # Bones with empty names are "proxy" nodes — they exist only to attach
                # a mesh to the parent bone. Resolve them to the parent bone name.
                if not bone_name:
                    # Use parent bone as the resolved name for mesh binding
                    resolved_bone = next_bone_name if next_bone_name else None
                    if geom_name and resolved_bone:
                        mesh_names[geom_name] = resolved_bone
                    # Do NOT add empty-named bones to bone_names or root
                    continue

                bone_names.append(bone_name)

                if next_bone_name:
                    tmp = root
                    bone_path = find_key(root, next_bone_name)
                    for j in (bone_path or [next_bone_name]):
                        tmp.setdefault(j, {})
                        tmp = tmp[j]
                    tmp[bone_name] = {}
                else:
                    root[bone_name] = {}

                if geom_name:
                    mesh_names[geom_name] = bone_name

            for i in range(struct.unpack("<i", file.read(4))[0]):
                animation_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                file.read(4)
                animations[animation_name] = {}
                for j in range(struct.unpack("<i", file.read(4))[0]):
                    bone_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                    animations[animation_name][bone_name] = []
                    # animation_length must be re-detected independently for each bone
                    animation_length = 12
                    for k in range(struct.unpack("<i", file.read(4))[0]):
                        animations[animation_name][bone_name].append({
                            "time":struct.unpack("<f", file.read(4))[0],
                            "scale":list(struct.unpack("<%df" % 3, file.read(12))),
                            "rotation":list(struct.unpack("<%df" % 4, file.read(16))),
                            "location":list(struct.unpack("<%df" % 3, file.read(12))),
                        })
                        file.read(4)
                        # 長さ確認（仮）: detect extra floats per frame by probing the
                        # gap between frame 0 and frame 1 timestamps.
                        if k == 0:
                            tmp = file.tell()
                            time = animations[animation_name][bone_name][0]["time"]
                            flag = True
                            animation_length = 12
                            while flag:
                                _time =struct.unpack("<f", file.read(4))[0]
                                if(_time - time < 0.04 and _time - time > 0.03):
                                    flag = False
                                else:
                                    animation_length = animation_length + 1
                            file.seek(tmp)
                        (list(struct.unpack("<%df" % (animation_length-12), file.read((animation_length-12)*4))))
                file.read(4)

            # --- Rigid prop fix ---
            # Objects with no skin block (e.g. accessories on a separate geometry block)
            # should be rigidly bound to the bone that mesh_names maps their geometry
            # block to. Give every vertex weight 1.0 on that one bone.
            for pname, meshes in objects.items():
                for mname, mdata in meshes.items():
                    if not mdata["bone_names"]:
                        target_bone = mesh_names.get(mname)
                        # target_bone may be empty string if the file had empty-named proxy
                        # bones that weren't resolved; fall back to None in that case.
                        if not target_bone:
                            target_bone = None
                        if target_bone and target_bone in bone_names:
                            vert_count = len(mdata["positions"])
                            mdata["bone_names"] = [target_bone]
                            mdata["face_groups"] = [{"bone_idx": [0], "weight": [1.0]}]
                            mdata["face_groups_idx"] = [0] * vert_count

            blender(root,bone_names,bones,objects,animations,mesh_names,directory,aura,ver,clear_scene=clear_scene)
            # write_obj(objects, os.path.dirname(file_path) + "/" + file_name + "/")
            return True
        else:
            return False

def load_aura(file_path):
    root = {}
    object_names = []
    animation_length = 0
    animations = {}
    animations2 = {}
    positions = {}
    faces = {}
    mesh_names = {}

    with open(file_path, 'rb') as file:
        v = struct.unpack("<i",  file.read(4))[0]
        # material
        for i in range(struct.unpack("<i", file.read(4))[0]):
            mesh_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            if v==20181101:
                material_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            
            if struct.unpack("<i", file.read(4))[0] == 1:
                pass
            else:
                file.read(struct.unpack("<i", file.read(4))[0]).decode()
            tex_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            loop_count = struct.unpack("<i", file.read(4))[0]
            for j in range(loop_count):
                file.read(4)
                key = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                value = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            blender = False
            if blender:
                mat = bpy.data.materials.new(name=i.stem)
                mat.use_nodes=True 
                principled_BSDF = mat.node_tree.nodes[0]

        # shapes
        for i in range(struct.unpack("<i", file.read(4))[0]):
            shape_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            positions[shape_name] = []
            faces[shape_name] = []
            file.read(12)
            mat_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            file.read(4)
            count = struct.unpack("<i", file.read(4))[0]
            for j in range(count):
                positions[shape_name].append(list(struct.unpack("<%df" % 3, file.read(3*4))))
                (list(struct.unpack("<%df" % 9, file.read(9*4))))
            for j in range(count):
                (struct.unpack("<i", file.read(4)))
            file.read(4)

            for j in range(0,count,3):
                faces[shape_name].append([j,j+1,j+2])

        
        #structure
        file.read(4)
        for i in range(struct.unpack("<i", file.read(4))[0]): 
            object_name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            object_names.append(object_name)
            next_bone_name_length = struct.unpack("<i", file.read(4))[0]
            if next_bone_name_length != 0:
                next_bone_name = file.read(next_bone_name_length).decode()

                tmp = root
                bone_path = find_key(root, next_bone_name)
                for j in (bone_path or [next_bone_name]):
                    tmp.setdefault(j, {})
                    tmp = tmp[j]
                tmp[object_name] = {}
                if struct.unpack("<i", file.read(4))[0]==0:
                    list(struct.unpack("<%df" % 10, file.read(40)))
                else:
                    mesh_names[object_name] = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                    list(struct.unpack("<%df" % 10, file.read(40)))
                    pass
            else:
                root[object_name] = {}
                if struct.unpack("<i", file.read(4))[0]==0:
                    list(struct.unpack("<%df" % 10, file.read(40)))
                else:
                    mesh_names[object_name] = file.read(struct.unpack("<i", file.read(4))[0]).decode()
                    list(struct.unpack("<%df" % 10, file.read(40)))
                    pass
        file.read(4)

        # animation
        file.read(struct.unpack("<i", file.read(4))[0]).decode()
        file.read(4)
        for i in range(struct.unpack("<i", file.read(4))[0]):
            name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            animations[name] = []
            for j in range(struct.unpack("<i", file.read(4))[0]):   
                if j == 0:
                    tmp = file.tell()
                    time = struct.unpack("<f", file.read(4))[0]
                    file.read(44)
                    flag = True
                    animation_length = 12
                    while flag:
                        _time =struct.unpack("<f", file.read(4))[0]
                        if(_time - time < 0.04 and _time - time > 0.03):
                            flag = False
                        else:
                            animation_length = animation_length + 1
                    file.seek(tmp)

                animations[name].append({
                    "time":struct.unpack("<f", file.read(4))[0],
                    "scale":list(struct.unpack("<%df" % 3, file.read(12))),
                    "rotation":list(struct.unpack("<%df" % 4, file.read(16))),
                    "location":list(struct.unpack("<%df" % 3, file.read(12))),
                })

                (list(struct.unpack("<%df" % (animation_length-11), file.read((animation_length-11)*4))))
        # animation???
        for i in range(struct.unpack("<i", file.read(4))[0]):
            name = file.read(struct.unpack("<i", file.read(4))[0]).decode()
            for j in range(struct.unpack("<i", file.read(4))[0]):   
                (list(struct.unpack("<%df" % 9, file.read(36))))
        

        return positions, faces, root, object_names, mesh_names
        # for k,v in positions.items():
        #     n_mesh_name = k
        #     mesh = bpy.data.meshes.new(n_mesh_name)
        #     obj = bpy.data.objects.new(n_mesh_name,mesh)
        #     mesh.from_pydata(v,[],faces[k])
        #     mesh.update()

        #     bpy.context.collection.objects.link(obj)




def find_key(d, target):
    """
    辞書 d の中から特定の要素 target の位置を探します。
    target が見つかった場合、その位置をリストで返します。
    見つからない場合は None を返します。
    """
    def dfs(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == target:
                    return path + [key]
                result = dfs(value, path + [key])
                if result:
                    return result
        return None

    return dfs(d, [])

def blender(root,bone_names,bones,objects,animations,mesh_names,directory,aura,ver,clear_scene=True):

    tex_list = list(pathlib.Path(directory).glob('*.png'))

    if clear_scene:
        for item in bpy.data.objects:
            bpy.data.objects.remove(item)

        for item in bpy.data.meshes:
            bpy.data.meshes.remove(item)

        for item in bpy.data.materials:
            bpy.data.materials.remove(item)

        for item in bpy.data.actions:
            bpy.data.actions.remove(item)

        for item in bpy.data.images:
            bpy.data.images.remove(item)
    
    for i in tex_list:
        bpy.data.images.load(str(i))
        mat = bpy.data.materials.new(name=i.stem)
        mat.use_nodes=True 
        principled_BSDF = mat.node_tree.nodes[0]

        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = bpy.data.images[i.name]

        if bpy.data.images[i.name].alpha_mode != "NONE":
            principled_BSDF.inputs["Alpha"].default_value = 1.0
        
        mat.node_tree.links.new(tex_node.outputs[0], principled_BSDF.inputs[0])

    # Pick the first non-empty key in root as the armature name.
    # Some YMD files have empty-named root nodes (proxy bones); skip them.
    valid_root_keys = [k for k in root.keys() if k.strip()]
    armature_name = valid_root_keys[0] if valid_root_keys else "Armature"

    bpy.ops.object.add(radius=1.0, type='ARMATURE', enter_editmode=False, align='WORLD', location=(0.0, 0.0, 0.0), rotation=(math.pi/2, 0.0, 0.0), scale=(0.0, 0.0, 0.0))
    armature_obj = bpy.context.active_object
    armature_obj.name = armature_name

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.context.view_layer.objects.active = armature_obj
    for i in bone_names:
        bone = bpy.data.objects[armature_name].data.edit_bones.new(i)
        bone.head.x = 0
        bone.head.y = -1
        bone.head.z = 0
        bone.tail.x = 0
        bone.tail.y = 0
        bone.tail.z = 0
        isDefinedBone = i in bones
        if isDefinedBone == True:
            try:
                bone.matrix = bones[i]["matrix"].inverted()
            except:
                bone.matrix = bones[i]["matrix"]
        else:
            bone.matrix = Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
        
        bone_path = find_key(root, i)
        if bone_path is None or len(bone_path) == 1:
            pass  # root-level bone or not found in hierarchy — no parent
        else:
            parent_name = bone_path[-2]
            # Guard against empty-named parent keys that may remain in root
            if parent_name and parent_name in bpy.data.objects[armature_name].data.edit_bones:
                bone.parent = bpy.data.objects[armature_name].data.edit_bones[parent_name]
    bpy.data.objects[armature_name].data.name = armature_name
        

    # binding
    for object_name, meshes in objects.items():
        for mesh_name, mesh_data in meshes.items():
            if True:
                n_mesh_name = mesh_names.get(mesh_name, mesh_name)
                if not n_mesh_name:
                    n_mesh_name = mesh_name
                mesh = bpy.data.meshes.new(n_mesh_name)
                obj = bpy.data.objects.new(n_mesh_name,mesh)
                mesh.from_pydata(mesh_data["positions"],[],mesh_data["faces"])
                mesh.update()

                bpy.context.collection.objects.link(obj)

                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                
                uv = bpy.context.active_object.data.uv_layers.new(name='UVmap')

                for loop in bpy.context.active_object.data.loops:
                    print(ver)
                    if ver >= 20181101:
                        uv.data[loop.index].uv = tuple([objects[object_name][mesh_name]["uvs"][loop.index][0],objects[object_name][mesh_name]["uvs"][loop.index][1]])
                    else:
                        uv.data[loop.index].uv = tuple([objects[object_name][mesh_name]["uvs"][loop.index][0],1.0-objects[object_name][mesh_name]["uvs"][loop.index][1]])

                
                obj.parent = bpy.data.objects[armature_name]

                group_vertices = []
                for i in enumerate(objects[object_name][mesh_name]["bone_names"]):
                    group_vertices.append([])

                for idx,i in enumerate(objects[object_name][mesh_name]["face_groups_idx"]):
                    if len(objects[object_name][mesh_name]["face_groups"]) > 0:
                        for jdx,j in enumerate(objects[object_name][mesh_name]["face_groups"][i]["bone_idx"]):
                            if objects[object_name][mesh_name]["face_groups"][i]["weight"][jdx] != 0:
                                group_vertices[j].append([idx,objects[object_name][mesh_name]["face_groups"][i]["weight"][jdx]])

                
                for idx,i in enumerate(objects[object_name][mesh_name]["bone_names"]):
                    group = obj.vertex_groups.new(name=i)
                    for jdx,j in enumerate(group_vertices[idx]):
                        group.add([j[0]], j[1], 'ADD')
                
                obj.modifiers.new("Armature","ARMATURE")
                obj.modifiers["Armature"].object = bpy.data.objects[armature_name]

                if object_name[-5:-3] in [i[-2:] for i in bpy.data.materials.keys()] and object_name[-2:] == "01":
                    obj.data.materials.append(bpy.data.materials[[i for i in bpy.data.materials.keys() if i[-2:] == object_name[-5:-3]][0]])
                else:
                    if os.path.exists(f"{directory}/modelInfo.txt"):
                        with open(f"{directory}/modelInfo.txt") as f:
                            json_data = json.load(f)
                            if "material" in json_data.keys():
                                result = filter(lambda item: item["name"] == object_name, json_data["material"])
                                if len(list(result)) > 0:
                                    try:
                                        obj.data.materials.append(bpy.data.materials[list(result)[0]["texture"][0]])
                                    except:
                                        obj.data.materials.append(bpy.data.materials[0])
                                        print("no texture source found. Auto attach to mesh")
                                else:
                                    obj.data.materials.append(bpy.data.materials[0])
                                    print("no texture source found. Auto attach to mesh")
                            else:
                                obj.data.materials.append(bpy.data.materials[0])
                                print("no texture source found. Auto attach to mesh")
                    else:
                        obj.data.materials.append(bpy.data.materials[0])
                        print("no texture source found. Auto attach to mesh")

    # animations
    scene = bpy.context.scene
    armature = bpy.data.objects[armature_name].data
    
    # Switch to Pose Mode
    bpy.context.view_layer.objects.active = bpy.data.objects[armature_name]
    bpy.ops.object.mode_set(mode='POSE')
    
    if bpy.data.objects[armature_name].animation_data:
        bpy.data.objects[armature_name].animation_data_clear()
    
    bpy.data.objects[armature_name].animation_data_create()
    for a_name,anim in animations.items():
        frame_count = len(animations[a_name][list(animations[a_name].keys())[0]])

        action = bpy.data.actions.new(name=a_name)
        bpy.data.objects[armature_name].animation_data.action = action
        
        scene.frame_start = 0
        scene.frame_end = frame_count
        
        bpy.context.scene.frame_set(0)
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.transforms_clear()   

        for frame in range(frame_count):
            for b_name,bone in animations[a_name].items():
                pose_bone = bpy.data.objects[armature_name].pose.bones[b_name]

                location = calculate_transformed_location(pose_bone,Vector([bone[frame]["location"][0],bone[frame]["location"][1],bone[frame]["location"][2]]))
                for i in range(3):
                    fcurve = action.fcurves.find("pose.bones[\"{}\"].location".format(pose_bone.name), index=i)
                    if not fcurve:
                        fcurve = action.fcurves.new(data_path="pose.bones[\"{}\"].location".format(pose_bone.name), index=i)
                    fcurve.keyframe_points.insert(frame, location[i])

                pose_bone.rotation_mode = 'QUATERNION'

                rotation = calculate_transformed_rotation(pose_bone,Vector([bone[frame]["rotation"][3],bone[frame]["rotation"][0],bone[frame]["rotation"][1],bone[frame]["rotation"][2]]))
                parent = pose_bone.parent
                while parent and not parent.bone.use_deform:
                    parent = parent.parent
                for i in range(4):
                    fcurve = action.fcurves.find("pose.bones[\"{}\"].rotation_quaternion".format(pose_bone.name), index=i)
                    if not fcurve:
                        fcurve = action.fcurves.new(data_path="pose.bones[\"{}\"].rotation_quaternion".format(pose_bone.name), index=i)
                    fcurve.keyframe_points.insert(frame, rotation[i])

                scale = calculate_transformed_scale(pose_bone,Vector([bone[frame]["scale"][0],bone[frame]["scale"][1],bone[frame]["scale"][2]]))
                for i in range(3):
                    fcurve = action.fcurves.find("pose.bones[\"{}\"].scale".format(pose_bone.name), index=i)
                    if not fcurve:
                        fcurve = action.fcurves.new(data_path="pose.bones[\"{}\"].scale".format(pose_bone.name), index=i)
                    fcurve.keyframe_points.insert(frame, scale[i])

    print("succeed")


"""
thanks to @Tiniifan
https://github.com/Tiniifan/Level-5-blender-addon/blob/e331fb7a2bad17eb486a1530e08c8872bd99e784/operators/fileio_xmtn.py
"""
def calculate_transformed_location(pose_bone, location):
    parent = pose_bone.parent
    while parent and not parent.bone.use_deform:
        parent = parent.parent

    pose_matrix = pose_bone.matrix
    if parent:
        parent_matrix = parent.matrix
        pose_matrix = parent_matrix.inverted() @ pose_matrix

    return pose_matrix.inverted() @ location
    
def calculate_transformed_rotation(pose_bone, rotation):
    parent = pose_bone.parent
    while parent and not parent.bone.use_deform:
        parent = parent.parent

    pose_matrix = pose_bone.matrix
    if parent:
        parent_matrix = parent.matrix
        pose_matrix = parent_matrix.inverted() @ pose_matrix

    # Create a Quaternion directly from Euler angles
    rotation_quaternion = Quaternion(rotation)

    # Convert quaternion rotation to Matrix
    rotation_matrix = rotation_quaternion.to_matrix().to_4x4()

    # Multiply pose matrix by rotation matrix
    transformed_matrix = pose_matrix.inverted() @ rotation_matrix

    # Extract quaternion from the result
    transformed_quaternion = transformed_matrix.to_quaternion()

    return transformed_quaternion
    
def calculate_transformed_scale(pose_bone, scale):
    parent = pose_bone.parent
    while parent and not parent.bone.use_deform:
        parent = parent.parent

    pose_matrix = pose_bone.matrix
    if parent:
        parent_matrix = parent.matrix
        pose_matrix = parent_matrix.inverted() @ pose_matrix

    # Create scale matrices for each axis
    scale_matrix_x = Matrix.Scale(scale[0], 4, (1, 0, 0))
    scale_matrix_y = Matrix.Scale(scale[1], 4, (0, 1, 0))
    scale_matrix_z = Matrix.Scale(scale[2], 4, (0, 0, 1))

    # Multiply pose matrix by scale matrices
    transformed_matrix = pose_matrix.inverted() @ (scale_matrix_x @ scale_matrix_y @ scale_matrix_z)

    # Extract scales from the result
    transformed_scale = transformed_matrix.to_scale()

    return transformed_scale

def decrypt_file(key, input_file, output_file=None, chunksize=64*1024):
    if not output_file:
        output_file = os.path.splitext(input_file)[0] + '.zip'

    filesize = os.path.getsize(input_file)

    cipher = AES.new(key, AES.MODE_CBC, b'0000000000000000')

    with open(input_file, 'rb') as infile:
        with open(output_file, 'wb') as outfile:
            while True:
                chunk = infile.read(chunksize)
                if len(chunk) == 0:
                    break
                outfile.write(cipher.decrypt(chunk))

            outfile.truncate(filesize)

# 2609010 line 169 (custom material)