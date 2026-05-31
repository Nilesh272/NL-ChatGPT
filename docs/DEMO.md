# Demo Guide — NL ChatGPT (2 minutes)

For fellowship prototype link and optional screen recording.

---

## Quick start (local)

```bash
cd "NL ChatGPT"
source .venv/bin/activate
cp .env.example .env   # add GROQ_API_KEY + TAVILY_API_KEY
streamlit run app/streamlit_app.py
```

Open: http://localhost:8501

---

## 2-minute demo script

| Time | Action | What to say |
|------|--------|-------------|
| 0:00 | Show sidebar — stakes **high**, API status green | “This is an evaluation-first assistant, not a black-box chatbot.” |
| 0:20 | Ask: **“What is Agentic RAG?”** | “Watch the pipeline: plan → retrieve → draft → verify → justify.” |
| 0:45 | Expand **Justification & review** | “Sources are clickable. Each claim has AI verdict + confidence.” |
| 1:00 | Set one claim to **Unsure**, add note, **Save review** | “The human stays in control — Trust, Unsure, or Reject.” |
| 1:20 | Check **sign-off** checkbox | “High stakes blocks export until you review.” |
| 1:35 | **Download review package (Markdown)** | “Export includes answer, citations, and your verdicts.” |
| 1:50 | Ask: **“Who is the CEO of FakeCorpXYZ123?”** | “When evidence is missing, we refuse rather than guess.” |
| 2:00 | Sidebar → **How this supports your judgment** | “Maps to output quality, calibration, legibility, human judgment.” |

---

## Optional: record a GIF

1. Install [LICEcap](https://www.cockos.com/licecap/) or use macOS Screenshot → Record.
2. Record at 1280×720, 15–20 fps, &lt; 40 MB for deck.
3. Save as `docs/assets/demo.gif` (add to deck slide 9).

---

## Deploy prototype (Streamlit Cloud)

1. Push repo to GitHub (ensure `.env` is **not** committed).
2. [share.streamlit.io](https://share.streamlit.io) → New app → point to `app/streamlit_app.py`.
3. Secrets: `GROQ_API_KEY`, `TAVILY_API_KEY`, `LLM_PROVIDER=groq`.
4. Paste URL in deck: **Prototype link**.

---

## CLI demo (no UI)

```bash
python -m src.agents.graph --query "What is Agentic RAG?" --stakes high
```

Shows JSON `JustificationBundle` with claims, citations, phase `5-judgment`.
