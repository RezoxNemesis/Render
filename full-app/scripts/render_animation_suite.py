# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared, bpy-free registry for Animation Studio's typed native tools."""
import importlib

VERSION = "render.animation-studio.v1"
MODULES = (
    ("render_animation_layers_contract", "render_animation_layers"),
    ("render_motion_lab_contract", "render_motion_lab"),
    ("render_animation_finish_contract", "render_animation_finish"),
)
OPS = {}
READ_ONLY = set()
_ROUTES = {}
for contract_name, implementation in MODULES:
    contract = importlib.import_module(contract_name)
    for operation, workspace in contract.OPS.items():
        if operation in OPS:
            raise RuntimeError("ANIMATION_STUDIO_DUPLICATE_OPERATION")
        OPS[operation] = workspace
        _ROUTES[operation] = (contract, implementation)
    READ_ONLY.update(contract.READ_ONLY)
READ_ONLY = frozenset(READ_ONLY)


def validate(operation, payload):
    if operation not in _ROUTES:
        raise ValueError("ANIMATION_STUDIO_OPERATION_UNAVAILABLE")
    return _ROUTES[operation][0].validate(operation, payload)


def capabilities():
    return [row for name, _ in MODULES
            for row in importlib.import_module(name).capabilities()]


def execute(operation, payload, root, scene):
    # Lazy bpy imports keep source contracts testable before Android starts.
    normalized = validate(operation, payload)
    module = importlib.import_module(_ROUTES[operation][1])
    return module.execute(operation, normalized, root, scene)
