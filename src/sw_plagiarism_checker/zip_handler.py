"""
zip_handler.py — Pack and Go ZIP Extraction
=============================================
Handles SolidWorks Pack and Go ZIP files for assembly analysis.
Each ZIP represents one student's submission.

A Pack and Go ZIP typically contains:
  - One .sldasm file (the main assembly)
  - Multiple .sldprt files (all referenced parts)
  - Possibly sub-assembly .sldasm files
"""

import os
import zipfile
import shutil
import re
from pathlib import Path

from .sldprt_parser import SUPPORTED_EXTENSIONS


def student_name_from_filename(filename: str) -> str:
    """
    Extract student name from a filename (primary identifier).
    
    Examples:
        'John Doe.sldprt'       → 'John Doe'
        'John_Doe.zip'          → 'John Doe'
        'john.doe.sldprt'       → 'John Doe'
        'Assignment1_JohnDoe.zip' → 'Assignment1 JohnDoe'
    """
    # Remove extension
    name = os.path.splitext(filename)[0]
    # Replace underscores and dots with spaces
    name = re.sub(r'[_.]', ' ', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def extract_pack_and_go(zip_path: str, output_dir: str) -> dict:
    """
    Extract a SolidWorks Pack and Go ZIP file.
    
    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory to extract files into
        
    Returns:
        {
            'student_name': str,
            'zip_filename': str,
            'assembly_files': list[str],  # .sldasm paths
            'part_files': list[str],       # .sldprt paths
            'all_sw_files': list[str],     # all SW file paths
            'extract_dir': str,
            'error': str or None,
        }
    """
    result = {
        'student_name': student_name_from_filename(os.path.basename(zip_path)),
        'zip_filename': os.path.basename(zip_path),
        'assembly_files': [],
        'part_files': [],
        'all_sw_files': [],
        'extract_dir': '',
        'error': None,
    }

    if not os.path.isfile(zip_path):
        result['error'] = f"ZIP file not found: {zip_path}"
        return result

    if not zipfile.is_zipfile(zip_path):
        result['error'] = f"Not a valid ZIP file: {zip_path}"
        return result

    # Create student-specific extract directory
    student_dir = os.path.join(output_dir, result['student_name'].replace(' ', '_'))
    os.makedirs(student_dir, exist_ok=True)
    result['extract_dir'] = student_dir

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Extract all files
            zf.extractall(student_dir)

            # Find all SolidWorks files (may be in subdirectories)
            for root, dirs, files in os.walk(student_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        full_path = os.path.join(root, fname)
                        result['all_sw_files'].append(full_path)
                        if ext == '.sldasm':
                            result['assembly_files'].append(full_path)
                        elif ext == '.sldprt':
                            result['part_files'].append(full_path)

    except Exception as e:
        result['error'] = f"ZIP extraction failed: {e}"
        return result

    if not result['all_sw_files']:
        result['error'] = "No SolidWorks files found in ZIP"

    return result


def parse_submission(zip_info: dict, parse_func) -> dict:
    """
    Parse all SolidWorks files in a student's extracted submission.
    
    Args:
        zip_info: Result from extract_pack_and_go()
        parse_func: The parse_sw_file function
        
    Returns:
        {
            'student_name': str,
            'zip_filename': str,
            'parsed_files': list[dict],       # all parsed file dicts
            'assembly_parsed': list[dict],     # parsed assembly files
            'part_parsed': list[dict],          # parsed part files
            'total_features': int,
            'total_parts': int,
            'error': str or None,
        }
    """
    submission = {
        'student_name': zip_info['student_name'],
        'zip_filename': zip_info['zip_filename'],
        'parsed_files': [],
        'assembly_parsed': [],
        'part_parsed': [],
        'total_features': 0,
        'total_parts': 0,
        'error': zip_info.get('error'),
    }

    if zip_info.get('error'):
        return submission

    for filepath in zip_info['all_sw_files']:
        parsed = parse_func(filepath)
        # Override uploader name with student name from filename
        parsed['uploader_name'] = zip_info['student_name']
        parsed['submission_student'] = zip_info['student_name']
        submission['parsed_files'].append(parsed)

        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.sldasm':
            submission['assembly_parsed'].append(parsed)
        else:
            submission['part_parsed'].append(parsed)

        submission['total_features'] += parsed.get('feature_count', 0)

    submission['total_parts'] = len(submission['part_parsed'])
    return submission


def compare_submissions(sub_a: dict, sub_b: dict, compare_func) -> dict:
    """
    Compare two student submissions (multi-file assemblies).
    
    Compares:
    1. Assembly files against each other
    2. Part files: best-match pairing by comparing all A parts vs all B parts
    3. Aggregates into an overall submission similarity score
    
    Args:
        sub_a, sub_b: Results from parse_submission()
        compare_func: The compare_files function
        
    Returns:
        Standard comparison result dict with additional submission metadata.
    """
    all_comparisons = []
    assembly_scores = []
    part_scores = []
    part_matches = []

    # 1. Compare assembly files
    for asm_a in sub_a.get('assembly_parsed', []):
        for asm_b in sub_b.get('assembly_parsed', []):
            result = compare_func(asm_a, asm_b)
            result['match_type'] = 'assembly_vs_assembly'
            assembly_scores.append(result['composite_score'])
            all_comparisons.append(result)

    # 2. Compare parts: compute full similarity matrix, then greedy best-match
    parts_a = sub_a.get('part_parsed', [])
    parts_b = sub_b.get('part_parsed', [])

    if parts_a and parts_b:
        # Build similarity matrix
        sim_matrix = []
        for i, pa in enumerate(parts_a):
            row = []
            for j, pb in enumerate(parts_b):
                result = compare_func(pa, pb)
                row.append((j, result['composite_score'], result))
            row.sort(key=lambda x: x[1], reverse=True)
            sim_matrix.append(row)

        # Greedy best-match assignment
        used_b = set()
        for i, row in enumerate(sim_matrix):
            for j_idx, score, result in row:
                if j_idx not in used_b:
                    used_b.add(j_idx)
                    result['match_type'] = 'part_vs_part'
                    part_scores.append(score)
                    part_matches.append({
                        'part_a': parts_a[i]['file_name'],
                        'part_b': parts_b[j_idx]['file_name'],
                        'score': score,
                        'risk_level': result['risk_level'],
                    })
                    all_comparisons.append(result)
                    break

    # 3. Aggregate scores
    # Weight: assembly similarity 40%, part similarity 60%
    asm_avg = sum(assembly_scores) / len(assembly_scores) if assembly_scores else 0.0
    part_avg = sum(part_scores) / len(part_scores) if part_scores else 0.0

    if assembly_scores and part_scores:
        composite = asm_avg * 0.40 + part_avg * 0.60
    elif assembly_scores:
        composite = asm_avg
    elif part_scores:
        composite = part_avg
    else:
        composite = 0.0

    # Risk level
    if composite >= 0.75:
        risk = "HIGH"
    elif composite >= 0.45:
        risk = "MEDIUM"
    elif composite >= 0.20:
        risk = "LOW"
    else:
        risk = "NONE"

    # Flags
    flags = []
    if composite >= 0.90:
        flags.append("NEAR_IDENTICAL_SUBMISSIONS")
    if asm_avg >= 0.85:
        flags.append("IDENTICAL_ASSEMBLY_STRUCTURE")
    if part_avg >= 0.85:
        flags.append("IDENTICAL_PARTS")
    high_matches = sum(1 for s in part_scores if s >= 0.75)
    if high_matches >= 2:
        flags.append(f"{high_matches}_PARTS_HIGHLY_SIMILAR")

    return {
        'student_a': sub_a['student_name'],
        'student_b': sub_b['student_name'],
        'file_a': sub_a['zip_filename'],
        'file_b': sub_b['zip_filename'],
        'composite_score': composite,
        'risk_level': risk,
        'flags': flags,
        'assembly_similarity': asm_avg,
        'part_similarity': part_avg,
        'part_matches': part_matches,
        'num_parts_a': len(parts_a),
        'num_parts_b': len(parts_b),
        'comparison_type': 'submission_vs_submission',
        'scores': {
            'assembly_avg': asm_avg,
            'part_avg': part_avg,
        },
        'shared_authors': [],
    }


def batch_compare_submissions(submissions: list, compare_func) -> list:
    """
    Compare all pairs of student submissions.
    Returns sorted results (highest similarity first).
    """
    results = []
    n = len(submissions)
    for i in range(n):
        for j in range(i + 1, n):
            results.append(compare_submissions(submissions[i], submissions[j], compare_func))
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results
