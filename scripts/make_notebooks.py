"""Generate the notebooks/ folder: one notebook per phase whose cells are the phase script, split at section
comments, so the work can be stepped through interactively. Run from the repo root."""
import re
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"; NB.mkdir(exist_ok=True)
MAP = {
    "00_profile.ipynb": ["00_profile_raw.py", "01_phase0_questions.py", "02_phase0_sql.py"],
    "01_baseline_ml.ipynb": ["10_phase1.py"],
    "02_baseline_did.ipynb": ["10_phase1.py"],
    "03_stress_tests.ipynb": ["20_phase2.py"],
    "04_elasticity.ipynb": ["30_phase3_elasticity.py"],
    "05_allocation.ipynb": ["40_phase4_allocation.py", "50_validation.py"],
}
for nb_name, scripts in MAP.items():
    nb = nbf.v4.new_notebook()
    nb.cells.append(nbf.v4.new_markdown_cell(f"# {nb_name.replace('.ipynb','').replace('_',' ').title()}\n\n"
                                             "Thin notebook over the phase script(s) in `scripts/`. Cells are split at the "
                                             "`# ----` section markers. Run from the repo root (`jupyter lab`), or just run the scripts."))
    nb.cells.append(nbf.v4.new_code_cell("import os, sys\nos.chdir(os.path.dirname(os.getcwd())) if os.path.basename(os.getcwd()) == 'notebooks' else None\nsys.path.insert(0, os.getcwd())\n%matplotlib inline"))
    for s in scripts:
        src = (ROOT / "scripts" / s).read_text(encoding="utf-8")
        src = src.replace('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path(os.getcwd())')
        src = src.replace('matplotlib.use("Agg")', '')
        parts = re.split(r"\n(?=# -{20,})", src)
        nb.cells.append(nbf.v4.new_markdown_cell(f"## scripts/{s}"))
        for ptxt in parts:
            if ptxt.strip():
                nb.cells.append(nbf.v4.new_code_cell(ptxt.strip("\n")))
    nbf.write(nb, NB / nb_name)
    print("wrote", nb_name)
