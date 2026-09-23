import os
import time
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="ClaimLens", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

from presets import PRESETS
from utils.llm import KNOWN_MODELS, MODEL_LARGE
from utils.search import search_web
from utils.sources import is_primary_source
from utils.echo_index import calculate_echo_index
from utils.preset_cache import load_cache, has_cache
from utils.mongo import save_audit, get_recent_audits, is_connected
from approach_a import stream_approach_a
from agents.claim_extractor import extract_claims
from agents.grounder import find_primary_sources
from agents.verifier import verify_claim

# ── Local vs cloud mode ───────────────────────────────────────────────────────
IS_LOCAL = bool(os.getenv("NEBIUS_API_KEY", "").strip())
PRESET_CLAIM_MAP = {p["claim"]: p["id"] for p in PRESETS}   # claim → preset_id

# ── Apply runtime key/model from session state ────────────────────────────────
if not IS_LOCAL:
    if st.session_state.get("_nebius_key"):
        os.environ["NEBIUS_API_KEY"] = st.session_state["_nebius_key"]
    if st.session_state.get("_nebius_model"):
        os.environ["NEBIUS_MODEL"] = st.session_state["_nebius_model"]

def _api_ready() -> bool:
    return bool(os.getenv("NEBIUS_API_KEY", "").strip())

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1A1A2E; }
::-webkit-scrollbar-thumb { background: #3D3D5C; border-radius: 3px; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D0D1A 0%, #13132B 100%);
    border-right: 1px solid #2D2D3E;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #1A1A2E; border: 1px solid #2D2D3E; color: #CBD5E1;
    text-align: left; font-size: 0.85rem; padding: 10px 14px;
    border-radius: 8px; transition: all 0.2s; width: 100%;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #22223A; border-color: #7C3AED; color: #E2E8F0; transform: translateX(3px);
}
.main .block-container { padding-top: 1rem; max-width: 100% !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: transparent; border-bottom: 1px solid #2D2D3E; }
.stTabs [data-baseweb="tab"] { background: transparent; border-radius: 8px 8px 0 0; color: #6B7280; font-weight: 500; font-size: 0.9rem; padding: 8px 20px; }
.stTabs [aria-selected="true"] { background: #1A1A2E !important; color: #A78BFA !important; border-bottom: 2px solid #7C3AED; }
div[data-testid="metric-container"] { background: #1A1A2E; border: 1px solid #2D2D3E; border-radius: 10px; padding: 12px 16px; }
div[data-testid="metric-container"] label { color: #9CA3AF !important; font-size: 0.75rem !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; }
details { background: #1A1A2E !important; border: 1px solid #2D2D3E !important; border-radius: 8px !important; }
details summary { color: #CBD5E1 !important; font-weight: 500; }
.stTextArea textarea, .stTextInput input {
    background: #1A1A2E !important; border: 1px solid #3D3D5C !important;
    border-radius: 8px !important; color: #E2E8F0 !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7C3AED, #6D28D9) !important;
    border: none !important; color: white !important; font-weight: 600 !important;
    border-radius: 8px !important;
}
hr { border-color: #2D2D3E !important; }
</style>
""", unsafe_allow_html=True)


# ── HTML helpers (static values only — no LLM text) ──────────────────────────

def _verdict_badge_html(verdict: dict, echo_index: int) -> str:
    key = verdict.get("verdict", "exaggerated")
    palette = {
        "verified":    ("linear-gradient(135deg,#059669,#10B981)", "#10B981"),
        "exaggerated": ("linear-gradient(135deg,#D97706,#F59E0B)", "#F59E0B"),
        "fabricated":  ("linear-gradient(135deg,#B91C1C,#EF4444)", "#EF4444"),
    }
    grad, accent = palette.get(key, palette["exaggerated"])
    echo_color = "#EF4444" if echo_index >= 70 else ("#F59E0B" if echo_index >= 40 else "#10B981")
    emoji = verdict.get("verdict_emoji", "🟡")
    label = verdict.get("verdict_label", "Unverifiable")
    conf  = verdict.get("confidence", 0)
    return f"""
<div style="background:rgba(255,255,255,0.03);border:1px solid {accent};border-radius:16px;padding:20px;
            box-shadow:0 0 30px {accent}18;margin-bottom:4px;">
    <div style="background:{grad};display:inline-flex;align-items:center;
                padding:10px 22px;border-radius:50px;margin-bottom:18px;">
        <span style="font-size:1.15rem;font-weight:800;color:#fff;">{emoji}&nbsp;{label}</span>
    </div>
    <div style="display:flex;gap:12px;">
        <div style="background:rgba(255,255,255,0.05);border-radius:12px;padding:12px 18px;text-align:center;min-width:88px;">
            <div style="font-size:0.65rem;font-weight:700;color:#9CA3AF;letter-spacing:.1em;margin-bottom:4px;">CONFIDENCE</div>
            <div style="font-size:2rem;font-weight:800;color:{accent};line-height:1;">{conf}%</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:12px;padding:12px 18px;flex:1;">
            <div style="font-size:0.65rem;font-weight:700;color:#9CA3AF;letter-spacing:.1em;margin-bottom:10px;">SEO ECHO INDEX</div>
            <div style="display:flex;align-items:center;gap:10px;">
                <div style="background:#2D2D3E;border-radius:50px;height:10px;flex:1;overflow:hidden;">
                    <div style="width:{echo_index}%;height:100%;background:{echo_color};border-radius:50px;"></div>
                </div>
                <span style="font-weight:700;color:{echo_color};min-width:38px;">{echo_index}%</span>
            </div>
            <div style="font-size:0.72rem;color:#6B7280;margin-top:5px;">{echo_index}% of search results are SEO echo</div>
        </div>
    </div>
</div>"""


def _source_row_html(title: str, url: str, is_primary: bool, body: str) -> str:
    border = "#10B981" if is_primary else "#3D3D5C"
    tag_bg = "#064E3B" if is_primary else "#1F2937"
    tag_col = "#34D399" if is_primary else "#6B7280"
    tag = "PRIMARY" if is_primary else "SEO ECHO"
    return f"""
<div style="background:#1A1A2E;border-left:3px solid {border};border-radius:0 8px 8px 0;padding:10px 14px;margin:5px 0;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:3px;">
        <span style="font-weight:600;color:#E2E8F0;font-size:0.84rem;">{title[:80]}</span>
        <span style="background:{tag_bg};color:{tag_col};font-size:0.65rem;font-weight:700;
                     padding:2px 8px;border-radius:20px;white-space:nowrap;">{tag}</span>
    </div>
    <div style="color:#9CA3AF;font-size:0.77rem;margin-bottom:4px;line-height:1.45;">{body[:160]}…</div>
    <a href="{url}" target="_blank" style="color:#A78BFA;font-size:0.74rem;text-decoration:none;">↗ {url[:65]}</a>
</div>"""


def _trace_row_html(step: int, agent: str, model: str, duration_ms: int, accent: str) -> str:
    return f"""
<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #2D2D3E;">
    <div style="background:{accent};color:#fff;font-size:0.7rem;font-weight:800;
                width:24px;height:24px;border-radius:50%;display:flex;align-items:center;
                justify-content:center;flex-shrink:0;">{step}</div>
    <div style="flex:1;">
        <div style="font-weight:700;color:#E2E8F0;font-size:0.88rem;">{agent}</div>
        <div style="color:#6B7280;font-size:0.75rem;">{model}</div>
    </div>
    <div style="font-weight:700;color:{accent};font-size:0.88rem;">{duration_ms:,} ms</div>
</div>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:0 4px 16px;">
        <div style="font-size:1.4rem;font-weight:800;
                    background:linear-gradient(135deg,#A78BFA,#38BDF8);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
            🔍 ClaimLens
        </div>
        <div style="color:#6B7280;font-size:0.78rem;margin-top:2px;">Viral Hoax Auditor</div>
    </div>
    """, unsafe_allow_html=True)

    # ── API key block (cloud mode only) ──────────────────────────────────────
    if not IS_LOCAL:
        st.markdown("""
        <div style="background:#1A1A2E;border:1px solid #3D3D5C;border-radius:10px;padding:14px;margin-bottom:14px;">
            <div style="font-size:0.7rem;font-weight:700;color:#A78BFA;letter-spacing:.08em;margin-bottom:10px;">
                🔑 NEBIUS AI CREDENTIALS
            </div>
        </div>
        """, unsafe_allow_html=True)

        key_in = st.text_input("API Key", type="password", placeholder="v1.Cm…",
                               key="key_input_field",
                               help="Get your key at studio.nebius.com → API Keys")
        if key_in:
            st.session_state["_nebius_key"] = key_in
            os.environ["NEBIUS_API_KEY"] = key_in

        model_labels = [label for label, _ in KNOWN_MODELS]
        model_ids    = {label: mid for label, mid in KNOWN_MODELS}
        sel_label = st.selectbox("Model", model_labels, key="model_select",
                                 help="Nebius updates models frequently — pick any from your plan")
        st.session_state["_nebius_model"] = model_ids[sel_label]
        os.environ["NEBIUS_MODEL"] = model_ids[sel_label]

        if not _api_ready():
            st.markdown("""
            <div style="background:rgba(245,158,11,0.1);border:1px solid #F59E0B;border-radius:8px;
                        padding:8px 12px;font-size:0.78rem;color:#FCD34D;margin-top:6px;">
                ⚡ Presets load instantly without a key.<br>
                A key is only needed for custom queries.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(16,185,129,0.08);border:1px solid #10B981;border-radius:8px;
                        padding:6px 12px;font-size:0.78rem;color:#34D399;margin-top:6px;">
                ✅ Key active — custom queries enabled.
            </div>
            """, unsafe_allow_html=True)

    else:
        # Local dev mode: show model selector only
        model_labels = [label for label, _ in KNOWN_MODELS]
        model_ids    = {label: mid for label, mid in KNOWN_MODELS}
        sel_label = st.selectbox("Model override", model_labels, key="model_select",
                                 help="Override the default Qwen3-235B for this session")
        chosen = model_ids[sel_label]
        if chosen != MODEL_LARGE:
            os.environ["NEBIUS_MODEL"] = chosen
        st.caption("🏠 Local mode — key loaded from .env")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Custom query ─────────────────────────────────────────────────────────
    custom_input = st.text_area("Enter a claim to audit:", height=76,
                                 placeholder="e.g. Drinking bleach cures COVID-19…",
                                 key="custom_input")
    if st.button("🔍 Audit This Claim", type="primary", use_container_width=True):
        if custom_input.strip():
            if not _api_ready():
                st.warning("Enter your Nebius API key above to run custom queries.")
            else:
                st.session_state.active_claim = custom_input.strip()
                st.session_state.pop(f"a_{hash(custom_input.strip())}", None)
                st.session_state.pop(f"b_{hash(custom_input.strip())}", None)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.7rem;font-weight:700;color:#6B7280;letter-spacing:.1em;margin-bottom:6px;'>⚡ QUICK PRESETS (cached)</div>", unsafe_allow_html=True)

    for p in PRESETS:
        cached = has_cache(p["id"])
        label = p["label"] + (" ⚡" if cached else " ⏳")
        if st.button(label, use_container_width=True, key=f"btn_{p['id']}"):
            st.session_state.active_claim = p["claim"]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Clear results", use_container_width=True):
        for k in [k for k in st.session_state if k.startswith(("a_", "b_"))]:
            del st.session_state[k]
        st.session_state.pop("active_claim", None)
        st.rerun()

    # ── Stack status ──────────────────────────────────────────────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    def _srow(dot_color: str, icon: str, name: str, detail: str) -> str:
        return (
            f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:0.76rem;">'
            f'<span style="color:{dot_color};font-size:0.65rem;">{"●" if dot_color != "#4B5563" else "○"}</span>'
            f'<span style="color:#CBD5E1;">{icon}&nbsp;{name}</span>'
            f'<span style="color:#6B7280;margin-left:auto;font-size:0.7rem;">{detail}</span>'
            f'</div>'
        )

    nebius_ok = _api_ready()
    mongo_ok  = is_connected()

    st.markdown(
        f'<div style="background:#111120;border:1px solid #2D2D3E;border-radius:8px;padding:10px 12px;">'
        f'<div style="font-size:0.62rem;font-weight:700;color:#4B5563;letter-spacing:.1em;margin-bottom:8px;">STACK STATUS</div>'
        + _srow("#10B981" if nebius_ok else "#4B5563", "🤖", "Nebius AI",     "active" if nebius_ok else "key needed")
        + _srow("#10B981" if mongo_ok  else "#4B5563", "🗄️", "MongoDB Atlas", "connected" if mongo_ok else "offline")
        + _srow("#10B981",                             "🔍", "DuckDuckGo",   "free · no key")
        + _srow("#10B981",                             "📖", "Wikipedia",    "REST · free")
        + _srow("#10B981",                             "💊", "OpenFDA",      "REST · free")
        + '</div>',
        unsafe_allow_html=True,
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:8px 0 20px;">
    <h1 style="margin:0;font-size:2rem;font-weight:800;
               background:linear-gradient(135deg,#A78BFA 0%,#38BDF8 100%);
               -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
        Viral Hoax Auditor
    </h1>
    <p style="color:#6B7280;margin:4px 0 0;font-size:0.9rem;">
        Side-by-side proof that standard LLMs echo hoaxes — agentic primary-source grounding catches the lie.
    </p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📊 Dual Comparison", "🔍 Source Explorer", "🔄 Agent Trace", "📋 Audit History"])


# ── Cache loader ─────────────────────────────────────────────────────────────
def _load_preset_to_session(claim: str) -> bool:
    """Populate session state from cache if this claim is a preset. Returns True on hit."""
    pid = PRESET_CLAIM_MAP.get(claim)
    if not pid or not has_cache(pid):
        return False
    a_key = f"a_{hash(claim)}"
    b_key = f"b_{hash(claim)}"
    if a_key not in st.session_state or b_key not in st.session_state:
        data = load_cache(pid)
        if data:
            result = {
                "sub_claims":     data["sub_claims"],
                "grounding":      data["grounding"],
                "verdict":        data["verdict"],
                "echo_index":     data["echo_index"],
                "agent_trace":    data["agent_trace"],
                "search_results": data.get("search_results", []),
                "from_cache":     True,
                "preset_id":      pid,
            }
            st.session_state[a_key] = data.get("approach_a", "")
            st.session_state[b_key] = result
            # Save to MongoDB once per session per preset
            if not st.session_state.get(f"_mongo_{hash(claim)}"):
                save_audit(claim, result, approach_a=data.get("approach_a", ""))
                st.session_state[f"_mongo_{hash(claim)}"] = True
    return True


# ── Live pipeline runner ──────────────────────────────────────────────────────
def _run_pipeline(claim: str, search_results: list) -> dict:
    b_key = f"b_{hash(claim)}"
    if b_key in st.session_state:
        return st.session_state[b_key]

    with st.status("Running 3-agent audit pipeline…", expanded=True) as status:
        t_total = time.time()

        st.write("🔧 **Step 1 / 3** — Extracting sub-claims…")
        t0 = time.time(); sub_claims = extract_claims(claim); d0 = int((time.time()-t0)*1000)
        st.write(f"✓ {len(sub_claims)} sub-claim(s)  `{d0} ms`")

        st.write("🔍 **Step 2 / 3** — Hunting primary sources…")
        t1 = time.time(); grounding = find_primary_sources(claim, sub_claims, search_results); d1 = int((time.time()-t1)*1000)
        src_count = len(grounding.get("primary_sources", []))
        st.write(f"✓ {src_count} primary source(s)  `{d1} ms`")

        st.write("⚖️ **Step 3 / 3** — Assigning verdict…")
        t2 = time.time(); verdict = verify_claim(claim, sub_claims, grounding); d2 = int((time.time()-t2)*1000)
        st.write(f"✓ **{verdict.get('verdict_emoji','')} {verdict.get('verdict_label','')}**  `{d2} ms`")
        status.update(label=f"Audit complete — {int((time.time()-t_total)*1000):,} ms", state="complete")

    result = {
        "sub_claims": sub_claims, "grounding": grounding, "verdict": verdict,
        "echo_index": calculate_echo_index(search_results),
        "search_results": search_results,
        "agent_trace": [
            {"step":1,"agent":"Claim Extractor","model":"Qwen3-30B", "input":claim,"output":sub_claims,"duration_ms":d0},
            {"step":2,"agent":"Grounder",       "model":"Qwen3-235B","input":f"{len(sub_claims)} sub-claims","output":grounding,"duration_ms":d1},
            {"step":3,"agent":"Verifier",       "model":"Qwen3-235B","input":f"{src_count} sources","output":verdict,"duration_ms":d2},
        ],
        "from_cache": False,
    }
    st.session_state[f"b_{hash(claim)}"] = result
    save_audit(claim, result, approach_a=st.session_state.get(f"a_{hash(claim)}", ""))
    st.session_state[f"_mongo_{hash(claim)}"] = True
    return result


# ── Shared B-column renderer ──────────────────────────────────────────────────
def _render_b_column(result: dict) -> None:
    verdict    = result["verdict"]
    echo_index = result["echo_index"]
    from_cache = result.get("from_cache", False)

    if from_cache:
        st.markdown('<span style="background:#064E3B;color:#34D399;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;">⚡ CACHED</span>', unsafe_allow_html=True)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    st.markdown(_verdict_badge_html(verdict, echo_index), unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if verdict.get("rewritten_claim"):
        st.markdown("**📝 Evidence-Based Rewrite**")
        st.info(verdict["rewritten_claim"])

    if verdict.get("reasoning"):
        st.markdown("**🧠 Reasoning**")
        st.write(verdict["reasoning"])

    if verdict.get("key_evidence"):
        st.markdown("""<div style="background:rgba(124,58,237,0.1);border-left:3px solid #7C3AED;
                       border-radius:0 8px 8px 0;padding:8px 14px;margin:6px 0 10px;">
            <div style="font-size:0.65rem;font-weight:700;color:#A78BFA;letter-spacing:.1em;">KEY EVIDENCE</div>
        </div>""", unsafe_allow_html=True)
        st.caption(verdict["key_evidence"])

    srcs = verdict.get("primary_sources", [])
    if srcs:
        st.markdown(f"**📚 Primary Sources ({len(srcs)})**")
        for s in srcs[:4]:
            icon = "✅" if s.get("supports_claim") else "❌"
            with st.expander(f"{icon} {s.get('title','Source')} · {s.get('domain_type','')}"):
                st.write(s.get("relevant_quote", ""))
                st.markdown(f"[View source →]({s.get('url','#')})")
    else:
        st.warning("No primary sources found — verdict based on absence of evidence.")


# ── Tab 1: Dual Comparison ────────────────────────────────────────────────────
with tab1:
    active_claim = st.session_state.get("active_claim", "")

    if not active_claim:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:3rem;margin-bottom:16px;">🔍</div>
            <div style="font-size:1.2rem;font-weight:600;color:#E2E8F0;margin-bottom:8px;">
                Select a preset or enter your own claim
            </div>
            <div style="color:#6B7280;font-size:0.9rem;">
                ⚡ Preset results are pre-cached — instant load, no API call required.
            </div>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("3-Agent Pipeline", "Extractor → Grounder → Verifier")
        c2.metric("Free APIs", "DuckDuckGo · Wikipedia · OpenFDA")
        c3.metric("Verdicts", "🟢 Real · 🟡 Exaggerated · 🔴 Hoax")
    else:
        # Try to load from cache first
        is_cached = _load_preset_to_session(active_claim)

        st.markdown(f"""
        <div style="background:#1A1A2E;border:1px solid #2D2D3E;border-radius:10px;
                    padding:12px 16px;margin-bottom:20px;display:flex;align-items:center;gap:10px;">
            <span style="color:#A78BFA;">🔎</span>
            <span style="color:#CBD5E1;font-size:0.95rem;font-weight:500;flex:1;">
                Auditing: <em>"{active_claim}"</em></span>
            {"<span style='background:#064E3B;color:#34D399;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;'>⚡ CACHED</span>" if is_cached else ""}
        </div>
        """, unsafe_allow_html=True)

        a_key = f"a_{hash(active_claim)}"
        b_key = f"b_{hash(active_claim)}"

        # Get search results (from cache or live)
        if is_cached and b_key in st.session_state:
            search_results = st.session_state[b_key].get("search_results", [])
        else:
            with st.spinner("Searching the web…"):
                search_results = search_web(active_claim, max_results=10)
            if not search_results:
                st.warning("DuckDuckGo returned no results — continuing with Wikipedia + OpenFDA only.")

        col_a, col_b = st.columns(2, gap="large")

        with col_a:
            st.markdown("""
            <div style="border-left:4px solid #EF4444;padding:4px 0 4px 12px;margin-bottom:12px;">
                <div style="font-size:1rem;font-weight:700;color:#F87171;">🤖 Approach A: Standard SEO</div>
                <div style="font-size:0.78rem;color:#6B7280;">Single LLM + top web results — Era 2 baseline</div>
            </div>
            """, unsafe_allow_html=True)
            with st.container(border=True):
                if a_key in st.session_state:
                    st.markdown(st.session_state[a_key])
                else:
                    full_text = st.write_stream(stream_approach_a(active_claim, search_results))
                    st.session_state[a_key] = full_text

        with col_b:
            st.markdown("""
            <div style="border-left:4px solid #7C3AED;padding:4px 0 4px 12px;margin-bottom:12px;">
                <div style="font-size:1rem;font-weight:700;color:#A78BFA;">🔬 Approach B: Agentic Auditor</div>
                <div style="font-size:0.78rem;color:#6B7280;">Multi-agent primary-source grounding — Era 3</div>
            </div>
            """, unsafe_allow_html=True)
            if b_key in st.session_state:
                _render_b_column(st.session_state[b_key])
            else:
                result = _run_pipeline(active_claim, search_results)
                _render_b_column(result)

        if b_key in st.session_state and st.session_state[b_key].get("sub_claims"):
            with st.expander("🔎 Sub-claims extracted from headline"):
                for i, c in enumerate(st.session_state[b_key]["sub_claims"], 1):
                    st.markdown(f"**{i}.** {c}")


# ── Tab 2: Source Explorer ────────────────────────────────────────────────────
with tab2:
    active_claim = st.session_state.get("active_claim", "")
    b_key = f"b_{hash(active_claim)}" if active_claim else ""

    if not active_claim or b_key not in st.session_state:
        st.info("Run an audit first — the source breakdown will appear here.")
    else:
        result = st.session_state[b_key]
        sr = result.get("search_results", [])
        primary_sources = result["grounding"].get("primary_sources", [])
        echo_n = sum(1 for r in sr if not is_primary_source(r.get("href","")))
        prime_n = len(sr) - echo_n

        st.markdown(f"""
        <div style="margin-bottom:20px;">
            <h3 style="margin:0;color:#E2E8F0;">Source Breakdown</h3>
            <p style="color:#A78BFA;margin:4px 0 0;font-size:0.88rem;font-style:italic;">"{active_claim}"</p>
        </div>
        """, unsafe_allow_html=True)

        col_s, col_p = st.columns(2, gap="large")

        with col_s:
            st.markdown(f"""
            <div style="border-left:4px solid #EF4444;padding:4px 0 4px 12px;margin-bottom:12px;">
                <div style="font-weight:700;color:#F87171;">🌐 DuckDuckGo Results ({len(sr)})</div>
                <div style="font-size:0.78rem;color:#6B7280;">{echo_n} SEO echo &nbsp;·&nbsp; {prime_n} primary</div>
            </div>
            """, unsafe_allow_html=True)
            for r in sr:
                st.markdown(_source_row_html(r.get("title",""), r.get("href",""),
                            r.get("is_primary", is_primary_source(r.get("href",""))),
                            r.get("body","")), unsafe_allow_html=True)

        with col_p:
            st.markdown(f"""
            <div style="border-left:4px solid #10B981;padding:4px 0 4px 12px;margin-bottom:12px;">
                <div style="font-weight:700;color:#34D399;">🔬 Primary Sources Used ({len(primary_sources)})</div>
                <div style="font-size:0.78rem;color:#6B7280;">Fed to Verifier for final verdict</div>
            </div>
            """, unsafe_allow_html=True)
            if primary_sources:
                for src in primary_sources:
                    icon = "✅" if src.get("supports_claim") else "❌"
                    with st.expander(f"{icon} {src.get('title','Source')}", expanded=True):
                        st.caption(f"Domain: **{src.get('domain_type','')}** · Reliability: **{src.get('reliability','')}**")
                        st.write(src.get("relevant_quote",""))
                        st.markdown(f"[Open →]({src.get('url','#')})")
            else:
                st.markdown("""<div style="background:rgba(245,158,11,0.08);border:1px solid #F59E0B;
                               border-radius:8px;padding:16px;color:#FCD34D;text-align:center;">
                    ⚠️ No primary sources found for this claim</div>""", unsafe_allow_html=True)

        if result["grounding"].get("notes"):
            st.markdown("---")
            st.markdown(f"**Grounder note:** {result['grounding']['notes']}")


# ── Tab 3: Agent Trace ────────────────────────────────────────────────────────
with tab3:
    active_claim = st.session_state.get("active_claim", "")
    b_key = f"b_{hash(active_claim)}" if active_claim else ""

    if not active_claim or b_key not in st.session_state:
        st.info("Run an audit first — the agent execution trace will appear here.")
    else:
        result = st.session_state[b_key]
        trace  = result.get("agent_trace", [])
        from_cache = result.get("from_cache", False)

        st.markdown(f"""
        <div style="margin-bottom:20px;">
            <h3 style="margin:0;color:#E2E8F0;">Agent Execution Trace
                {'<span style="background:#064E3B;color:#34D399;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;margin-left:10px;">⚡ FROM CACHE</span>' if from_cache else ""}
            </h3>
            <p style="color:#6B7280;margin:4px 0 0;font-size:0.88rem;">
                Step-by-step pipeline — inputs, outputs, and timing for each agent
            </p>
        </div>
        """, unsafe_allow_html=True)

        accents   = ["#7C3AED", "#0EA5E9", "#10B981"]
        total_ms  = sum(s["duration_ms"] for s in trace)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Duration", f"{total_ms:,} ms")
        c2.metric("Agents Run", len(trace))
        c3.metric("Primary Sources", len(result["grounding"].get("primary_sources",[])))

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        for step in trace:
            accent = accents[(step["step"]-1) % len(accents)]
            st.markdown(_trace_row_html(step["step"], step["agent"], step["model"],
                                        step["duration_ms"], accent), unsafe_allow_html=True)
            with st.expander(f"▶ Step {step['step']} detail"):
                ic, oc = st.columns(2, gap="medium")
                with ic:
                    st.markdown("**Input**")
                    inp = step["input"]
                    st.code(inp if isinstance(inp, str) else str(inp)[:400], language=None)
                with oc:
                    st.markdown("**Output**")
                    out = step["output"]
                    if isinstance(out, list):
                        for item in out: st.markdown(f"- {item}")
                    elif isinstance(out, dict):
                        preview = {k: v for k, v in out.items() if k != "primary_sources"}
                        st.json(preview)
                        if "primary_sources" in out:
                            st.caption(f"{len(out['primary_sources'])} source object(s) — see Source Explorer tab")
                    else:
                        st.write(out)

        st.markdown("---")
        v = result["verdict"]
        st.markdown(f"### Final Verdict: {v.get('verdict_emoji','')} {v.get('verdict_label','')} &nbsp; `{v.get('confidence',0)}% confidence`")
        st.write(v.get("reasoning",""))


# ── Tab 4: Audit History ──────────────────────────────────────────────────────
with tab4:
    st.markdown("""
    <div style="margin-bottom:20px;">
        <h3 style="margin:0;color:#E2E8F0;">Audit History</h3>
        <p style="color:#6B7280;margin:4px 0 0;font-size:0.88rem;">
            All claims audited this session, persisted in MongoDB Atlas.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if not is_connected():
        st.warning("MongoDB is not configured. Add `MONGODB_URI` to your `.env` file and restart.")
    else:
        if st.button("🔄 Refresh", key="refresh_history"):
            st.rerun()

        audits = get_recent_audits(limit=20)
        if not audits:
            st.info("No audits recorded yet — run a preset or custom query to populate history.")
        else:
            verdict_colors = {
                "verified":    ("#10B981", "#064E3B"),
                "exaggerated": ("#F59E0B", "#451A03"),
                "fabricated":  ("#EF4444", "#450A0A"),
            }

            for audit in audits:
                v        = audit.get("verdict", {})
                vkey     = v.get("verdict", "exaggerated")
                accent, bg = verdict_colors.get(vkey, ("#6B7280", "#1F2937"))
                emoji    = v.get("verdict_emoji", "🟡")
                label    = v.get("verdict_label", "Unknown")
                conf     = v.get("confidence", 0)
                echo     = audit.get("echo_index", 0)
                ts       = audit.get("timestamp")
                ts_str   = ts.strftime("%b %d %H:%M UTC") if hasattr(ts, "strftime") else str(ts)[:16]
                claim    = audit.get("claim", "")
                pid      = audit.get("preset_id", "")

                with st.expander(f"{emoji} {claim[:90]}{'…' if len(claim)>90 else ''}"):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(f"**Claim**\n\n{claim}")
                    c2.markdown(f"""
                    <div style="background:{bg};border:1px solid {accent};border-radius:8px;
                                padding:8px;text-align:center;">
                        <div style="color:{accent};font-size:0.7rem;font-weight:700;">VERDICT</div>
                        <div style="color:#E2E8F0;font-weight:700;">{emoji} {label}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    c3.metric("Confidence", f"{conf}%")
                    c4.metric("SEO Echo", f"{echo}%")

                    st.caption(f"Audited: {ts_str}" + (f" · Preset: `{pid}`" if pid else " · Custom query"))

                    if v.get("reasoning"):
                        st.markdown("**Reasoning**")
                        st.write(v["reasoning"])

                    load_btn_key = f"load_{hash(claim)}_hist"
                    if st.button("Load in Comparison →", key=load_btn_key):
                        st.session_state.active_claim = claim
                        st.rerun()

            st.markdown("---")
            st.caption(f"Showing {len(audits)} most recent audits from MongoDB `claimlens.audits`")
