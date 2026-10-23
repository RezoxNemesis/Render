# SPDX-License-Identifier: GPL-2.0-or-later
"""Public CC0 assets inside native Blender; network workers never call bpy.

Search/download are explicit, cached and resumable. Imported models stay native
editable Blender data. Original provider files and license provenance are kept.
"""
import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import threading
import time
from urllib.parse import urlsplit
import urllib.request

try:
    import bpy
except ImportError:
    bpy = None

_LOCK = threading.RLock()
_CATALOG = None
_CATALOG_THREAD = None
_CATALOG_ERROR = ""
_JOBS = {}
_KINDS = {"hdris": 0, "textures": 1, "models": 2}
_RESOLUTIONS = ("1k", "2k", "4k", "8k", "16k")
_HOSTS = {"api.polyhaven.com", "dl.polyhaven.org", "cdn.polyhaven.com"}
_ASSET = re.compile(r"^[A-Za-z0-9_-]{1,96}$")
_INSTALLED = False
_UI_ITEMS = [("NONE", "Search the CC0 catalog", "")]


def _fields(p, allowed, required=()):
    if not isinstance(p, dict) or set(p) - set(allowed) or set(required) - set(p):
        raise ValueError("INVALID_ASSET_ARGUMENTS")


def _url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in _HOSTS
            or parts.port not in (None, 443) or parts.username or parts.password
            or parts.fragment):
        raise ValueError("ASSET_URL_NOT_TRUSTED")
    return url


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        _url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


@lru_cache(maxsize=1)
def _opener():
    context = ssl.create_default_context()
    # Android's bundled Python may not have a desktop OpenSSL CA directory.
    # Load actual system trust anchors; certificate verification stays required.
    if not context.get_ca_certs():
        for folder in ("/apex/com.android.conscrypt/cacerts", "/system/etc/security/cacerts"):
            path = Path(folder)
            if path.is_dir():
                for cert in path.glob("*.0"):
                    try:
                        context.load_verify_locations(cafile=str(cert))
                    except (OSError, ssl.SSLError):
                        continue
                if context.get_ca_certs():
                    break
    return urllib.request.build_opener(_Redirects(), urllib.request.HTTPSHandler(context=context))


def _request(url, headers=None):
    options = {"User-Agent": "RenderStudio/0.29 (native Blender CC0 asset browser)",
               "Accept": "application/json, application/octet-stream"}
    options.update(headers or {})
    return _opener().open(urllib.request.Request(_url(url), headers=options), timeout=30)


