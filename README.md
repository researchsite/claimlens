# ClaimLens: Viral Hoax Auditor

> **Side-by-side proof that standard LLMs echo viral hoaxes — and a multi-agent pipeline that catches the lie.**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?logo=streamlit)](https://claimlens-xh52zvqh5z3xrstpzcvyoo.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red?logo=streamlit)](https://streamlit.io)
[![Nebius AI](https://img.shields.io/badge/Nebius_AI-Qwen3-purple)](https://studio.nebius.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green?logo=mongodb)](https://mongodb.com/atlas)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What is this?

When a viral rumor spreads online, dozens of low-quality SEO blogs copy the same unverified text.
Standard search engines rank those blogs at the top. A naive LLM reading those results synthesises them into fluent, confident-sounding prose — **repeating the lie as fact** ("fluent prose fraud").

**ClaimLens** exposes this pattern by running two approaches on every claim simultaneously:

| | Approach A | Approach B |
|---|---|---|
| **Pattern** | Single LLM + top DuckDuckGo results | Multi-agent pipeline |
| **Era** | Era 2 — Co-pilot / RAG baseline | Era 3 — Co-scientist / Agentic |
| **Result** | Echoes SEO rumours | Grounds claim in primary sources |
| **Verdict** | Unverified summary | 🟢 Verified · 🟡 Exaggerated · 🔴 Fabricated |

---

## Architecture

![System Architecture](docs/architecture.svg)

---

## Design Spec

![Design Spec Diagram](docs/design-spec.svg)

---

## Feature Walkthrough

See **[docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)** for a full visual walkthrough with annotated screenshots of all 4 preset test cases across all 4 tabs.

---

## Quick Start

**Try it live (no install needed):** [https://claimlens-xh52zvqh5z3xrstpzcvyoo.streamlit.app/](https://claimlens-xh52zvqh5z3xrstpzcvyoo.streamlit.app/)

Or run locally:

```bash
git clone https://github.com/researchsite/claimlens.git
cd claimlens
pip install -r requirements.txt
cp .env.example .env          # fill in your keys (see Configuration)
python scripts/setup_mongo.py  # create indexes + seed presets into MongoDB
streamlit run app.py
```

**Click any preset in the sidebar — results load instantly from cache, no API key required.**

---

## How to Use

### Preset claims (instant, no key needed)
Click any of the 4 sidebar presets. Results are pre-computed and served from `cache/*.json` in milliseconds.

### Custom queries (requires Nebius API key)
- **Local:** Set `NEBIUS_API_KEY` in `.env` — the key input is hidden automatically.
- **Cloud deploy:** Enter your key in the sidebar API key field. It's stored in browser session only.

### Reading the results
| Tab | Content |
|---|---|
| 📊 Dual Comparison | Approach A narrative (left) vs. Approach B verdict card (right) |
| 🔍 Source Explorer | DuckDuckGo results labelled PRIMARY / SEO ECHO + primary sources used |
| 🔄 Agent Trace | Step-by-step timing and I/O for each of the 3 agents |
| 📋 Audit History | All past audits from MongoDB; click any to reload in Tab 1 |

### Verdict legend
- **🟢 Verified Real** — primary sources confirm the claim
- **🟡 Exaggerated / Unverifiable** — claim overstates evidence, or no primary source found
- **🔴 Fabricated Hoax** — primary sources directly contradict the claim

---

## Installation

### Requirements
- Python 3.11+
- [Nebius AI](https://studio.nebius.com) account (for custom queries only)
- [MongoDB Atlas](https://cloud.mongodb.com) M0 free tier (optional — for audit history)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```
Edit `.env`:
```env
NEBIUS_API_KEY=v1.Cm...       # only needed for custom queries
MONGODB_URI=mongodb+srv://...  # optional — enables Audit History tab
```

### 3. MongoDB setup (optional)
See [MongoDB Atlas setup](#mongodb-atlas-setup) below, then:
```bash
python scripts/setup_mongo.py
```
Creates the `claimlens.audits` collection, 3 indexes, and seeds all 4 preset results.

### 4. Pre-compute preset cache
The `cache/` directory is included in the repo with pre-computed results.
To regenerate (requires `NEBIUS_API_KEY`):
```bash
python scripts/precompute_presets.py          # all 4 presets
python scripts/precompute_presets.py --preset lemon_water --refresh  # single
```

### 5. Run
```bash
streamlit run app.py
```

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `NEBIUS_API_KEY` | For custom queries | API key from [studio.nebius.com](https://studio.nebius.com) |
| `MONGODB_URI` | No | Atlas connection string for persistent audit storage |
| `NEBIUS_MODEL` | No | Override default model (set via sidebar; default: Qwen3-235B) |

### Available models (Nebius AI)
| Label | Model ID | Use case |
|---|---|---|
| Qwen3-235B (default) | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Best quality |
| Qwen3-30B | `Qwen/Qwen3-30B-A3B-Instruct-2507` | Faster / cheaper |
| DeepSeek-V4-Flash | `deepseek-ai/DeepSeek-V4-Flash-0731` | Fastest |
| DeepSeek-V4-Pro | `deepseek-ai/DeepSeek-V4-Pro` | Pro quality |
| Kimi-K3 | `moonshotai/Kimi-K3` | Alternative |

---

## Technical Details

### Agent pipeline (Approach B)

```
Claim Input
    │
    ├─ [Claim Extractor Agent] ── Qwen3-30B
    │   Breaks headline into 3-5 verifiable sub-claims
    │
    ├─ [Grounder Agent] ── Qwen3-235B
    │   Hunts primary sources: Wikipedia REST, OpenFDA REST,
    │   plus domain whitelist (.gov, .edu, PubMed, nasa.gov, etc.)
    │
    └─ [Verifier Agent] ── Qwen3-235B
        Conservative rules:
        - "verified"    = primary sources CONFIRM claim
        - "exaggerated" = overstated OR no primary source found
        - "fabricated"  = primary sources CONTRADICT claim
        Output: verdict + confidence % + rewritten claim
```

### SEO Echo Chamber Index
Percentage of DuckDuckGo results whose domain is NOT a primary source (not `.gov`, `.edu`, PubMed, WHO, NASA, etc.).  
High echo index (>70%) = viral misinformation environment.

### Conservative verdict rule
The verifier is deliberately constrained: it only calls 🔴 Fabricated when evidence **directly contradicts** the claim.
Absence of evidence → 🟡 Exaggerated (not Fabricated). This prevents false accusations.

### Preset caching
Pre-computed results in `cache/*.json` are loaded instantly without any API calls. This allows the app to be demoed without a Nebius key and eliminates token costs for repeat views.

### Local vs. cloud mode
Detected by `bool(os.getenv("NEBIUS_API_KEY"))`.
- **Local:** key in `.env` → key input hidden, model selector shown
- **Cloud:** no key in env → sidebar shows key input + model selector; key stored in `st.session_state` and injected into `os.environ` for lazy `get_client()` pickup

---

## MongoDB Atlas Setup

### 1. Create free cluster
1. [cloud.mongodb.com](https://cloud.mongodb.com) → Sign up → New Project → Build a Database
2. Select **M0 Free** → any region → Create

### 2. Create database user
1. Database Access → Add New User
2. Auth: Password · Role: Atlas Admin (or `readWriteAnyDatabase`)

### 3. Network access
- Local dev: Add Current IP Address
- Cloud deploy (Streamlit Community Cloud): Allow `0.0.0.0/0`

### 4. Get connection string
Database → Connect → Drivers → Python 3.12+ → copy URI → replace `<password>`

### 5. Add to `.env`
```env
MONGODB_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?appName=Cluster0
```

### 6. Run setup
```bash
python scripts/setup_mongo.py         # setup + seed
python scripts/setup_mongo.py --reset # wipe + re-seed
```

### Collection schema (`claimlens.audits`)
```
claim         string   (unique — one record per distinct claim)
preset_id     string   (empty for custom queries)
timestamp     date
approach_a    string   (Approach A LLM narrative)
verdict       object   {verdict, verdict_emoji, verdict_label, confidence,
                        reasoning, rewritten_claim, key_evidence, primary_sources}
echo_index    int      (0–100, % of results that are SEO echo)
sub_claims    array
grounding     object   {primary_sources[], primary_source_count, notes}
agent_trace   array    [{step, agent, model, input, output, duration_ms}]
from_cache    bool
total_ms      int
```

### Indexes
| Name | Field | Type |
|---|---|---|
| `by_timestamp` | `timestamp` | Descending |
| `by_claim` | `claim` | Ascending (unique) |
| `by_verdict` | `verdict.verdict` | Ascending |

---

## File Reference

```
claimlens/
├── app.py                    Main Streamlit application — all tabs, sidebar, layout
├── approach_a.py             Approach A: streaming single-LLM SEO summariser
├── presets.py                4 built-in test claims with expected verdicts
├── requirements.txt          Python dependencies
├── .env.example              Environment variable template
│
├── agents/
│   ├── claim_extractor.py    Agent 1 — breaks headline into 3-5 sub-claims (Qwen3-30B)
│   ├── grounder.py           Agent 2 — hunts primary sources: Wikipedia, OpenFDA, domain whitelist
│   └── verifier.py           Agent 3 — assigns verdict, rewrites claim, conservative rules
│
├── utils/
│   ├── llm.py                Nebius AI client factory + model constants + KNOWN_MODELS list
│   ├── search.py             DuckDuckGo wrapper with 1.5s rate-limit delay + st.cache_data TTL
│   ├── sources.py            PRIMARY_DOMAINS whitelist · is_primary_source() · score_source()
│   ├── echo_index.py         calculate_echo_index() — % non-primary-source search results
│   ├── preset_cache.py       load_cache() / save_cache() — read/write cache/*.json
│   └── mongo.py              save_audit() / get_recent_audits() — optional MongoDB helper
│
├── cache/
│   ├── lemon_water.json      Pre-computed: 🔴 Fabricated · "Hot lemon water cures diabetes"
│   ├── nasa_signal.json      Pre-computed: 🔴 Fabricated · "NASA alien signal from Mars"
│   ├── cash_ban.json         Pre-computed: 🔴 Fabricated · "Federal law bans cash payments"
│   └── leqembi.json          Pre-computed: 🟢 Verified   · "FDA approves Leqembi"
│
├── scripts/
│   ├── precompute_presets.py One-time: runs all 4 presets end-to-end, saves to cache/
│   └── setup_mongo.py        One-time: creates DB indexes + seeds from cache/ into MongoDB
│
├── docs/
│   ├── architecture.svg      System architecture component diagram
│   ├── design-spec.svg       Key UI & architectural design spec (from req.txt)
│   ├── WALKTHROUGH.md        Full visual walkthrough — all presets × all tabs with screenshots
│   └── screenshots/          17 Playwright-captured screenshots (01_home + 4 presets × 4 tabs)
│
└── .streamlit/
    └── config.toml           Dark theme config (primaryColor, backgroundColor, font)
```

---

## Built-in Test Cases

| Preset | Expected Verdict | What it demonstrates |
|---|---|---|
| 🔴 Hot Lemon Water | Fabricated | No Harvard study exists; only modest glycemic effect in healthy subjects found on PubMed |
| 🔴 NASA Alien Signal | Fabricated | ESA simulation misrepresented; no NASA records confirm alien signal |
| 🔴 US Cash Ban | Fabricated | Claim is backwards — legislation REQUIRES cash acceptance, not banning it |
| 🟢 Leqembi FDA Approval | Verified | Confirmed by alzheimers.gov + .edu sources + clinical trial data |

---

## Extending for Long Blog Articles

The current pipeline handles single-sentence claims. To audit an entire blog post:

### Short-term (minimal changes)
1. **Chunk the article** — split on paragraphs or sentences (`spacy` sentencer or simple `\n\n` split)
2. **Run Claim Extractor on each chunk** — it already returns a list of sub-claims per input
3. **Merge all sub-claims** → run Grounder + Verifier once per sub-claim in a `ThreadPoolExecutor`
4. **Aggregate results** → `verified_pct`, `fabricated_pct`, `exaggerated_pct`

### Output changes
Instead of a single verdict card, render:
- A **Truth Score bar** — e.g., `42% verified · 35% fabricated · 23% exaggerated`
- **Annotated text** — highlight the original article with colour-coded spans
- **Claim table** — each row = one claim + its verdict + source

### New files needed
```
utils/chunker.py       split_into_claims(text: str) -> list[str]
agents/batch_runner.py run_pipeline_batch(claims, max_workers=4) -> list[dict]
```

The verdict model stays identical — only the input changes from one headline to many claims.

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with [Streamlit](https://streamlit.io) · [Nebius AI](https://studio.nebius.com) · [DuckDuckGo ddgs](https://pypi.org/project/ddgs/) · [Wikipedia REST](https://www.mediawiki.org/wiki/API:REST_API) · [OpenFDA](https://open.fda.gov/apis/) · [MongoDB Atlas](https://www.mongodb.com/atlas)*
