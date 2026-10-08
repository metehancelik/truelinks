# Decisions

Working log of decisions and experiments. Source material for the README.

## Stack

- **Python backend (FastAPI, Pydantic), Next.js frontend, Postgres.** The first few hours were written in TypeScript on Next.js alone. Re-reading the role ("weighted toward backend", "strong core Python") the split was the better fit: the rules, verification and evaluation logic is plain typed Python with no framework in it, and the UI stays a thin client. The port cost about two hours because the design did not change, only the syntax; Zod schemas became Pydantic models.
- **uv, ruff, pyright (strict), pytest.** One lockfile, one command to set up, type errors caught before runtime.

## Architecture

- **Domain-based modules** (`unit`, `lease`, `issue`). The product revolves around the unit; `lease` and `issue` depend on `unit`, never on each other.
- **`LLMProvider` protocol.** Modules depend on one small interface, not on a vendor SDK. The constructor carries configuration, the request carries the work, so one provider serves many tasks with different schemas.
- **Pydantic AI behind the port.** It handles the wire format, JSON-schema constrained output and validation, and re-asks the model with the validation error when an answer does not fit the schema. No hand-rolled HTTP client.
- **Stub provider with per-task resolvers.** Fixtures live with the module that owns them. Answers are schema-validated and an unknown task throws, so the stub cannot pass bad data silently.

## Model

- **Local model: `gemma4:12b` via Ollama**, through the OpenAI-compatible API. Same adapter works with any OpenAI-compatible endpoint by changing env vars.
- **Open weights because of privacy.** A lease carries names, ID references, rents and signatures; issue photos show the inside of people's homes. An open model running on the owner's own machine or cloud means no third party sees tenant data. Zero cost per call is a bonus, not the reason.
- **Thinking off, temperature 0** for extraction. Measured on an M4 / 24 GB: the same prompt took 44 s with thinking on and 9.5 s with it off (~10 tokens/s either way).
- **Context length set explicitly** (`OLLAMA_CONTEXT_LENGTH=16384`). Ollama defaults to 4096 and truncates silently, which would drop the end of a lease (signatures, termination).
- **26b did not fit.** Loading 12b moves ~9 GB into wired memory; a 16 GB model leaves no headroom on 24 GB.

## Verification

- **Rules are deterministic code, not model calls.** R1-R7 are formulas; the model only extracts fields.
- **Three layers, cheapest first:** (1) the quote exists in the document, (2) the value agrees with its quote, (3) an evaluator model checks what code cannot (contradictions, interpretive clauses).
- **The evaluator raises flags, it never changes values.** A human decides.
- **No model-reported confidence.** Field status is computed: `VERIFIED`, `UNVERIFIED`, `MISSING`.

- **A field is trusted only when the code checks and the evaluator both accept it.** An evaluator concern turns a `VERIFIED` field into `UNVERIFIED`, with the concern as the reason and the evaluator's sentence attached. The value is never rewritten. A field the code already rejected keeps its own, deterministic reason, and the evaluator may only raise the three issues that need judgement (`WRONG_SOURCE`, `CONTRADICTION`, `IMPLAUSIBLE`).
- **A missing field never fails a rule.** "Not found by the model" is not "not in the lease", so the rule is `NOT_DETERMINABLE` and a person looks. A rule in the file with no code behind it is also `NOT_DETERMINABLE`, never a silent pass.
- **The model reads, code calculates.** The term in months, and monthly versus annual rent, are extracted only as the lease states them. If the model derived one from the other, rules R4 and R6 could never fail.
- **Signatures need eyes, not text.** In a scanned lease a signature is an image; OCR turned a hand-drawn signature into `PANS A Ae`. For scans the last page now goes to the vision model (see Documents). For text documents the signature is whatever the text says (`/s/ Name` or a blank line).

## Designed, not built yet: one bounded correction round

When a field ends up `UNVERIFIED`, re-ask the extractor for that field only, telling it what was wrong, then run the same three layers on the new answer. At most one retry.

