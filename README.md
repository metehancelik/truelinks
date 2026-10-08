# Lease and property-issue agents

A small full-stack service for a property owner and their team.

- **Lease agent:** reads a lease (text, PDF or scan) into a structured record where every field points at the sentence it came from, checks each field, validates the lease against the owner's rules, and checks that it really is the lease of the unit it was added to.
- **Issue agent:** looks at photos of a unit and drafts a work order: condition, equipment, damage, urgency.
- **One screen per unit:** the lease and the issues meet on the unit. A person accepts, corrects or rejects every field, rule result and work order. Nothing changes the unit until a person activates the lease.

Live demo: https://truelinks.ravey.app (runs on a local model; the demo mode below needs no model at all).

The short version of the approach: **the model reads, code checks, a person decides.**

---

## Contents

1. [Run it](#run-it)
2. [How it works](#how-it-works)
3. [Key decisions and trade-offs](#key-decisions-and-trade-offs)
4. [What I tested on the real model, and what it found](#what-i-tested-on-the-real-model-and-what-it-found)
5. [Evaluation](#evaluation)
6. [Where I would take the product next](#where-i-would-take-the-product-next)
7. [What I left out](#what-i-left-out)
8. [Where it breaks first at scale](#where-it-breaks-first-at-scale)
9. [How I used AI tools, and where they broke](#how-i-used-ai-tools-and-where-they-broke)

The working log behind this README is [DECISIONS.md](DECISIONS.md).

---

## Run it

### Option 1: Docker, no model (demo mode)

```bash
LLM_PROVIDER=stub docker compose up --build
```

Open http://localhost:3000. The stub serves canned answers for the two bundled sample leases and for issue reports, so the whole flow (upload, review, rules, activation, work orders) works without a model. Everything except the model call is the real code path.

### Option 2: Docker with a real local model

```bash
ollama pull gemma4:12b
OLLAMA_CONTEXT_LENGTH=16384 ollama serve     # Ollama silently truncates at 4,096 tokens otherwise

docker compose up --build
```

The API reaches Ollama on the host through `host.docker.internal`. Any OpenAI-compatible endpoint works instead: set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TEXT_MODEL` (and `LLM_VISION_MODEL` if the text model cannot see images).

### Option 3: without Docker

```bash
cd backend
cp .env.example .env        # SQLite by default, no database to install
uv sync
uv run uvicorn truelinks.api.app:app --reload

cd web
npm install
API_URL=http://localhost:8000 npm run dev
```

Scanned PDFs need Tesseract on the machine (`brew install tesseract`). The Docker image already has it.

### Tests and checks

```bash
cd backend
uv run pytest               # 90 tests, no model needed
uv run ruff check . && uv run ruff format --check . && uv run pyright   # pyright in strict mode

cd web
npm run lint && npm run build
```

CI runs all of this, then builds the Docker images and calls the API through the web proxy.

### Evaluation

```bash
cd backend
uv run python scripts/run_evals.py --out ../evals/results.json   # the model in .env
uv run python scripts/run_evals.py --stub                         # checks the harness only
```

### Things to try

- **Bundled samples** (buttons on each unit's page): a clean lease that passes every rule when added to MC-B-1204, and a problem lease that fails six of seven on MC-B-1205. Add one to the wrong unit and R7 says so.
- **`samples/test-uploads/`:** the same new lease (MC-B-0902) as a text PDF, as a scan, and as a scan where only the landlord signed by hand.
- **Issues:** any photo of a room or appliance. The brief's photos were not attached to the email, so I tested with my own.

---

## How it works

### Lease

```
upload ─► read ─► extract ─► verify ─► review ─► [signatures] ─► rules ─► person decides ─► activate
          code     model      code      model      model (scans)   code
```

A lease is added on its unit's page, so the person's choice of unit is the link. The agent's reading still counts: if the lease's own wording names a different unit, R7 fails and a person decides.

| Step | What it does | Why |
|---|---|---|
| **read** | Text file, PDF text layer, or Tesseract OCR for scans. | The text produced here is what every quote is checked against. |
| **extract** | The model returns 16 fields. Each field is a value **and the exact sentence it came from**. | A value without a source cannot be checked. |
| **verify** | Code checks (1) the quote exists in the document and (2) the value agrees with its quote: numbers, dates and names are compared, not trusted. | Cheap, deterministic, catches invented or altered values. |
| **review** | A second model call reads the lease and the extracted record and raises concerns code cannot: a quote from the wrong clause, a contradiction, an implausible value. It also judges rule R2 (is the escalation clause defined). | Some checks need judgement. The evaluator **flags**, it never changes a value. |
| **signatures** | Scans only: the last page goes to the vision model, which says whether each party signed. | OCR reads letters; a handwritten signature is not letters. |
| **rules** | R1 to R7 as plain functions over the fields. | Rules are arithmetic and lookups. A model has no business deciding them. |

Each field gets a **computed** status, never a model-reported confidence:

- `VERIFIED`: the quote is in the document, the value agrees with it, and the evaluator raised nothing.
- `UNVERIFIED`: one of those failed. The reason is shown next to the field.
- `MISSING`: the model found nothing.

Rules are recomputed every time the lease is read, from the current values. When a person corrects the deposit, R1 flips at once; nothing is cached that could go stale.

A missing field never fails a rule. "The model did not find it" is not "the lease does not have it", so the rule becomes `NOT_DETERMINABLE` and a person looks.

**Activation** is the only place occupancy changes. It needs every field decided, every non-passing rule acknowledged, and the unit to exist and be available. Then the unit becomes occupied.

### Issue

```
photos + note ─► assess (vision model) ─► check (code) ─► draft work order ─► person accepts, edits or rejects
```

- Every damage and equipment finding names the photo it came from. Code flags a finding that points at a photo that was not sent.
- When the photos show no damage, code flags it and the work order asks for an inspection. This matters more than spotting damage: the dangerous failure is a model that invents damage to match the tenant's note.
- When a person edits the work order, the agent's original draft is kept beside it.

### Structure

```
backend/src/truelinks/
  modules/unit/     units, the owner's records
  modules/lease/    reading, extraction, verification, review, signatures, rules, service
  modules/issue/    assessment, checks, work orders
  platform/         LLM port and adapters, database, settings, trace
  api/              FastAPI routes
web/                Next.js: units list, one page per unit
data/               ruleset and units supplied with the brief
```

`lease` and `issue` depend on `unit`, never on each other. Every row carries a `tenant_id` (the owner organisation), and units are keyed by `(tenant_id, unit_id)`, so two owners can both have a unit called `MC-B-1204` without seeing each other.

Every agent run stores a trace: each step, the model or "code", the duration and the tokens. It is on the screen under "What the agent did".

---

## Key decisions and trade-offs

| Decision | Trade-off accepted |
|---|---|
| **Python backend, Next.js as a thin client.** The verification and rules logic is the heart of the product and reads best as plain typed Python; the UI only shows what the API decided. | Two languages in one repo. |
| **Open-weight model run locally (`gemma4:12b` on Ollama)** behind an OpenAI-compatible adapter (Pydantic AI). The main reason is privacy: a lease holds names, ID references, rents and signatures. With open weights the document never leaves the owner's machine or their own cloud, and no third party sees tenant data. It also costs nothing per call. | Slow: about 65 s to extract a lease, 25 to 40 s per issue on a laptop. A larger open model on a GPU server fixes the speed without giving up the privacy. A hosted API is still possible: it is configuration, not code. |
| **Structured output with a schema, temperature 0, thinking off.** | Thinking on was 4x slower for no gain on extraction. |
| **Quotes, not confidence scores.** Status is computed from evidence. | The model must return more tokens (a quote per field). |
| **The evaluator flags, never fixes.** | A wrong value is not auto-corrected. A person sees why it is suspicious and fixes it in one click. |
| **Same model as extractor and evaluator.** | They can share blind spots. A second model family is the production answer; it did not fit in 24 GB next to the first. |
| **Rules recomputed on read, not stored.** | A little compute per page view, in exchange for no stale verdicts after a correction. |
| **Tesseract for scans, for now.** A vision model "transcribes" by generating text, so it could put words in the document that are not there, and the quote check would then be checking the model against itself. Gemma could read the pages, but it is not built for documents and the laptop has no room for a second model. | Tesseract makes character mistakes. They surface as `UNVERIFIED` fields instead of passing silently (see the next section). On a bigger machine I would move OCR to a document-specialised open vision model (see "Where next"). |
| **Signatures on scans go to the vision model, and always come back `UNVERIFIED`.** | Code cannot check a judgement about an image, so a person always confirms, with the page on screen. |
| **Background tasks inside the API process,** UI polls every 3 s. | A restart during processing loses the job. A queue is the first thing to add (see "breaks first"). |
| **Stub provider with per-task fixtures.** Tests and the demo run the real code with canned model answers. | The stub cannot see images, so vision is only tested on the real model. |
| **Postgres in Docker, SQLite for local runs and tests.** | Tests do not run on the production database engine. |
| **One repo, two apps, one `docker compose up`.** Only `web` is public; it proxies `/api` to the Python service. | No CORS, one domain. The module boundaries are drawn if the apps ever need to split. |

Experiments that did not make it, with numbers, are in [DECISIONS.md](DECISIONS.md#experiments) (for example, a small decision model as a second judge: 3 of 4 on the escalation clause, and it missed exactly the case rule R2 exists for).

---

## What I tested on the real model, and what it found

I ran the deployed app end to end against `gemma4:12b`. The bugs below came from those runs, not from the unit tests.

| Test | Result |
|---|---|
| Clean lease, MC-B-1204 | 16 of 16 fields verified, 7 of 7 rules pass, linked to the unit, activated, unit became occupied. |
| Problem lease, MC-B-1205 | R1, R2, R4, R5, R6, R7 fail with the right reasons. Corrected the deposit to 11,000: R1 flipped to pass immediately. |
| Photo of an AC unit with water stains, **no note** | Found the AC unit and the staining from the photo alone. |
| Photo of a clean kitchen, note "Oven is not heating" | Did not invent damage. Asked for a technician because a photo cannot show a heating fault. Read the brand name off the oven door. |
| Scanned PDF | OCR read it in about 10 s with one mistake: "commencing on **1** February" became "commencing on **\|** February". |

Bugs found and fixed:

1. **An active lease failed its own unit rule.** R7 says "the unit must be available"; after activation the unit is occupied, by this lease. Rules are recomputed on read, so the lease started failing itself.
2. **The "no visible damage" flag never fired** on the kitchen photo, because the model filled the damage list with "no visible damage". The check now also looks at the overall condition. The prompt says it, but the code enforces it.
3. **Urgency was "high" for an old water stain.** The model was following my prompt ("high for water leaks"). The rule now separates an active leak from signs of an old one.
4. **A decided work order stayed editable** and gave no feedback while saving.

---

## Evaluation

`evals/leases/cases.json` holds hand-written answers for six leases: every field and every rule outcome. The script runs the whole agent on each and scores it.

The headline metric is **trusted but wrong**: a field marked `VERIFIED` whose value is wrong. It reaches a person looking settled, so review cannot catch it. Every other mistake is flagged, which is what review is for. This number must be zero.

| Case | What it tests |
|---|---|
| clean | Should pass everything. |
| problems | Six rule failures, including a term that contradicts its dates. |
| text-pdf | A PDF whose text layer breaks lines mid-sentence. |
| quarterly-no-escalation | Only annual and quarterly rent are stated, no escalation clause. The model must leave monthly rent and escalation empty, not calculate or invent them. |
| distractors-unknown-unit | A parking fee, a late fee and a previous occupant's deposit sit next to the real amounts. The term is over the limit and the building is not the owner's. |
| scan-landlord-signed-only | A scan read by OCR; only the landlord signed by hand. |

**Result on `gemma4:12b`** (full report in [`evals/results.json`](evals/results.json)):

| | |
|---|---|
| Fields right | 96 / 96 |
| Trusted but wrong | **0** |
| Right, but sent to a person | 3 (all on the scan) |
| Rules right | 42 / 42 |
| Seconds per lease | 87 (text), 106 (scan: OCR plus the signature check) |

On the scan, the three fields a person is asked to confirm are exactly the ones that should be: both signatures (a judgement on an image, which code cannot check) and the commencement date (OCR read "1 February" as "| February", so the quote no longer proves the value). The values were right, the system was right not to trust them on its own.

How I read it:

- **A perfect score says the set is too small, not that the agent is perfect.** Six leases from one template. The next step is real leases from a customer, with the answers taken from the corrections their reviewers make.
- **The traps did not work,** which is the useful part: no calculated monthly rent, no parking fee read as rent, no previous deposit read as the deposit.
- **Summaries are scored loosely.** For renewal and termination the eval only checks that something was extracted, and the real model sometimes returns a fragment ("twelve (12) months"). The eval does not measure summary quality yet.
- **The evaluator stayed silent on the 24-versus-18-month contradiction,** in the live test and here. Rule R4 caught it both times. That is the argument for keeping arithmetic in code.
- **One run.** Temperature 0 makes repeats likely, not guaranteed; a CI gate would run each case several times.

---

## Where I would take the product next

The build answers "can an agent read a lease". The product question is what a property manager does on a Monday morning with 300 units, and what they currently do in spreadsheets, email and WhatsApp. Ideas in the order I would ship them.

### 1. A work queue instead of a unit list

Today you open a unit to see what needs you. A manager wants the opposite: **one inbox of things waiting for a decision**, sorted by consequence. Leases in review, high-severity rule failures, urgent work orders, fields the agent was unsure about. Each item opens straight at the field or the photo that needs a look.

### 2. Lease lifecycle, not just lease intake

Reading a lease is a one-off. The value is in what the record makes possible afterwards, because every date and amount is now structured and sourced:

- **Expiry and renewal alerts** at 90, 60 and 30 days, with the renewal and notice clauses quoted in the alert.
- **Rent escalation schedule:** the agent already reads "5% on each renewal"; turn it into the next rent and the date it applies.
- **Occupied units with no lease on file:** two of the five sample units are occupied with no lease. Every portfolio has these, and they are a compliance and collection risk. A report and a one-click "upload the lease" closes the gap.
- **Duplicate detection:** the same lease uploaded twice should be caught before review, not after (I did it myself while testing).

### 3. Make review faster than doing it by hand

If checking the agent takes as long as reading the lease, nobody uses it.

- **Highlight the quote on the original PDF page** instead of showing it as text. Bounding boxes from OCR or the PDF layer make "where did this come from" a glance.
- **Accept all verified fields in one action** (built) and keep attention on the unverified ones.
- **One bounded correction round:** when a field is unverified, re-ask the model for that field only, telling it why, then verify again. At most one retry, and only kept if it improves the numbers below. Designed in DECISIONS.md, not built.

### 4. Close the loop on issues

Today the story ends at "work order accepted". The manager's job does not.

- **Tenant reporting from a phone:** a link per unit, photos plus a sentence. The agent's first assessment is ready before anyone opens it.
- **Dispatch to a contractor** by trade (AC, plumbing, electrical) and urgency, with the photos and the agent's description attached.
- **Track to closure:** before and after photos, the agent compares them, the tenant confirms.
- **Recurring issues per unit and per equipment:** the third AC leak in a year is a replacement, not a repair. That is a capital planning signal for the owner.
- **Lease-aware triage:** the lease already says who maintains what ("the Landlord is responsible for the air conditioning"). The work order should say whose cost it is.

### 5. Owner-facing view

Owners do not want to review fields; they want to know their portfolio is in order: occupancy, leases expiring, rules overridden and by whom, open issues and their cost. Every override a manager makes against the owner's rules should be visible to the owner, with the reason.

### 6. Fit into the systems they already use

Property teams already live in Yardi or similar. The agent should **read units and occupancy from there and write the approved lease back**, rather than becoming another system to keep in sync. The verified, sourced record is the part those systems do not have.

### 7. Grow the evaluation set from real corrections

Every correction a reviewer makes is a labelled example. Feed them into the evaluation set above, split by document type, and gate every prompt or model change on it in CI. Cost and latency per lease are already traced per step and belong on the same dashboard.

### 8. Better reading of scans, without sending documents out

Tesseract is the safe start, not the end. Open-weight vision-language models, the Qwen-VL family in particular, are strong at document OCR: tables, stamps, mixed Arabic and English, poor scans. With a GPU server I would:

- **Read scans with a Qwen-VL model**, run on the owner's own infrastructure like the main model, so documents still never leave.
- **Keep Tesseract as a second, independent reader.** Where the two disagree on a quoted sentence, the field goes to `UNVERIFIED`. Two different readers that agree are much stronger evidence than one model checking itself.
- **Use the same model for signatures, stamps and handwritten amendments**, which plain OCR cannot read at all.

Open weights throughout, for the privacy reason in the decisions table: tenant data stays in the owner's environment. That is a selling point, not just a constraint.

### 9. Region-specific details that matter in Doha

- **Arabic and bilingual leases:** OCR language packs and a model that reads Arabic. A large share of real leases will need this.
- **Hijri and Gregorian dates** in the same document.

---

## What I left out

| Left out | Why, and what it would take |
|---|---|
| **Authentication and roles** | Out of scope for the exercise. Everything is already scoped by `tenant_id`; adding auth means deriving it from the session instead of settings. |
| **Row-level security in Postgres** | Isolation is enforced in the application today. RLS would make a forgotten filter impossible: a `tenant_id` policy per table and `SET app.tenant_id` per request. |
| **Database migrations** | Tables are created on start. Alembic is the first thing to add before any real data; a schema change now means dropping tables. |
| **Job queue** | Background tasks run in the API process (see below). |
| **OCR in other languages, multi-page signature detection** | Tesseract runs in English, and the signature check looks at the last page only. |
| **Editing rules in the UI** | The owner's ruleset is a file. Rules are code for a reason (they must be deterministic), but their thresholds (36 months, one month's deposit) could be owner settings. |
| **Tenant portal, contractor dispatch, notifications** | Product ideas above. |
| **Deploy gated on CI** | The server deploys on push; CI runs in parallel. A failing push still deploys. |

---

## Where it breaks first at scale

1. **The model.** One local model processes one request at a time: a minute per lease. A batch of 200 leases is three hours. Fix: a hosted model or a GPU pool, and a queue in front of it.
2. **Jobs inside the API process.** A deploy or crash during processing loses the job and leaves it "processing" forever. Fix: a Postgres-backed queue (the `PROCESSING` status already exists; workers claim rows with `SELECT ... FOR UPDATE SKIP LOCKED`, reclaim stale ones after a timeout). Workers are the same image with a different command, and scale by count. Adding workers only helps once the model scales too.
3. **OCR in the request.** About 10 s a page, 20-page limit. A long scanned lease would time out the upload. Moves to the same queue.
4. **Long leases.** The whole text goes to the model in one call. A 40-page commercial lease needs the document split by section, with each field extracted from the sections that can contain it.
5. **Uploads on a local volume.** Fine on one server, wrong on two. Object storage.
6. **Polling every 3 s** from every open page. Fine for a team, not for hundreds of users. Server-sent events.

---

## How I used AI tools, and where they broke

I build with AI coding agents every day, and this project was no different. They are fast at the parts with a known shape and unreliable exactly where it matters, so the habits below are the ones I worked by.

- **Stale knowledge stated with confidence.** Model generations, speed estimates and browser behaviour (Chrome and Brave now run OCR on scanned PDFs) were all suggested confidently and wrong. Each was caught by checking, not by trusting.
- **Two copies drifting apart.** A lockfile updated without its `pyproject.toml` broke the Docker build. Any file that moves between environments is now verified by checksum.
- **It follows the prompt you wrote, not the one you meant.** The "urgency: high" bug was my own rule, faithfully applied.
- **Plausible tests are not real tests.** The four bugs above passed the unit tests; they only showed up on the real model with real photos.

The rule I took from it is the same one the product is built on: let the model do the reading, and check its work with something that is not a model.
