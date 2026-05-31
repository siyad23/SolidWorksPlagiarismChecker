
"""
similarity_engine.py  --  Advanced Plagiarism Detection Engine
================================================================
Multi-signal comparison with:
  - LCS-based feature sequence alignment (graceful degradation)
  - N-gram feature shingling (local pattern matching)
  - Scale-invariant geometry vectors (tolerant of unit/precision differences)
  - MOI eigenvalue fingerprinting (rotation-invariant shape signature)
  - Feature parameter comparison (extrude depths, fillet radii, etc.)
  - Adaptive weight tuning (lab-aware author suppression)
  - Transitive cluster detection (copy-ring grouping)
"""
import math
import hashlib
import datetime

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

PLAGIARISM_HIGH   = 0.75
PLAGIARISM_MEDIUM = 0.45
PLAGIARISM_LOW    = 0.20

# ---------------------------------------------------------------------------
# Base weights — may be adjusted by adaptive tuning
# ---------------------------------------------------------------------------

WEIGHTS = {
    "full_hash_match":           1.00,
    "feature_sequence_lcs":      0.90,
    "feature_name_lcs":          0.75,
    "feature_ngram_similarity":  0.80,
    "feature_set_jaccard":       0.55,
    "geometry_vector_similarity":0.85,
    "moi_similarity":            0.88,
    "mass_props_similarity":     0.70,
    "param_similarity":          0.82,
    "custom_props_match":        0.60,
    "author_overlap":            0.90,
    "timestamp_proximity":       0.35,
    "feature_distribution":      0.45,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Improvement 1: LCS-Based Feature Sequence Alignment
# ---------------------------------------------------------------------------

def _lcs_length(seq_a: list, seq_b: list) -> int:
    """Compute LCS length using space-optimised DP — O(min(m,n)) memory."""
    if not seq_a or not seq_b:
        return 0
    m, n = len(seq_a), len(seq_b)
    # Ensure seq_b is the shorter one for space efficiency
    if m < n:
        seq_a, seq_b = seq_b, seq_a
        m, n = n, m
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if seq_a[i - 1] == seq_b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    return prev[n]


def _lcs_similarity(seq_a: list, seq_b: list) -> float:
    """Normalised LCS similarity: len(LCS) / max(len(a), len(b))."""
    if not seq_a and not seq_b:
        return 0.0
    max_len = max(len(seq_a), len(seq_b))
    if max_len == 0:
        return 0.0
    return _lcs_length(seq_a, seq_b) / max_len


# ---------------------------------------------------------------------------
# Improvement 2: N-Gram Feature Shingling
# ---------------------------------------------------------------------------

def _ngram_similarity(seq_a: list, seq_b: list, n: int = 3) -> float:
    """Jaccard similarity of n-grams from feature type sequences."""
    if len(seq_a) < n or len(seq_b) < n:
        # Fallback: if sequences too short for n-grams, use bigrams or unigrams
        n = min(n, len(seq_a), len(seq_b))
        if n < 1:
            return 0.0

    grams_a = set(tuple(seq_a[i:i + n]) for i in range(len(seq_a) - n + 1))
    grams_b = set(tuple(seq_b[i:i + n]) for i in range(len(seq_b) - n + 1))

    if not grams_a and not grams_b:
        return 0.0

    intersection = len(grams_a & grams_b)
    union = len(grams_a | grams_b)

    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Improvement 3: Normalised Geometry Vector (scale-invariant)
# ---------------------------------------------------------------------------

def _geometry_vector_similarity(mp_a: dict, mp_b: dict) -> float:
    """Scale-invariant geometry comparison using normalised shape ratios."""
    if not mp_a or not mp_b:
        return 0.0

    vol_a = _safe_float(mp_a.get("volume", 0))
    vol_b = _safe_float(mp_b.get("volume", 0))
    sa_a = _safe_float(mp_a.get("surface_area", 0))
    sa_b = _safe_float(mp_b.get("surface_area", 0))
    mass_a = _safe_float(mp_a.get("mass", 0))
    mass_b = _safe_float(mp_b.get("mass", 0))

    if vol_a <= 0 or vol_b <= 0:
        return 0.0

    # ---- Build scale-invariant feature vector ----

    # 1. Sphericity: SA / V^(2/3)  — how sphere-like the shape is
    sph_a = sa_a / (vol_a ** (2.0 / 3.0))
    sph_b = sa_b / (vol_b ** (2.0 / 3.0))

    # 2. Density: mass / volume — material identity
    den_a = mass_a / vol_a
    den_b = mass_b / vol_b

    # 3. Volume ratio (direct, tolerant)
    vol_ratio = min(vol_a, vol_b) / max(vol_a, vol_b)

    # Compare sphericity & density via ratio closeness
    def _ratio_sim(a, b):
        if a == 0 and b == 0:
            return 1.0
        if a == 0 or b == 0:
            return 0.0
        return min(a, b) / max(a, b)

    sph_sim = _ratio_sim(sph_a, sph_b)
    den_sim = _ratio_sim(den_a, den_b)

    # Center-of-mass comparison (normalised by bounding dimension)
    com_a = mp_a.get("center_of_mass", [0, 0, 0])
    com_b = mp_b.get("center_of_mass", [0, 0, 0])
    com_sim = 1.0
    if len(com_a) == 3 and len(com_b) == 3:
        # Normalise CoM distance by the cube root of volume (characteristic length)
        char_len = max((vol_a ** (1.0 / 3.0) + vol_b ** (1.0 / 3.0)) / 2.0, 1e-10)
        com_dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(com_a, com_b)))
        com_sim = max(0.0, 1.0 - com_dist / char_len)

    # Weighted combination
    return (sph_sim * 0.30 + den_sim * 0.20 + vol_ratio * 0.30 + com_sim * 0.20)