- **Specific feedback.** The retry prompt carries the field, the previous value and quote, and the reason ("the quote is about the deposit, not the rent"), not a generic "try again".
- **Only the flagged fields.** About 10 seconds instead of 75 on local hardware, and correct fields cannot be disturbed (over-correction).
- **Code findings trigger it too.** "Quote not in document" is an objective failure and the most reliable feedback there is.
- **The fix earns its status.** The new value goes through layers 1 to 3 again. If it still fails it stays `UNVERIFIED` and goes to a person. Both attempts stay in the trace.
- **Measure before trusting it.** Fields fixed, fields broken, and seconds per fix, on the evaluation set. Without those three numbers the loop is a guess.

Deferred because the review screen and issue reporting are required by the brief and the loop is not. Known limit either way: extractor and evaluator are the same model and share blind spots; a second model family is the production answer and did not fit in 24 GB.

## Delivery

- **One repository, two apps.** API and UI change together and start with one command. Module boundaries are already drawn if they need to split.
- **Only `web` is public.** The browser calls `/api/*` and Next.js proxies to the Python service: one domain, no CORS.
- **CI builds the images and calls the health endpoint through the proxy,** so a broken Dockerfile fails the pipeline instead of the deploy.
- **Known gap: deploy does not wait for CI.** A push that fails tests is still deployed.

## Experiments

### Decision model as an independent judge (Laya) - not adopted

Tried Laya (open-weights decision model, served locally via `laya-serve`) as a second, independent judge for clause checks, zero-shot, English checkpoint.

| Clause | Expected | Got | Confidence |
|---|---|---|---|
| "increase by 5% on each anniversary" | defined | defined | 0.68 |
| "as mutually agreed between the parties" | undefined | defined | 0.62 |
| "in line with the Qatar Consumer Price Index" | defined | defined | 0.67 |
| "at its discretion" | undefined | undefined | 0.60 |

- 3 of 4 correct. The miss is the exact case rule R2 exists for.
- Confidence was 0.60-0.68 on right and wrong answers alike, so it could not gate anything.
- Value-vs-quote checks were also weak (0.79 for a match, 0.36 for a mismatch); those are handled in code anyway.

