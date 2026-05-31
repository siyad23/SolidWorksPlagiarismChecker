"""SW Plagiarism Checker Core Engine"""

from .sldprt_parser import (
    parse_sldprt, parse_sw_file, format_datetime,
    SUPPORTED_EXTENSIONS,
)
from .similarity_engine import (
    compare_files, batch_compare, compare_against_reference,
    detect_clusters, compute_adaptive_weights,
    get_risk_color, similarity_percentage,
    PLAGIARISM_HIGH, PLAGIARISM_MEDIUM, PLAGIARISM_LOW,
)
from .report_generator import (
    generate_summary_report, generate_pdf_report,
    export_pairwise_csv, export_metadata_csv,
)
from .zip_handler import (
    student_name_from_filename, extract_pack_and_go,
    parse_submission, compare_submissions,
    batch_compare_submissions,
)

__all__ = [
    "parse_sldprt", "parse_sw_file", "format_datetime", "SUPPORTED_EXTENSIONS",
    "compare_files", "batch_compare", "compare_against_reference",
    "detect_clusters", "compute_adaptive_weights",
    "get_risk_color", "similarity_percentage",
    "PLAGIARISM_HIGH", "PLAGIARISM_MEDIUM", "PLAGIARISM_LOW",
    "generate_summary_report", "generate_pdf_report",
    "export_pairwise_csv", "export_metadata_csv",
    "student_name_from_filename", "extract_pack_and_go",
    "parse_submission", "compare_submissions",
    "batch_compare_submissions",
]
