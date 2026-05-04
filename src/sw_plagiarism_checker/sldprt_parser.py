"""
sldprt_parser.py  —  SolidWorks COM API edition
================================================
Extracts rich data from SolidWorks .SLDPRT files using the SolidWorks COM API
(win32com / pywin32).  Requires SolidWorks to be installed on the machine.

Extracted data per file
-----------------------
- File metadata  : path, name, size, filesystem timestamps
- OLE properties : author, last-author, created, last-saved (via olefile fallback)
- SW custom props: all key/value pairs
- Feature tree   : ordered list of {name, type, suppressed, created_by}
- Mass properties: volume, surface_area, density, mass, centre_of_mass, MOI
- Configuration  : active configuration name
- SW version     : SolidWorks version that last saved the file
- Fingerprints   : SHA-256 of full file, feature-sequence hash,
                   geometry fingerprint (mass props hash), custom-props hash
"""

import os
import sys
import hashlib
import datetime
import json
import re
import struct

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    import olefile
    _HAS_OLEFILE = True
except ImportError:
    _HAS_OLEFILE = False

try:
    import win32com.client
    import pythoncom
    _HAS_WIN32COM = True
except ImportError:
    _HAS_WIN32COM = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_datetime(dt):
    if dt is None:
        return "—"
    if isinstance(dt, datetime.datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_str(s):
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Filesystem metadata
# ---------------------------------------------------------------------------

def _get_fs_metadata(path):
    try:
        stat = os.stat(path)
        return {
            "file_size_bytes": stat.st_size,
            "fs_created":  datetime.datetime.fromtimestamp(stat.st_ctime),
            "fs_modified": datetime.datetime.fromtimestamp(stat.st_mtime),
            "fs_accessed": datetime.datetime.fromtimestamp(stat.st_atime),
        }
    except Exception as e:
        return {"file_size_bytes": 0, "fs_created": None,
                "fs_modified": None, "fs_accessed": None, "error": str(e)}


# ---------------------------------------------------------------------------
# OLE metadata fallback (no SolidWorks needed)
# ---------------------------------------------------------------------------

PIDSI_AUTHOR      = 0x04
PIDSI_LASTAUTHOR  = 0x08
PIDSI_CREATE_DTM  = 0x0C
PIDSI_LASTSAVE_DTM = 0x0D
PIDSI_LASTPRINTED = 0x0B
PIDSI_APPNAME     = 0x12


def _filetime_to_dt(ft):
    if not ft or ft == 0:
        return None
    try:
        EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        return (EPOCH + datetime.timedelta(microseconds=ft // 10)).replace(tzinfo=None)
    except Exception:
        return None


def _get_ole_metadata(path):
    meta = {"author": None, "last_author": None,
            "created": None, "last_saved": None, "last_printed": None}
    if not _HAS_OLEFILE:
        return meta
    try:
        if not olefile.isOleFile(path):
            return meta
        ole = olefile.OleFileIO(path)
        if ole.exists("\x05SummaryInformation"):
            si = ole.getproperties("\x05SummaryInformation", convert_time=True)
            meta["author"]       = si.get(PIDSI_AUTHOR)
            meta["last_author"]  = si.get(PIDSI_LASTAUTHOR)
            for k, pid in [("created", PIDSI_CREATE_DTM),
                            ("last_saved", PIDSI_LASTSAVE_DTM),
                            ("last_printed", PIDSI_LASTPRINTED)]:
                v = si.get(pid)
                meta[k] = v if isinstance(v, datetime.datetime) else _filetime_to_dt(v) if isinstance(v, int) else None
            for k in ("author", "last_author"):
                if isinstance(meta[k], bytes):
                    meta[k] = meta[k].decode("utf-8", errors="replace").strip("\x00")
        ole.close()
    except Exception as e:
        meta["ole_error"] = str(e)
    return meta


# ---------------------------------------------------------------------------
# SolidWorks COM API extraction
# ---------------------------------------------------------------------------

swDocPART               = 1
swOpenDocOptions_Silent  = 1
swOpenDocOptions_ReadOnly = 2


def _connect_solidworks():
    """Connect to running SolidWorks or start a new hidden instance."""
    pythoncom.CoInitialize()
    try:
        swApp = win32com.client.GetActiveObject("SldWorks.Application")
        return swApp, True
    except Exception:
        pass
    try:
        swApp = win32com.client.Dispatch("SldWorks.Application")
        swApp.Visible = False
        return swApp, False
    except Exception as e:
        raise RuntimeError(
            f"Cannot connect to SolidWorks. Ensure SolidWorks 2025 is installed.\nError: {e}"
        )


def _extract_via_com(path):
    """Open SLDPRT via SolidWorks COM API and extract all data."""
    result = {
        "features": [], "mass_props": {}, "custom_props": {},
        "sw_metadata": {}, "config_name": None, "sw_version": None,
        "authors": [], "com_error": None,
    }
    swApp = None
    doc = None
    was_running = False

    try:
        swApp, was_running = _connect_solidworks()

        # Open document silently, read-only
        errors   = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = swApp.OpenDoc6(
            path, swDocPART,
            swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly,
            "", errors, warnings
        )

        if doc is None:
            result["com_error"] = f"OpenDoc6 returned None (error code={errors.value})"
            return result

        # Active configuration
        try:
            cfg = doc.GetActiveConfiguration()
            if cfg:
                result["config_name"] = cfg.Name
        except Exception:
            pass

        # SolidWorks version
        try:
            result["sw_version"] = swApp.RevisionNumber()
        except Exception:
            pass

        # ---- Feature tree ----
        try:
            feat = doc.FirstFeature()
            feature_list = []
            seen = set()
            while feat is not None:
                try:
                    fname = feat.Name or ""
                    try:
                        ftype = feat.GetTypeName2()
                    except Exception:
                        ftype = feat.GetTypeName() or "Unknown"
                    try:
                        fsuppressed = bool(feat.IsSuppressed2(0, None))
                    except Exception:
                        fsuppressed = False
                    created_by = None
                    try:
                        created_by = feat.CreatedBy
                    except Exception:
                        pass

                    key = f"{fname}::{ftype}"
                    if key not in seen:
                        seen.add(key)
                        feature_list.append({
                            "name": fname,
                            "type": ftype,
                            "suppressed": fsuppressed,
                            "created_by": created_by,
                        })
                        if created_by and created_by not in result["authors"]:
                            result["authors"].append(created_by)
                except Exception:
                    pass
                try:
                    feat = feat.GetNextFeature()
                except Exception:
                    break
            result["features"] = feature_list
        except Exception as e:
            result["com_error"] = f"Feature tree: {e}"

        # ---- Mass properties ----
        try:
            mp = doc.Extension.CreateMassProperty()
            if mp:
                mp.UseSystemUnits = True
                com_list = mp.CenterOfMass
                com = list(com_list) if com_list else [0.0, 0.0, 0.0]
                try:
                    moi = list(mp.GetMomentOfInertia(0))
                except Exception:
                    moi = []
                result["mass_props"] = {
                    "volume":         _safe_float(mp.Volume),
                    "surface_area":   _safe_float(mp.SurfaceArea),
                    "mass":           _safe_float(mp.Mass),
                    "density":        _safe_float(mp.Density),
                    "center_of_mass": com,
                    "moi":            moi,
                }
        except Exception as e1:
            try:
                status = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                mp2 = doc.GetMassProperties2(status)
                if mp2 and len(mp2) >= 6:
                    result["mass_props"] = {
                        "volume":         _safe_float(mp2[3]),
                        "surface_area":   _safe_float(mp2[4]),
                        "mass":           _safe_float(mp2[5]),
                        "density":        0.0,
                        "center_of_mass": [_safe_float(mp2[0]), _safe_float(mp2[1]), _safe_float(mp2[2])],
                        "moi":            list(mp2[6:]) if len(mp2) > 6 else [],
                    }
            except Exception as e2:
                result["mass_props"]["error"] = f"{e1} | {e2}"

        # ---- Custom properties ----
        try:
            mgr = doc.Extension.CustomPropertyManager("")
            if mgr:
                prop_names = mgr.GetNames()
                if prop_names:
                    for pname in prop_names:
                        try:
                            val_out  = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
                            rval_out = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, "")
                            mgr.Get5(pname, False, val_out, rval_out)
                            result["custom_props"][pname] = str(rval_out.value or val_out.value or "")
                        except Exception:
                            try:
                                result["custom_props"][pname] = str(mgr.Get(pname) or "")
                            except Exception:
                                pass
        except Exception as e:
            result["custom_props"]["_error"] = str(e)

        # ---- Document title ----
        try:
            result["sw_metadata"]["title"] = doc.GetTitle()
        except Exception:
            pass

    except Exception as e:
        result["com_error"] = str(e)
    finally:
        if doc is not None:
            try:
                swApp.CloseDoc(path)
            except Exception:
                pass
        if swApp is not None and not was_running:
            try:
                swApp.ExitApp()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def _compute_fingerprints(data):
    fp = {}
    fp["full_hash"] = data.get("full_hash", "")

    features = data.get("features", [])
    active   = [f for f in features if not f.get("suppressed", False)]

    # Feature sequence (ordered types)
    seq = "|".join(f["type"] for f in active)
    fp["feature_sequence_hash"] = _sha256_str(seq)[:16] if seq else ""

    # Feature set (sorted types)
    fset = "|".join(sorted(set(f["type"] for f in features)))
    fp["feature_set_hash"] = _sha256_str(fset)[:16] if fset else ""

    # Feature name sequence
    name_seq = "|".join(f["name"] for f in active)
    fp["feature_name_sequence_hash"] = _sha256_str(name_seq)[:16] if name_seq else ""

    # Geometry hash from mass properties
    mp = data.get("mass_props", {})
    if mp and _safe_float(mp.get("volume", 0)) > 0:
        geo_str = (
            f"{_safe_float(mp.get('volume',0)):.6f}|"
            f"{_safe_float(mp.get('surface_area',0)):.6f}|"
            f"{_safe_float(mp.get('mass',0)):.6f}|"
            f"{','.join(f'{v:.4f}' for v in mp.get('center_of_mass',[]))}"
        )
        fp["geometry_hash"] = _sha256_str(geo_str)[:16]
    else:
        fp["geometry_hash"] = ""

    # Custom properties hash
    cp = {k: v for k, v in data.get("custom_props", {}).items() if not k.startswith("_")}
    fp["custom_props_hash"] = _sha256_str(json.dumps(cp, sort_keys=True))[:16] if cp else ""

    # Feature type distribution
    type_counts = {}
    for f in features:
        t = f["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    fp["feature_type_counts"] = type_counts
    fp["feature_count"] = len(features)

    # Authors
    authors = set(data.get("authors", []))
    for k, v in cp.items():
        if any(kw in k.lower() for kw in ("author", "created", "designer", "drawn")):
            if v and len(v) < 100:
                authors.add(v.strip())
    fp["authors"] = sorted(authors)

    return fp


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def parse_sldprt(filepath):
    """
    Parse a SolidWorks .SLDPRT file using the SolidWorks COM API.

    Returns a dict with:
        file_path, file_name, fs_metadata, ole_metadata,
        features, mass_props, custom_props, sw_metadata,
        config_name, sw_version, authors, fingerprints,
        feature_type_counts, feature_count,
        full_hash, parse_error
    """
    filepath = os.path.abspath(filepath)

    result = {
        "file_path":    filepath,
        "file_name":    os.path.basename(filepath),
        "fs_metadata":  {},
        "ole_metadata": {},
        "features":     [],
        "mass_props":   {},
        "custom_props": {},
        "sw_metadata":  {},
        "config_name":  None,
        "sw_version":   None,
        "authors":      [],
        "fingerprints": {},
        "feature_type_counts": {},
        "feature_count": 0,
        "full_hash":    "",
        "parse_error":  None,
    }

    if not os.path.isfile(filepath):
        result["parse_error"] = f"File not found: {filepath}"
        return result

    # Always extract filesystem metadata and full file hash
    result["fs_metadata"] = _get_fs_metadata(filepath)
    result["full_hash"]   = _sha256_file(filepath)

    # OLE metadata (no SolidWorks needed)
    result["ole_metadata"] = _get_ole_metadata(filepath)
    for k in ("author", "last_author"):
        v = result["ole_metadata"].get(k)
        if v and v not in result["authors"]:
            result["authors"].append(v)

    # SolidWorks COM API extraction
    if _HAS_WIN32COM:
        try:
            com = _extract_via_com(filepath)
            if com.get("com_error"):
                result["parse_error"] = com["com_error"]
            else:
                result["features"]     = com["features"]
                result["mass_props"]   = com["mass_props"]
                result["custom_props"] = com["custom_props"]
                result["sw_metadata"]  = com["sw_metadata"]
                result["config_name"]  = com["config_name"]
                result["sw_version"]   = com["sw_version"]
                for a in com.get("authors", []):
                    if a and a not in result["authors"]:
                        result["authors"].append(a)
        except Exception as e:
            result["parse_error"] = f"COM extraction failed: {e}"
    else:
        result["parse_error"] = (
            "pywin32 not installed — install with: pip install pywin32\n"
            "OLE metadata extracted as fallback only."
        )

    # Compute fingerprints
    result["fingerprints"] = _compute_fingerprints({
        "full_hash":    result["full_hash"],
        "features":     result["features"],
        "mass_props":   result["mass_props"],
        "custom_props": result["custom_props"],
        "authors":      result["authors"],
    })
    result["feature_type_counts"] = result["fingerprints"]["feature_type_counts"]
    result["feature_count"]       = result["fingerprints"]["feature_count"]

    return result
