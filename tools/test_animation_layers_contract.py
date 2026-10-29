# SPDX-License-Identifier: GPL-2.0-or-later
"""Strict payload and polygon boundary tests without Blender."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_animation_layers_contract as C

VALID = {
    "studio.animation.catalog": {},
    "studio.animation.layer.create": {"name": "Foreground"},
    "studio.animation.parallax.create": {"name": "ParallaxCamera", "layers": ["Front", "Back"]},
    "studio.animation.morph.create": {"object": "Actor", "name": "Breath"},
}


class AnimationLayerContractTests(unittest.TestCase):
    def test_normalized_defaults_are_independent_and_json_safe(self):
        for op,p in VALID.items():
            before = copy.deepcopy(p)
            clean = C.validate(op,p)
            self.assertEqual(p,before)
            self.assertEqual(clean,C.validate(op,clean))
            json.dumps(clean,allow_nan=False)
        a = C.validate("studio.animation.layer.create",VALID["studio.animation.layer.create"])
        a["color"][0] = 1
        b = C.validate("studio.animation.layer.create",VALID["studio.animation.layer.create"])
        self.assertEqual(b["color"],[.3,.55,.8])

    def test_unknown_and_required_fields(self):
        for desc in C.capabilities():
            op = desc["operation"]
            for field in ("python","url","path","script",3):
                with self.assertRaises(ValueError):
                    C.validate(op,{**VALID[op],field:"bad"})
            for field in desc["input_schema"]["required"]:
                missing = dict(VALID[op]); missing.pop(field)
                with self.assertRaises(ValueError):
                    C.validate(op,missing)
        for op in (None,[],False,"studio.animation.run"):
            with self.assertRaises(ValueError):
                C.validate(op,{})

    def test_numeric_fields_fail_closed(self):
        for desc in C.capabilities():
            for field,spec in desc["input_schema"]["properties"].items():
                if spec["type"] not in ("integer","number"):
                    continue
                for bad in (True,False,math.nan,math.inf,-math.inf,"1",None,10**1000,
                            spec["minimum"]-1,spec["maximum"]+1):
                    with self.subTest(field=field,bad=str(bad)[:20]):
                        with self.assertRaises(ValueError):
                            C.validate(desc["operation"],{**VALID[desc["operation"]],field:bad})

    def test_simple_concave_polygon_and_winding(self):
        points = [[-1,-1],[1,-1],[0,0],[1,1],[-1,1]]
        valid = {"name":"Cutout","shape":"polygon","points":points}
        self.assertEqual(C.validate("studio.animation.layer.create",valid)["points"],points)
        valid["points"] = list(reversed(points))
        self.assertEqual(C.validate("studio.animation.layer.create",valid)["points"],points)
        self.assertEqual(valid["points"],list(reversed(points)))

    def test_polygon_degeneracy_and_intersection_rejected(self):
        bad = [[],[[0,0],[1,1]],[[0,0],[0,0],[1,1]],
               [[-1,-1],[1,1],[-1,1],[1,-1]],
               [[0,0],[.5,0],[1,0]],
               [[0,0],[1,0],[1,1],[.5,0],[0,1]],
               [[0,0],[math.nan,1],[1,0]],
               [[0,0],[2,1],[1,0]],
               [[0,0,0],[1,0],[1,1]],
               [[0,0],[1,0],[1,1],[0,0]]]
        for points in bad:
            with self.assertRaises(ValueError):
                C.validate("studio.animation.layer.create",{"name":"Invalid","shape":"polygon","points":points})
        with self.assertRaises(ValueError):
            C.validate("studio.animation.layer.create",{"name":"NoPoints","shape":"polygon"})
        with self.assertRaises(ValueError):
            C.validate("studio.animation.layer.create",{"name":"WrongShape","points":[[-1,-1],[1,-1],[0,1]]})

    def test_adjacent_collinear_vertices_keep_forward_control_points_but_reject_backtracking(self):
        # A forward point on an edge is a useful editable control vertex.
        forward = [[-1,-1],[0,-1],[1,-1],[1,1],[-1,1]]
        clean = C.validate("studio.animation.layer.create",{
            "name":"Forward", "shape":"polygon", "points":forward})
        self.assertEqual(clean["points"],forward)
        # Backtracking edges overlap. Also test wrap-around adjacency and both windings.
        backward = [[-1,-1],[1,-1],[0,-1],[1,1],[-1,1]]
        for i in range(len(backward)):
            rotated = backward[i:]+backward[:i]
            for points in (rotated,list(reversed(rotated))):
                with self.assertRaises(ValueError):
                    C.validate("studio.animation.layer.create",{
                        "name":"Backtrack", "shape":"polygon", "points":points})

    def test_layer_and_timing_constraints(self):
        op="studio.animation.parallax.create"
        for patch in ({"layers":["A"]},{"layers":["A","A"]},{"name":"Front"},
                      {"travel_x":0,"travel_y":0},{"start":120,"end":120},
                      {"start":1,"end":10002}):
            with self.assertRaises(ValueError):
                C.validate(op,{**VALID[op],**patch})
        with self.assertRaises(ValueError):
            C.validate("studio.animation.morph.create",{"object":"Actor","name":"Basis"})
        with self.assertRaises(ValueError):
            C.validate("studio.animation.morph.create",{"object":"Actor","name":"Wave","loop":1})

    def test_names_and_colors(self):
        for bad in ("../Secret","A/B","A\nB","","Trailing ",True):
            with self.assertRaises(ValueError):
                C.validate("studio.animation.layer.create",{"name":bad})
        for bad in ([1,2,0],[0,0],[False,0,1],[math.nan,0,0],(1,1,1)):
            with self.assertRaises(ValueError):
                C.validate("studio.animation.layer.create",{"name":"Layer","color":bad})

    def test_catalog_does_not_claim_spatial_4d_or_paint_engine(self):
        catalog = C.catalog()
        self.assertFalse(catalog["four_spatial_dimensions"])
        self.assertFalse(catalog["raster_paint_engine"])
        self.assertFalse(catalog["existing_animation_overwritten"])
        descriptors = C.capabilities()
        self.assertEqual(set(d["operation"] for d in descriptors),set(C.OPS))
        for d in descriptors:
            self.assertEqual(d["checkpoint_before_change"],d["operation"] not in C.READ_ONLY)
            self.assertFalse(d["input_schema"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
