"""
Report Generator and CSV Exporter
===================================
Generates structured CSV reports from plagiarism comparison results.
"""

import csv
import os
import datetime
from typing import Optional
from .sldprt_parser import format_datetime
from .similarity_engine import similarity_percentage


def _safe(val, default="N/A") -> str:
    """Safely convert a value to string."""
    if val is None:
        return default
    if isinstance(val, datetime.datetime):
        return format_datetime(val)
    return str(val).strip() or default


def export_pairwise_csv(comparison_results: list[dict],
                         parsed_files: list[dict],
                         output_path: str) -> str:
    """
    Export pairwise comparison results to CSV.
    Each row = one file pair with similarity scores and metadata.
    """
    fieldnames = [
        "File A",
        "File B",
        "Comparison Type",
        "Similarity Score (%)",
        "Risk Level",
        "Flags",
        # Dimension scores
        "Full Hash Match",
        "Geometry Hash Match",
        "Feature Sequence Match",
        "Feature Set Match",
        "Feature Count Similarity (%)",
        "Author Overlap Score",
        "Timestamp Proximity Score",
        "Username Overlap Score",
        # Shared indicators
        "Shared Authors",
        "Shared Usernames",
        # File A metadata
        "File A - OLE Author",
        "File A - Created (OLE)",
        "File A - Last Saved (OLE)",
        "File A - Last Printed (OLE)",
        "File A - FS Created",
        "File A - FS Modified",
        "File A - FS Accessed",
        "File A - File Size (bytes)",
        "File A - Feature Count",
        # File B metadata
        "File B - OLE Author",
        "File B - Created (OLE)",
        "File B - Last Saved (OLE)",
        "File B - Last Printed (OLE)",
        "File B - FS Created",
        "File B - FS Modified",
        "File B - FS Accessed",
        "File B - File Size (bytes)",
        "File B - Feature Count",
        # Notes
        "Detection Notes",
    ]
    
    # Build a lookup dict for parsed files
    parsed_lookup = {p["file_name"]: p for p in parsed_files}
    
    rows = []
    for cmp in comparison_results:
        pa = parsed_lookup.get(cmp["file_a"], {})
        pb = parsed_lookup.get(cmp["file_b"], {})
        
        ole_a = pa.get("ole_metadata", {})
        ole_b = pb.get("ole_metadata", {})
        fs_a  = pa.get("fs_metadata", {})
        fs_b  = pb.get("fs_metadata", {})
        sc    = cmp.get("scores", {})
        
        notes = "; ".join(cmp.get("details", {}).values())
        
        row = {
            "File A":                       cmp["file_a"],
            "File B":                       cmp["file_b"],
            "Comparison Type":              cmp.get("comparison_type", "student_vs_student"),
            "Similarity Score (%)":         similarity_percentage(cmp["composite_score"]),
            "Risk Level":                   cmp["risk_level"],
            "Flags":                        " | ".join(cmp.get("flags", [])),
            "Full Hash Match":              "YES" if sc.get("full_hash_match", 0) >= 1.0 else "NO",
            "Geometry Hash Match":          "YES" if sc.get("geometry_hash_match", 0) >= 1.0 else "NO",
            "Feature Sequence Match":       "YES" if sc.get("feature_sequence_match", 0) >= 1.0 else "NO",
            "Feature Set Match":            "YES" if sc.get("feature_set_match", 0) >= 1.0 else "NO",
            "Feature Count Similarity (%)": f"{sc.get('feature_count_cosine', 0)*100:.1f}%",
            "Author Overlap Score":         f"{sc.get('author_overlap', 0):.3f}",
            "Timestamp Proximity Score":    f"{sc.get('timestamp_proximity', 0):.3f}",
            "Username Overlap Score":       f"{sc.get('username_overlap', 0):.3f}",
            "Shared Authors":               ", ".join(cmp.get("shared_authors", [])),
            "Shared Usernames":             ", ".join(cmp.get("shared_usernames", [])[:10]),
            # File A metadata
            "File A - OLE Author":          _safe(ole_a.get("author")),
            "File A - Created (OLE)":       _safe(ole_a.get("created")),
            "File A - Last Saved (OLE)":    _safe(ole_a.get("last_saved")),
            "File A - Last Printed (OLE)":  _safe(ole_a.get("last_printed")),
            "File A - FS Created":          _safe(fs_a.get("fs_created")),
            "File A - FS Modified":         _safe(fs_a.get("fs_modified")),
            "File A - FS Accessed":         _safe(fs_a.get("fs_accessed")),
            "File A - File Size (bytes)":   _safe(fs_a.get("file_size_bytes")),
            "File A - Feature Count":       str(len(pa.get("features", []))),
            # File B metadata
            "File B - OLE Author":          _safe(ole_b.get("author")),
            "File B - Created (OLE)":       _safe(ole_b.get("created")),
            "File B - Last Saved (OLE)":    _safe(ole_b.get("last_saved")),
            "File B - Last Printed (OLE)":  _safe(ole_b.get("last_printed")),
            "File B - FS Created":          _safe(fs_b.get("fs_created")),
            "File B - FS Modified":         _safe(fs_b.get("fs_modified")),
            "File B - FS Accessed":         _safe(fs_b.get("fs_accessed")),
            "File B - File Size (bytes)":   _safe(fs_b.get("file_size_bytes")),
            "File B - Feature Count":       str(len(pb.get("features", []))),
            "Detection Notes":              notes,
        }
        rows.append(row)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return output_path


