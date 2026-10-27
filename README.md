# AI Proposal Triage System Design

* **Candidate Name:** Muhammad Umair
* **Reference:** MATACS-TH-2026-02
* **Time Spent:** ~60 minutes
* **Submission Contents:**
  * [System Architecture Diagram](./diagram/architecture_flow.png)
  * [Design Write-Up (WRITEUP.md)](./WRITEUP.md)
  * [AI Prompts & Schemas (PROMPTS.md)](./PROMPTS.md)
  * [Sample Set Ranking Output (ranking.json)](./ranking.json)
  * [Evaluation Prototype Script (prototype/)](./prototype/)

## How AI Tools Were Used
I used an AI assistant as an architectural sounding board to stress-test my hybrid extraction-scoring pipeline and format the JSON schemas. 

**Where I Disagreed with and Corrected the AI:**
Initially, the AI suggested a single-step prompt that fed all five proposals and the admin criteria into the LLM at once to directly output the final `ranking.json` scores. I rejected this approach for three reasons:
1. **Non-deterministic arithmetic:** LLMs are unreliable at weighted mathematical normalization (e.g., calculating proportional price scores against a $260k ceiling).
2. **Cross-context contamination & Prompt Injection:** Feeding multiple proposals into one context window allows an adversarial injection in one document (such as the prompt injection in Proposal C's appendix) to hijack the ranking of all other proposals.
3. **Auditability:** I redesigned the flow so the LLM acts strictly as an isolated **Structured Data Extractor & Qualitative Rubric Evaluator** per document (using `temperature: 0` and strict JSON schema enforcement), while deterministic application code handles mandatory pass/fail gates, quantitative normalization, weighted summation, and sorting.