# ---------------------------------------------------------------------------
# Improvement 4: MOI Eigenvalue Fingerprinting
# ---------------------------------------------------------------------------

def _eigenvalues_3x3_symmetric(m):
    """
    Analytical eigenvalues for a 3×3 symmetric matrix.
    Avoids numpy dependency.  Uses the algorithm from Wikipedia's
    'Eigenvalue algorithm' article for 3×3 real symmetric matrices.
    Input: list/tuple of 9 values [m00,m01,m02, m10,m11,m12, m20,m21,m22]
    Returns sorted eigenvalues [λ1, λ2, λ3] (ascending).
    """
    if len(m) < 9:
        return None

    a00, a01, a02 = m[0], m[1], m[2]
    a11, a12 = m[4], m[5]
    a22 = m[8]

    # Sum of squares of off-diagonal elements
    p1 = a01 * a01 + a02 * a02 + a12 * a12

    if p1 < 1e-14:
        # Matrix is already diagonal
        return sorted([a00, a11, a22])

    q = (a00 + a11 + a22) / 3.0  # trace / 3
    p2 = (a00 - q) ** 2 + (a11 - q) ** 2 + (a22 - q) ** 2 + 2.0 * p1
    p = math.sqrt(p2 / 6.0)

    # B = (A - q*I) / p
    b00 = (a00 - q) / p
    b11 = (a11 - q) / p
    b22 = (a22 - q) / p
    b01 = a01 / p
    b02 = a02 / p
    b12 = a12 / p

    # r = det(B) / 2
    r = (b00 * (b11 * b22 - b12 * b12)
         - b01 * (b01 * b22 - b12 * b02)
         + b02 * (b01 * b12 - b11 * b02)) / 2.0

    # Clamp for numerical safety (r ∈ [-1, 1] for a symmetric matrix)
    r = max(-1.0, min(1.0, r))

    phi = math.acos(r) / 3.0

    eig1 = q + 2.0 * p * math.cos(phi)
    eig3 = q + 2.0 * p * math.cos(phi + 2.0 * math.pi / 3.0)
    eig2 = 3.0 * q - eig1 - eig3  # trace is preserved

    return sorted([eig1, eig2, eig3])


