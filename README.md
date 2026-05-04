# sw_plagiarism_checker

A Python library for detecting plagiarism and calculating similarity between SolidWorks Part (`.sldprt`) files.

This engine parses the OLE compound document properties and embedded geometric feature trees of SolidWorks files, without requiring a SolidWorks installation or license.

## Features
- **Fast Offline Parsing**: Reads `.sldprt` files directly using `olefile`.
- **Advanced Similarity Matrix**:
  - Full file hash validation
  - Geometry hash checking
  - Feature tree sequence alignment
  - Feature set matching
  - Embedded Author and Timestamp proximity checks
- **Reporting Generator**: Exports pairwise comparisons and extracted metadata to CSV files.

## Installation

You can install this package locally using `pip`:

```bash
pip install -e .
```

## Usage

```python
from sw_plagiarism_checker import batch_compare, generate_summary_report

# Define target paths
files_to_check = ["student1.sldprt", "student2.sldprt"]

# Run batch comparison
results, metadata = batch_compare(files_to_check)

# View comparisons
for res in results:
    print(f"Similarity between {res['file1']} and {res['file2']}: {res['similarity']}%")
```

## Contributing
Contributions are welcome! Please open an issue or submit a Pull Request.

## License
MIT