def _json_url(url):
    with _request(url) as response:
        data = response.read(12 * 1024 * 1024 + 1)
        if len(data) > 12 * 1024 * 1024:
            raise ValueError("ASSET_CATALOG_RESPONSE_TOO_LARGE")
        return json.loads(data)


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf8") as output:
        json.dump(data, output, sort_keys=True, allow_nan=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _library(root):
    folder = Path(root) / "Assets" / "Library"
    if any(path.is_symlink() for path in (folder, folder.parent, Path(root))):
        raise ValueError("ASSET_LIBRARY_SYMLINK")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder


def _refresh(root):
    global _CATALOG, _CATALOG_ERROR
    try:
        data = _json_url("https://api.polyhaven.com/assets")
        if not isinstance(data, dict) or not data:
            raise ValueError("INVALID_ASSET_CATALOG")
        data = {key: value for key, value in data.items()
                if _ASSET.fullmatch(key) and isinstance(value, dict)
                and value.get("type") in _KINDS.values()}
        _atomic(_library(root) / "catalog.json", {"saved_at": time.time(), "assets": data})
        with _LOCK:
            _CATALOG, _CATALOG_ERROR = data, ""
    except Exception as error:
        with _LOCK:
            _CATALOG_ERROR = type(error).__name__


def search(root, p):
    global _CATALOG, _CATALOG_THREAD
    _fields(p, ("query", "kind", "offset", "limit", "refresh"))
    query, kind = p.get("query", ""), p.get("kind", "all")
    offset, limit = p.get("offset", 0), p.get("limit", 20)
    if (not isinstance(query, str) or len(query) > 120 or kind not in (*_KINDS, "all")
            or type(offset) is not int or not 0 <= offset <= 100000
            or type(limit) is not int or not 1 <= limit <= 40
            or type(p.get("refresh", False)) is not bool):
        raise ValueError("INVALID_ASSET_SEARCH")
    with _LOCK:
        if _CATALOG is None:
            cached = _library(root) / "catalog.json"
            if cached.is_file() and not cached.is_symlink() and cached.stat().st_size <= 12 * 1024 * 1024:
                try:
                    data = json.loads(cached.read_text())
                    if isinstance(data.get("assets"), dict):
                        _CATALOG = data["assets"]
                except (OSError, ValueError, TypeError):
                    pass
        if (_CATALOG is None or p.get("refresh")) and not (_CATALOG_THREAD and _CATALOG_THREAD.is_alive()):
            _CATALOG_THREAD = threading.Thread(target=_refresh, args=(root,), daemon=True)
            _CATALOG_THREAD.start()
        catalog = dict(_CATALOG or {})
        loading = bool(_CATALOG_THREAD and _CATALOG_THREAD.is_alive())
        error = _CATALOG_ERROR
    terms = query.casefold().split()
    matches = []
    for ident, asset in catalog.items():
        text = " ".join((ident, str(asset.get("name", "")),
                         " ".join(asset.get("tags", [])), " ".join(asset.get("categories", [])),
                         str(asset.get("description", "")))).casefold()
        if kind != "all" and asset.get("type") != _KINDS[kind]:
            continue
        if not all(term in text for term in terms):
            continue
        matches.append({"id": ident, "name": asset.get("name", ident),
                        "kind": next((k for k, v in _KINDS.items() if v == asset.get("type")), "unknown"),
                        "license": "CC0-1.0", "provider": "Poly Haven",
                        "authors": list(asset.get("authors", {})),
                        "source_url": "https://polyhaven.com/a/" + ident,
                        "max_resolution": asset.get("max_resolution"),
                        "polycount": asset.get("polycount")})
    matches.sort(key=lambda value: value["name"].casefold())
    return {"state": "loading" if loading else "ready" if catalog else "unavailable",
            "results": matches[offset:offset + limit], "total_matches": len(matches),
            "catalog_assets": len(catalog), "next_offset": offset + limit if offset + limit < len(matches) else None,
            "network_error": error, "provider": "Poly Haven", "license": "CC0-1.0",
            "license_url": "https://polyhaven.com/license", "catalog_is_finite": True,
            "original_asset_quality_changed": False}


def _relative(folder, name):
    part = PurePosixPath(name)
    if (not name or "\\" in name or part.is_absolute() or ".." in part.parts
            or len(name) > 240 or any(not re.fullmatch(r"[A-Za-z0-9_. -]+", x) for x in part.parts)):
        raise ValueError("INVALID_ASSET_DEPENDENCY_PATH")
    target = folder.joinpath(*part.parts)
    for path in (target, *target.parents):
        if path == folder.parent:
            break
        if path.is_symlink():
            raise ValueError("ASSET_DEPENDENCY_SYMLINK")
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError("ASSET_OUTSIDE_LIBRARY")
    return target


def file_plan(details, ident, resolution, kind):
    if not _ASSET.fullmatch(ident) or resolution not in _RESOLUTIONS or kind not in _KINDS:
        raise ValueError("INVALID_ASSET_DOWNLOAD")
    section, form = ("hdri", "exr") if kind == "hdris" else ("blend", "blend")
    formats = details.get(section, {}).get(resolution, {})
    entry = formats.get(form)
    if not isinstance(entry, dict):
        raise ValueError("REQUESTED_ASSET_RESOLUTION_UNAVAILABLE")
    main = ident + "_" + resolution + "." + form
    files = [(main, entry)] + list(entry.get("include", {}).items())
    checked = []
    for name, item in files:
        if (not isinstance(item, dict) or type(item.get("size")) is not int
                or not 0 < item["size"] <= 8 * 1024 ** 3
                or not re.fullmatch(r"[a-f0-9]{32}", item.get("md5", ""))):
            raise ValueError("INVALID_PROVIDER_FILE_METADATA")
        _url(item.get("url", ""))
        if PurePosixPath(name).suffix.lower() not in (".blend", ".jpg", ".jpeg", ".png", ".exr", ".hdr", ".webp"):
            raise ValueError("UNSUPPORTED_ASSET_DEPENDENCY")
        checked.append({"filename": name, "url": item["url"], "bytes": item["size"], "md5": item["md5"]})
    if len(checked) > 100:
        raise ValueError("ASSET_DEPENDENCY_LIMIT")
    return main, checked


def _digest(path, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_file(target, item, stopped, progress):
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.is_file() and target.stat().st_size == item["bytes"] and _digest(target, "md5") == item["md5"]:
        progress(item["bytes"])
        return
    part = target.with_name(target.name + ".partial")
    if part.is_symlink():
        raise ValueError("ASSET_PARTIAL_SYMLINK")
    offset = part.stat().st_size if part.is_file() else 0
    if offset >= item["bytes"]:
        offset = 0
    headers = {"Range": "bytes=%d-" % offset} if offset else {}
    with _request(item["url"], headers) as response:
        if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith("bytes %d-" % offset)):
            if response.status != 200:
                raise ValueError("INVALID_ASSET_RESUME_RESPONSE")
            offset = 0
        progress(offset)
        with part.open("ab" if offset else "wb") as output:
            done = offset
            while True:
                if stopped.is_set():
                    raise InterruptedError("ASSET_DOWNLOAD_PAUSED")
                block = response.read(256 * 1024)
                if not block:
                    break
                done += len(block)
                if done > item["bytes"]:
                    raise ValueError("ASSET_DOWNLOAD_SIZE_MISMATCH")
                if shutil.disk_usage(target.parent).free < len(block) + 128 * 1024 * 1024:
                    raise OSError("ASSET_DOWNLOAD_STORAGE_PRESSURE")
                output.write(block)
                progress(done)
            output.flush()
            os.fsync(output.fileno())
    if part.stat().st_size != item["bytes"] or _digest(part, "md5") != item["md5"]:
        raise ValueError("ASSET_DOWNLOAD_INTEGRITY_FAILED")
    os.replace(part, target)


def _download(root, job, folder, report, stop):
    def save():
        _atomic(folder / "download.json", report)
    try:
        details = _json_url("https://api.polyhaven.com/files/" + report["asset_id"])
        main, files = file_plan(details, report["asset_id"], report["resolution"], report["kind"])
        paths = [(item, _relative(folder, item["filename"])) for item in files]
        total = sum(item["bytes"] for item in files)
        # Originals remain full size. Insufficient disk pauses the request;
        # it never substitutes smaller textures or a lower-polygon model.
        required = sum(item["bytes"] for item, path in paths if not path.is_file())
        if shutil.disk_usage(folder).free < required + 128 * 1024 * 1024:
            raise OSError("ASSET_DOWNLOAD_STORAGE_PRESSURE")
        report.update(state="downloading", total_bytes=total, files=files, main_file=main)
        save()
        completed = 0
        last = 0.0
        for item, target in paths:
            def progress(count):
                nonlocal last
                report["downloaded_bytes"] = completed + count
                if time.monotonic() - last >= 0.5:
                    save()
                    last = time.monotonic()
            _download_file(target, item, stop, progress)
            item["sha256"] = _digest(target)
            completed += item["bytes"]
            report["downloaded_bytes"] = completed
            save()
        report.update(state="downloaded", license="CC0-1.0", license_url="https://polyhaven.com/license",
                      originals_preserved=True, completed_at=time.time(), error="")
        save()
    except Exception as error:
        report.update(state="paused" if isinstance(error, InterruptedError) else "failed",
                      error=str(error) if re.fullmatch(r"[A-Z_]{3,96}", str(error)) else type(error).__name__)
        save()


def download(root, p):
    _fields(p, ("asset_id", "resolution", "kind"), ("asset_id", "resolution", "kind"))
    ident, resolution, kind = p["asset_id"], p["resolution"], p["kind"]
    if (not isinstance(ident, str) or not _ASSET.fullmatch(ident)
            or resolution not in _RESOLUTIONS or kind not in _KINDS):
        raise ValueError("INVALID_ASSET_DOWNLOAD")
    job = hashlib.sha256((ident + ":" + resolution + ":" + kind).encode()).hexdigest()[:32]
    folder = _library(root) / job
    if folder.is_symlink():
        raise ValueError("ASSET_LIBRARY_SYMLINK")
    folder.mkdir(exist_ok=True, mode=0o700)
    with _LOCK:
        current = _JOBS.get(job)
        if current and current[0].is_alive():
            return status(root, {"download_id": job})
        receipt = folder / "download.json"
        if receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size < 131072:
            previous = json.loads(receipt.read_text())
            if previous.get("state") == "downloaded":
                return dict(status(root, {"download_id": job}), already_downloaded=True, started=False)
        if any(thread.is_alive() for thread, _ in _JOBS.values()):
            raise RuntimeError("ANOTHER_ASSET_DOWNLOAD_RUNNING")
        report = {"download_id": job, "asset_id": ident, "resolution": resolution, "kind": kind,
                  "provider": "Poly Haven", "source_url": "https://polyhaven.com/a/" + ident,
                  "state": "preparing", "downloaded_bytes": 0, "total_bytes": 0,
                  "original_asset_quality_changed": False}
        _atomic(folder / "download.json", report)
        stop = threading.Event()
        thread = threading.Thread(target=_download, args=(root, job, folder, report, stop), daemon=True)
        _JOBS[job] = (thread, stop)
        thread.start()
    return {"download_id": job, "state": "preparing", "started": True,
            "native_import_completed": False, "original_asset_quality_changed": False}


def status(root, p, cancel=False):
    _fields(p, ("download_id",), ("download_id",))
    job = p["download_id"]
    if not isinstance(job, str) or not re.fullmatch(r"[a-f0-9]{32}", job):
        raise ValueError("INVALID_ASSET_DOWNLOAD_ID")
    folder = _library(root) / job
    path = _relative(folder, "download.json")
    if not path.is_file() or path.stat().st_size > 131072:
        raise ValueError("ASSET_DOWNLOAD_NOT_FOUND")
    with _LOCK:
        active = _JOBS.get(job)
        if cancel and active:
            active[1].set()
        report = json.loads(path.read_text())
        if report.get("state") in ("preparing", "downloading") and not (active and active[0].is_alive()):
            report["state"] = "interrupted"
        report["pause_requested"] = cancel
        # Poll receipts stay bounded even when the model has many textures.
        # The full provider manifest remains in download.json for resuming.
        report["files"] = [{key: value for key, value in item.items()
                            if key in ("filename", "bytes", "sha256")}
                           for item in report.get("files", [])]
        return report


def import_asset(scene, root, p):
    _fields(p, ("download_id",), ("download_id",))
    if scene.get("production_frozen_job"):
        raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
    report = status(root, p)
    if report["state"] != "downloaded":
        raise ValueError("ASSET_DOWNLOAD_NOT_COMPLETE")
    folder = _library(root) / report["download_id"]
    for item in report["files"]:
        path = _relative(folder, item["filename"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or _digest(path) != item["sha256"]:
            raise ValueError("ASSET_LOCAL_INTEGRITY_FAILED")
    key = report["download_id"]
    for collection in scene.collection.children_recursive:
        if collection.get("render_asset_download_id") == key:
            return {"collection": collection.name, "already_imported": True, "license": "CC0-1.0"}
    path = _relative(folder, report["main_file"])
    if report["kind"] == "hdris":
        if scene.world and scene.world.get("render_asset_download_id") == key:
            return {"world": scene.world.name, "already_imported": True, "license": "CC0-1.0"}
        world = scene.world.copy() if scene.world else bpy.data.worlds.new("AssetEnvironment")
        world.use_nodes = True
        nodes = world.node_tree.nodes
        image = nodes.new("ShaderNodeTexEnvironment")
        image.image = bpy.data.images.load(str(path), check_existing=True)
        image.image.pack()
        background = next((node for node in nodes if node.type == "BACKGROUND"), None)
        if background is None:
            background = nodes.new("ShaderNodeBackground")
            output = nodes.new("ShaderNodeOutputWorld")
            world.node_tree.links.new(background.outputs[0], output.inputs[0])
        world.node_tree.links.new(image.outputs["Color"], background.inputs["Color"])
        scene.world = world
        world["render_asset_download_id"] = key
        return {"world": world.name, "license": "CC0-1.0", "original_hdr_preserved": True}
    group = bpy.data.collections.new("CC0_" + report["asset_id"])
    before_objects = set(bpy.data.objects)
    before_collections = set(bpy.data.collections)
    before_images = set(bpy.data.images)
    try:
        with bpy.data.libraries.load(str(path), link=False) as (source, target):
            if report["kind"] == "models":
                target.collections = list(source.collections)
                if not target.collections:
                    target.objects = list(source.objects)
            else:
                target.materials = list(source.materials)
        for image in set(bpy.data.images) - before_images:
            if image.source == "FILE" and not image.packed_file:
                if image.filepath.startswith("//"):
                    candidate = _relative(folder, image.filepath[2:])
                    if candidate.is_file():
                        image.filepath = str(candidate)
                        image.reload()
                image.pack()
        scene.collection.children.link(group)
        loaded = [item for item in getattr(target, "collections", ()) if item]
        for collection in loaded:
            if not any(collection.name in parent.children for parent in loaded):
                group.children.link(collection)
        for ob in getattr(target, "objects", ()):
            if ob:
                group.objects.link(ob)
        materials = [item for item in getattr(target, "materials", ()) if item]
        selected = getattr(bpy.context, "object", None)
        if materials and selected and selected.type == "MESH":
            selected.data.materials.append(materials[0])
        group["render_asset_download_id"] = key
        group["render_asset_license"] = "CC0-1.0"
        group["render_asset_source"] = report["source_url"]
        return {"collection": group.name, "objects": len(group.all_objects),
                "materials": [item.name for item in materials], "editable": True,
                "license": "CC0-1.0", "already_imported": False, "originals_preserved": True}
    except Exception:
        for ob in set(bpy.data.objects) - before_objects:
            bpy.data.objects.remove(ob, do_unlink=True)
        for collection in set(bpy.data.collections) - before_collections | {group}:
            if collection.name in bpy.data.collections:
                bpy.data.collections.remove(collection, do_unlink=True)
        raise


def execute(operation, scene, root, p):
    if operation == "asset.search":
        return search(root, p)
    if operation == "asset.download":
        return download(root, p)
    if operation in ("asset.download.status", "asset.download.pause"):
        return status(root, p, operation.endswith("pause"))
    if operation == "asset.import":
        return import_asset(scene, root, p)
    raise ValueError("ASSET_OPERATION_UNAVAILABLE")


def _root():
    spool = os.environ.get("RENDER_AGENT_SPOOL", "")
    if not spool:
        raise RuntimeError("RENDER_LOCAL_STORAGE_UNAVAILABLE")
    return Path(spool).resolve().parent / "Production"


if bpy is not None and getattr(getattr(bpy, "types", None), "Operator", None):
    class RENDERSTUDIO_OT_catalog(bpy.types.Operator):
        bl_idname = "renderstudio.asset_catalog"
        bl_label = "Search CC0 Assets"
        bl_description = "Search Poly Haven models, materials and HDRIs inside Blender"

        def execute(self, context):
            global _UI_ITEMS
            try:
                result = search(_root(), {"query": context.scene.render_asset_query,
                                         "kind": context.scene.render_asset_kind, "limit": 40})
                _UI_ITEMS = [(item["id"], item["name"], item["kind"] + " / CC0") for item in result["results"]]
                if not _UI_ITEMS:
                    _UI_ITEMS = [("NONE", "Catalog loading" if result["state"] == "loading" else "No matching assets", "")]
                context.scene.render_asset_message = result["state"] + " • " + str(result["total_matches"]) + " matches"
                return {"FINISHED"}
            except Exception as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

    class RENDERSTUDIO_OT_asset_download(bpy.types.Operator):
        bl_idname = "renderstudio.asset_download"
        bl_label = "Download Selected Asset"

        def execute(self, context):
            try:
                scene = context.scene
                kind = scene.render_asset_kind
                if kind == "all":
                    matches = search(_root(), {"query": scene.render_asset_selection, "limit": 40})
                    kind = next(item["kind"] for item in matches["results"] if item["id"] == scene.render_asset_selection)
                result = download(_root(), {"asset_id": scene.render_asset_selection,
                                           "kind": kind, "resolution": scene.render_asset_resolution})
                scene.render_asset_download_id = result["download_id"]
                return {"FINISHED"}
            except Exception as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

    class RENDERSTUDIO_OT_asset_import(bpy.types.Operator):
        bl_idname = "renderstudio.asset_import"
        bl_label = "Import Download into Blender"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            try:
                import_asset(context.scene, _root(), {"download_id": context.scene.render_asset_download_id})
                return {"FINISHED"}
            except Exception as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

    class RENDERSTUDIO_OT_image_reference(bpy.types.Operator):
        bl_idname = "renderstudio.import_image_reference"
        bl_label = "Import Image Reference"
        bl_options = {"REGISTER", "UNDO"}
        filepath: bpy.props.StringProperty(subtype="FILE_PATH")
        filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff;*.exr;*.hdr;*.bmp;*.tga", options={"HIDDEN"})

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            try:
                if context.scene.get("production_frozen_job"):
                    raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
                image = bpy.data.images.load(self.filepath, check_existing=True)
                image.pack()
                ob = bpy.data.objects.new("ImageReference_" + Path(self.filepath).stem[:40], None)
                ob.empty_display_type = "IMAGE"
                ob.data = image
                ob.empty_display_size = 5
                ob.location = context.scene.cursor.location
                context.scene.collection.objects.link(ob)
                self.report({"INFO"}, "Original image imported at native resolution")
                return {"FINISHED"}
            except Exception as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

    class RENDERSTUDIO_PT_library(bpy.types.Panel):
        bl_label = "Render Studio • Assets"
        bl_idname = "RENDERSTUDIO_PT_library"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Render Studio"

        def draw(self, context):
            layout, scene = self.layout, context.scene
            layout.prop(scene, "render_asset_query", text="Search")
            layout.prop(scene, "render_asset_kind", text="Library")
            layout.operator("renderstudio.asset_catalog", icon="VIEWZOOM")
            layout.label(text=scene.render_asset_message)
            layout.prop(scene, "render_asset_selection", text="Asset")
            layout.prop(scene, "render_asset_resolution", text="Texture size")
            layout.operator("renderstudio.asset_download", icon="IMPORT")
            if scene.render_asset_download_id:
                try:
                    state = status(_root(), {"download_id": scene.render_asset_download_id})
                    total = state.get("total_bytes", 0)
                    if total:
                        layout.progress(factor=min(1, state.get("downloaded_bytes", 0) / total),
                                        text=state["state"], type="BAR")
                    else:
                        layout.label(text=state["state"])
                    if state.get("error"):
                        layout.label(text=state["error"], icon="ERROR")
                    row = layout.row()
                    row.enabled = state["state"] == "downloaded"
                    row.operator("renderstudio.asset_import")
                except Exception:
                    layout.label(text="Download status unavailable")
            layout.label(text="Poly Haven • CC0 • originals preserved")
            layout.separator()
            layout.operator("renderstudio.import_image_reference", icon="IMAGE_DATA")


def _redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass
    return 1.0


def install():
    global _INSTALLED
    if _INSTALLED or bpy is None or bpy.app.background:
        return
    scene = bpy.types.Scene
    scene.render_asset_query = bpy.props.StringProperty(name="Search", default="grass", maxlen=120)
    scene.render_asset_kind = bpy.props.EnumProperty(items=[(k, k.title(), k) for k in ("all", *_KINDS)], default="all")
    scene.render_asset_selection = bpy.props.EnumProperty(items=lambda self, context: _UI_ITEMS)
    scene.render_asset_resolution = bpy.props.EnumProperty(items=[(v, v, v) for v in _RESOLUTIONS], default="4k")
    scene.render_asset_download_id = bpy.props.StringProperty(options={"HIDDEN"})
    scene.render_asset_message = bpy.props.StringProperty(default="Search models, materials and HDR lighting")
    for cls in (RENDERSTUDIO_OT_catalog, RENDERSTUDIO_OT_asset_download,
                RENDERSTUDIO_OT_asset_import, RENDERSTUDIO_OT_image_reference, RENDERSTUDIO_PT_library):
        bpy.utils.register_class(cls)
    bpy.app.timers.register(_redraw, first_interval=1, persistent=True)
    _INSTALLED = True


def register():
    pass  # Installed by Render session tools after the native window is ready.


def unregister():
    pass
