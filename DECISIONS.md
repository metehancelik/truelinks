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
- **Signatures are a known blind spot.** In a scanned lease a signature is an image, which text extraction cannot see. R5 then returns `NOT_DETERMINABLE` and asks a person to check. Sending the signature page to the vision model is the fix.

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