def export_metadata_csv(parsed_files: list[dict], output_path: str) -> str:
    """
    Export per-file metadata to CSV.
    Each row = one student file with all extracted metadata.
    """
    fieldnames = [
        "File Name",
        "File Path",
        "File Size (bytes)",
        # OLE metadata
        "OLE Author",
        "OLE Last Author",
        "OLE App Name",
        "OLE Revision",
        "OLE Company",
        "OLE Category",
        "Date Created (OLE)",
        "Date Last Saved (OLE)",
        "Date Last Printed (OLE)",
        # Filesystem metadata
        "FS Date Created",
        "FS Date Modified",
        "FS Date Accessed",
        # Feature info
        "Total Features Detected",
        "Feature Types",
        # Fingerprints
        "Full File Hash (SHA-256)",
        "Geometry Hash (SHA-256)",
        "Feature Sequence Hash (MD5)",
        "Feature Set Hash (MD5)",
        # Parse status
        "Parse Status",
    ]
    
    rows = []
    for p in parsed_files:
        ole = p.get("ole_metadata", {})
        fs  = p.get("fs_metadata", {})
        fp  = p.get("fingerprints", {})
        
        feature_types_str = ", ".join(
            f"{k}:{v}" for k, v in sorted(p.get("feature_type_counts", {}).items())
        )
        
        row = {
            "File Name":                p["file_name"],
            "File Path":                p["file_path"],
            "File Size (bytes)":        _safe(fs.get("file_size_bytes")),
            "OLE Author":               _safe(ole.get("author")),
            "OLE Last Author":          _safe(ole.get("last_author")),
            "OLE App Name":             _safe(ole.get("app_name")),
            "OLE Revision":             _safe(ole.get("revision")),
            "OLE Company":              _safe(ole.get("company")),
            "OLE Category":             _safe(ole.get("category")),
            "Date Created (OLE)":       _safe(ole.get("created")),
            "Date Last Saved (OLE)":    _safe(ole.get("last_saved")),
            "Date Last Printed (OLE)":  _safe(ole.get("last_printed")),
            "FS Date Created":          _safe(fs.get("fs_created")),
            "FS Date Modified":         _safe(fs.get("fs_modified")),
            "FS Date Accessed":         _safe(fs.get("fs_accessed")),
            "Total Features Detected":  str(len(p.get("features", []))),
            "Feature Types":            feature_types_str or "N/A",
            "Full File Hash (SHA-256)": fp.get("full_hash", "N/A") or "N/A",
            "Geometry Hash (SHA-256)":  fp.get("geometry_hash", "N/A") or "N/A",
            "Feature Sequence Hash (MD5)": fp.get("feature_sequence_hash", "N/A") or "N/A",
            "Feature Set Hash (MD5)":   fp.get("feature_set_hash", "N/A") or "N/A",
            "Parse Status":             "OK" if not p.get("parse_error") else f"ERROR: {p['parse_error']}",
        }
        rows.append(row)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return output_path


def export_feature_detail_csv(parsed_files: list[dict], output_path: str) -> str:
    """
    Export per-feature detail for all files.
    Each row = one feature from one file.
    """
    fieldnames = [
        "File Name",
        "Feature Name",
        "Feature Type",
        "Creator",
        "Date Created",
        "Date Modified",
        "Stream Source",
    ]
    
    rows = []
    for p in parsed_files:
        for f in p.get("features", []):
            row = {
                "File Name":    p["file_name"],
                "Feature Name": f.get("feature_name", "N/A"),
                "Feature Type": f.get("feature_type", "N/A"),
                "Creator":      f.get("creator") or "N/A",
                "Date Created": _safe(f.get("date_created")),
                "Date Modified": _safe(f.get("date_modified")),
                "Stream Source": f.get("stream", "N/A"),
            }
            rows.append(row)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return output_path


def generate_summary_report(comparison_results: list[dict],
                              parsed_files: list[dict],
                              output_dir: str,
                              session_name: str = None) -> dict:
    """
    Generate all three CSV reports and return their paths.
    """
    if session_name is None:
        session_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    os.makedirs(output_dir, exist_ok=True)
    
    paths = {
        "pairwise":   os.path.join(output_dir, f"plagiarism_pairwise_{session_name}.csv"),
        "metadata":   os.path.join(output_dir, f"file_metadata_{session_name}.csv"),
        "features":   os.path.join(output_dir, f"feature_details_{session_name}.csv"),
    }
    
    export_pairwise_csv(comparison_results, parsed_files, paths["pairwise"])
    export_metadata_csv(parsed_files, paths["metadata"])
    export_feature_detail_csv(parsed_files, paths["features"])
    
    return paths