**Same four clauses with `gemma4:12b`** (thinking off, rule R2's own wording as the instruction): 4 of 4 correct, each with a one-sentence reason that names the mechanism or its absence. Slower (seconds per clause instead of milliseconds) and it gives no calibrated probability, but the answer is right and the reason is something a reviewer can read. Both prompts named "mutual agreement" as an undefined case, so the comparison is like for like.

**Decision:** the evaluator runs on the LLM. Small sample, zero-shot. A fine-tuned checkpoint or a hosted decision model (Jev, same wire protocol) is the natural next step; the evaluator sits behind an interface so it can be swapped in. Not tried: Jev, because it is hosted and lease text would leave the machine.

## Lease workflow

- **Agents run in the background, the UI polls.** A local model needs a minute per lease, far too long to hold a request open. The upload returns at once with `PROCESSING`; the page asks again every 3 seconds. Trade-off: the job lives in the API process and is lost on a restart (see Scale in the README).
- **Rules are recomputed on every read, never stored.** A person's correction changes the inputs, and every rule that depends on them updates at once. Nothing cached can go stale.
- **Activation is the only place occupancy changes.** It requires every field decided, every non-passing rule acknowledged, and the unit to exist and be available. Uploading or matching a lease changes nothing on the unit.
- **An active lease passes R7 on its own unit.** Found on the live app: after activation the unit is occupied by this very lease, and because rules are recomputed, the lease started failing "unit must be available". The rule now knows which unit the lease occupies.
- **A lease is added on its unit's page, and the person's choice of unit wins.** Linking used to come from the extracted unit reference, so a misread reference left the lease unlinked or on the wrong unit. Now the upload names the unit. The agent's reading still counts: R7 fails when the lease's own wording names a different unit, and a person acknowledges or dismisses it like any other rule.
- **Occupied with no lease on file is a valid state.** The owner's records say two units are occupied; their leases were never uploaded. The data model allows it (activation implies occupied, not the reverse), and the unit page says so plainly instead of looking broken.

## Multi-tenancy

- **`tenant_id` on every row, units keyed by `(tenant_id, unit_id)`.** Two owners can both have `MC-B-1204`. Started with `unit_id` alone, which would have collided across owners; fixed before any real data existed.
- **Isolation in the application, not yet in the database.** Every query filters by tenant. Row-level security in Postgres is the next step, so a forgotten filter cannot leak data.
- **No migrations.** Tables are created on start. The composite-key change meant dropping tables on the server. Alembic comes before any real data.

## Documents

- **Text first, OCR only when there is no text.** A PDF with a text layer is read directly. A scan (no text layer) is rendered at 300 DPI and read by Tesseract.
- **Tesseract, not the vision model, for the text.** A vision model transcribes by generating, so it can put words in the document that are not there, and the quote check would then compare the model with itself. Tesseract makes character mistakes instead, and those surface: OCR read "1 February" as "| February", so the date's quote no longer supports its value and the field goes to a person.
- **Later: a document-specialised open vision model (Qwen-VL family) for OCR, with Tesseract kept as a second reader.** Needs a bigger machine than a 24 GB laptop already running the main model. Two independent readers that agree are stronger evidence than one.
- **Signatures on scans are checked on the page by the vision model, and always come back `UNVERIFIED`.** Code cannot verify a judgement about an image, so a person confirms it, with the page on screen. Assumption: signatures are on the last page.
- **Reading is the first step of the trace** (`read: text`, `read: pdf_text`, `read: ocr`), so a reviewer can see when a lease came from a scan.
- **Known limit: OCR runs inside the upload request.** About 10 seconds a page, capped at 20 pages. Moves to the job queue together with the agents.

## Issues

- **Every finding names its photo, and code checks the number.** A finding that points at a photo that was not sent is flagged as possibly invented.
- **"No visible damage" is enforced by code, not by the prompt.** On a clean kitchen photo with the note "oven is not heating" the model correctly invented nothing, but filled the damage list with "no visible damage", so the flag never fired. The check now also uses the overall condition.
- **Urgency needs written criteria.** An old water stain came back as `high` because the prompt said "high for water leaks". Now: high for an active leak, an electrical fault or anything unsafe; medium for signs of an earlier leak or equipment that does not work; low for cosmetic wear.
- **The agent's draft is kept when a person edits the work order.** What the agent proposed and what the person decided are both on record; the difference is evaluation data.
- **A decided work order becomes read-only.** Before, it stayed editable after "accepted" and gave no feedback while saving. A decision is a record, not a draft.

## Found by testing on the real model

Unit tests run on the stub, so they prove the code path, not the model. Running the deployed app on `gemma4:12b` found four problems the 80+ unit tests could not: R7 on an active lease, the silent no-damage flag, urgency, and the editable decided work order. The R7 and no-damage fixes have unit tests; the urgency prompt and the UI change were checked by hand on the live app.

What went right on the real model: 16 of 16 fields verified on the clean lease; the problem lease failed exactly the six rules it should; the AC photo was assessed correctly with no note at all; the kitchen photo produced no invented damage and the oven's brand was read off the door.

What it showed about the evaluator: it did not flag the 24-month term against 18 months of dates. Rule R4 did. Arithmetic stays in code.


## Evaluation

- **Hand-written answers, never model-written.** A golden set produced by the model would record its own mistakes as correct.
- **Headline metric: trusted but wrong.** A `VERIFIED` field with a wrong value is the only failure review cannot catch. Accuracy alone hides it.
- **Traps over volume.** Two of the six leases exist to tempt specific mistakes: calculating a value the lease does not state, and reading a nearby amount (parking fee, late fee, a previous deposit) as the rent or the deposit.
- **The harness is tested on the stub in CI,** so a broken scorer cannot report a good score.
- **First run on `gemma4:12b`:** 96/96 fields, 0 trusted but wrong, 42/42 rules, 87 s per text lease and 106 s per scan. Read as "the set is too small", not "the agent is perfect". Summaries are scored loosely, and it was one run.
- **On the scan, three right values went to a person:** both signatures and the commencement date that OCR misread. That is the design working: review load is the price of never trusting what cannot be checked.
