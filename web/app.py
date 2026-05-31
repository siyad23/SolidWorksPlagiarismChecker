"""
SolidWorks Plagiarism Checker — Web Application
=================================================
FastAPI-based web interface with two analysis modes:
  1. Part Analysis   — Upload individual .sldprt files (one per student)
  2. Assembly Analysis — Upload Pack and Go .zip files (one per student)

Student identity is determined by the filename.

Run with:
  python -m web.app
  uvicorn web.app:app --reload --port 8000
"""

import os
import uuid
import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import Request

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
REPORT_DIR = BASE_DIR / "reports"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="SolidWorks Plagiarism Checker",
    description="Detect plagiarism in SolidWorks assignment files",
    version="0.2.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory session store
_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student_name_from_filename(filename: str) -> str:
    """Extract student name from filename (primary identifier)."""
    import re
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[_.]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _make_session(session_id, parsed_files, results, clusters, pdf_path, csv_paths,
                  mode="parts", submissions=None):
    """Store session data."""
    _sessions[session_id] = {
        "parsed_files": parsed_files,
        "results": results,
        "clusters": clusters,
        "pdf_path": pdf_path,
        "csv_paths": csv_paths,
        "mode": mode,
        "submissions": submissions,
        "created": datetime.datetime.now().isoformat(),
    }


def _generate_reports(session_id, results, parsed_files, clusters):
    """Generate PDF and CSV reports. Returns (pdf_path, csv_paths)."""
    from sw_plagiarism_checker.report_generator import generate_pdf_report, generate_summary_report

    report_dir = REPORT_DIR / session_id
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    pdf_path = str(report_dir / f"plagiarism_report_{ts}.pdf")
    generate_pdf_report(results, parsed_files, pdf_path, clusters=clusters)

    csv_paths = generate_summary_report(
        results, parsed_files, str(report_dir), ts, include_pdf=False, clusters=clusters
    )
    return pdf_path, csv_paths


# ---------------------------------------------------------------------------
# Part Analysis API
# ---------------------------------------------------------------------------

@app.post("/api/upload/parts")
async def upload_parts(files: list[UploadFile] = File(...)):
    """
    Part Analysis: Upload individual .sldprt files.
    Each file = one student. Student name = filename.
    """
    from sw_plagiarism_checker import (
        parse_sw_file, batch_compare, detect_clusters, SUPPORTED_EXTENSIONS
    )

    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save and parse files
    parsed_files = []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        dest = session_dir / f.filename
        with open(dest, "wb") as out:
            out.write(await f.read())

        parsed = parse_sw_file(str(dest))
        # Primary identifier = filename
        parsed["uploader_name"] = _student_name_from_filename(f.filename)
        parsed_files.append(parsed)

    if not parsed_files:
        raise HTTPException(400, "No valid SolidWorks files uploaded (.sldprt, .sldasm)")

    # Compare
    results = batch_compare(parsed_files)
    clusters = detect_clusters(results)

    # Reports
    pdf_path, csv_paths = _generate_reports(session_id, results, parsed_files, clusters)
    _make_session(session_id, parsed_files, results, clusters, pdf_path, csv_paths, mode="parts")

    return JSONResponse(_build_parts_response(session_id, parsed_files, results))


# ---------------------------------------------------------------------------
# Assembly Analysis API
# ---------------------------------------------------------------------------

