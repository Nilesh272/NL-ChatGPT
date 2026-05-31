# Failure Modes & Mitigations — NL ChatGPT

For fellowship deck slide: **“Why our solution might fail”** (required depth).

---

## 1. Verifier hallucinating verdicts

**Risk:** LLM verifier marks claims “supported” without real evidence.

**Mitigation:**
- Structured JSON with mandatory `source_ids` + `supporting_quote`
- MiniCheck heuristic re-scores low-confidence claims
- UI shows per-claim verdict + sources for **human** override (Trust / Unsure / Reject)

---

## 2. False sense of safety (checkbox theater)

**Risk:** User signs off without reading; export unlocks anyway.

**Mitigation:**
- High-stakes requires ≥1 claim review + explicit sign-off text
- “Review before using” banner on low overall confidence
- Export JSON includes all user verdicts and rejected claims

---

## 3. Cognitive overload

**Risk:** Justification panel too dense; users skip review.

**Mitigation:**
- Collapsible expanders (sources, claims, checklist)
- Stakes-based gating (low = light UI)
- Color-coded confidence (green / amber / red)

---

## 4. Latency on verify + refine loop

**Risk:** Multi-step graph feels slow vs plain ChatGPT.

**Mitigation:**
- Parallel Tavily queries when multiple retrieval strings
- Session cache for repeated retrieval keys
- Optional disable verify loop in sidebar for demos

---

## 5. Retrieval failure / noisy sources

**Risk:** Tavily returns irrelevant snippets; draft inherits noise.

**Mitigation:**
- Perplexity fallback
- URL deduplication + relevance scoring
- Refuse to answer when zero contexts (“I do not have enough information”)

---

## 6. Over-trust in confidence scores

**Risk:** Users treat 8/10 as “true” without checking sources.

**Mitigation:**
- Scores labeled as model-assisted, not authoritative
- Verify checklist in every bundle
- Fellowship copy: AI assists judgment, does not replace it

---

## 7. Conflicting sources

**Risk:** Two sources disagree; draft hides tension.

**Mitigation:**
- Verifier `contradictions` field in report
- Draft prompt: “If sources conflict, note the uncertainty”
- Gaps section surfaces unsupported/contradicted counts

---

## 8. Overconfident polished drafts

**Risk:** Fluent prose outruns evidence (core problem statement).

**Mitigation:**
- Core product: justification layer + human review
- Refine loop removes unsupported sentences
- Eval metric: unsupported claim rate < 10% post-verify

---

## 9. API cost & key exposure

**Risk:** Keys in repo; runaway API usage.

**Mitigation:**
- `.env` gitignored; `scripts/check_secrets.py`
- Mock mode without keys for CI/dev
- Eval cap on DeepEval sample size

---

## 10. Mock mode in production demo

**Risk:** Demo uses mock IBM/LangGraph URLs while claiming “live” verification.

**Mitigation:**
- Sidebar shows API status (LLM / retrieval)
- Gaps list includes “Using mock retrieval” when applicable
- README documents key requirements for live demo

---

*Use 2–3 of these in the deck; go deep on mitigations you actually built.*
