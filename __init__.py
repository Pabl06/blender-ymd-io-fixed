import bpy
from .operators import *

bl_info = {
    "name": "ezPuniImporter_1.3.2_UNFINISHED_BETA_BUILD",
    "author": "hina, pabl06 & Math_kk",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export > ez",
    "description": "Import Yo-kai Watch Puni Puni's character models, Crank-a-kai models & Chibi Map models.",
}

def draw_menu_import(self, context):
    bl_label = "Puni"
    bl_idname = "TOPBAR_MT_file_Puni_import"
    self.layout.operator(ImportEZ.bl_idname, text="YWPP Models (.ez)")    

def register():
    bpy.utils.register_class(ImportEZ)
    bpy.types.TOPBAR_MT_file_import.append(draw_menu_import)

def unregister():
    bpy.utils.unregister_class(ImportEZ)
    bpy.types.TOPBAR_MT_file_import.remove(draw_menu_import)

if __name__ == "__main__":
    register()