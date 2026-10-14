"""Streamlit front end for the Code Reviewer CLI.
Uses the shared interfaces: detectors.detect(path) and llm.explain(finding).
Run: streamlit run app.py
"""
import html
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from detectors import detect
from llm import explain

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
SEV_COLOR = {"high": "#F9857D", "medium": "#D4BE7A", "low": "#8FA3B3"}
PENALTY = {"high": 10, "medium": 5, "low": 2}

st.set_page_config(page_title="Code Reviewer", page_icon="🔍", layout="centered")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, .stApp, [class*="css"] { font-family: 'Hanken Grotesk', system-ui, sans-serif; }
#MainMenu, header, footer { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 3rem; padding-bottom: 5rem; }
.brand { color: #048AF8; font-weight: 700; font-size: 1.05rem; margin-bottom: 2.2rem; }
h1.hero { font-size: 2.6rem; line-height: 1.1; font-weight: 700; margin: 0 0 .8rem; letter-spacing: -0.02em; }
p.sub { color: #9FB3C4; font-size: 1.1rem; line-height: 1.55; max-width: 34rem; margin: 0 0 2rem; }
[data-testid="stFileUploaderDropzone"] { background: #0A3558; border: 1px dashed #486073; border-radius: 8px; }
.summary { display: flex; align-items: baseline; gap: 1.4rem; margin: 2.5rem 0 .5rem; }
.score { font-size: 5rem; font-weight: 700; line-height: 1; letter-spacing: -0.03em; }
.score small { font-size: 1.4rem; font-weight: 500; color: #6F8798; letter-spacing: 0; }
.counts { color: #9FB3C4; font-size: 1.05rem; line-height: 1.5; }
.finding { border-left: 3px solid var(--sev); padding: .15rem 0 .15rem 1.1rem; margin: 1.7rem 0 .4rem; }
.finding .loc { font-family: 'JetBrains Mono', monospace; font-size: .85rem; color: #7E95A6; }
.finding .title { font-size: 1.2rem; font-weight: 700; margin: .15rem 0 .45rem; }
.finding .title .name { font-family: 'JetBrains Mono', monospace; font-weight: 500; color: #9FB3C4; font-size: 1rem; margin-left: .4rem; }
.finding .sev { color: var(--sev); font-weight: 500; font-size: .95rem; margin-left: .6rem; }
.finding p { margin: .25rem 0; line-height: 1.55; max-width: 40rem; }
.finding p b { color: #9FB3C4; font-weight: 500; margin-right: .4rem; }
.errnote { border-left: 3px solid #F9857D; padding-left: 1rem; margin: 1rem 0; color: #F9C3BE; }
details { border: 1px solid #1B4668 !important; border-radius: 6px !important; }
.stDownloadButton button, .stButton button { background: #048AF8; color: #fff; border: 0; border-radius: 6px; font-weight: 500; }
.stDownloadButton button:hover { background: #2D9DFA; color: #fff; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="brand">Code Reviewer</div>', unsafe_allow_html=True)
st.markdown(
    '<h1 class="hero">Find what is wrong with your Python, in plain language.</h1>'
    '<p class="sub">Upload a file. It is parsed with <code>ast</code>, every problem gets a line number, '
    "and an LLM explains each one with a suggested fix.</p>",
    unsafe_allow_html=True,
)


def score_of(findings):
    penalty = sum(PENALTY.get(str(f.get("severity", "low")).lower(), 2) for f in findings)
    return max(0, 100 - penalty)


def sort_key(f):
    return (SEV_ORDER.get(str(f.get("severity", "low")).lower(), 3), str(f.get("file", "")), f.get("line") or 0)


def safe_explain(f):
    try:
        res = explain(f)
        return res if isinstance(res, dict) else f
    except Exception:
        return f


@st.cache_data(show_spinner=False)
def analyze(files, use_llm):
    """files: tuple of (name, bytes). Returns (findings, errors)."""
    findings, errors = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in files:
            path = Path(tmp) / Path(name).name
            path.write_bytes(data)
            try:
                found = detect(str(path))
            except SyntaxError as e:
                errors.append(f"{name}: syntax error on line {e.lineno}: {e.msg}")
                continue
            except Exception as e:
                errors.append(f"{name}: could not analyze ({e})")
                continue
            for f in found:
                f["file"] = name
            findings.extend(found)
    if use_llm and findings:
        with ThreadPoolExecutor(max_workers=4) as pool:
            findings = list(pool.map(safe_explain, findings))
    findings.sort(key=sort_key)
    return findings, errors


def build_report(findings, score):
    lines = ["# Code review report", "", f"Score: **{score}/100** · {len(findings)} problems", ""]
    for f in findings:
        lines += [
            f"## {f.get('file')}:{f.get('line')} — {f.get('type')} ({f.get('severity')})",
            f"`{f.get('name', '')}`",
            "",
            f"**Why:** {f.get('why') or 'n/a'}",
            f"**Fix:** {f.get('fix') or 'n/a'}",
        ]
        if f.get("corrected_code"):
            lines += ["", "```python", f["corrected_code"], "```"]
        lines.append("")
    return "\n".join(lines)


uploads = st.file_uploader("Python files", type=["py"], accept_multiple_files=True, label_visibility="collapsed")
use_llm = st.toggle("Explain with AI", value=True)

if uploads:
    with st.spinner("Reviewing..."):
        findings, errors = analyze(tuple((u.name, u.getvalue()) for u in uploads), use_llm)

    for msg in errors:
        st.markdown(f'<div class="errnote">{html.escape(msg)}</div>', unsafe_allow_html=True)

    if not findings and not errors:
        st.markdown('<p class="sub">No problems found.</p>', unsafe_allow_html=True)
    elif findings:
        score = score_of(findings)
        color = "#C9D4A3" if score >= 80 else "#D4BE7A" if score >= 50 else "#F9857D"
        n = lambda s: sum(1 for f in findings if str(f.get("severity")).lower() == s)
        st.markdown(
            f'<div class="summary"><div class="score" style="color:{color}">{score}<small>/100</small></div>'
            f'<div class="counts">{len(findings)} problems<br>{n("high")} high, {n("medium")} medium, {n("low")} low</div></div>',
            unsafe_allow_html=True,
        )
        st.download_button("Download report.md", build_report(findings, score), "report.md", "text/markdown")

        e = lambda v: html.escape(str(v or ""))
        for f in findings:
            sev = str(f.get("severity", "low")).lower()
            why = f'<p><b>Why</b>{e(f.get("why"))}</p>' if f.get("why") else ""
            fix = f'<p><b>Fix</b>{e(f.get("fix"))}</p>' if f.get("fix") else ""
            st.markdown(
                f'<div class="finding" style="--sev:{SEV_COLOR.get(sev, "#8FA3B3")}">'
                f'<div class="loc">{e(f.get("file"))}:{e(f.get("line"))}</div>'
                f'<div class="title">{e(f.get("type"))}<span class="name">{e(f.get("name"))}</span>'
                f'<span class="sev">{e(sev)}</span></div>{why}{fix}</div>',
                unsafe_allow_html=True,
            )
            if f.get("corrected_code"):
                with st.expander("Corrected code"):
                    st.code(f["corrected_code"], language="python")
