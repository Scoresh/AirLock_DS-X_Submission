# Responsibility and ethics

## Data sourcing

- **Reference population:** the organizers' NSSE synthetic data, 20,731 fictional respondents. Majors are invented and lemur species stand in for an identity group. No real student records are used. A real deployment would use aggregate enrollment statistics or a secure computation with the registrar (see JIFF below), never a copy of individual records.
- **Documents:** the demo and test theses were written by the team; every person in them is fictional. Their participants were described with combinations that exist in the synthetic data so that k-values are meaningful.
- **Thesis rules:** the *BU Guide for Writers of Theses and Dissertations* provided by the organizers; each rule cites its page.
- **Handling:** the data file stays in a git-ignored folder; analysis scripts print aggregates only and suppress counts below 5; tests use a Faker fixture with the same columns.

## Privacy by design

- **Local first.** Parsing, identifier detection, profiling, risk scoring, rewriting and format checks all run on the user's machine. Name detection uses a small local NLP model (spaCy), not an LLM.
- **One network call, behind a gate.** Only `review._send` talks to a model, and the backend refuses it while any described participant has k < 5. A test records the outgoing request and fails if any name, email, phone number or ID appears in it.
- **Reversible tokens, local key.** Identifiers become tokens such as `[PERSON_01]`; the key file never leaves the machine and is never returned by the API. Model feedback is de-tokenized locally.
- **The user sees what is sent.** The comparison view shows the original next to the exact prepared text, and only says "Sent to model" after a model actually received it.
- **The model is the user's choice.** Any OpenAI-compatible endpoint, including a lab-approved model or a local one, so labs bound by data agreements can stay within them.
- **Fail closed.** If name detection or the reference data is missing, the app stops and says why instead of returning a clean-looking result.

## Fairness: who carries the risk

Re-identification risk is not shared equally. On the exact details, members of the smallest affiliation group in the data are unique **26.3%** of the time and high risk **47.2%** of the time, compared with **11.2%** and **17.0%** in the largest group (`docs/RISK_REPORT.md`, section 3). "Anonymized" descriptions therefore expose minority groups first, and the rewrites needed to protect them (omitting affiliation) also remove the very information that makes their experience visible in research.

We respond to this in three ways: the gate applies the same threshold to everyone, so smaller groups are not left exposed; suggestions are ranked by how much they help, so authors can keep the details that matter most to their argument; and we report risk as levels and estimates rather than as a verdict on a group.

## Limitations

- **k is an estimate.** It counts matches in a fictional reference population, not the real student body. A low k is a reason to rewrite, not proof that someone is identified; a high k is not a guarantee of anonymity. The UI says "Ready for review", never "anonymous".
- **Rule-based extraction can miss details.** Participant descriptions are recognised from patterns and the data's vocabulary; unusual phrasing, nicknames or details outside the scored columns (for example a hometown) are not counted. The user confirms the extracted profile on screen.
- **Name detection can err both ways.** We add safeguards against headings and equipment being taken for names and replace a name everywhere once found, but a missed name is possible, which is why the prepared text is shown before anything is sent.
- **Models make mistakes.** Model findings are labelled as such, quote the rubric line they apply, and are kept separate from the measurable rules, which run as code.
- **Synthetic data, synthetic stakes.** Results on the demo depend on the organizers' synthetic distribution.

## Misuse

The tool could in principle help someone test whether a description identifies a person. We limit this by design: it only scores descriptions in the document the user uploads, never outputs or guesses an identity, never shows matching records, and never exposes the reference population (only counts). Logging and session data are kept in memory and the token key stays on the user's machine.

## Secure counting (in progress)

To avoid holding a copy of any population file, a two-party computation with JIFF (`jiff/`) lets a researcher and a registrar compute how many records match a profile while each side sees only the count. It is being built as a standalone demo first and then as a switch in the risk engine.
