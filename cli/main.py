#!/usr/bin/env python3
"""
SolidWorks Plagiarism Checker — CLI
====================================
A command-line tool for detecting plagiarism in SolidWorks assignment files.

Usage
-----
  sw-plagiarism-checker --folder ./assignments
  sw-plagiarism-checker --drive "https://drive.google.com/drive/folders/..."
  sw-plagiarism-checker --folder ./assignments --format both --threshold 0.5
"""

import argparse
import os
import sys
import glob
import datetime

# ---------------------------------------------------------------------------
# Optional pretty-printing deps
# ---------------------------------------------------------------------------
try:
    from tqdm import tqdm
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False
    class _Dummy:
        RED = YELLOW = GREEN = CYAN = WHITE = MAGENTA = RESET = ""
        BRIGHT = DIM = RESET_ALL = ""
    Fore = Style = _Dummy()


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _risk_color(risk: str) -> str:
    return {
        "HIGH": Fore.RED,
        "MEDIUM": Fore.YELLOW,
        "LOW": Fore.YELLOW,
        "NONE": Fore.GREEN,
    }.get(risk, "")


def _print_banner():
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════╗
║        SolidWorks Plagiarism Checker  v0.1.0         ║
║   Detect copied assignments • Export PDF reports     ║
╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def _print_summary(results, parsed_files, threshold, clusters=None):
    """Print a colored console summary table."""
    high = sum(1 for r in results if r["risk_level"] == "HIGH")
    medium = sum(1 for r in results if r["risk_level"] == "MEDIUM")
    low = sum(1 for r in results if r["risk_level"] == "LOW")
    clean = sum(1 for r in results if r["risk_level"] == "NONE")

    print(f"\n{Style.BRIGHT}{'='*60}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}  ANALYSIS COMPLETE{Style.RESET_ALL}")
    print(f"{'='*60}")
    print(f"  Files analyzed:  {len(parsed_files)}")
    print(f"  Pairs compared:  {len(results)}")
    print(f"  Threshold:       {threshold*100:.0f}%")
    print()
    print(f"  {Fore.RED}■ HIGH risk:    {high}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}■ MEDIUM risk:  {medium}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}■ LOW risk:     {low}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}■ CLEAN:        {clean}{Style.RESET_ALL}")
    print(f"{'='*60}\n")

    # Top flagged pairs
    flagged = [r for r in results if r["composite_score"] >= threshold]
    if flagged:
        print(f"{Style.BRIGHT}  Flagged Pairs (score ≥ {threshold*100:.0f}%):{Style.RESET_ALL}\n")
        print(f"  {'File A':<28} {'File B':<28} {'Score':>7}  {'Risk':<8}")
        print(f"  {'─'*28} {'─'*28} {'─'*7}  {'─'*8}")
        for r in flagged:
            color = _risk_color(r["risk_level"])
            fa = r["file_a"][:27] + "…" if len(r["file_a"]) > 28 else r["file_a"]
            fb = r["file_b"][:27] + "…" if len(r["file_b"]) > 28 else r["file_b"]
            score_str = f"{r['composite_score']*100:.1f}%"
            print(f"  {fa:<28} {fb:<28} {color}{score_str:>7}{Style.RESET_ALL}  {color}{r['risk_level']:<8}{Style.RESET_ALL}")
        print()
    else:
        print(f"  {Fore.GREEN}✓ No pairs exceeded the threshold.{Style.RESET_ALL}\n")

    # Show clusters
    if clusters:
        print(f"\n  {Style.BRIGHT}Plagiarism Clusters:{Style.RESET_ALL}")
        for idx, cluster in enumerate(clusters):
            max_pct = f"{cluster['max_score']*100:.1f}%"
            files_str = ', '.join(cluster['files'])
            color = Fore.RED if cluster['max_score'] >= 0.75 else Fore.YELLOW
            print(f"    {color}Cluster {idx+1}{Style.RESET_ALL}: {files_str}")
            print(f"      Max similarity: {color}{max_pct}{Style.RESET_ALL}, {cluster['size']} files")
        print()


# ---------------------------------------------------------------------------
# Assembly Analysis Mode
# ---------------------------------------------------------------------------

