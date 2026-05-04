"""SW Plagiarism Checker Core Engine"""

from .sldprt_parser import parse_sldprt, format_datetime
from .similarity_engine import (
    compare_files, batch_compare, compare_against_reference,
    get_risk_color, similarity_percentage,
    PLAGIARISM_HIGH, PLAGIARISM_MEDIUM, PLAGIARISM_LOW,
)
from .report_generator import generate_summary_report, export_pairwise_csv, export_metadata_csv

__all__ = [
    "parse_sldprt", "format_datetime",
    "compare_files", "batch_compare", "compare_against_reference",
    "get_risk_color", "similarity_percentage",
    "PLAGIARISM_HIGH", "PLAGIARISM_MEDIUM", "PLAGIARISM_LOW",
    "generate_summary_report", "export_pairwise_csv", "export_metadata_csv",
]
