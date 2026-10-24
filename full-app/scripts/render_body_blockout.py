# SPDX-License-Identifier: GPL-2.0-or-later
"""Proportion-controlled body volumes built by Render's native Android bpy.

Stage one only: editable closed anatomical volumes, before sculpt union,
retopology, facial detail, garments or rigging. No image-to-3D/likeness claim.
"""
import math
import re
import json

DEFAULTS = dict(height_m=1.65, shoulder_width_m=.41, bust_width_m=.405,
                bust_depth_m=.34, waist_width_m=.35, waist_depth_m=.30,
                hip_width_m=.45, hip_depth_m=.34, head_height_m=.23,
                head_width_m=.155, upper_arm_diameter_m=.115,
                thigh_diameter_m=.21, calf_diameter_m=.115)


def profile_schema():
    return {'type': 'object', 'additionalProperties': False,
            'properties': {key: {'type': 'number', 'minimum': .5 if key == 'height_m' else .0075,
                                'maximum': 2.5 if key == 'height_m' else 1.625}
                           for key in DEFAULTS}}


def validate_profile(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('INVALID_BODY_PROPORTIONS')
    for key, number in value.items():
        if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
            raise ValueError('INVALID_BODY_DIMENSION')
    height = value.get('height_m', DEFAULTS['height_m'])
    if not .5 <= height <= 2.5:
        raise ValueError('BODY_HEIGHT_OUT_OF_RANGE')
    scale = height / DEFAULTS['height_m']
    result = {key: value.get(key, default * scale) for key, default in DEFAULTS.items()}
    result['height_m'] = height
    if any(not .015 * height <= number <= .65 * height
           for key, number in result.items() if key != 'height_m'):
        raise ValueError('BODY_DIMENSION_OUT_OF_RANGE')
    if not .10 * height <= result['head_height_m'] <= .20 * height:
        raise ValueError('BODY_HEAD_RATIO_OUT_OF_RANGE')
    if result['shoulder_width_m'] < 1.7 * result['head_width_m']:
        raise ValueError('BODY_SHOULDER_RATIO_OUT_OF_RANGE')
    if result['hip_width_m'] < 1.6 * result['thigh_diameter_m']:
        raise ValueError('BODY_HIP_LEG_RATIO_OUT_OF_RANGE')
    return result


def create(scene, name, proportions, subdivision_levels=2):
    # Geometry is computed here in the installed native Blender timer, never
    # by a host mesh generator or a desktop/cloud Blender substitute.
    import bpy
    import bmesh
    if bpy.app.background or bpy.context.window is None:
        raise ValueError('BODY_BLOCKOUT_REQUIRES_NATIVE_EDITOR')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', name):
        raise ValueError('INVALID_BODY_NAME')
    if name in bpy.data.objects:
        raise ValueError('BODY_NAME_EXISTS')
    if type(subdivision_levels) is not int or not 0 <= subdivision_levels <= 3:
        raise ValueError('INVALID_BODY_SUBDIVISION')
    p = validate_profile(proportions)
    height = p['height_m']; scale = height / 1.65
    vertices, faces, components = [], [], []

    def rings(label, sections, axis='Z'):
        # Each section is (axis position, center first axis, center second
        # axis, first radius, negative second radius, positive second radius).
        base = len(vertices); sides = 32
        for position, first, second, radius, front, back in sections:
            for i in range(sides):
                angle = 2 * math.pi * i / sides
                x = first + radius * math.cos(angle)
                sine = math.sin(angle)
                other = second + sine * (back if sine >= 0 else front)
                vertices.append((x, other, position) if axis == 'Z' else (x, position, other))
        for row in range(len(sections)-1):
            for i in range(sides):
                a=base+row*sides+i; b=base+row*sides+(i+1)%sides
                faces.append((a,b,b+sides,a+sides))
        faces.append(tuple(base+i for i in reversed(range(sides))))
        end=base+(len(sections)-1)*sides
        faces.append(tuple(end+i for i in range(sides)))
        components.append(label)

    shoulder=p['shoulder_width_m']/2; bust=p['bust_width_m']/2
    waist=p['waist_width_m']/2; hip=p['hip_width_m']/2
    bd=p['bust_depth_m']; wd=p['waist_depth_m']; hd=p['hip_depth_m']
    torso=[(.455,hip*.65,hd*.27,hd*.30),(.49,hip*.91,hd*.38,hd*.48),
           (.53,hip,hd*.43,hd*.57),(.575,waist*1.10,wd*.61,wd*.42),
           (.625,waist,wd*.57,wd*.43),(.665,bust*.90,bd*.43,bd*.32),
           (.70,bust*.97,bd*.55,bd*.34),(.73,bust,bd*.66,bd*.34),
           (.77,bust*.98,bd*.48,bd*.33),(.805,shoulder,bd*.33,bd*.31),
           (.83,shoulder*.94,bd*.28,bd*.28),(.855,shoulder*.42,.068*scale,.07*scale),
           (.88,.058*scale,.060*scale,.065*scale)]
    rings('TorsoPelvisNeck',[(z*height,0,0,x,front,back) for z,x,front,back in torso])
    head_height=p['head_height_m']; head_width=p['head_width_m']/2
    chin=height-head_height
    head=[(0,.10,.30),(.10,.50,.60),(.22,.76,.82),(.39,.95,.96),
          (.58,1,1),(.78,.87,.97),(.93,.52,.70),(1,.03,.04)]
    rings('HeadLandmarkVolume',[(chin+z*head_height,0,0,head_width*w,
          .090*scale*d,.103*scale*d) for z,w,d in head])
    for sign,label in [(-1,'Left'),(1,'Right')]:
        arm=p['upper_arm_diameter_m']/2
        arm_sections=[]
        for z,offset,radius in [(.825,0,.83),(.80,.015,1),(.75,.043,.98),
                                (.69,.069,.81),(.66,.083,.67),(.62,.099,.74),
                                (.57,.119,.59),(.52,.139,.43)]:
            arm_sections.append((z*height,sign*(shoulder+offset*scale),0,
                                 arm*radius,arm*radius*.95,arm*radius*.95))
        rings(label+'Arm',arm_sections)
        wrist=shoulder+.139*scale
        rings(label+'Hand',[(.53*height,sign*wrist,0,.027*scale,.018*scale,.018*scale),
              (.49*height,sign*(wrist+.013*scale),-.005*scale,.037*scale,.020*scale,.020*scale),
              (.445*height,sign*(wrist+.025*scale),-.009*scale,.031*scale,.015*scale,.015*scale),
              (.425*height,sign*(wrist+.029*scale),-.007*scale,.012*scale,.009*scale,.009*scale)])
        rings(label+'Thumb',[(.505*height,sign*(wrist-.026*scale),-.005*scale,.019*scale,.018*scale,.018*scale),
              (.477*height,sign*(wrist-.045*scale),-.015*scale,.018*scale,.017*scale,.017*scale),
              (.455*height,sign*(wrist-.045*scale),-.020*scale,.009*scale,.009*scale,.009*scale)])
        thigh=p['thigh_diameter_m']/2; calf=p['calf_diameter_m']/2
        leg_x=sign*p['hip_width_m']*.24
        leg=[]
        for z,radius,depth in [(.53,thigh*.85,thigh),(.49,thigh,thigh*1.08),
              (.44,thigh*.96,thigh),(.38,thigh*.80,thigh*.85),(.31,thigh*.61,thigh*.67),
              (.275,calf*.92,calf),(.245,calf*.98,calf*1.13),(.20,calf,calf*1.22),
              (.14,calf*.82,calf),(.08,calf*.56,calf*.72),(.045,calf*.50,calf*.65)]:
            leg.append((z*height,leg_x,.013*scale,radius,depth,depth))
        rings(label+'Leg',leg)
        rings(label+'Foot',[(y*scale,leg_x,z*scale,r*scale,d*scale,d*scale)
              for y,z,r,d in [(-.19,.018,.016,.018),(-.165,.024,.039,.024),
                              (-.10,.041,.047,.031),(-.02,.05,.038,.04),
                              (.055,.036,.034,.036),(.068,.02,.014,.02)]],axis='Y')
    mesh = bpy.data.meshes.new(name+'Mesh'); ob = None
    try:
        mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new()
        try:
            bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh)
        finally:bm.free()
        for polygon in mesh.polygons:polygon.use_smooth=True
        ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        if subdivision_levels:
            mod=ob.modifiers.new('EditableBlockoutSurface','SUBSURF')
            mod.levels=subdivision_levels;mod.render_levels=subdivision_levels
        ob.color=(.52,.55,.58,1)
        ob['render_work_stage']='01_body_proportions'
        ob['render_body_proportions']=json.dumps(p,sort_keys=True)
        ob['render_sculpt_union_pending']=True
        ob['render_likeness_verified']=False
        for selected in list(bpy.context.selected_objects):selected.select_set(False)
        ob.select_set(True);bpy.context.view_layer.objects.active=ob
        return {'object':ob.name,'name':ob.name,'stage':'01_body_proportions',
                'proportions_m':p,'base_vertices':len(mesh.vertices),'base_polygons':len(mesh.polygons),
                'anatomical_volumes':components,'subdivision_levels':subdivision_levels,
                'sculpt_union_pending':True,'fingers_face_clothing_rigging_completed':False,
                'visual_likeness_verified':False,'geometry_created_inside_native_blender':True,
                'performed_visible_pointer_click':False}
    except Exception:
        if ob is not None:bpy.data.objects.remove(ob,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
        raise
