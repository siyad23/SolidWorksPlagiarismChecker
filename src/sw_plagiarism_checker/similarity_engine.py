
"""
similarity_engine.py  --  COM API edition
"""
import math, hashlib, datetime

PLAGIARISM_HIGH   = 0.75
PLAGIARISM_MEDIUM = 0.45
PLAGIARISM_LOW    = 0.20

WEIGHTS = {
    "full_hash_match":        1.00,
    "geometry_hash_match":    0.95,
    "feature_sequence_match": 0.85,
    "feature_name_seq_match": 0.75,
    "feature_set_match":      0.65,
    "mass_props_similarity":  0.80,
    "custom_props_match":     0.60,
    "author_overlap":         0.90,
    "timestamp_proximity":    0.35,
    "feature_distribution":   0.45,
}

def _safe_float(v, default=0.0):
    try: return float(v)
    except: return default

def _cosine_similarity(a, b):
    keys = set(a) | set(b)
    if not keys: return 0.0
    dot = sum(a.get(k,0)*b.get(k,0) for k in keys)
    mag_a = math.sqrt(sum(v**2 for v in a.values()))
    mag_b = math.sqrt(sum(v**2 for v in b.values()))
    if mag_a==0 or mag_b==0: return 0.0
    return dot/(mag_a*mag_b)

def _mass_props_similarity(mp_a, mp_b):
    if not mp_a or not mp_b: return 0.0
    scores = []
    for k in ["volume","surface_area","mass"]:
        va = _safe_float(mp_a.get(k,0))
        vb = _safe_float(mp_b.get(k,0))
        if va==0 and vb==0: scores.append(1.0)
        elif va==0 or vb==0: scores.append(0.0)
        else: scores.append(min(va,vb)/max(va,vb))
    com_a = mp_a.get("center_of_mass",[0,0,0])
    com_b = mp_b.get("center_of_mass",[0,0,0])
    if len(com_a)==3 and len(com_b)==3:
        dist = math.sqrt(sum((a-b)**2 for a,b in zip(com_a,com_b)))
        scores.append(max(0.0, 1.0 - dist/1.0))
    return sum(scores)/len(scores) if scores else 0.0

def _author_overlap(authors_a, authors_b):
    if not authors_a or not authors_b: return 0.0
    set_a = {a.lower().strip() for a in authors_a if a}
    set_b = {b.lower().strip() for b in authors_b if b}
    if not set_a or not set_b: return 0.0
    if set_a & set_b: return 1.0
    for a in set_a:
        for b in set_b:
            if len(a)>3 and len(b)>3 and (a in b or b in a): return 0.7
    return 0.0

def _timestamp_proximity(fs_a, fs_b, ole_a, ole_b):
    best = 0.0
    pairs = [
        (fs_a.get("fs_created"),  fs_b.get("fs_created")),
        (fs_a.get("fs_modified"), fs_b.get("fs_modified")),
        (ole_a.get("created"),    ole_b.get("created")),
        (ole_a.get("last_saved"), ole_b.get("last_saved")),
    ]
    for ta,tb in pairs:
        if isinstance(ta,datetime.datetime) and isinstance(tb,datetime.datetime):
            diff = abs((ta-tb).total_seconds())
            if diff<=10: score=1.0
            elif diff<=300: score=1.0-(diff-10)/290
            else: score=0.0
            best = max(best,score)
    return best