def _run_assembly_mode(args):
    """Handle assembly analysis: .zip Pack and Go files."""
    from sw_plagiarism_checker import (
        parse_sw_file, compare_files, detect_clusters,
        generate_summary_report, generate_pdf_report,
    )
    from sw_plagiarism_checker.zip_handler import (
        extract_pack_and_go, parse_submission,
        batch_compare_submissions,
    )

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print(f"  {Fore.RED}✗ Folder not found: {folder}{Style.RESET_ALL}")
        return 1

    # Find ZIP files
    zip_files = glob.glob(os.path.join(folder, "*.zip"))
    zip_files += glob.glob(os.path.join(folder, "*.ZIP"))
    zip_files = sorted(set(os.path.abspath(f) for f in zip_files))

    if not zip_files:
        print(f"  {Fore.RED}✗ No .zip files found in {folder}{Style.RESET_ALL}")
        return 1

    print(f"  {Fore.GREEN}✓ Found {len(zip_files)} ZIP submissions{Style.RESET_ALL}\n")

    # Extract and parse each ZIP
    extract_dir = os.path.join(args.output, "_extracted")
    os.makedirs(extract_dir, exist_ok=True)

    submissions = []
    all_parsed = []

    for zp in zip_files:
        basename = os.path.basename(zp)
        print(f"  {Fore.CYAN}⊕ Extracting: {basename}{Style.RESET_ALL}")
        zip_info = extract_pack_and_go(zp, extract_dir)

        if zip_info.get('error'):
            print(f"    {Fore.YELLOW}⚠ {zip_info['error']}{Style.RESET_ALL}")
            continue

        sub = parse_submission(zip_info, parse_sw_file)
        if sub.get('error'):
            print(f"    {Fore.YELLOW}⚠ {sub['error']}{Style.RESET_ALL}")
            continue

        print(f"    Student: {Fore.CYAN}{sub['student_name']}{Style.RESET_ALL}"
              f"  |  Parts: {sub['total_parts']}"
              f"  |  Assemblies: {len(sub.get('assembly_parsed', []))}"
              f"  |  Features: {sub['total_features']}")
        submissions.append(sub)
        all_parsed.extend(sub['parsed_files'])

    if len(submissions) < 2:
        print(f"\n  {Fore.RED}✗ Need at least 2 valid submissions. Got {len(submissions)}.{Style.RESET_ALL}")
        return 1

    # Compare submissions
    print(f"\n  {Fore.CYAN}⊕ Comparing {len(submissions)} submissions...{Style.RESET_ALL}")
    results = batch_compare_submissions(submissions, compare_files)
    clusters = detect_clusters(results, args.threshold)

    # Generate reports
    print(f"  {Fore.CYAN}⊕ Generating reports...{Style.RESET_ALL}")
    session = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.output, exist_ok=True)

    paths = {}
    if args.format in ("pdf", "both"):
        pdf_path = os.path.join(args.output, f"plagiarism_report_{session}.pdf")
        generate_pdf_report(results, all_parsed, pdf_path, clusters=clusters)
        paths["pdf"] = pdf_path
    if args.format in ("csv", "both"):
        csv_paths = generate_summary_report(
            results, all_parsed, args.output, session, include_pdf=False, clusters=clusters
        )
        paths.update(csv_paths)

    # Print summary
    _print_assembly_summary(results, submissions, args.threshold, clusters)

    print(f"  {Style.BRIGHT}Reports saved:{Style.RESET_ALL}")
    for key, path in paths.items():
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} [{key.upper()}] {os.path.abspath(path)}")
    print()

    # Auto-open
    if args.open and "pdf" in paths:
        try:
            if sys.platform == "win32":
                os.startfile(paths["pdf"])
        except Exception:
            pass

    return 0


