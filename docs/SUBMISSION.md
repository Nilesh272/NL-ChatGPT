# Fellowship Submission Checklist — NL ChatGPT

**Deadline:** 3 June 2026  
**Deck file name:** `NL ChatGPT.pdf` (per fellowship guidelines)

---

## Deliverables

| Item | Status | Location |
|------|--------|----------|
| 10-slide deck | Template ready | [docs/deck/NL_CHATGPT_SLIDES.md](./deck/NL_CHATGPT_SLIDES.md) → export PDF |
| Prototype link | Deploy or local | [docs/DEMO.md](./DEMO.md) |
| Prompt log | Done | [docs/PROMPTS.md](./PROMPTS.md) |
| Architecture | Done | [docs/ARCHITECTURE.md](./ARCHITECTURE.md) |
| Failure modes | Done | [docs/FAILURE_MODES.md](./FAILURE_MODES.md) |
| Eval summary | Run `make eval-quick` | `eval/results/summary.md` |
| User research | Templates | [docs/research/](./research/) |

---

## Before you submit

1. **Export deck** from `docs/deck/NL_CHATGPT_SLIDES.md` — add prototype URL, survey link, interview doc links.
2. **Run security check:** `make check-secrets`
3. **Record demo** (optional): follow [docs/DEMO.md](./DEMO.md)
4. **Run eval:** `make eval-quick` and paste metrics into slide 8.
5. **Deploy Streamlit** (optional): Streamlit Cloud + secrets in dashboard.

---

## Hyperlinks for deck (required)

- Prototype: `https://your-app.streamlit.app` or “Local: see README”
- Prompts: GitHub raw / repo path to `docs/PROMPTS.md`
- Research: Google Doc / Form links (fill in after interviews)
- Eval: `eval/results/summary.md` in repo

---

## Repo hygiene

- No `.env` committed (use `.env.example`)
- `data/judgments.db` gitignored
- `make test` passes
- `make check-secrets` passes
