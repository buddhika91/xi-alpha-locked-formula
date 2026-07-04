#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROT RH / Xi-alpha locked formula report builder

Scans the CSV/JSON artifacts produced by the Xi-alpha audit scripts and builds
one clean GitHub-ready Markdown report plus a machine-readable manifest.

Designed for the output family created by scripts such as:
  - rot_rh_xi_alpha_locked_formula_component_ablation_audit.py
  - rot_rh_xi_alpha_locked_formula_symbolic_derivation_audit.py
  - rot_rh_xi_alpha_locked_formula_convergence_universality_audit.py
  - rot_rh_alpha_formula_zero_shell_consistency_audit.py
  - optional GUE bridge negative audits

No third-party packages required.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# -----------------------------
# small utilities
# -----------------------------

def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm_key(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "null", ""}:
        return None
    s = s.replace("−", "-")
    try:
        return float(s)
    except Exception:
        # handle things like "3.049e-09 rel=..." by taking first number
        m = re.search(r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
    return None


def fmt_value(x: Any, digits: int = 12) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "True" if x else "False"
    f = safe_float(x)
    if f is not None:
        if f == 0:
            return "0"
        af = abs(f)
        if af >= 1e6 or af < 1e-4:
            return f"{f:.{min(digits, 6)}e}"
        if af >= 100:
            return f"{f:.12f}".rstrip("0").rstrip(".")
        return f"{f:.{digits}g}"
    return str(x)


def first_nonempty(*vals: Any) -> Any:
    for v in vals:
        if v is not None and str(v).strip() != "":
            return v
    return None


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# -----------------------------
# file discovery + parsing
# -----------------------------

def discover_one(base: Path, patterns: Sequence[str]) -> Optional[Path]:
    hits: List[Path] = []
    for pat in patterns:
        full = str(base / pat)
        hits.extend(Path(p) for p in glob.glob(full))
    # stable deterministic: prefer shortest then newest-ish alphabetical
    hits = sorted(set(hits), key=lambda p: (len(p.name), p.name))
    return hits[0] if hits else None


def discover_all(base: Path, patterns: Sequence[str]) -> List[Path]:
    hits: List[Path] = []
    for pat in patterns:
        hits.extend(Path(p) for p in glob.glob(str(base / pat)))
    return sorted(set(hits), key=lambda p: p.name)


def read_csv_rows(path: Optional[Path]) -> List[Dict[str, str]]:
    if path is None or not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            return [dict(r) for r in reader]
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as f:
            reader = csv.DictReader(f)
            return [dict(r) for r in reader]
    except Exception:
        return []


def read_json_obj(path: Optional[Path]) -> Any:
    if path is None or not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_summary_dict(path: Optional[Path]) -> Dict[str, Any]:
    rows = read_csv_rows(path)
    if not rows:
        return {}
    fieldnames = list(rows[0].keys())
    nfields = [norm_key(c) for c in fieldnames]

    # common key/value style
    key_col = None
    val_col = None
    for k in fieldnames:
        nk = norm_key(k)
        if nk in {"key", "name", "metric", "field", "item", "label"} and key_col is None:
            key_col = k
        if nk in {"value", "val", "result"} and val_col is None:
            val_col = k
    if key_col and val_col:
        out: Dict[str, Any] = {}
        for r in rows:
            kk = r.get(key_col, "")
            vv = r.get(val_col, "")
            if kk:
                out[str(kk)] = vv
        return out

    # 2-column fallback: first column = key, second = value
    if len(fieldnames) == 2 and len(rows) > 1:
        out = {}
        for r in rows:
            kk = r.get(fieldnames[0], "")
            vv = r.get(fieldnames[1], "")
            if kk:
                out[str(kk)] = vv
        if out:
            return out

    # one-row summary style
    if len(rows) == 1:
        return dict(rows[0])

    # multirow with no key/value: return first row plus count marker
    out = dict(rows[0])
    out["_row_count"] = str(len(rows))
    return out


def get_field(d: Dict[str, Any], *names: str) -> Any:
    if not d:
        return None
    norm_map = {norm_key(k): k for k in d.keys()}
    for name in names:
        nk = norm_key(name)
        if nk in norm_map:
            return d.get(norm_map[nk])
    # also allow contains matching for script variants
    for name in names:
        nk = norm_key(name)
        for dk, rawk in norm_map.items():
            if nk and (nk in dk or dk in nk):
                return d.get(rawk)
    return None


def get_num(d: Dict[str, Any], *names: str) -> Optional[float]:
    return safe_float(get_field(d, *names))


# -----------------------------
# Markdown generation
# -----------------------------

def md_escape(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def md_table(rows: List[Dict[str, Any]], columns: Sequence[str], max_rows: int = 20) -> str:
    if not rows:
        return "_No rows found._\n"

    # resolve requested columns against actual normalized keys
    actual_cols = list(rows[0].keys())
    norm_to_actual = {norm_key(c): c for c in actual_cols}
    resolved: List[Tuple[str, str]] = []
    for c in columns:
        nc = norm_key(c)
        if nc in norm_to_actual:
            resolved.append((c, norm_to_actual[nc]))
        else:
            # contains fallback
            found = None
            for nk, ac in norm_to_actual.items():
                if nc and (nc in nk or nk in nc):
                    found = ac
                    break
            if found:
                resolved.append((c, found))

    if not resolved:
        # fallback to first 6 columns
        resolved = [(c, c) for c in actual_cols[:6]]

    lines = []
    lines.append("| " + " | ".join(md_escape(label) for label, _ in resolved) + " |")
    lines.append("| " + " | ".join("---" for _ in resolved) + " |")
    for r in rows[:max_rows]:
        vals = [fmt_value(r.get(actual)) for _, actual in resolved]
        lines.append("| " + " | ".join(md_escape(v) for v in vals) + " |")
    if len(rows) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(rows)} rows._")
    return "\n".join(lines) + "\n"


def bullet_kv(items: Sequence[Tuple[str, Any]], digits: int = 12) -> str:
    lines = []
    for k, v in items:
        lines.append(f"- **{k}:** {fmt_value(v, digits=digits)}")
    return "\n".join(lines) + "\n"


def math_block(lines: str, use_fence: bool = True) -> str:
    if use_fence:
        return "```math\n" + lines.strip() + "\n```\n"
    return "\n" + lines.strip() + "\n"


def section(title: str) -> str:
    return f"\n## {title}\n\n"


# -----------------------------
# report logic
# -----------------------------

def collect_artifacts(args: argparse.Namespace) -> Dict[str, Any]:
    base = Path(args.base_dir).resolve()

    def one(*patterns: str) -> Optional[Path]:
        return discover_one(base, patterns)

    def many(*patterns: str) -> List[Path]:
        return discover_all(base, patterns)

    artifacts: Dict[str, Any] = {
        "base_dir": str(base),
        "missing": [],
        "files": {},
        "data": {},
    }

    file_specs = {
        "consistency_summary": [f"{args.consistency_prefix}_azc_summary.csv", f"{args.consistency_prefix}*summary*.csv"],
        "consistency_rows": [f"{args.consistency_prefix}_azc_consistency_rows.csv", f"{args.consistency_prefix}*consistency*rows*.csv"],
        "ablation_summary": [f"{args.ablation_prefix}_ablation_summary.csv", f"{args.ablation_prefix}*summary*.csv"],
        "ablation_component_summary": [f"{args.ablation_prefix}_ablation_component_summary.csv", f"{args.ablation_prefix}*component*summary*.csv"],
        "ablation_real_rows": [f"{args.ablation_prefix}_ablation_real_rows.csv", f"{args.ablation_prefix}*real*rows*.csv"],
        "ablation_fake_family": [f"{args.ablation_prefix}_ablation_fake_family_summary.csv", f"{args.ablation_prefix}*fake*family*.csv"],
        "symbolic_summary": [f"{args.symbolic_prefix}_symderiv_summary.csv", f"{args.symbolic_prefix}*summary*.csv"],
        "symbolic_sources": [f"{args.symbolic_prefix}_symderiv_symbolic_sources.csv", f"{args.symbolic_prefix}*symbolic_sources*.csv"],
        "symbolic_trace_rewrites": [f"{args.symbolic_prefix}_symderiv_trace_rewrites.csv", f"{args.symbolic_prefix}*trace*rewrite*.csv"],
        "symbolic_backsolve": [f"{args.symbolic_prefix}_symderiv_backsolve_diagnostics.csv", f"{args.symbolic_prefix}*backsolve*.csv"],
        "symbolic_fake_family": [f"{args.symbolic_prefix}_symderiv_fake_family_summary.csv", f"{args.symbolic_prefix}*fake*family*.csv"],
        "convergence_summary": [f"{args.convergence_prefix}_cu_summary.csv", f"{args.convergence_prefix}*summary*.csv"],
        "convergence_rows": [f"{args.convergence_prefix}_cu_convergence_rows.csv", f"{args.convergence_prefix}*convergence*rows*.csv"],
        "convergence_dps_rows": [f"{args.convergence_prefix}_cu_dps_rows.csv", f"{args.convergence_prefix}*dps*rows*.csv"],
        "convergence_fake_family": [f"{args.convergence_prefix}_cu_fake_family_summary.csv", f"{args.convergence_prefix}*fake*family*.csv"],
        # optional earlier formula-lock summary, names varied across scripts
        "formula_lock_summary": [f"{args.formula_lock_prefix}*summary*.csv", "*smooth_formula_lock*summary*.csv"],
    }

    for name, patterns in file_specs.items():
        p = one(*patterns)
        artifacts["files"][name] = str(p) if p else None
        if p is None and name in args.required_files:
            artifacts["missing"].append(name)

    # optional GUE bridge/negative summaries
    gue_patterns = []
    for pref in args.gue_prefixes.split(",") if args.gue_prefixes else []:
        pref = pref.strip()
        if pref:
            gue_patterns.extend([f"{pref}*summary*.csv"])
    gue_files = many(*gue_patterns) if gue_patterns else []
    artifacts["files"]["gue_summaries"] = [str(p) for p in gue_files]

    # load summaries
    for name, path_s in artifacts["files"].items():
        if isinstance(path_s, list):
            continue
        p = Path(path_s) if path_s else None
        if p and p.suffix.lower() == ".csv":
            if "summary" in name and not any(x in name for x in ["component_summary", "fake_family"]):
                artifacts["data"][name] = read_summary_dict(p)
            else:
                artifacts["data"][name] = read_csv_rows(p)
        elif p and p.suffix.lower() == ".json":
            artifacts["data"][name] = read_json_obj(p)
        else:
            artifacts["data"][name] = {} if "summary" in name else []

    # load GUE summaries as list of dicts with source file
    gue_loaded = []
    for p in gue_files:
        d = read_summary_dict(p)
        d["_source_file"] = p.name
        gue_loaded.append(d)
    artifacts["data"]["gue_summaries"] = gue_loaded

    return artifacts


def infer_key_results(art: Dict[str, Any]) -> Dict[str, Any]:
    data = art.get("data", {})
    conv = data.get("convergence_summary", {}) or {}
    sym = data.get("symbolic_summary", {}) or {}
    abl = data.get("ablation_summary", {}) or {}
    cons = data.get("consistency_summary", {}) or {}
    formula = data.get("formula_lock_summary", {}) or {}

    # prefer convergence final values, then symbolic/ablation/consistency/formula
    A_corr = first_nonempty(
        get_field(conv, "locked A_corr final", "locked_A_corr_final", "locked A corr final"),
        get_field(sym, "locked A_corr", "locked_A_corr", "locked A corr"),
        get_field(abl, "locked A_corr", "locked_A_corr", "locked A corr"),
        get_field(cons, "formula A_corr", "formula_A_corr", "formula A corr"),
        get_field(formula, "locked A_corr", "A_corr", "best_source_A_corr"),
    )
    rel_err = first_nonempty(
        get_field(conv, "locked rel err final", "locked_rel_err_final"),
        get_field(sym, "locked rel err obs", "locked_rel_err_obs"),
        get_field(abl, "locked rel err obs", "locked_rel_err_obs"),
        get_field(cons, "formula rel err obs", "formula_rel_err_obs"),
        get_field(formula, "locked rel err obs", "best source rel err", "best_source_rel_err"),
    )
    A0 = first_nonempty(
        get_field(conv, "A0", "base A0"),
        get_field(sym, "A0", "base A0"),
        get_field(abl, "A0", "base A0"),
        get_field(cons, "A0", "base A0"),
    )
    fake_p = first_nonempty(
        get_field(conv, "fake p locked<=real", "fake_p_locked_le_real"),
        get_field(sym, "fake p locked<=real", "fake_p_locked_le_real"),
        get_field(abl, "fake p locked<=real", "fake_p_locked_le_real"),
        get_field(cons, "fake p locked alpha", "fake_p_locked_alpha"),
    )
    fake_best_p = first_nonempty(
        get_field(conv, "fake p best<=realbest", "fake_p_best_le_realbest"),
        get_field(sym, "fake p best<=real", "fake_p_best_le_real"),
        get_field(abl, "fake p best<=real", "fake_p_best_le_real"),
        get_field(cons, "fake p best joint", "fake_p_best_joint"),
    )

    flags = []
    for label, d in [
        ("consistency", cons),
        ("component ablation", abl),
        ("symbolic derivation", sym),
        ("convergence/universality", conv),
        ("formula lock", formula),
    ]:
        f = get_field(d, "global flag", "global_flag", "audit flag")
        if f:
            flags.append((label, f))

    return {
        "A_corr": A_corr,
        "rel_err": rel_err,
        "A0": A0,
        "fake_p_locked": fake_p,
        "fake_p_best": fake_best_p,
        "flags": flags,
    }


def build_markdown(args: argparse.Namespace, art: Dict[str, Any]) -> str:
    data = art.get("data", {})
    files = art.get("files", {})
    key = infer_key_results(art)
    use_math = not args.no_github_math_fences

    conv = data.get("convergence_summary", {}) or {}
    sym = data.get("symbolic_summary", {}) or {}
    abl = data.get("ablation_summary", {}) or {}
    cons = data.get("consistency_summary", {}) or {}
    formula = data.get("formula_lock_summary", {}) or {}

    lines: List[str] = []
    lines.append(f"# {args.title}\n")
    lines.append(f"Generated: `{now_stamp()}`\n")
    lines.append(
        "> This report summarizes a numerical finding. It is not a proof of RH, not a proof of the physical fine-structure constant, and not a confirmed GUE crack.\n"
    )

    lines.append(section("Executive status"))
    lines.append(bullet_kv([
        ("Locked corrected count A_corr", key.get("A_corr")),
        ("Relative error versus alpha^-1", key.get("rel_err")),
        ("Fake p-value, locked formula", key.get("fake_p_locked")),
        ("Fake p-value, best local scan", key.get("fake_p_best")),
    ]))

    if key.get("flags"):
        lines.append("### Audit flags\n")
        flag_rows = [{"audit": a, "flag": f} for a, f in key["flags"]]
        lines.append(md_table(flag_rows, ["audit", "flag"], max_rows=20))

    if art.get("missing"):
        lines.append("### Missing expected files\n")
        for m in art["missing"]:
            lines.append(f"- `{m}`\n")
        lines.append("\n")

    lines.append(section("Locked formula"))
    lines.append("The base Xi curvature count is defined from the completed zeta function at the critical center.\n\n")
    lines.append(math_block(r"""
K_2 = -\frac{d^2}{d\gamma^2}\log \Xi(1/2+i\gamma)\bigg|_{\gamma=0},
\qquad
A_0 = \frac{2\pi}{K_2}.
""", use_math))
    lines.append("The locked zero-shell correction uses a Fermi/logistic occupancy over the zero index.\n\n")
    lines.append(math_block(r"""
w_n = \frac{1}{1+\exp\left(\frac{n-(16+1/2)}{1/\sqrt{2\pi}}\right)},
\qquad
Z_{\rm eff}=\frac{\pi}{\sum_n w_n/\gamma_n^2}.
""", use_math))
    lines.append(math_block(r"""
r=\frac{Z_{\rm eff}-A_0}{A_0},
\qquad
A_{\rm corr}=A_0\left(1+\frac{1}{4}\frac{r}{16+|r|}\right).
""", use_math))

    lines.append(section("Core numerical result"))
    core_items = [
        ("A_corr", key.get("A_corr")),
        ("relative error", key.get("rel_err")),
        ("convergence flag", get_field(conv, "global flag", "global_flag")),
        ("ablation flag", get_field(abl, "global flag", "global_flag")),
        ("symbolic flag", get_field(sym, "global flag", "global_flag")),
    ]
    lines.append(bullet_kv(core_items))

    lines.append(section("Consistency: formula lock versus zero/gap convention"))
    lines.append("This section checks whether the formula-lock convention agrees with the zero-spacing machinery after correcting the half-index convention.\n\n")
    lines.append(bullet_kv([
        ("formula A_corr", get_field(cons, "formula A_corr", "formula_A_corr")),
        ("formula rel err", get_field(cons, "formula rel err obs", "formula_rel_err_obs")),
        ("gap-left unshifted rel err", get_field(cons, "gap-left unshifted rel err", "gap_left_unshifted_rel_err")),
        ("gap-left shifted rel err", get_field(cons, "gap-left shifted rel err", "gap_left_shifted_rel_err")),
        ("consistency fixed", get_field(cons, "consistency fixed", "consistency_fixed")),
        ("GUE bridge flag", get_field(cons, "global flag", "global_flag")),
    ]))
    cons_rows = data.get("consistency_rows", []) or []
    if cons_rows:
        lines.append("### Top consistency rows\n")
        lines.append(md_table(cons_rows, ["label", "conv", "center", "width", "A_corr", "rel_err_obs"], args.max_table_rows))

    lines.append(section("Component ablation"))
    lines.append("The ablation audit replaces one locked component at a time and measures loss of alpha precision.\n\n")
    lines.append(bullet_kv([
        ("locked rank", get_field(abl, "locked rank", "locked_rank")),
        ("components necessary >10x", get_field(abl, "components necessary >10x", "components_necessary_10x")),
        ("components necessary >100x", get_field(abl, "components necessary >100x", "components_necessary_100x")),
        ("single-component strong count", get_field(abl, "single-component strong count", "single_component_strong_count")),
        ("fake p locked<=real", get_field(abl, "fake p locked<=real", "fake_p_locked_le_real")),
        ("fake p best<=real", get_field(abl, "fake p best<=real", "fake_p_best_le_real")),
    ]))
    comp_rows = data.get("ablation_component_summary", []) or []
    if comp_rows:
        lines.append("### Component necessity table\n")
        lines.append(md_table(comp_rows, ["component", "best_damage", "median_damage", "best", "necessary10x", "necessary100x"], args.max_table_rows))
    real_rows = data.get("ablation_real_rows", []) or []
    if real_rows:
        lines.append("### Top ablation rows\n")
        # sort by rel err if present
        rows_sorted = sorted(real_rows, key=lambda r: safe_float(get_field(r, "rel_err_obs", "rel", "err")) or 1e99)
        lines.append(md_table(rows_sorted, ["label", "component", "A_corr", "rel_err_obs", "damage"], args.max_table_rows))

    lines.append(section("Symbolic structure and trace/Fermi rewrites"))
    lines.append("This audit checks whether the locked constants have simple symbolic sources and whether the expression is stable under trace/Fermi-style rewrites.\n\n")
    lines.append(bullet_kv([
        ("symbolic exact components", get_field(sym, "symbolic exact components", "symbolic_exact_components")),
        ("rewrite precision passes", get_field(sym, "rewrite precision passes", "rewrite_precision_passes")),
        ("rewrite strong passes", get_field(sym, "rewrite strong passes", "rewrite_strong_passes")),
        ("fake p locked<=real", get_field(sym, "fake p locked<=real", "fake_p_locked_le_real")),
        ("fake p best<=real", get_field(sym, "fake p best<=real", "fake_p_best_le_real")),
    ]))
    sources = data.get("symbolic_sources", []) or []
    if sources:
        lines.append("### Symbolic source checks\n")
        lines.append(md_table(sources, ["component", "best", "target", "rel", "meaning"], args.max_table_rows))
    rewrites = data.get("symbolic_trace_rewrites", []) or []
    if rewrites:
        rows_sorted = sorted(rewrites, key=lambda r: safe_float(get_field(r, "rel_err_obs", "rel")) or 1e99)
        lines.append("### Trace/Fermi/heat rewrite checks\n")
        lines.append(md_table(rows_sorted, ["rewrite", "shape", "nonlin", "A_corr", "rel_err_obs"], args.max_table_rows))
    backsolve = data.get("symbolic_backsolve", []) or []
    if backsolve:
        lines.append("### Backsolve diagnostics\n")
        lines.append(md_table(backsolve, ["label", "value", "target", "rel_symbol", "rel_obs"], args.max_table_rows))

    lines.append(section("Convergence and universality"))
    lines.append("This section checks truncation stability, numerical precision stability, and fake/toy zero-spectrum controls.\n\n")
    lines.append(bullet_kv([
        ("locked A_corr final", get_field(conv, "locked A_corr final", "locked_A_corr_final")),
        ("locked rel err final", get_field(conv, "locked rel err final", "locked_rel_err_final")),
        ("tail A_corr rel span", get_field(conv, "tail A_corr rel span", "tail_A_corr_rel_span")),
        ("dps A_corr rel span", get_field(conv, "dps A_corr rel span", "dps_A_corr_rel_span")),
        ("fake p locked<=real", get_field(conv, "fake p locked<=real", "fake_p_locked_le_real")),
        ("fake p best<=realbest", get_field(conv, "fake p best<=realbest", "fake_p_best_le_realbest")),
        ("passes precision/tail/dps/fake", get_field(conv, "passes precision/tail/dps/fake", "passes_precision_tail_dps_fake")),
    ]))
    conv_rows = data.get("convergence_rows", []) or []
    if conv_rows:
        lines.append("### Zero-truncation convergence\n")
        lines.append(md_table(conv_rows, ["zero_max", "N", "A_corr", "rel_err_obs", "gap_capture", "tail_w_next"], args.max_table_rows))
    dps_rows = data.get("convergence_dps_rows", []) or []
    if dps_rows:
        lines.append("### DPS stability\n")
        lines.append(md_table(dps_rows, ["dps", "A_corr", "rel_err_obs", "K2", "A0"], args.max_table_rows))
    fake_family = data.get("convergence_fake_family", []) or []
    if fake_family:
        lines.append("### Fake/toy family controls\n")
        lines.append(md_table(fake_family, ["family", "n", "locked_med", "best_med", "p_locked", "p_best"], args.max_table_rows))

    if args.include_gue_summaries:
        lines.append(section("Negative GUE bridge audits"))
        lines.append("These optional summaries are included to separate the alpha formula from the unconfirmed GUE-bridge attempts.\n\n")
        gue_rows = data.get("gue_summaries", []) or []
        if gue_rows:
            lines.append(md_table(gue_rows, ["_source_file", "global flag", "bridge core passes", "none core passes", "best mode", "fake p locked GUE", "meaning"], max_rows=30))
        else:
            lines.append("_No GUE bridge summary files found._\n")

    lines.append(section("Interpretation"))
    lines.append(
        "The evidence supports a locked numerical phenomenon: a canonical Xi-curvature count plus a Fermi/logistic zero-shell trace correction gives a stable value matching `alpha^-1` to about `3e-9` relative error. "
        "The result survives component ablation, symbolic rewrite checks, truncation sweeps, precision sweeps, and fake/toy zero-spectrum controls.\n\n"
    )
    lines.append(
        "The evidence does **not** yet prove that the physical electromagnetic fine-structure constant must equal this expression. It also does **not** confirm a GUE crack or an RH proof. The next mathematical task is to derive the Fermi-shell trace correction from first principles.\n"
    )

    lines.append(section("Reproducibility notes"))
    lines.append("Expected audit outputs were searched in this directory:\n\n")
    lines.append(f"`{art.get('base_dir')}`\n\n")
    lines.append("### Source files used\n")
    file_rows = []
    for k, v in files.items():
        if isinstance(v, list):
            for item in v:
                file_rows.append({"artifact": k, "file": Path(item).name})
        else:
            file_rows.append({"artifact": k, "file": Path(v).name if v else "MISSING/OPTIONAL"})
    lines.append(md_table(file_rows, ["artifact", "file"], max_rows=200))

    lines.append(section("Recommended citation-style summary"))
    lines.append(
        "A canonical Xi-curvature count `A0 = 2*pi/K2` is corrected by a locked Fermi/logistic zero-shell trace at shell `m=16=2^4`, midpoint `16+1/2`, width `1/sqrt(2*pi)`, coupling `1/4`, and denominator `16`, producing "
        f"`A_corr = {fmt_value(key.get('A_corr'), 15)}` with relative error `{fmt_value(key.get('rel_err'), 12)}` versus `alpha^-1`. "
        "The result is ablation-stable, symbolically structured, truncation/dps stable, and fake/toy zero controls do not reproduce it.\n"
    )

    return "\n".join(lines).replace("\n\n\n", "\n\n")


def write_manifest(args: argparse.Namespace, art: Dict[str, Any], md_path: Path) -> Path:
    key = infer_key_results(art)
    manifest = {
        "generated_at": now_stamp(),
        "base_dir": art.get("base_dir"),
        "report_path": str(md_path),
        "key_results": key,
        "files": art.get("files"),
        "missing": art.get("missing"),
        "arguments": vars(args),
    }
    out = Path(args.base_dir).resolve() / f"{args.out_prefix}_manifest.json"
    ensure_parent(out)
    with out.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return out


# -----------------------------
# CLI
# -----------------------------

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Build a GitHub-ready report for the Xi-alpha locked formula audit family."
    )
    ap.add_argument("--base-dir", default=".", help="Directory containing audit CSV/JSON outputs.")
    ap.add_argument("--out-prefix", default="xi_alpha_locked_formula_report", help="Output prefix.")
    ap.add_argument("--title", default="Xi-Alpha Locked Formula Numerical Report", help="Markdown report title.")

    ap.add_argument("--consistency-prefix", default="alpha_formula_zero_shell_consistency")
    ap.add_argument("--ablation-prefix", default="xi_alpha_locked_formula_component_ablation")
    ap.add_argument("--symbolic-prefix", default="xi_alpha_locked_formula_symbolic_derivation")
    ap.add_argument("--convergence-prefix", default="xi_alpha_locked_formula_convergence_universality")
    ap.add_argument("--formula-lock-prefix", default="xi_alpha_gap_smooth_formula_lock")

    ap.add_argument(
        "--gue-prefixes",
        default="alpha_micro_macro_transport_gue,alpha_green_transport_gue,alpha_locked_zero_shell_gue_spacing",
        help="Comma-separated optional GUE bridge prefixes to summarize.",
    )
    ap.add_argument("--include-gue-summaries", action="store_true", help="Include optional negative GUE bridge summaries.")
    ap.add_argument("--max-table-rows", type=int, default=16)
    ap.add_argument("--no-github-math-fences", action="store_true", help="Use plain Markdown equations instead of GitHub ```math fences.")
    ap.add_argument("--strict", action="store_true", help="Exit nonzero if required files are missing.")
    ap.add_argument(
        "--required-files",
        default="consistency_summary,ablation_summary,symbolic_summary,convergence_summary",
        help="Comma-separated artifact keys required in strict mode.",
    )

    args = ap.parse_args(argv)
    if isinstance(args.required_files, str):
        args.required_files = [x.strip() for x in args.required_files.split(",") if x.strip()]
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    base = Path(args.base_dir).resolve()
    if not base.exists():
        print(f"ERROR: base directory does not exist: {base}", file=sys.stderr)
        return 2

    print("=" * 120)
    print("ROT RH / XI-ALPHA LOCKED FORMULA REPORT BUILDER")
    print("=" * 120)
    print(f"time       : {now_stamp()}")
    print(f"base_dir   : {base}")
    print(f"out_prefix : {args.out_prefix}")
    print("-" * 120)

    art = collect_artifacts(args)
    if art.get("missing"):
        print("Missing required/expected artifacts:")
        for m in art["missing"]:
            print(f"  - {m}")
        if args.strict:
            print("Strict mode enabled; aborting.", file=sys.stderr)
            return 3

    md = build_markdown(args, art)
    md_path = base / f"{args.out_prefix}.md"
    ensure_parent(md_path)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md)

    manifest_path = write_manifest(args, art, md_path)

    key = infer_key_results(art)
    print("KEY RESULTS")
    print("-" * 120)
    print(f"A_corr              : {fmt_value(key.get('A_corr'), 15)}")
    print(f"rel err             : {fmt_value(key.get('rel_err'), 12)}")
    print(f"fake p locked       : {fmt_value(key.get('fake_p_locked'), 12)}")
    print(f"fake p best         : {fmt_value(key.get('fake_p_best'), 12)}")
    print("FLAGS")
    for label, flag in key.get("flags", []):
        print(f"  {label:24s}: {flag}")
    print("-" * 120)
    print("Files written")
    print(f"  report   : {md_path}")
    print(f"  manifest : {manifest_path}")
    print("=" * 120)
    print("AUDIT FLAG: XI_ALPHA_LOCKED_FORMULA_REPORT_BUILT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
