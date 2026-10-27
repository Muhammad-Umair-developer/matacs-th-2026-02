# AI Proposal Triage — Process Design & Architectural Decisions

## System Overview & Sample Evaluation Summary
Our design separates **unstructured comprehension (AI)** from **policy enforcement and math (Deterministic Code)**. Each uploaded proposal is processed in an isolated execution context against an immutable snapshot of the admin's category criteria.

When applied to the Commercial Solar Installation sample set ($260,000 CAD ceiling, 16-week max timeline):
* **Proposal A (Ranked #1 — Score: 92/100):** Passes all mandatory gates. Strongest relevant experience (14 installs >=100 kW in the last 5 years, including local warehouse roofs), competitive price ($238,000), fast timeline (12 weeks), and comprehensive team/monitoring plan.
* **Proposal E (Ranked #2 — Score: 85/100):** Passes all mandatory gates. Solid experience (8 installs), slightly higher price ($242,500) and timeline (13 weeks) than A, but superior workmanship warranty (12 years) and monitoring (24 months) plus a roof load assessment.
* **Proposal C (Status: `flagged`):** Contains an adversarial prompt injection in Appendix C attempting to override scoring instructions. Automatically quarantined by the pre-scoring security guardrail.
* **Proposal D (Status: `ineligible`):** Meets licensing and insurance gates, but fails to commit to the mandatory 16-week completion ceiling ("schedule determined after site assessment"). Cannot be deterministically scored on timeline or guaranteed to meet project constraints.
* **Proposal B (Status: `ineligible`):** Fails the mandatory Ontario Electrical Contractor Licence gate. The licence must be held by the bidder and stated in the proposal; deferring to an unnamed post-award subcontractor violates the pass/fail requirement.

---

## Answers to Core Design Questions

### 1. AI vs. Rules: Where the Line is Drawn and Why
* **Plain Code / Deterministic Rules:** PDF text extraction, regex/heuristic injection scanning, enforcing mandatory pass/fail boolean gates, validating hard project ceilings (Price <= $260,000, Timeline <= 16 weeks), normalizing numerical values into scores, applying percentage weights, and sorting the final rank.
* **AI (LLM):** Extracting structured fields from varied prose (e.g., distinguishing whether an ECRA/ESA licence belongs to the prime bidder vs. an unconfirmed subcontractor), detecting semantic prompt manipulation, evaluates qualitative rubrics ("Team and approach"), and generating concise, evidence-backed summary rationales.
* **Why draw the line here?** LLMs are probabilistic engines; they hallucinate arithmetic and struggle to apply strict mathematical scales consistently across separate runs. Conversely, rigid regex rules cannot reliably parse nuanced legal/technical language in PDFs. Using the LLM strictly as a **Text-to-Structured-JSON compiler** and delegating all math and gatekeeping to deterministic code gives us both natural language flexibility and 100% mathematical reliability.

### 2. Consistency and Explainability
* **Repeatability:** If the same proposals are ranked twice under the same criteria version, the output is identical. We achieve this by:
  1. Processing each proposal in an **isolated single-document call** (so upload order never alters context).
  2. Setting LLM `temperature: 0.0`, fixing the `seed`, and enforcing **Structured Outputs (JSON Schema)**.
  3. Computing numerical scores via deterministic formulas in code (e.g., `Price Score = 100 * (Ceiling - Bid) / (Ceiling - MinValidBid)` or fixed bracket rubrics) rather than asking the LLM to "pick a number."
* **Explainability:** For every extracted attribute and qualitative sub-score, the schema requires the LLM to return a `verbatim_quote` and `page_reference` from the source PDF. The reviewer UI displays a breakdown table showing each criterion's weight, extracted value, raw sub-score, weighted points, and the exact highlighted snippet from the contractor's PDF.

### 3. Human in the Loop and Audit Logging
* **Human Checkpoints:**
  1. **Security & Exception Triage:** A human reviewer must inspect `flagged` proposals (like Proposal C's prompt injection) and `ineligible` proposals (like Proposal B and D) to either confirm disqualification or grant a manual exception (e.g., requesting a schedule clarification from Vendor D).
  2. **Score & Extraction Verification:** Before publishing the shortlist, the reviewer can click any extracted field to view the source quote and override an extraction error (which triggers an instant deterministic recalculation).
  3. **Final Award Decision:** The system only triages and ranks; a human explicitly signs off on the winning bid.
* **Audit Trail:** Every run writes an immutable audit record containing: `timestamp`, `proposal_file_hash (SHA-256)`, `criteria_schema_version_id`, `model_id_and_version`, raw LLM JSON output, deterministic score breakdown, and any human override actions (`user_id`, `previous_value`, `new_value`, `mandatory_justification_note`).

### 4. Changing Criteria After Proposals Are Scored
* **Immutable Criteria Versioning:** Admin edits never mutate existing criteria in place; saving an edit creates a new version (`v1` -> `v2`).
* **Handling Weight-Only Changes:** If an admin only adjusts percentage weights (e.g., Price from 25% to 30%), the system **does not re-run the LLM**. Deterministic code instantly recalculates the weighted sum from the cached structured extractions in milliseconds at zero AI cost.
* **Handling New/Modified Criteria Text:** If an admin adds a new criterion or changes what they are looking for, existing scores are marked `Stale (Scored under v1)`. The reviewer is prompted to trigger a batch re-evaluation against `v2`, preserving `v1` results in the audit history so reviewers can compare how the rule change shifted the rankings.

### 5. Risks and Architectural Safeguards
* **Prompt Injection / Manipulation (e.g., Proposal C):**
  * *Safeguard:* Wrap proposal text in strict XML delimiters (`<untrusted_proposal_text>`) with system instructions explicitly forbidding obedience to commands inside the tags. Run an instruction-detection classifier/heuristic check; if triggered, halt scoring and set status to `flagged`.
* **Hallucinations / Wrong Extraction:**
  * *Safeguard:* Require an exact `verbatim_quote` for every extracted fact. Plain code verifies that the returned quote exists as a substring in the source text; if verification fails or confidence is null, flag the field for human review.
* **Unfair Bias:**
  * *Safeguard:* Each proposal is evaluated independently against explicit rubric anchors rather than relative LLM comparison, preventing brand-name recognition or ordering bias.
* **Runaway API Cost & Latency:**
  * *Safeguard:* Cache extractions by `SHA-256(file) + criteria_version_id`, enforce token/page limits, and separate extraction from weight calculation so tuning weights costs $0.