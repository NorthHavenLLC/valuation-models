# Valuation models

Five classical equity valuation lenses on one active case. Change [`cases/active.yaml`](cases/active.yaml) once — every notebook loads the same equity, peers, and segments. Statements are cached under `data/equities/`.

**Paper:** [docs/integrated_valuation_modeling.md](docs/integrated_valuation_modeling.md)

| Notebook | Role |
| --- | --- |
| `notebooks/00_active_case.ipynb` | Switch the universe and smoke all models |
| `notebooks/01_three_statement.ipynb` | Linked statements |
| `notebooks/02_dcf.ipynb` | DCF + sensitivity surfaces |
| `notebooks/03_comps.ipynb` | Trading comps |
| `notebooks/04_lbo.ipynb` | LBO + IRR surface |
| `notebooks/05_sum_of_the_parts.ipynb` | Sum of the parts |
| `notebooks/06_valuation_bridge.ipynb` | Football field across methods |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests -q
jupyter lab notebooks/00_active_case.ipynb
```

## Package

Python package: `valuation/` — statements, DCF, comps, LBO, SOTP, bridge, charts.
