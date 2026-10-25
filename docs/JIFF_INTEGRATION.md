# Integrated JIFF population checks

## Run the synthetic product demo

Activate the existing Python backend environment and install `jiff/` dependencies with `npm install` (or `pnpm install --frozen-lockfile`). Then, from the repository root:

```sh
python backend/scripts/run_jiff_demo.py
# Automated real-process verification, without any model call:
python backend/scripts/run_jiff_demo.py --self-test
```

Pass `--node /absolute/path/to/node` if Node is not on PATH. Alternate ports: `--port 18003 --relay-port 19411 --bridge-port 19412`.

The launcher starts a localhost JIFF relay, a trusted local Researcher bridge, a separate Registrar process, and FastAPI. It generates random service tokens in memory and passes them via environment variables, never through browser code or command-line arguments. Ctrl-C stops the services. The self-test keeps token key files in a temporary directory and removes them at exit.

In the app choose **Secure population check · JIFF prototype**, then **Open sample document**. The supplied PDF matches the public demo manifest. It contains one supported participant profile with k=1. Accept the affiliation omission to obtain k=5. Local formatting checks run after the gate opens; external model review still requires an explicit user action and a configured model.

The normal sample remains available in local pandas mode. Source is fixed at scrub time for each document; start a new document to change sources. CSV mode remains local and does not use this protocol.

## Ownership and data flow

```text
Researcher machine                       Registrar machine/process
PDF -> local scrub -> private profiles   private normalized population JSON
                  |                                  |
        local authenticated bridge -> JIFF shares <- registrar JIFF client
                  |             relay                |
                  +---- opened aggregate counts -----+
                  |
        trusted backend gate -> prepared document -> selected review model
```

In the all-local synthetic launcher these are separate processes on one computer, not distinct institutional hosts. The bridge is trusted Researcher-side infrastructure: plaintext profiles pass from FastAPI to that authenticated localhost process. Plaintext profiles and population records are not submitted to the relay HTTP job API. Its queue contains only random session IDs, public-manifest fingerprints, query counts and expirations.

JIFF's trusted crypto provider supplies preprocessing material. Security assumes honest-but-curious non-colluding parties and a trusted preprocessing relay. Party identity/authentication at the JIFF socket layer, malicious-input proofs, production TLS deployment and a cryptographic result attestation service are not implemented. The localhost bearer token protects the backend-to-bridge result channel under this trusted-local-process model; it is not a proof against a compromised Researcher machine.

## Public versus private data

`jiff/fixtures/public-manifest.json` is a team-authored public codebook with a population ID, version, row count and ordered category domains. `jiff/fixtures/population.json` contains eight explicitly fictional records for the Registrar. Both ship for reproducibility; neither is real NSSE or Registrar data.

For manual services:

| Process | Configuration |
|---|---|
| Relay: `node jiff/server.js` | `PORT`, `JIFF_COORD_TOKEN` |
| Researcher bridge: `node jiff/bridge.js` | `JIFF_MANIFEST`, `JIFF_RELAY_URL`, `JIFF_COORD_TOKEN`, `JIFF_BRIDGE_TOKEN`, optional `JIFF_BRIDGE_PORT` |
| Registrar: `node jiff/registrar.js` | `JIFF_MANIFEST`, `JIFF_POPULATION`, `JIFF_RELAY_URL`, `JIFF_COORD_TOKEN` |
| FastAPI | `JIFF_MANIFEST`, `JIFF_BRIDGE_URL`, `JIFF_BRIDGE_TOKEN` |

Each service token must be a random secret of at least 32 characters. They are operator configuration, never frontend inputs. Use different bridge and coordinator tokens. Only the Registrar process needs the private population file; both sides need the reviewed public manifest. Never derive or publish a confidential population's unique values automatically as a public codebook.

Private rows must already be normalized to the labels and derived fields in `risk_config.json`: class labels, major fields, major-count labels and transfer-history labels. Missing population values use reserved code 0. Omit a query field to generalize it; query null is rejected. Values outside the public domains fail closed. This prototype counts unweighted rows; aggregated `n` rows require a future weighted protocol.

## Backend gate lifecycle

- `POST /scrub/{doc_id}?source=jiff` fixes the source and extracts participant profiles using only the public vocabulary. It does not load `risk.population()`.
- Existing `/score` requests remain unchanged. The backend obtains all distinct current and proposed profiles and submits one authenticated batch request. Individual MPC sessions run serially within the batch.
- The bridge chooses fresh random session IDs, verifies manifest identity, executes real Researcher JIFF clients and returns counts bound to the backend's request binding. No frontend count-submission endpoint exists.
- The backend validates result length, integer bounds, document-state binding, public-manifest fingerprint, population ID and version before saving a score.
- Accepting edits invalidates the old score before computation starts. A failure leaves no authorized score and never silently falls back to pandas.
- A per-document lock prevents score, scrub and review operations from authorizing inconsistent document states.
- Both `/review` and `/rubric-check` verify the stored binding and gate. JIFF results expire after five minutes. The backend rechecks the configured public manifest and live bridge manifest before review.
- Operators must increment the public population version whenever records change and restart the bridge/Registrar together. The version is an operator assertion, not a digest proving the content of the private population.
- Rescrubbing resets accepted edits and previous authorization. Browser-supplied `k` or `gate_open` fields have no authority.

`ScoreResult` adds `population_source`, `population_id`, and `population_version` with backward-compatible defaults. Existing request contracts and the default local mode are preserved. `/status?source=jiff` checks the public manifest and local detection setup; a successful status does not imply the Registrar is online. A count attempt reports offline/timeout errors explicitly.

## Verification performed

- Python suite: **57 passed**, including existing local-mode tests and new source isolation, high-risk blocking, stale-text/edits/version/expiry rejection, failure invalidation, forged-result rejection, rescrub invalidation and browser-count non-authority tests.
- Node suite: **8 passed**, including real two-party counts and an authenticated bridge with the Registrar in a separate OS process. It covers the successful-disconnect regression: pending shares must flush before closing the session.
- Real HTTP self-test: generated PDF, local parsing and NLP scrubbing, JIFF k=1, HTTP 403 on review, accepted rewrite, JIFF k=5, local-rule review, and comparison text containing neither the original email nor the omitted affiliation.
- Browser: select JIFF, open its sample PDF, inspect source/version and k=1, accept the affiliation rewrite, observe k=5 and a ready gate with local formatting findings.

## Limits and next work

Maximum 64 rows, 8 fields, 32 categories per field and 32 distinct candidate profiles per batch. This is integrated functionality on a small synthetic population, not a benchmark or deployment against all 20,731 NSSE records. Larger domains and population scale need protocol/performance work; batches currently have a 65-second bridge request timeout.

Exact output counts, public domains, population size and traffic metadata are revealed. Repeated queries can expose membership. Query authorization, budgets, threshold-only output/suppression policy, audited public-domain governance, remote-institution deployment and malicious-party security remain required before sensitive real-data use. Passing k>=5 is not a guarantee of anonymity.
