# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary audience: the reviewers evaluating this take-home project. They open the web UI to see, in a few minutes, what the lease and issue agents produced and whether the human-review loop around them is sound. They read critically, compare the UI against DECISIONS.md, and judge trust and clarity more than visual flourish.

The in-product persona is a property owner or manager for Marina Crest Residences (Marina Crest Holdings W.L.L., Lusail Marina District, Doha) who accepts, corrects or rejects what the agents produced, unit by unit.

## Product Purpose

A small full-stack service for a property owner. One agent reads a lease into a structured, verifiable record and checks it against the owner's rules; a second agent turns photos of a unit into a reported issue and a draft work order. Both meet on the unit. Success is a reviewer seeing that every agent output is traceable to its source, computed rather than self-reported, and decided by a person.

## Positioning

Verification over confidence. Field status is computed (`VERIFIED`, `UNVERIFIED`, `MISSING`) from the quote in the document, never from model-reported confidence. Owner rules are deterministic code. The evaluator raises flags but never changes values; a human decides.

## Operating Context

- Two routes: the units list (`/`), which also hosts lease upload and unlinked leases, and the unit view (`/units/[unitId]`) with its lease record and issues.
- Agents run on a local model (gemma4:12b via Ollama), so processing takes one to two minutes; `PROCESSING` states are real and visible.
- Every agent output carries a trace: steps, model, duration and token counts.

## Capabilities and Constraints

- Next.js 16 + React 19 + Tailwind CSS 4. No other UI dependencies; none may be added.
- System font stacks only: nothing is downloaded at build time.
- UI copy is English and is preserved as written.
- Terminology: lease field, source quote, check (verification status), decision (accepted, corrected, rejected), owner rules R1-R7 (pass, fail, not determinable), acknowledge or dismiss, issue, assessment, work order, urgency, trace.

## Evidence on Hand

- `data/units.json`: five units across Tower A and Tower B.
- `data/owner_ruleset.json`: the owner's rules.
- `samples/leases/`: two sample leases (one clean, one with problems); `samples/test-uploads/`: text and scanned PDFs.
- No logo or brand assets exist. Do not invent customers, metrics or claims.

## Product Principles

1. Show the source: every value sits next to the quote it came from.
2. Computed status, never confidence: badges reflect checks, not model self-assessment.
3. The person decides: agent output is a proposal until accepted, corrected or rejected, and decided records stop being editable.
4. Honest about slowness and failure: processing, failure and missing data are stated plainly.
5. Thin client: the UI presents what the API decided; it does not reinterpret it.
