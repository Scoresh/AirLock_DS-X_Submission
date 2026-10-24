Put the organizers' NSSE synthetic data, lookup table, and codebook here. This folder is git-ignored.
The NSSE 2026 US codebook (public) is in /docs.

Until we have access to the organizers' NSSE-synthetic.csv, generate a fallback population:

    cd backend
    python scripts/make_population.py --check

This writes `data/population-synthetic.csv`: 18,000 made-up students with NSSE column names
(class, IRage, IRagecol, IRsex19, MAJfirstcode, MAJfirstcol, internat, country22, countrycol22,
living18, athlete, firstgen, WEIGHT2). Proportions are rough guesses, not real BU statistics.
Each row is one student, so WEIGHT2 = 1.0 and k = number of matching rows.
The same seed always produces the same file, so everyone gets identical data.
