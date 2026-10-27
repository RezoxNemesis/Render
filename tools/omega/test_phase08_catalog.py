# SPDX-License-Identifier: GPL-2.0-or-later
"""Audit the legacy 17 native preset catalog without importing Blender UI."""
import ast
from pathlib import Path
import unittest

LEGACY = Path(__file__).resolve().parents[2] / 'full-app/scripts/render_assets.py'


def _read_catalog():
    tree = ast.parse(LEGACY.read_text(encoding='utf-8'))
    items = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in ('PRESETS','_CATEGORIES')
                for target in node.targets):
            items.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'search_presets':
            items.append(node)
    ns = {}
    exec(compile(ast.Module(body=items,type_ignores=[]),str(LEGACY),'exec'),ns)
    return ns


class Phase08LegacyCatalogTest(unittest.TestCase):
    def test_existing_seventeen_not_renamed(self):
        c = _read_catalog()
        names = [name for name,_ in c['PRESETS']]
        self.assertEqual(names,[
            'COLUMN','ARCH','STAIRS','WALL','WINDOW','ROOF','TREE','SHRUB',
            'ROCK','GRASS','BENCH','LAMP','WATER','TERRAIN','HUMANOID','QUADRUPED','STUDIO'])
        self.assertEqual(set(names),set(c['_CATEGORIES']))

    def test_search_category_license_and_no_remote_dependencies(self):
        s=_read_catalog()['search_presets']
        self.assertEqual(len(s()),17)
        self.assertEqual([v['id'] for v in s('leafy tree')],['TREE'])
        self.assertEqual(len(s(category='Vegetation')),3)
        self.assertTrue(all(v['license']=='GPL-2.0-or-later' and not v['external_download']
                            for v in s()))
        self.assertEqual(s('this certainly does not exist'),[])
        for q in [None, 7, 'A'*81]:
            with self.assertRaises(ValueError):s(q)
        with self.assertRaises(ValueError):s(category='Unlicensed')


if __name__=='__main__':unittest.main()