@app.post("/api/upload/assemblies")
async def upload_assemblies(files: list[UploadFile] = File(...)):
    """
    Assembly Analysis: Upload Pack and Go .zip files.
    Each ZIP = one student's submission. Student name = ZIP filename.
    """
    from sw_plagiarism_checker import parse_sw_file, compare_files, detect_clusters
    from sw_plagiarism_checker.zip_handler import (
        extract_pack_and_go, parse_submission,
        batch_compare_submissions,
    )

    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save ZIP files
    zip_paths = []
    for f in files:
        if not f.filename.lower().endswith('.zip'):
            continue
        dest = session_dir / f.filename
        with open(dest, "wb") as out:
            out.write(await f.read())
        zip_paths.append(str(dest))

    if not zip_paths:
        raise HTTPException(400, "No ZIP files uploaded. Upload Pack and Go .zip files.")

    # Extract and parse each ZIP
    submissions = []
    all_parsed_files = []
    for zp in zip_paths:
        zip_info = extract_pack_and_go(zp, str(session_dir / "_extracted"))
        if zip_info.get('error'):
            continue
        sub = parse_submission(zip_info, parse_sw_file)
        if sub.get('error'):
            continue
        submissions.append(sub)
        all_parsed_files.extend(sub['parsed_files'])

    if len(submissions) < 2:
        raise HTTPException(400, f"Need at least 2 valid submissions. Got {len(submissions)}.")

    # Compare submissions pairwise
    results = batch_compare_submissions(submissions, compare_files)
    clusters = detect_clusters(results)

    # Reports
    pdf_path, csv_paths = _generate_reports(session_id, results, all_parsed_files, clusters)
    _make_session(session_id, all_parsed_files, results, clusters, pdf_path, csv_paths,
                  mode="assemblies", submissions=submissions)

    return JSONResponse(_build_assembly_response(session_id, submissions, results))


# ---------------------------------------------------------------------------
# Google Drive (kept for backward compat)
# ---------------------------------------------------------------------------

@app.post("/api/drive")
async def analyze_drive(drive_url: str = Form(...)):
    """Download files from Google Drive and run part analysis."""
    from sw_plagiarism_checker import parse_sw_file, batch_compare, detect_clusters
    from sw_plagiarism_checker.drive_downloader import download_from_drive

    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloaded = download_from_drive(drive_url, output_dir=str(session_dir))
    except Exception as e:
        raise HTTPException(400, f"Drive download failed: {e}")

    if not downloaded:
        raise HTTPException(400, "No SolidWorks files found in Drive folder")

    parsed_files = []
    for p in downloaded:
        parsed = parse_sw_file(p)
        parsed["uploader_name"] = _student_name_from_filename(os.path.basename(p))
        parsed_files.append(parsed)

    results = batch_compare(parsed_files)
    clusters = detect_clusters(results)

    pdf_path, csv_paths = _generate_reports(session_id, results, parsed_files, clusters)
    _make_session(session_id, parsed_files, results, clusters, pdf_path, csv_paths)

    return JSONResponse(_build_parts_response(session_id, parsed_files, results))


# ---------------------------------------------------------------------------
# Report Downloads
# ---------------------------------------------------------------------------

@app.get("/api/report/{session_id}/pdf")
async def download_pdf(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    pdf_path = session.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(404, "PDF report not found")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"plagiarism_report_{session_id}.pdf")


