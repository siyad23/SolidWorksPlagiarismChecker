# SolidWorks Plagiarism Checker

> **Detect copied assignments** by analyzing feature trees, geometry fingerprints, metadata, and authorship signatures across SolidWorks `.sldprt` and `.sldasm` files.

A standalone **Windows CLI app** and **Web App** for educators to check if students have plagiarized SolidWorks assignments. Supports **local folders** and **Google Drive** integration, with exportable **PDF reports**.

---

## Features

- **Multi-Signal Plagiarism Detection** — Goes beyond simple file hash comparison:
  - Full file SHA-256 hash matching
  - Geometry fingerprinting (volume, surface area, mass, center of mass)
  - Feature tree sequence alignment
  - Feature type distribution (cosine similarity)
  - OLE author/last-author matching
  - Timestamp proximity analysis
  - Custom property comparison
- **Assembly Support** — Handles both `.sldprt` (part) and `.sldasm` (assembly) files
- **Uploader Identification** — Automatically extracts student names from OLE author metadata and educational email patterns
- **PDF Reports** — Professional plagiarism reports with cover page, color-coded similarity matrix, detailed pair analysis, and per-file metadata
- **Google Drive Integration** — Download assignments directly from a shared Drive folder
- **Web App** — Premium dark-theme web interface with drag-and-drop upload
- **Docker Support** — One-command deployment with Docker Compose
- **Open Source** — MIT licensed, contributions welcome

---

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/siyad23/SolidWorksPlagiarismChecker.git
cd SolidWorksPlagiarismChecker

# Install (core + CLI)
pip install -e .

# Install with all optional features
pip install -e ".[all]"

# Or install specific extras
pip install -e ".[drive]"    # Google Drive support
pip install -e ".[web]"      # Web app support
```

### CLI Usage

```bash
# Analyze a local folder
sw-plagiarism-checker --folder ./assignments

# Analyze from Google Drive
sw-plagiarism-checker --drive "https://drive.google.com/drive/folders/XXXXX"

# Custom threshold + both PDF and CSV
sw-plagiarism-checker --folder ./assignments --format both --threshold 0.5

# Compare against a reference/template file
sw-plagiarism-checker --folder ./assignments --reference ./template.sldprt
```

### Web App

```bash
# Install web dependencies
pip install -e ".[web]"

# Run the web app
python -m web.app

# Open http://localhost:8000 in your browser
```

### Docker

```bash
# Build and run
docker-compose up -d

# Open http://localhost:8000
```

---

## How It Works

### Parsing Engine

Each SolidWorks file is parsed to extract:
- **OLE metadata** — Author, last author, creation date, last saved date (no SolidWorks needed)
- **Feature tree** — Ordered list of features with types, names, and creators (requires SolidWorks)
- **Mass properties** — Volume, surface area, mass, density, center of mass (requires SolidWorks)
- **Custom properties** — All user-defined key/value pairs
- **File fingerprints** — SHA-256 hashes for full file, geometry, feature sequence, and feature set

### Similarity Scoring

Each file pair is compared across 10 weighted signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| Full Hash Match | 1.00 | Identical files (byte-for-byte) |
| Geometry Hash | 0.95 | Same volume, surface area, mass, CoM |
| Feature Sequence | 0.85 | Same ordered feature types |
| Feature Names | 0.75 | Same feature names in order |
| Feature Set | 0.65 | Same set of feature types (unordered) |
| Mass Properties | 0.80 | Numerical similarity of mass props |
| Custom Properties | 0.60 | Identical custom property values |
| Author Overlap | 0.90 | Shared author/username |
| Timestamp Proximity | 0.35 | Files created/saved within minutes |
| Feature Distribution | 0.45 | Cosine similarity of feature type counts |

Composite scores are classified into risk levels:
- 🔴 **HIGH** (≥75%) — Likely plagiarism
- 🟠 **MEDIUM** (≥45%) — Suspicious, needs review
- 🟡 **LOW** (≥20%) — Minor similarities
- 🟢 **NONE** (<20%) — Clean

### Uploader Detection

Student names are automatically extracted from:
1. OLE `Author` field — If it's an email (e.g., `john.doe@university.edu`), the name part is parsed
2. OLE `Last Author` field
3. Custom properties (`DrawnBy`, `Designer`, `Author`, `CreatedBy`)

---

## Google Drive Setup

To use the `--drive` option, you need a Google Cloud project:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the **Google Drive API**
4. Create **OAuth 2.0 Client ID** (Desktop App type)
5. Download the credentials and save as `credentials.json` in your working directory
6. On first run, a browser window will open for authentication

---

## Requirements

| Component | Required | Notes |
|-----------|----------|-------|
| Python 3.10+ | ✅ | Core requirement |
| SolidWorks | ⚠️ Optional | Needed for full feature tree + mass properties extraction. Without it, OLE metadata (author, timestamps, file hash) is used as fallback |
| Google Cloud Project | ⚠️ Optional | Only for `--drive` integration |

---

## Project Structure

```
SolidWorksPlagiarismChecker/
├── src/sw_plagiarism_checker/     # Core library
│   ├── sldprt_parser.py           # File parser (COM API + OLE fallback)
│   ├── similarity_engine.py       # Multi-signal comparison
│   ├── report_generator.py        # PDF + CSV report generation
│   └── drive_downloader.py        # Google Drive integration
├── cli/
│   └── main.py                    # CLI entry point
├── web/
│   ├── app.py                     # FastAPI web backend
│   ├── templates/index.html       # Web UI
│   └── static/                    # CSS + JS
├── Dockerfile                     # Docker support
├── docker-compose.yml
└── pyproject.toml
```

---

## Contributing

Contributions are welcome! Please open an issue or submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.
