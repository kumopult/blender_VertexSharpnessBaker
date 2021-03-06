# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "VertexSharpnessBaker",
    "author" : "Kumopult",
    "description" : "",
    "blender" : (2, 83, 0),
    "version" : (0, 0, 1),
    "location" : "",
    "warning" : "",
    "category" : "Generic"
}

import bpy
from numpy import dot, mean, median, average, interp

class VSB_PT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Outline"
    bl_label = "Vertex Sharpness Bake Tool"

    def draw(self, context):
        s = bpy.context.scene.kumopult_vsb
        ob = bpy.context.active_object
        layout = self.layout

        box = layout.box()
        # for p in s.inter_points:
        #     row = box.row()
        #     row.prop(p, "xp", text="", emboss=False)
        #     row.split(factor=0.25)
        #     row.prop(p, "fp", text="", slider=True)

        box.prop(s, "inter_point_0", text="0°", slider=True)
        box.prop(s, "inter_point_90", text="90°", slider=True)
        box.prop(s, "inter_point_180", text="180°", slider=True)
        box.prop(s, "inter_point_270", text="270°", slider=True)
        box.prop(s, "inter_point_360", text="360°", slider=True)
        layout.prop_search(s, "vert_group", ob, "vertex_groups")
        layout.prop(s, 'mix_mode')
        layout.operator('kumopult_vsb.bake', text='烘培', icon='NLA')


# class VSB_InterPoint(bpy.types.PropertyGroup):
#     # 暂时没时间实现这个了。。
#     xp: bpy.props.FloatProperty(min=0, max=360)
#     fp: bpy.props.FloatProperty(min=0, max=1)


class VSB_State(bpy.types.PropertyGroup):
    mix_mode: bpy.props.EnumProperty(
        name="混合模式",
        description="每个顶点以何种方式混合相邻线段的尖锐度",
        items= (("WEIGHT",  "加权", "加权平均"),
                ("MEDIAN",  "中位", "取中位数"),
                ("MAX",     "最大", "取最大值"),
                ("AVERAGE", "平均", "取平均值"),
                ("MIN",     "最小", "取最小值"),
                ("EXTREME", "极端", "取最大或最小值中更接近极端的那一侧"),)
    )

    mix_method = {
        "WEIGHT": lambda wl: average(wl, weights=list(map(lambda val: abs(val-0.5)*2+0.001, wl))),
        "MEDIAN": median,
        "MAX": max,
        "AVERAGE": mean,
        "MIN": min,
        "EXTREME": lambda wl: min(wl) if 0.5 - min(wl) > max(wl) - 0.5 else max(wl)
    }
    
    vert_group: bpy.props.StringProperty(
        name="目标顶点组",
        description="选择一个顶点组用于存储烘培的结果，以此控制实体化修改器的偏移幅度",
        default="outline_width"
    )

    # inter_points: bpy.props.CollectionProperty(type=VSB_InterPoint)

    # def init(self):
    #     for i in range(5):
    #         self.add_inter_point(360 * i / 4, 1)
    
    # def sort_points(self):
    #     return

    # def add_inter_point(self, xp, fp):
    #     p = self.inter_points.add()
    #     p.xp = xp
    #     p.fp = fp

    inter_point_0: bpy.props.FloatProperty(min=0, max=1)
    inter_point_90: bpy.props.FloatProperty(min=0, max=1)
    inter_point_180: bpy.props.FloatProperty(min=0, max=1)
    inter_point_270: bpy.props.FloatProperty(min=0, max=1)
    inter_point_360: bpy.props.FloatProperty(min=0, max=1)

    def width_map(self, x):
        xp = [0, 0.25, 0.5, 0.75, 1]
        fp = [self.inter_point_0,
             self.inter_point_90,
             self.inter_point_180,
             self.inter_point_270,
             self.inter_point_360]
        return interp(x, xp, fp)
    

class VSB_OT_Bake(bpy.types.Operator):
    bl_idname = 'kumopult_vsb.bake'
    bl_label = '烘培尖锐度'
    bl_description = '将依据每个顶点的相邻面法线计算尖锐程度并烘培进顶点组权重中'

    @classmethod
    def poll(cls, context):
        s = bpy.context.scene.kumopult_vsb
        return bpy.context.object.vertex_groups.get(s.vert_group)

    def execute(self, context):
        print("Bake!")
        s = bpy.context.scene.kumopult_vsb
        mesh = bpy.context.object.data

        mesh_points = mesh.vertices
        mesh_lines = mesh.edges
        mesh_faces = mesh.polygons

        def cal_line_weight(line, face1, face2):
            face_normal_dot = dot(face1.normal, face2.normal)
            face_normal_add = face1.normal + face2.normal
            face_line_vec = (mesh_points[line.vertices[0]].co + mesh_points[line.vertices[1]].co) - (face1.center + face2.center) 
            if dot(face_normal_add, face_line_vec) > 0:
                return (face_normal_dot - 3) *-0.25
            else:
                return (face_normal_dot + 1) * 0.25
        
        line_face = [[] for _ in range(0, len(mesh_lines))]
        # n*n,有办法优化么...
        for i,line in enumerate(mesh_lines):
            for face in mesh_faces:
                if (line.vertices[0] in face.vertices and line.vertices[1] in face.vertices):
                    line_face[i].append(face)
        
        line_weight = [0 for _ in range(0, len(mesh_lines))]

        for i, faces in enumerate(line_face):
            if len(faces) == 2:
                line_weight[i] = cal_line_weight(mesh_lines[i], faces[0], faces[1])
            else:
                line_weight[i] = 1
        
        point_weight = [0 for _ in range(0, len(mesh_points))]
        for i, weight in enumerate(point_weight):
            point_line_weight = []
            for j, line in enumerate(mesh_lines):
                if i in line.vertices:
                    point_line_weight.append(line_weight[j])
            point_weight[i] = s.mix_method[s.mix_mode](point_line_weight)
        
        point_width = s.width_map(point_weight)

        group = bpy.context.object.vertex_groups.get(s.vert_group)
        for i, width in enumerate(point_width):
            group.add([i], width, "REPLACE")

        return {"FINISHED"}

classes = (
	VSB_PT_Panel, 
    VSB_OT_Bake,
    # VSB_InterPoint,
	VSB_State,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kumopult_vsb = bpy.props.PointerProperty(type=VSB_State)
    print("hello kumopult!")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kumopult_vsb
    print("goodbye kumopult!")
