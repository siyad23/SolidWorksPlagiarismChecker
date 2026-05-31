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
                              session_name: str = None,
                              include_pdf: bool = True,
                              clusters: list = None) -> dict:
    """
    Generate all reports and return their paths.
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

    if include_pdf:
        pdf_path = os.path.join(output_dir, f"plagiarism_report_{session_name}.pdf")
        generate_pdf_report(comparison_results, parsed_files, pdf_path, clusters=clusters)
        paths["pdf"] = pdf_path
    
    return paths


# ---------------------------------------------------------------------------
# PDF Report Generator (FPDF2)
# ---------------------------------------------------------------------------

def _ensure_fpdf():
    try:
        from fpdf import FPDF
        return FPDF
    except ImportError:
        raise ImportError(
            "PDF report generation requires fpdf2.\n"
            "Install with:  pip install fpdf2"
        )


def generate_pdf_report(comparison_results: list[dict],
                         parsed_files: list[dict],
                         output_path: str,
                         clusters: list = None) -> str:
    """
    Generate a professional PDF plagiarism report.
    """
    from fpdf import FPDF

    # ---- Risk color mapping ----
    RISK_COLORS = {
        "HIGH":   (255, 77, 109),
        "MEDIUM": (255, 159, 67),
        "LOW":    (255, 209, 102),
        "NONE":   (6, 214, 160),
    }
    RISK_BG = {
        "HIGH":   (60, 20, 25),
        "MEDIUM": (60, 40, 15),
        "LOW":    (50, 45, 20),
        "NONE":   (15, 45, 35),
    }

    class PlagiarismReport(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(140, 140, 150)
                self.cell(0, 8, "SolidWorks Plagiarism Checker Report", align="L")
                self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
                self.set_draw_color(60, 60, 80)
                self.line(10, self.get_y(), self.w - 10, self.get_y())
                self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(100, 100, 110)
            self.cell(0, 10, "Generated by SolidWorks Plagiarism Checker — github.com/siyad23/SolidWorksPlagiarismChecker", align="C")

    pdf = PlagiarismReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)

    # ============================================================
    # COVER PAGE
    # ============================================================
    pdf.add_page()
    pdf.set_fill_color(10, 10, 18)
    pdf.rect(0, 0, 210, 297, "F")

    # Title block
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(230, 230, 245)
    pdf.cell(0, 15, "Plagiarism Report", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(140, 140, 170)
    pdf.cell(0, 10, "SolidWorks File Similarity Analysis", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)
    pdf.set_draw_color(80, 80, 120)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(20)

    # Stats
    total_files = len(parsed_files)
    total_pairs = len(comparison_results)
    high_risk = sum(1 for c in comparison_results if c["risk_level"] == "HIGH")
    medium_risk = sum(1 for c in comparison_results if c["risk_level"] == "MEDIUM")

    stats = [
        ("Files Analyzed", str(total_files)),
        ("Pairs Compared", str(total_pairs)),
        ("High Risk Pairs", str(high_risk)),
        ("Medium Risk Pairs", str(medium_risk)),
        ("Report Date", datetime.datetime.now().strftime("%B %d, %Y  %H:%M")),
    ]

    pdf.set_font("Helvetica", "", 12)
    for label, value in stats:
        pdf.set_text_color(120, 120, 140)
        pdf.cell(85, 10, f"  {label}", align="R")
        pdf.set_text_color(220, 220, 240)
        pdf.cell(0, 10, f"  {value}", align="L", new_x="LMARGIN", new_y="NEXT")

    # ============================================================
    # SUMMARY TABLE
    # ============================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(230, 230, 245)
    pdf.cell(0, 12, "Similarity Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if comparison_results:
        # Table header
        col_widths = [55, 55, 28, 22, 30]
        headers = ["File A", "File B", "Score", "Risk", "Flags"]

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(30, 30, 50)
        pdf.set_text_color(180, 180, 200)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 8, f" {h}", border=0, fill=True)
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 8)
        for idx, cmp in enumerate(comparison_results):
            risk = cmp["risk_level"]
            bg = RISK_BG.get(risk, (25, 25, 35))
            fg = RISK_COLORS.get(risk, (180, 180, 200))

            if idx % 2 == 0:
                pdf.set_fill_color(bg[0], bg[1], bg[2])
            else:
                pdf.set_fill_color(max(0, bg[0]-5), max(0, bg[1]-5), max(0, bg[2]-5))

            pdf.set_text_color(200, 200, 215)

            # Truncate long filenames
            fa = cmp["file_a"][:24] + "…" if len(cmp["file_a"]) > 25 else cmp["file_a"]
            fb = cmp["file_b"][:24] + "…" if len(cmp["file_b"]) > 25 else cmp["file_b"]

            pdf.cell(col_widths[0], 7, f" {fa}", fill=True)
            pdf.cell(col_widths[1], 7, f" {fb}", fill=True)

            score_str = f"{cmp['composite_score']*100:.1f}%"
            pdf.set_text_color(fg[0], fg[1], fg[2])
            pdf.cell(col_widths[2], 7, f" {score_str}", fill=True)

            pdf.cell(col_widths[3], 7, f" {risk}", fill=True)

            pdf.set_text_color(160, 160, 180)
            flag_count = str(len(cmp.get("flags", [])))
            pdf.cell(col_widths[4], 7, f" {flag_count} flag(s)", fill=True)
            pdf.ln()

            # Page break check
            if pdf.get_y() > 265:
                pdf.add_page()
    else:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(140, 140, 160)
        pdf.cell(0, 10, "No comparison results to display.", new_x="LMARGIN", new_y="NEXT")

    # ============================================================
    # DETAILED ANALYSIS (for MEDIUM+ risk pairs)
    # ============================================================
    flagged = [c for c in comparison_results if c["risk_level"] in ("HIGH", "MEDIUM")]

    if flagged:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 77, 109)
        pdf.cell(0, 12, "Flagged Pairs — Detailed Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        parsed_lookup = {p["file_name"]: p for p in parsed_files}

        for cmp in flagged:
            if pdf.get_y() > 220:
                pdf.add_page()

            risk = cmp["risk_level"]
            fg = RISK_COLORS.get(risk, (200, 200, 200))

            # Pair header
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(fg[0], fg[1], fg[2])
            pdf.cell(0, 8, f"{cmp['file_a']}  vs  {cmp['file_b']}", new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(180, 180, 200)
            score_pct = f"{cmp['composite_score']*100:.1f}%"
            pdf.cell(0, 6, f"Composite Score: {score_pct}  |  Risk: {risk}", new_x="LMARGIN", new_y="NEXT")

            # Uploader names
            pa = parsed_lookup.get(cmp["file_a"], {})
            pb = parsed_lookup.get(cmp["file_b"], {})
            name_a = pa.get("uploader_name") or pa.get("ole_metadata", {}).get("author") or "Unknown"
            name_b = pb.get("uploader_name") or pb.get("ole_metadata", {}).get("author") or "Unknown"
            pdf.cell(0, 6, f"Uploader A: {name_a}  |  Uploader B: {name_b}", new_x="LMARGIN", new_y="NEXT")

            # Signal scores
            pdf.ln(2)
            scores = cmp.get("scores", {})
            signal_labels = {
                "full_hash_match": "Full File Hash",
                "feature_sequence_lcs": "Feature Sequence (LCS)",
                "feature_name_lcs": "Feature Names (LCS)",
                "feature_ngram_similarity": "Feature N-Grams",
                "feature_set_jaccard": "Feature Set (Jaccard)",
                "geometry_vector_similarity": "Geometry Vector",
                "moi_similarity": "Shape Signature (MOI)",
                "mass_props_similarity": "Mass Properties",
                "param_similarity": "Feature Parameters",
                "custom_props_match": "Custom Properties",
                "author_overlap": "Author Overlap",
                "timestamp_proximity": "Timestamp Proximity",
                "feature_distribution": "Feature Distribution",
            }

            pdf.set_font("Helvetica", "", 8)
            for sig_key, sig_label in signal_labels.items():
                val = scores.get(sig_key, 0)
                pct = f"{val*100:.0f}%"

                pdf.set_text_color(140, 140, 160)
                pdf.cell(50, 5, f"  {sig_label}", align="L")

                # Color code the value
                if val >= 0.9:
                    pdf.set_text_color(255, 77, 109)
                elif val >= 0.5:
                    pdf.set_text_color(255, 159, 67)
                else:
                    pdf.set_text_color(6, 214, 160)
                pdf.cell(20, 5, pct, align="R")

                # Simple bar
                bar_w = val * 60
                y = pdf.get_y() + 1
                x = pdf.get_x() + 5
                pdf.set_fill_color(40, 40, 55)
                pdf.rect(x, y, 60, 3, "F")
                if val >= 0.9:
                    pdf.set_fill_color(255, 77, 109)
                elif val >= 0.5:
                    pdf.set_fill_color(255, 159, 67)
                else:
                    pdf.set_fill_color(6, 214, 160)
                if bar_w > 0:
                    pdf.rect(x, y, bar_w, 3, "F")
                pdf.ln()

            # Flags
            flags = cmp.get("flags", [])
            if flags:
                pdf.ln(1)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(255, 159, 67)
                pdf.cell(0, 5, f"  Flags: {', '.join(flags)}", new_x="LMARGIN", new_y="NEXT")

            # Shared authors
            shared = cmp.get("shared_authors", [])
            if shared:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(255, 77, 109)
                pdf.cell(0, 5, f"  Shared Authors: {', '.join(shared)}", new_x="LMARGIN", new_y="NEXT")

            pdf.ln(6)
            pdf.set_draw_color(50, 50, 70)
            pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
            pdf.ln(4)

    # ============================================================
    # PLAGIARISM CLUSTERS
    # ============================================================
    if clusters:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(255, 159, 67)
        pdf.cell(0, 12, "Plagiarism Clusters", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(160, 160, 180)
        pdf.cell(0, 6, "Groups of files connected by high similarity scores (potential copy rings)",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        for idx, cluster in enumerate(clusters):
            if pdf.get_y() > 230:
                pdf.add_page()

            max_score = cluster.get("max_score", 0)
            if max_score >= 0.75:
                color = (255, 77, 109)
            elif max_score >= 0.45:
                color = (255, 159, 67)
            else:
                color = (255, 209, 102)

            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(color[0], color[1], color[2])
            pdf.cell(0, 8, f"Cluster {idx + 1}  ({cluster.get('size', 0)} files, "
                           f"max similarity: {max_score*100:.1f}%)",
                     new_x="LMARGIN", new_y="NEXT")

            # List files in cluster
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(180, 180, 200)
            for fname in cluster.get("files", []):
                pdf.cell(0, 5, f"    • {fname}", new_x="LMARGIN", new_y="NEXT")

            # List pairs
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(140, 140, 160)
            for pair in cluster.get("pairs", []):
                score_pct = f"{pair['score']*100:.1f}%"
                pdf.cell(0, 5, f"      {pair['file_a']}  ↔  {pair['file_b']}  ({score_pct})",
                         new_x="LMARGIN", new_y="NEXT")

            pdf.ln(4)
            pdf.set_draw_color(50, 50, 70)
            pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
            pdf.ln(4)

    # ============================================================
    # PER-FILE METADATA APPENDIX
    # ============================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(230, 230, 245)
    pdf.cell(0, 12, "File Metadata Appendix", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for p in parsed_files:
        if pdf.get_y() > 240:
            pdf.add_page()

        ole = p.get("ole_metadata", {})
        fs = p.get("fs_metadata", {})
        uploader = p.get("uploader_name") or "Unknown"

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(200, 200, 230)
        pdf.cell(0, 7, p["file_name"], new_x="LMARGIN", new_y="NEXT")

        meta_rows = [
            ("Uploader", uploader),
            ("File Type", p.get("file_type", "N/A")),
            ("OLE Author", _safe(ole.get("author"))),
            ("OLE Last Author", _safe(ole.get("last_author"))),
            ("Created (OLE)", _safe(ole.get("created"))),
            ("Last Saved (OLE)", _safe(ole.get("last_saved"))),
            ("File Size", f"{fs.get('file_size_bytes', 0):,} bytes"),
            ("Features", str(p.get("feature_count", 0))),
            ("Config", _safe(p.get("config_name"))),
            ("SW Version", _safe(p.get("sw_version"))),
            ("Full Hash", (p.get("full_hash", "")[:32] + "…") if p.get("full_hash") else "N/A"),
        ]

        pdf.set_font("Helvetica", "", 8)
        for label, value in meta_rows:
            pdf.set_text_color(120, 120, 140)
            pdf.cell(40, 5, f"  {label}", align="L")
            pdf.set_text_color(180, 180, 200)
            pdf.cell(0, 5, str(value), align="L", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)
        pdf.set_draw_color(40, 40, 60)
        pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
        pdf.ln(3)

    # ---- Save ----
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pdf.output(output_path)
    return output_path