def _moi_similarity(mp_a: dict, mp_b: dict) -> float:
    """Compare MOI eigenvalues (rotation-invariant shape signature)."""
    moi_a = mp_a.get("moi", [])
    moi_b = mp_b.get("moi", [])

    if len(moi_a) < 9 or len(moi_b) < 9:
        return 0.0

    eig_a = _eigenvalues_3x3_symmetric(moi_a)
    eig_b = _eigenvalues_3x3_symmetric(moi_b)

    if eig_a is None or eig_b is None:
        return 0.0

    # Normalise by trace for scale invariance
    trace_a = sum(abs(e) for e in eig_a) or 1.0
    trace_b = sum(abs(e) for e in eig_b) or 1.0
    norm_a = [e / trace_a for e in eig_a]
    norm_b = [e / trace_b for e in eig_b]

    # Euclidean distance in normalised eigenvalue space
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(norm_a, norm_b)))

    # Map distance to similarity (empirically tuned)
    # dist=0 → 1.0,  dist≥0.3 → ~0.0
    return max(0.0, 1.0 - dist / 0.3)


# ---------------------------------------------------------------------------
# Legacy mass-props similarity (kept as supplementary signal)
# ---------------------------------------------------------------------------

def _mass_props_similarity(mp_a: dict, mp_b: dict) -> float:
    """Direct mass property comparison with tolerance."""
    if not mp_a or not mp_b:
        return 0.0
    scores = []
    for k in ["volume", "surface_area", "mass"]:
        va = _safe_float(mp_a.get(k, 0))
        vb = _safe_float(mp_b.get(k, 0))
        if va == 0 and vb == 0:
            scores.append(1.0)
        elif va == 0 or vb == 0:
            scores.append(0.0)
        else:
            ratio = min(va, vb) / max(va, vb)
            # Apply tolerance curve: ratios above 0.98 score very high
            scores.append(ratio)
    return sum(scores) / len(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Improvement 7: Feature Parameter Comparison
# ---------------------------------------------------------------------------

def _param_similarity(features_a: list, features_b: list) -> float:
    """
    Compare feature parameters for matched feature types.
    Uses greedy type-matching to pair features, then compares params.
    """
    if not features_a or not features_b:
        return 0.0

    # Build lists of (type, params) for features that have params
    def _extract(features):
        return [(f["type"], f.get("params", {})) for f in features
                if f.get("params") and isinstance(f.get("params"), dict)]

    feats_a = _extract(features_a)
    feats_b = _extract(features_b)

    if not feats_a or not feats_b:
        return 0.0

    # Greedy matching: for each feature in A, find best match in B by type
    used_b = set()
    match_scores = []

    for type_a, params_a in feats_a:
        best_score = -1.0
        best_j = -1
        for j, (type_b, params_b) in enumerate(feats_b):
            if j in used_b:
                continue
            if type_a != type_b:
                continue
            # Compare shared parameter keys
            shared_keys = set(params_a.keys()) & set(params_b.keys())
            if not shared_keys:
                score = 0.5  # Same type, but no comparable params
            else:
                ratios = []
                for k in shared_keys:
                    va = _safe_float(params_a.get(k))
                    vb = _safe_float(params_b.get(k))
                    if va == 0 and vb == 0:
                        ratios.append(1.0)
                    elif va == 0 or vb == 0:
                        ratios.append(0.0)
                    else:
                        ratios.append(min(abs(va), abs(vb)) / max(abs(va), abs(vb)))
                score = sum(ratios) / len(ratios) if ratios else 0.5
            if score > best_score:
                best_score = score
                best_j = j
        if best_j >= 0:
            used_b.add(best_j)
            match_scores.append(best_score)

    if not match_scores:
        return 0.0

    # Penalise for unmatched features
    total_features = max(len(feats_a), len(feats_b))
    matched_sum = sum(match_scores)
    return matched_sum / total_features


# ---------------------------------------------------------------------------
# Feature set Jaccard (replaces binary hash match)
# ---------------------------------------------------------------------------

def _feature_set_jaccard(features_a: list, features_b: list) -> float:
    """Jaccard similarity of feature type sets (unordered)."""
    set_a = set(f["type"] for f in features_a if f.get("type"))
    set_b = set(f["type"] for f in features_b if f.get("type"))
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Cosine similarity for feature type distribution
# ---------------------------------------------------------------------------

def _cosine_similarity(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v ** 2 for v in a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Author overlap
# ---------------------------------------------------------------------------

def _author_overlap(authors_a: list, authors_b: list) -> float:
    if not authors_a or not authors_b:
        return 0.0
    set_a = {a.lower().strip() for a in authors_a if a}
    set_b = {b.lower().strip() for b in authors_b if b}
    if not set_a or not set_b:
        return 0.0
    if set_a & set_b:
        return 1.0
    for a in set_a:
        for b in set_b:
            if len(a) > 3 and len(b) > 3 and (a in b or b in a):
                return 0.7
    return 0.0


# ---------------------------------------------------------------------------
# Timestamp proximity
# ---------------------------------------------------------------------------

def _timestamp_proximity(fs_a: dict, fs_b: dict, ole_a: dict, ole_b: dict) -> float:
    best = 0.0
    pairs = [
        (fs_a.get("fs_created"), fs_b.get("fs_created")),
        (fs_a.get("fs_modified"), fs_b.get("fs_modified")),
        (ole_a.get("created"), ole_b.get("created")),
        (ole_a.get("last_saved"), ole_b.get("last_saved")),
    ]
    for ta, tb in pairs:
        if isinstance(ta, datetime.datetime) and isinstance(tb, datetime.datetime):
            diff = abs((ta - tb).total_seconds())
            if diff <= 10:
                score = 1.0
            elif diff <= 300:
                score = 1.0 - (diff - 10) / 290
            else:
                score = 0.0
            best = max(best, score)
    return best


# ---------------------------------------------------------------------------
# Improvement 5: Adaptive Weight Tuning
# ---------------------------------------------------------------------------

def compute_adaptive_weights(parsed_files: list, base_weights: dict = None) -> dict:
    """
    Adjust signal weights based on the dataset characteristics.
    - If >50% of files share the same OLE author → suppress author_overlap
    - If timestamps cluster tightly (lab session) → suppress timestamp_proximity
    """
    weights = dict(base_weights or WEIGHTS)

    if not parsed_files or len(parsed_files) < 2:
        return weights

    total = len(parsed_files)

    # ---- Author frequency analysis ----
    author_counts = {}
    for p in parsed_files:
        author = (p.get("ole_metadata", {}).get("author") or "").lower().strip()
        if author:
            author_counts[author] = author_counts.get(author, 0) + 1

    if author_counts:
        most_common_count = max(author_counts.values())
        most_common_pct = most_common_count / total
        if most_common_pct > 0.5:
            # Lab environment — shared machine/user detected
            weights["author_overlap"] = 0.05
        elif most_common_pct > 0.3:
            weights["author_overlap"] = 0.30

    # ---- Timestamp clustering analysis ----
    ole_timestamps = []
    for p in parsed_files:
        ts = p.get("ole_metadata", {}).get("last_saved")
        if isinstance(ts, datetime.datetime):
            ole_timestamps.append(ts)

    if len(ole_timestamps) >= 3:
        ole_timestamps.sort()
        # Compute median pairwise gap
        gaps = [(ole_timestamps[i + 1] - ole_timestamps[i]).total_seconds()
                for i in range(len(ole_timestamps) - 1)]
        median_gap = sorted(gaps)[len(gaps) // 2]
        if median_gap < 120:
            # Files saved within ~2 minutes of each other (lab session)
            weights["timestamp_proximity"] = 0.08

    return weights


# ---------------------------------------------------------------------------
# Main comparison function (all improvements integrated)
# ---------------------------------------------------------------------------

def compare_files(parsed_a: dict, parsed_b: dict,
                  weights: dict = None) -> dict:
    """
    Compare two parsed SolidWorks files using the advanced multi-signal engine.
    """
    w = weights or WEIGHTS

    fp_a = parsed_a.get("fingerprints", {})
    fp_b = parsed_b.get("fingerprints", {})
    mp_a = parsed_a.get("mass_props", {})
    mp_b = parsed_b.get("mass_props", {})
    fs_a = parsed_a.get("fs_metadata", {})
    fs_b = parsed_b.get("fs_metadata", {})
    ol_a = parsed_a.get("ole_metadata", {})
    ol_b = parsed_b.get("ole_metadata", {})
    feat_a = parsed_a.get("features", [])
    feat_b = parsed_b.get("features", [])

    # Active (non-suppressed) features
    active_a = [f for f in feat_a if not f.get("suppressed", False)]
    active_b = [f for f in feat_b if not f.get("suppressed", False)]

    # Feature type sequences
    type_seq_a = [f["type"] for f in active_a]
    type_seq_b = [f["type"] for f in active_b]

    # Feature name sequences
    name_seq_a = [f["name"] for f in active_a]
    name_seq_b = [f["name"] for f in active_b]

    # ---- Compute all signals ----
    scores = {}

    # 1. Full hash match (kept — exact copy detection)
    h_a = parsed_a.get("full_hash", "")
    h_b = parsed_b.get("full_hash", "")
    scores["full_hash_match"] = 1.0 if (h_a and h_b and h_a == h_b) else 0.0

    # 2. Feature sequence LCS (IMPROVEMENT 1)
    scores["feature_sequence_lcs"] = _lcs_similarity(type_seq_a, type_seq_b)

    # 3. Feature name LCS (IMPROVEMENT 1)
    scores["feature_name_lcs"] = _lcs_similarity(name_seq_a, name_seq_b)

    # 4. Feature N-gram shingling (IMPROVEMENT 2)
    scores["feature_ngram_similarity"] = _ngram_similarity(type_seq_a, type_seq_b, n=3)

    # 5. Feature set Jaccard (replaces binary hash)
    scores["feature_set_jaccard"] = _feature_set_jaccard(feat_a, feat_b)

    # 6. Geometry vector similarity (IMPROVEMENT 3)
    scores["geometry_vector_similarity"] = _geometry_vector_similarity(mp_a, mp_b)

    # 7. MOI eigenvalue similarity (IMPROVEMENT 4)
    scores["moi_similarity"] = _moi_similarity(mp_a, mp_b)

    # 8. Legacy mass props similarity (kept as supplement)
    scores["mass_props_similarity"] = _mass_props_similarity(mp_a, mp_b)

    # 9. Feature parameter similarity (IMPROVEMENT 7)
    scores["param_similarity"] = _param_similarity(feat_a, feat_b)

    # 10. Custom properties match
    cp_a = fp_a.get("custom_props_hash", "")
    cp_b = fp_b.get("custom_props_hash", "")
    scores["custom_props_match"] = 1.0 if (cp_a and cp_b and cp_a == cp_b) else 0.0

    # 11. Author overlap
    auth_a = parsed_a.get("authors", [])
    auth_b = parsed_b.get("authors", [])
    scores["author_overlap"] = _author_overlap(auth_a, auth_b)

    # 12. Timestamp proximity
    scores["timestamp_proximity"] = _timestamp_proximity(fs_a, fs_b, ol_a, ol_b)

    # 13. Feature type distribution (cosine)
    dist_a = fp_a.get("feature_type_counts", {})
    dist_b = fp_b.get("feature_type_counts", {})
    scores["feature_distribution"] = _cosine_similarity(dist_a, dist_b)

    # ---- Weighted composite ----
    total_weight = 0.0
    weighted_sum = 0.0
    for signal, score in scores.items():
        signal_w = w.get(signal, 0.0)
        if signal_w == 0:
            continue

        # Skip signals that have no data to contribute
        if signal in ("geometry_vector_similarity", "moi_similarity", "mass_props_similarity"):
            if not mp_a or not mp_b:
                continue
        if signal in ("feature_sequence_lcs", "feature_name_lcs", "feature_ngram_similarity",
                       "feature_set_jaccard", "feature_distribution", "param_similarity"):
            if not feat_a and not feat_b:
                continue
        if signal == "custom_props_match":
            if not parsed_a.get("custom_props") and not parsed_b.get("custom_props"):
                continue

        weighted_sum += score * signal_w
        total_weight += signal_w

    composite = min(1.0, max(0.0, weighted_sum / total_weight if total_weight > 0 else 0.0))

    # ---- Risk level ----
    if composite >= PLAGIARISM_HIGH:
        risk = "HIGH"
    elif composite >= PLAGIARISM_MEDIUM:
        risk = "MEDIUM"
    elif composite >= PLAGIARISM_LOW:
        risk = "LOW"
    else:
        risk = "NONE"

    # ---- Flags ----
    flags = []
    if scores["full_hash_match"] == 1.0:
        flags.append("IDENTICAL_FILES")
    if scores["feature_sequence_lcs"] >= 0.95:
        flags.append("NEAR_IDENTICAL_FEATURE_SEQUENCE")
    elif scores["feature_sequence_lcs"] >= 0.80:
        flags.append("HIGH_FEATURE_SEQUENCE_SIMILARITY")
    if scores["feature_name_lcs"] >= 0.90:
        flags.append("NEAR_IDENTICAL_FEATURE_NAMES")
    if scores["feature_ngram_similarity"] >= 0.80:
        flags.append("HIGH_NGRAM_OVERLAP")
    if scores["geometry_vector_similarity"] >= 0.95:
        flags.append("NEAR_IDENTICAL_GEOMETRY")
    elif scores["geometry_vector_similarity"] >= 0.85:
        flags.append("SIMILAR_GEOMETRY")
    if scores["moi_similarity"] >= 0.95:
        flags.append("IDENTICAL_SHAPE_SIGNATURE")
    elif scores["moi_similarity"] >= 0.80:
        flags.append("SIMILAR_SHAPE_SIGNATURE")
    if scores["param_similarity"] >= 0.90:
        flags.append("NEAR_IDENTICAL_PARAMETERS")
    elif scores["param_similarity"] >= 0.70:
        flags.append("SIMILAR_PARAMETERS")
    if scores["mass_props_similarity"] >= 0.999:
        flags.append("IDENTICAL_MASS_PROPERTIES")
    elif scores["mass_props_similarity"] >= 0.95:
        flags.append("NEAR_IDENTICAL_MASS_PROPERTIES")
    if scores["custom_props_match"] == 1.0:
        flags.append("IDENTICAL_CUSTOM_PROPERTIES")
    if scores["author_overlap"] >= 1.0:
        flags.append("SHARED_AUTHOR_USERNAME")
    elif scores["author_overlap"] > 0:
        flags.append("PARTIAL_AUTHOR_MATCH")
    if scores["timestamp_proximity"] >= 0.9:
        flags.append("NEAR_IDENTICAL_CREATION_TIME")
    elif scores["timestamp_proximity"] >= 0.5:
        flags.append("CLOSE_CREATION_TIME")

    # Shared authors
    set_a = {a.lower().strip() for a in auth_a if a}
    set_b = {b.lower().strip() for b in auth_b if b}
    shared_authors = sorted(set_a & set_b)

    return {
        "file_a": parsed_a["file_name"],
        "file_b": parsed_b["file_name"],
        "path_a": parsed_a["file_path"],
        "path_b": parsed_b["file_path"],
        "scores": scores,
        "composite_score": composite,
        "risk_level": risk,
        "flags": flags,
        "shared_authors": shared_authors,
        "comparison_type": "student_vs_student",
    }


# ---------------------------------------------------------------------------
# Batch comparison with adaptive weights
# ---------------------------------------------------------------------------

def batch_compare(parsed_files: list, weights: dict = None) -> list:
    """
    Compare all pairs with adaptive weight tuning.
    Returns results sorted by composite score (highest first).
    """
    # Compute adaptive weights based on dataset characteristics
    adaptive_w = compute_adaptive_weights(parsed_files, weights or WEIGHTS)

    results = []
    n = len(parsed_files)
    for i in range(n):
        for j in range(i + 1, n):
            results.append(compare_files(parsed_files[i], parsed_files[j], adaptive_w))
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


def compare_against_reference(parsed_student: dict, parsed_reference: dict,
                               weights: dict = None) -> dict:
    result = compare_files(parsed_student, parsed_reference, weights)
    result["comparison_type"] = "student_vs_reference"
    result["file_b"] = f"[REF] {parsed_reference['file_name']}"
    return result


# ---------------------------------------------------------------------------
# Improvement 6: Transitive Cluster Detection (Union-Find)
# ---------------------------------------------------------------------------

def detect_clusters(results: list, threshold: float = None) -> list:
    """
    Find connected components of files above the threshold.
    Uses Union-Find for efficient O(α(n)) amortised operations.

    Returns a list of cluster dicts:
      [{"files": {"a.sldprt", "b.sldprt", ...}, "max_score": 0.92, "pairs": [...]}, ...]
    """
    if threshold is None:
        threshold = PLAGIARISM_MEDIUM

    parent = {}
    rank = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])  # path compression
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        # Union by rank
        if rank.get(rx, 0) < rank.get(ry, 0):
            rx, ry = ry, rx
        parent[ry] = rx
        if rank.get(rx, 0) == rank.get(ry, 0):
            rank[rx] = rank.get(rx, 0) + 1

    # Build clusters from flagged pairs
    flagged_pairs = []
    for r in results:
        if r["composite_score"] >= threshold:
            union(r["file_a"], r["file_b"])
            flagged_pairs.append(r)

    if not flagged_pairs:
        return []

    # Group files by root
    cluster_map = {}
    for r in flagged_pairs:
        for f in (r["file_a"], r["file_b"]):
            root = find(f)
            if root not in cluster_map:
                cluster_map[root] = {"files": set(), "pairs": [], "max_score": 0.0}
            cluster_map[root]["files"].add(f)

    # Attach pairs to clusters
    for r in flagged_pairs:
        root = find(r["file_a"])
        cluster_map[root]["pairs"].append({
            "file_a": r["file_a"],
            "file_b": r["file_b"],
            "score": r["composite_score"],
            "risk_level": r["risk_level"],
        })
        cluster_map[root]["max_score"] = max(
            cluster_map[root]["max_score"], r["composite_score"]
        )

    # Convert to sorted list
    clusters = list(cluster_map.values())
    for c in clusters:
        c["files"] = sorted(c["files"])
        c["size"] = len(c["files"])
    clusters.sort(key=lambda c: c["max_score"], reverse=True)

    return clusters


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_risk_color(risk_level: str) -> str:
    return {
        "HIGH": "#FF4D6D", "MEDIUM": "#FF9F43",
        "LOW": "#FFD166", "NONE": "#06D6A0",
    }.get(risk_level, "#9095B4")


def similarity_percentage(score: float) -> str:
    return f"{score * 100:.1f}%"
