# Add fallback synthetic population generator

**Files changed:**
- `backend/scripts/make_population.py`
- `data/README.md`

We do not have access to the organizers' NSSE-synthetic.csv yet (the bushare links return 404), so the risk engine had no reference population. Added a script that generates 18,000 made-up students using the NSSE codebook's column names and codes, so `risk.py` can be built now and switched to the real file later without code changes. Proportions (class, age by class, major category, international share, country, housing, athletes) are rough approximations, not real BU statistics. Each row is one student, so WEIGHT2 is 1.0 and k equals the number of matching rows. A fixed seed makes the output identical for every teammate. `--check` picks a real Icelandic student from the population and generalizes one field at a time; k goes 1, 1, 4, 4, 74, which shows the gate opening only after the last step. The trap thesis should describe students taken from real rows like this one, so the starting k is at least 1. The generated CSV stays git-ignored in `data/`.
