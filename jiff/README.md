# JIFF population-count prototype

Implements Tier 2's first milestone from the project outline: an independent researcher / registrar demo using **real JIFF secret sharing**, not simulated private inputs. It does not replace the application's pandas risk engine or change its gate.

## Run

Requires Node.js 20+ and npm or pnpm.

```sh
cd jiff
npm install
npm start
```

The repository also includes a pnpm lockfile (`pnpm install --frozen-lockfile`). Some package managers report ignored optional native build scripts; the tested protocol works using the JavaScript implementations.

Open `http://127.0.0.1:9111/?party=1` for Researcher and `http://127.0.0.1:9111/?party=2` for Registrar. The relay binds to localhost only. Do not use this prototype as a hosted service.

1. In each window, click **Load fictional example for this role**. The public example is team-created demonstration data, not NSSE population records.
2. Agree a fresh random session ID of 12–80 letters, numbers, underscores or hyphens. Enter it in both windows. It is coordination metadata, not authentication.
3. Both parties must use exactly the same public codebook (including field/category order) and row count. The browser hashes these parameters into the computation ID; mismatches time out instead of silently producing a number.
4. Click **Join secure count** in both windows. Both see `k=1`.
5. Reload both windows and use a fresh session ID. Load the same inputs, but delete `affiliation` from the researcher's profile. The result is `k=5`. This crosses the existing application's numeric threshold, but this independent demo does not authorize a review.
6. For private testing, load your own JSON file through the file input. The file is read in the owning tab; no file-upload endpoint exists. Records must be normalized and use the public codebook. Never add private population files to `public/`.

Limits: 1–64 rows, 1–8 fields, and up to 32 categories per field. These are prototype limits, not a claim of tested NSSE-scale performance. JSON only; CSV ingestion and risk_config normalization are not wired into this demo.

## Protocol

- Researcher (party 1): private profile values and private field-presence bits.
- Registrar (party 2): private normalized population records.
- Public: field names, ordered category domains, number of records, session ID and protocol version.
- Values are encoded by their positions in the public codebook, avoiding hash collisions. Code 0 is reserved for missing population values. Query nulls are rejected; omit a field to generalize it.
- Query and population bits are shared with threshold 2 among parties 1 and 2 over the field Z_65537.
- Bit equality is computed as `1 - x - y + 2xy`. Shared multiplications combine bits and active fields, then shared addition counts matching rows.
- **Only the final sum is opened to both parties.** Per-field and per-row results are never explicitly opened by the application. JIFF uses masked openings internally for multiplication.
- The relay's HTTP surface is a fixed file allowlist. It serves no input-upload endpoint and does not serve keys, populations or arbitrary repository files.

The `crypto_provider: true` configuration relies on JIFF's trusted server for preprocessing material. Security assumes honest-but-curious, non-colluding parties and a trusted preprocessing server. This prototype does not provide malicious-input proofs, authenticated party assignment, query authorization, query budgets, TLS deployment or protection against an actively modified client. Parties can infer information from the count and their own input; do not describe the result as revealing literally nothing about the other input.

Exact counts, including k=0/1, intentionally support the synthetic demonstration. Repeated or adaptive queries can reveal population membership. A registrar deployment needs authorization, rate limits/query budgets, a decision about count suppression or threshold-only results, and an agreed threat model. These policies are separate from MPC correctness.

## Verification

```sh
npm test
```

Integration tests start an ephemeral localhost JIFF server and two real clients. They compare each result with an independent plaintext oracle and assert that the application calls `open` only for the final count. They also check invalid-input rejection and static-file isolation. These tests demonstrate functional correctness, not a cryptographic security audit.

Observed on this machine (8 fictional rows, 3 fields):

| Case | Both parties' result | Time including connection |
|---|---:|---:|
| Exact profile | 1 | 194 ms |
| Affiliation omitted | 5 | 153 ms |
| No matches | 0 | 132 ms |
| All fields omitted | 8 | 131 ms |

Seven test assertions/subtests passed. A browser Researcher also computed k=1 with a separate Node Registrar client; the browser reported 115 ms for computation. These measurements do not predict full-population runtime.

## Next integration boundary

`backend/app/risk.py:k_value(profile)` is the logical counting interface, but replacing only that function is insufficient:

1. Decouple `risk.vocabulary()` and local profile extraction from the private population. Use a reviewed public codebook; do not fetch a codebook derived from confidential population records without approval.
2. Normalize the same fields, labels, derived major fields and missing-value behavior as `risk_config.json`. Weighted `n` rows require a separate weighted protocol; this demo counts one row as one person.
3. Batch the current profile and proposed generalizations into deterministic queries; benchmark before attempting 20,731 records.
4. Make the backend consume a session-bound, authorized protocol result. Never trust a count posted by the browser to open `/review` or `/rubric-check`.
5. Fail closed if a required MPC computation fails. Keep pandas as an explicit synthetic/local mode, rather than silently substituting it for MPC.

No production privacy guarantees, institutional approvals or real registrar partnership are implied.

Official references: https://github.com/multiparty/jiff and https://multiparty.org/jiff/docs/jsdoc/.