def compare_files(parsed_a, parsed_b):
    fp_a = parsed_a.get("fingerprints",{})
    fp_b = parsed_b.get("fingerprints",{})
    mp_a = parsed_a.get("mass_props",{})
    mp_b = parsed_b.get("mass_props",{})
    fs_a = parsed_a.get("fs_metadata",{})
    fs_b = parsed_b.get("fs_metadata",{})
    ol_a = parsed_a.get("ole_metadata",{})
    ol_b = parsed_b.get("ole_metadata",{})

    scores = {}
    h_a = parsed_a.get("full_hash",""); h_b = parsed_b.get("full_hash","")
    scores["full_hash_match"] = 1.0 if (h_a and h_b and h_a==h_b) else 0.0
    g_a = fp_a.get("geometry_hash",""); g_b = fp_b.get("geometry_hash","")
    scores["geometry_hash_match"] = 1.0 if (g_a and g_b and g_a==g_b) else 0.0
    fs_ha = fp_a.get("feature_sequence_hash",""); fs_hb = fp_b.get("feature_sequence_hash","")
    scores["feature_sequence_match"] = 1.0 if (fs_ha and fs_hb and fs_ha==fs_hb) else 0.0
    fn_a = fp_a.get("feature_name_sequence_hash",""); fn_b = fp_b.get("feature_name_sequence_hash","")
    scores["feature_name_seq_match"] = 1.0 if (fn_a and fn_b and fn_a==fn_b) else 0.0
    fset_a = fp_a.get("feature_set_hash",""); fset_b = fp_b.get("feature_set_hash","")
    scores["feature_set_match"] = 1.0 if (fset_a and fset_b and fset_a==fset_b) else 0.0
    scores["mass_props_similarity"] = _mass_props_similarity(mp_a,mp_b)
    cp_a = fp_a.get("custom_props_hash",""); cp_b = fp_b.get("custom_props_hash","")
    scores["custom_props_match"] = 1.0 if (cp_a and cp_b and cp_a==cp_b) else 0.0
    auth_a = parsed_a.get("authors",[]); auth_b = parsed_b.get("authors",[])
    scores["author_overlap"] = _author_overlap(auth_a,auth_b)
    scores["timestamp_proximity"] = _timestamp_proximity(fs_a,fs_b,ol_a,ol_b)
    dist_a = fp_a.get("feature_type_counts",{}); dist_b = fp_b.get("feature_type_counts",{})
    scores["feature_distribution"] = _cosine_similarity(dist_a,dist_b)

    total_weight = 0.0; weighted_sum = 0.0
    for signal, score in scores.items():
        w = WEIGHTS.get(signal, 0.0)
        if signal in ("geometry_hash_match","mass_props_similarity") and not mp_a and not mp_b: continue
        if signal in ("feature_sequence_match","feature_name_seq_match","feature_set_match","feature_distribution"):
            if not fp_a.get("feature_count") and not fp_b.get("feature_count"): continue
        if signal=="custom_props_match" and not parsed_a.get("custom_props") and not parsed_b.get("custom_props"): continue
        weighted_sum += score*w; total_weight += w

    composite = min(1.0, max(0.0, weighted_sum/total_weight if total_weight>0 else 0.0))
    if composite>=PLAGIARISM_HIGH: risk="HIGH"
    elif composite>=PLAGIARISM_MEDIUM: risk="MEDIUM"
    elif composite>=PLAGIARISM_LOW: risk="LOW"
    else: risk="NONE"

    flags = []
    if scores["full_hash_match"]==1.0: flags.append("IDENTICAL_FILES")
    if scores["geometry_hash_match"]==1.0: flags.append("IDENTICAL_GEOMETRY")
    if scores["feature_sequence_match"]==1.0: flags.append("IDENTICAL_FEATURE_SEQUENCE")
    if scores["feature_name_seq_match"]==1.0: flags.append("IDENTICAL_FEATURE_NAMES")
    if scores["feature_set_match"]==1.0: flags.append("IDENTICAL_FEATURE_SET")
    if scores["mass_props_similarity"]>=0.999: flags.append("IDENTICAL_MASS_PROPERTIES")
    elif scores["mass_props_similarity"]>=0.95: flags.append("NEAR_IDENTICAL_MASS_PROPERTIES")
    if scores["custom_props_match"]==1.0: flags.append("IDENTICAL_CUSTOM_PROPERTIES")
    if scores["author_overlap"]>=1.0: flags.append("SHARED_AUTHOR_USERNAME")
    elif scores["author_overlap"]>0: flags.append("PARTIAL_AUTHOR_MATCH")
    if scores["timestamp_proximity"]>=0.9: flags.append("NEAR_IDENTICAL_CREATION_TIME")
    elif scores["timestamp_proximity"]>=0.5: flags.append("CLOSE_CREATION_TIME")

    set_a = {a.lower().strip() for a in auth_a if a}
    set_b = {b.lower().strip() for b in auth_b if b}
    shared_authors = sorted(set_a & set_b)

    return {
        "file_a": parsed_a["file_name"], "file_b": parsed_b["file_name"],
        "path_a": parsed_a["file_path"], "path_b": parsed_b["file_path"],
        "scores": scores, "composite_score": composite,
        "risk_level": risk, "flags": flags,
        "shared_authors": shared_authors,
        "comparison_type": "student_vs_student",
    }

def batch_compare(parsed_files):
    results = []
    n = len(parsed_files)
    for i in range(n):
        for j in range(i+1,n):
            results.append(compare_files(parsed_files[i],parsed_files[j]))
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results

def compare_against_reference(parsed_student, parsed_reference):
    result = compare_files(parsed_student, parsed_reference)
    result["comparison_type"] = "student_vs_reference"
    result["file_b"] = f"[REF] {parsed_reference['file_name']}"
    return result

def get_risk_color(risk_level):
    return {"HIGH":"#FF4D6D","MEDIUM":"#FF9F43","LOW":"#FFD166","NONE":"#06D6A0"}.get(risk_level,"#9095B4")

def similarity_percentage(score):
    return f"{score*100:.1f}%"
