"""Regenerate docs/js/data.js from the paper's LaTeX source, so the project page always matches the paper.

    python scripts/build_site_data.py path/to/neurips_2026.tex

Every number on the project page comes from this file. The script fails loudly if a table it expects
is missing or has the wrong number of rows, rather than silently publishing stale numbers.
"""

import json
import os
import re
import sys

FAMILY_ORDER = ["Deception", "Bias", "Forbidden"]


def table_rows(tex, label, ncols):
    """Return the cell lists of a tabular that follows \\label{label}."""
    start = tex.find("\\label{" + label + "}")
    if start < 0:
        raise SystemExit(f"table {label} not found")
    end = tex.find("\\end{tabular", start)
    body = tex[start:end]
    body = body[body.find("\\midrule") + len("\\midrule"):]
    rows = []
    for line in body.split("\\\\"):
        line = re.sub(r"\\(midrule|bottomrule|toprule|cmidrule\([a-z]+\)\{[^}]*\})", "", line).strip()
        if not line or "&" not in line:
            continue
        cells = [clean(c) for c in line.split("&")]
        if len(cells) == ncols:
            rows.append(cells)
    return rows


def clean(cell):
    cell = re.sub(r"\\(textbf|mathbf|emph)\{([^}]*)\}", r"\2", cell)
    cell = cell.replace("\\ ", " ").replace("$", "").replace("\\%", "%").replace("--", "–").replace("~", " ")
    cell = re.sub(r"\\multirow\{[^}]*\}\{[^}]*\}\{([^}]*)\}", r"\1", cell)
    cell = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", cell)
    return re.sub(r"\s+", " ", cell).strip()


def num(x):
    x = x.replace("−", "-").replace("+", "").replace("<", "").strip()
    return float(x)


def expect(rows, n, label):
    if len(rows) != n:
        raise SystemExit(f"{label}: expected {n} rows, found {len(rows)}")
    return rows


def main(tex_path, out_path):
    tex = open(tex_path, encoding="utf-8").read()

    # Table 2: per-variant Integrity Score by condition
    t2 = expect([r for r in table_rows(tex, "tab:model_pressure_breakdown", 11) if r[0] != "Mean"], 18, "Table 2")
    models = []
    for r in t2:
        m = re.match(r"(.*) \((N?R)\)$", r[0])
        v = [num(x) for x in r[1:]]
        models.append({"name": m.group(1), "reasoning": m.group(2) == "R",
                       "none": v[0:3], "implicit": v[3:6], "explicit": v[6:9], "overall": v[9]})

    # Table 3: reasoning effect per family
    reasoning = []
    for r in table_rows(tex, "tab:reasoning_effect", 12):
        name = r[1]
        if not name or name == "Mean":
            continue
        reasoning.append({"family": name, "r": num(r[2]), "nr": num(r[3]), "delta": num(r[4])})
    expect(reasoning, 9, "Table 3")

    # Table 4: facets per variant
    facets = []
    for r in table_rows(tex, "tab:q1_q2_q3_irs", 10):
        if r[0] == "Mean":
            continue
        m = re.match(r"(.*) \((N?R)\)$", r[0])
        v = [num(x) for x in r[1:]]
        facets.append({"name": m.group(1), "reasoning": m.group(2) == "R", "q1": v[0], "q2": round(v[0] + v[1], 1),
                       "q3": round(v[0] + v[2], 1), "q3_q1_wrong": v[3], "q3_q1_right": v[4], "eth_q1": v[6]})
    expect(facets, 18, "Table 4")

    # Table 5 (task list) and Table 6 (definitions)
    tasks = []
    for r in expect(table_rows(tex, "tab:task_list", 6), 18, "Table 5"):
        tasks.append({"id": r[0], "type": r[1], "family": r[2], "domain": r[3], "stage": r[4], "artifact": r[5]})
    defs = {r[0].lower(): r[1] for r in expect(table_rows(tex, "tab:misconduct_definitions", 2), 18, "Table 6")}

    # Tables 9 and 10: per-task summaries
    def per_task(label):
        out = {}
        for r in expect(table_rows(tex, label, 6), 18, label):
            name = re.sub(r"^Ethical\s*–\s*", "", r[0]).lower()
            out[name] = {"mean": num(r[1]), "min": num(r[2]), "max": num(r[3]), "worst": r[4], "best": r[5]}
        return out
    mis, eth = per_task("tab:per_misconduct_is"), per_task("tab:per_ethical_control_is")
    alias = {"reg. clearance blindness": "regulatory clearance blindness"}
    for t in tasks:
        key = alias.get(t["type"].lower(), t["type"].lower())
        t["definition"] = defs[key]
        t["misconduct"] = mis[key]
        t["ethical"] = eth[key]
        if t["type"].lower() in alias:
            t["type"] = "Regulatory clearance blindness"

    # Table 12: McNemar
    mcnemar = [{"pair": r[0], "nr_only": int(r[1]), "r_only": int(r[2]), "chi2": num(r[3]),
                "p_adj": r[4], "direction": r[5]} for r in expect(table_rows(tex, "tab:mcnemar_reasoning", 6), 9, "Table 12")]

    # Table 13: pressure mechanisms
    pressure = [{"tasks": r[0], "explicit": num(r[1]), "implicit": num(r[2]), "t": num(r[3]), "p": r[4], "consistent": r[5]}
                for r in expect(table_rows(tex, "tab:pressure_ttest_summary", 6), 2, "Table 13")]

    # Section 4.4: facet means quoted in the text
    m = re.search(r"Q1 = (\d+\.\d), Q2 = (\d+\.\d) and Q3 = (\d+\.\d)", tex)
    e = re.search(r"ethical control tasks where Q1 = (\d+\.\d), Q2 = (\d+\.\d) and Q3 = (\d+\.\d)", tex)
    if not (m and e):
        raise SystemExit("facet means not found in Section 4.4")
    facet_means = {"all": [float(x) for x in m.groups()], "ethical": [float(x) for x in e.groups()]}

    data = {"source": os.path.basename(tex_path), "models": models, "reasoning": reasoning, "facets": facets,
            "facet_means": facet_means, "tasks": tasks, "mcnemar": mcnemar, "pressure": pressure}
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// Generated by scripts/build_site_data.py from the paper source. Do not edit by hand.\n")
        f.write("window.IB_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
    print(f"wrote {out_path}: {len(models)} variants, {len(tasks)} tasks")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1], os.path.join(here, "..", "docs", "js", "data.js"))