def _print_assembly_summary(results, submissions, threshold, clusters=None):
    """Print assembly analysis summary."""
    high = sum(1 for r in results if r["risk_level"] == "HIGH")
    medium = sum(1 for r in results if r["risk_level"] == "MEDIUM")
    low = sum(1 for r in results if r["risk_level"] == "LOW")
    clean = sum(1 for r in results if r["risk_level"] == "NONE")

    print(f"\n{Style.BRIGHT}{'='*60}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}  ASSEMBLY ANALYSIS COMPLETE{Style.RESET_ALL}")
    print(f"{'='*60}")
    print(f"  Submissions:     {len(submissions)}")
    print(f"  Pairs compared:  {len(results)}")
    print(f"  Threshold:       {threshold*100:.0f}%")
    print()
    print(f"  {Fore.RED}■ HIGH risk:    {high}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}■ MEDIUM risk:  {medium}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}■ CLEAN:        {clean + low}{Style.RESET_ALL}")
    print(f"{'='*60}\n")

    flagged = [r for r in results if r["composite_score"] >= threshold]
    if flagged:
        print(f"{Style.BRIGHT}  Flagged Pairs:{Style.RESET_ALL}\n")
        for r in flagged:
            color = _risk_color(r["risk_level"])
            score_str = f"{r['composite_score']*100:.1f}%"
            asm_str = f"{r.get('assembly_similarity', 0)*100:.1f}%"
            part_str = f"{r.get('part_similarity', 0)*100:.1f}%"
            print(f"  {color}{r.get('student_a', r.get('file_a', ''))}"
                  f"  vs  {r.get('student_b', r.get('file_b', ''))}{Style.RESET_ALL}")
            print(f"    Overall: {color}{score_str}{Style.RESET_ALL}"
                  f"  |  Assembly: {asm_str}  |  Parts: {part_str}")

            for pm in r.get("part_matches", []):
                pm_score = f"{pm.get('score', 0)*100:.1f}%"
                pm_color = Fore.RED if pm.get('score', 0) >= 0.75 else Fore.YELLOW if pm.get('score', 0) >= 0.45 else ""
                print(f"      {pm_color}{pm['part_a']}  ↔  {pm['part_b']}  ({pm_score}){Style.RESET_ALL}")
            print()
    else:
        print(f"  {Fore.GREEN}✓ No pairs exceeded the threshold.{Style.RESET_ALL}\n")

    if clusters:
        print(f"  {Style.BRIGHT}Plagiarism Clusters:{Style.RESET_ALL}")
        for idx, cluster in enumerate(clusters):
            max_pct = f"{cluster['max_score']*100:.1f}%"
            files_str = ', '.join(cluster['files'])
            color = Fore.RED if cluster['max_score'] >= 0.75 else Fore.YELLOW
            print(f"    {color}Cluster {idx+1}{Style.RESET_ALL}: {files_str}")
            print(f"      Max similarity: {color}{max_pct}{Style.RESET_ALL}, {cluster['size']} files")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="sw-plagiarism-checker",
        description="Detect plagiarism in SolidWorks (.sldprt / .sldasm) assignment files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sw-plagiarism-checker --folder ./assignments
  sw-plagiarism-checker --folder ./assemblies --assemblies
  sw-plagiarism-checker --drive "https://drive.google.com/drive/folders/XXXXX"
  sw-plagiarism-checker --folder ./assignments --format both --threshold 0.5
  sw-plagiarism-checker --folder ./assignments --reference ./template.sldprt
        """,
    )

    # Input source
    input_group = parser.add_argument_group("Input Source (one required)")
    input_group.add_argument(
        "--drive", metavar="URL",
        help="Google Drive folder URL or ID",
    )
    input_group.add_argument(
        "--folder", metavar="PATH",
        help="Local folder path containing SolidWorks files",
    )

    # Analysis mode
    parser.add_argument(
        "--assemblies", action="store_true",
        help="Assembly mode: treat .zip files as Pack and Go submissions",
    )

    # Options
    parser.add_argument(
        "--output", "-o", metavar="DIR", default="./reports",
        help="Output directory for reports (default: ./reports)",
    )
    parser.add_argument(
        "--format", "-f", choices=["pdf", "csv", "both"], default="pdf",
        help="Report format (default: pdf)",
    )
    parser.add_argument(
        "--threshold", "-t", type=float, default=0.45,
        help="Minimum similarity score to flag (default: 0.45)",
    )
    parser.add_argument(
        "--reference", "-r", metavar="FILE",
        help="Optional reference file to compare all submissions against",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed progress and debug info",
    )
    parser.add_argument(
        "--credentials", metavar="FILE", default="credentials.json",
        help="Path to Google API credentials.json (default: credentials.json)",
    )
    parser.add_argument(
        "--open", action="store_true", default=True,
        help="Automatically open the PDF report when done (default: True)",
    )
    parser.add_argument(
        "--no-open", action="store_false", dest="open",
        help="Do not open the report automatically",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.drive and not args.folder:
        parser.error("You must specify either --drive or --folder")

    _print_banner()

    # Import core library
    from sw_plagiarism_checker import (
        parse_sw_file, batch_compare, compare_against_reference,
        detect_clusters, student_name_from_filename,
        generate_summary_report, generate_pdf_report,
        SUPPORTED_EXTENSIONS,
    )

    # ---- Assembly mode? ----
    assembly_mode = args.assemblies

    if assembly_mode:
        print(f"  {Style.BRIGHT}Mode: Assembly Analysis (Pack & Go ZIPs){Style.RESET_ALL}\n")
        return _run_assembly_mode(args)

    print(f"  {Style.BRIGHT}Mode: Part File Analysis{Style.RESET_ALL}\n")

    # ---- Step 1: Collect files ----
    sw_files = []

    if args.drive:
        print(f"  {Fore.CYAN}↓ Downloading from Google Drive...{Style.RESET_ALL}")
        try:
            from sw_plagiarism_checker.drive_downloader import download_from_drive

            def _progress(name, idx, total):
                print(f"    [{idx}/{total}] {name}")

            local_files = download_from_drive(
                args.drive,
                output_dir=os.path.join(args.output, "_drive_cache"),
                credentials_path=args.credentials,
                progress_callback=_progress,
            )
            sw_files.extend(local_files)
            print(f"  {Fore.GREEN}✓ Downloaded {len(local_files)} files{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"  {Fore.RED}✗ Drive download failed: {e}{Style.RESET_ALL}")
            sys.exit(1)

    if args.folder:
        folder = os.path.abspath(args.folder)
        if not os.path.isdir(folder):
            print(f"  {Fore.RED}✗ Folder not found: {folder}{Style.RESET_ALL}")
            sys.exit(1)
        print(f"  {Fore.CYAN}◎ Scanning folder: {folder}{Style.RESET_ALL}")
        for ext in SUPPORTED_EXTENSIONS:
            pattern = os.path.join(folder, f"**/*{ext}")
            sw_files.extend(glob.glob(pattern, recursive=True))
            sw_files.extend(glob.glob(os.path.join(folder, f"**/*{ext.upper()}"), recursive=True))
        sw_files = sorted(set(os.path.abspath(f) for f in sw_files))
        print(f"  {Fore.GREEN}✓ Found {len(sw_files)} SolidWorks files{Style.RESET_ALL}\n")

    if not sw_files:
        print(f"  {Fore.RED}✗ No SolidWorks files found!{Style.RESET_ALL}")
        sys.exit(1)

    # ---- Step 2: Parse files ----
    print(f"  {Fore.CYAN}⊕ Parsing files...{Style.RESET_ALL}")
    parsed_files = []

    if _HAS_TQDM:
        iterator = tqdm(sw_files, desc="  Parsing", unit="file", ncols=70)
    else:
        iterator = sw_files

    for filepath in iterator:
        if args.verbose and not _HAS_TQDM:
            print(f"    Parsing: {os.path.basename(filepath)}")
        parsed = parse_sw_file(filepath)
        # Primary identifier = filename
        parsed["uploader_name"] = student_name_from_filename(os.path.basename(filepath))
        parsed_files.append(parsed)

        if args.verbose and parsed.get("parse_error"):
            print(f"    {Fore.YELLOW}⚠ {os.path.basename(filepath)}: {parsed['parse_error']}{Style.RESET_ALL}")

    # Show students identified
    print(f"\n  {Style.BRIGHT}Students identified:{Style.RESET_ALL}")
    for p in parsed_files:
        name = p.get("uploader_name") or "Unknown"
        print(f"    • {p['file_name']}  →  {Fore.CYAN}{name}{Style.RESET_ALL}")
    print()

    # ---- Step 3: Compare ----
    print(f"  {Fore.CYAN}⊕ Comparing files...{Style.RESET_ALL}")
    results = batch_compare(parsed_files)

    # Reference comparison
    if args.reference:
        ref_path = os.path.abspath(args.reference)
        if os.path.isfile(ref_path):
            print(f"  {Fore.CYAN}⊕ Comparing against reference: {os.path.basename(ref_path)}{Style.RESET_ALL}")
            ref_parsed = parse_sw_file(ref_path)
            for p in parsed_files:
                ref_result = compare_against_reference(p, ref_parsed)
                results.append(ref_result)
        else:
            print(f"  {Fore.YELLOW}⚠ Reference file not found: {ref_path}{Style.RESET_ALL}")

    # Sort by score
    results.sort(key=lambda x: x["composite_score"], reverse=True)

    # Detect plagiarism clusters
    clusters = detect_clusters(results, args.threshold)

    # ---- Step 4: Generate reports ----
    print(f"  {Fore.CYAN}⊕ Generating reports...{Style.RESET_ALL}")

    include_pdf = args.format in ("pdf", "both")
    session = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.format == "csv":
        paths = generate_summary_report(
            results, parsed_files, args.output, session, include_pdf=False, clusters=clusters
        )
    elif args.format == "pdf":
        pdf_path = os.path.join(args.output, f"plagiarism_report_{session}.pdf")
        os.makedirs(args.output, exist_ok=True)
        generate_pdf_report(results, parsed_files, pdf_path, clusters=clusters)
        paths = {"pdf": pdf_path}
    else:  # both
        paths = generate_summary_report(
            results, parsed_files, args.output, session, include_pdf=True, clusters=clusters
        )

    # ---- Step 5: Print summary ----
    _print_summary(results, parsed_files, args.threshold, clusters)

    # Report paths
    print(f"  {Style.BRIGHT}Reports saved:{Style.RESET_ALL}")
    for key, path in paths.items():
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} [{key.upper()}] {os.path.abspath(path)}")
    print()

    # Auto-open PDF
    if args.open and "pdf" in paths:
        pdf_path = paths["pdf"]
        print(f"  {Fore.CYAN}↗ Opening report...{Style.RESET_ALL}")
        try:
            if sys.platform == "win32":
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", pdf_path])
            else:
                import subprocess
                subprocess.run(["xdg-open", pdf_path])
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