@app.get("/api/report/{session_id}/csv")
async def download_csv(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    csv_paths = session.get("csv_paths", {})
    pairwise = csv_paths.get("pairwise")
    if not pairwise or not os.path.exists(pairwise):
        raise HTTPException(404, "CSV report not found")
    return FileResponse(pairwise, media_type="text/csv",
                        filename=f"plagiarism_pairwise_{session_id}.csv")


# ---------------------------------------------------------------------------
# Response Builders
# ---------------------------------------------------------------------------

def _build_parts_response(session_id, parsed_files, results):
    """Build response for Part Analysis mode."""
    from sw_plagiarism_checker import get_risk_color

    files_info = []
    for p in parsed_files:
        files_info.append({
            "file_name": p["file_name"],
            "student_name": p.get("uploader_name") or "Unknown",
            "file_type": p.get("file_type", ""),
            "feature_count": p.get("feature_count", 0),
            "file_size": p.get("fs_metadata", {}).get("file_size_bytes", 0),
            "parse_error": p.get("parse_error"),
        })

    comparisons = _format_comparisons(results)
    clusters = _format_clusters(session_id)
    summary = _format_summary(parsed_files, results)

    return {
        "session_id": session_id,
        "mode": "parts",
        "files": files_info,
        "comparisons": comparisons,
        "clusters": clusters,
        "summary": summary,
    }


def _build_assembly_response(session_id, submissions, results):
    """Build response for Assembly Analysis mode."""
    from sw_plagiarism_checker import get_risk_color

    subs_info = []
    for s in submissions:
        subs_info.append({
            "student_name": s["student_name"],
            "zip_filename": s["zip_filename"],
            "total_parts": s["total_parts"],
            "total_features": s["total_features"],
            "assembly_count": len(s.get("assembly_parsed", [])),
            "error": s.get("error"),
        })

    comparisons = []
    for r in results:
        comp = {
            "student_a": r.get("student_a", r.get("file_a", "")),
            "student_b": r.get("student_b", r.get("file_b", "")),
            "file_a": r.get("file_a", ""),
            "file_b": r.get("file_b", ""),
            "score": round(r["composite_score"] * 100, 1),
            "risk_level": r["risk_level"],
            "risk_color": get_risk_color(r["risk_level"]),
            "flags": r.get("flags", []),
            "assembly_similarity": round(r.get("assembly_similarity", 0) * 100, 1),
            "part_similarity": round(r.get("part_similarity", 0) * 100, 1),
            "part_matches": r.get("part_matches", []),
        }
        # Format part match scores
        for pm in comp["part_matches"]:
            pm["score"] = round(pm.get("score", 0) * 100, 1)
        comparisons.append(comp)

    clusters = _format_clusters(session_id)

    all_parsed = []
    for s in submissions:
        all_parsed.extend(s.get("parsed_files", []))

    return {
        "session_id": session_id,
        "mode": "assemblies",
        "submissions": subs_info,
        "comparisons": comparisons,
        "clusters": clusters,
        "summary": {
            "total_submissions": len(submissions),
            "total_pairs": len(results),
            "high_risk": sum(1 for r in results if r["risk_level"] == "HIGH"),
            "medium_risk": sum(1 for r in results if r["risk_level"] == "MEDIUM"),
            "low_risk": sum(1 for r in results if r["risk_level"] == "LOW"),
            "clean": sum(1 for r in results if r["risk_level"] == "NONE"),
        },
    }


def _format_comparisons(results):
    from sw_plagiarism_checker import get_risk_color
    comparisons = []
    for r in results:
        comparisons.append({
            "file_a": r["file_a"],
            "file_b": r["file_b"],
            "score": round(r["composite_score"] * 100, 1),
            "risk_level": r["risk_level"],
            "risk_color": get_risk_color(r["risk_level"]),
            "flags": r.get("flags", []),
            "shared_authors": r.get("shared_authors", []),
            "scores": {k: round(v * 100, 1) for k, v in r.get("scores", {}).items()},
        })
    return comparisons


def _format_clusters(session_id):
    session = _sessions.get(session_id, {})
    clusters_data = []
    for c in session.get("clusters", []):
        clusters_data.append({
            "files": c.get("files", []),
            "size": c.get("size", 0),
            "max_score": round(c.get("max_score", 0) * 100, 1),
        })
    return clusters_data


def _format_summary(parsed_files, results):
    return {
        "total_files": len(parsed_files),
        "total_pairs": len(results),
        "high_risk": sum(1 for r in results if r["risk_level"] == "HIGH"),
        "medium_risk": sum(1 for r in results if r["risk_level"] == "MEDIUM"),
        "low_risk": sum(1 for r in results if r["risk_level"] == "LOW"),
        "clean": sum(1 for r in results if r["risk_level"] == "NONE"),
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("\n  SolidWorks Plagiarism Checker — Web App")
    print("  http://localhost:8000\n")
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
