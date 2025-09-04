import streamlit as st, os, io, re, json, pandas as pd
# Optional parsers
try: import pypdf
except: pypdf = None
try: import docx
except: docx = None

# OpenAI (only used if key provided)
OPENAI_OK = False
try:
    from openai import OpenAI
    if os.getenv("OPENAI_API_KEY"):
        client = OpenAI()
        OPENAI_OK = True
except: pass

st.set_page_config(page_title="SpecWise MVP", page_icon="📐", layout="wide")
st.title("📐 SpecWise MVP")
st.caption("Upload a spec → Summary → Compliance Flags → Submittal Log → Bid Notes")

with st.sidebar:
    st.header("Settings")
    model = st.selectbox("Model", ["gpt-4o-mini","gpt-4o","gpt-4.1"], index=0)
    temp = st.slider("Temperature", 0.0, 1.0, 0.2, step=0.05)
    max_tokens = st.slider("Max tokens/call", 256, 4000, 1200, step=50)
    st.write("OpenAI key present:", "✅" if OPENAI_OK else "❌")
    st.write("Add OPENAI_API_KEY in Streamlit → Settings → Secrets")

def read_pdf(f)->str:
    if not pypdf: return ""
    r = pypdf.PdfReader(io.BytesIO(f.read()))
    return "\n".join([(p.extract_text() or "") for p in r.pages])

def read_docx(f)->str:
    if not docx: return ""
    d = docx.Document(io.BytesIO(f.read()))
    return "\n".join(p.text for p in d.paragraphs)

def chunk_text(text, size=2500, overlap=200):
    toks = text.split(); out=[]; i=0
    while i < len(toks):
        out.append(" ".join(toks[i:i+size])); i += size - overlap
        if i<=0: break
    return out

def ask(system, user):
    if not OPENAI_OK: return "[No API key] Add OPENAI_API_KEY to enable AI."
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=float(temp), max_tokens=int(max_tokens)
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[OpenAI error] {e}"

st.subheader("1) Upload Spec (PDF or DOCX)")
f = st.file_uploader("Choose file", type=["pdf","docx"])
if not f:
    st.info("Upload a spec to begin.")
    st.stop()

with st.spinner("Extracting text..."):
    text = read_pdf(f) if f.name.lower().endswith(".pdf") else read_docx(f)

if not text.strip():
    st.error("Couldn't extract text. Try a text-based PDF/DOCX.")
    st.stop()

tabs = st.tabs(["AI Summary","Compliance Flags","Submittal Log","Bid Assistant (v1)"])

with tabs[0]:
    st.subheader("AI Summary")
    chunks = chunk_text(text)
    st.caption(f"Processing {len(chunks)} chunks (first 5 shown for speed).")
    outs=[]
    for i, ch in enumerate(chunks[:5]):
        prompt = f"""You are SpecWise, an AI assistant for federal construction specs.
Summarize into ≤8 bullets focusing on: submittal requirements, QA/QC, tests, certifications, unusual constraints.
Text:
{ch}
"""
        outs.append(ask("Be concise and accurate.", prompt))
    st.write("\n\n".join(outs))

with tabs[1]:
    st.subheader("Compliance Flags")
    defaults = "shall, must, submit, warranty, inspection, test report, certificate, QA/QC, submittal register, closeout, within"
    user_terms = st.text_input("Terms (comma-separated)", defaults)
    terms = [t.strip() for t in user_terms.split(",") if t.strip()]
    hits=[]
    low=text.lower()
    for t in terms:
        t0=t.lower(); start=0
        while True:
            idx = low.find(t0, start)
            if idx<0: break
            s=max(0, idx-60); e=min(len(text), idx+len(t0)+60)
            hits.append({"term":t, "context":text[s:e].replace("\n"," ")})
            start=idx+len(t0)
    st.write(f"Found **{len(hits)}** hits.")
    if hits: st.dataframe(pd.DataFrame(hits), use_container_width=True)

with tabs[2]:
    st.subheader("Draft Submittal Log")
    schema = ["Section","Item","Type","Due By","Notes","Source Ref"]
    prompt = f"""Return JSON only. From the specification text, extract a submittal log as an array of objects with keys:
Section, Item, Type, Due By, Notes, Source Ref. Only include explicit or strongly implied submittals.
Text (may be partial):
{text[:20000]}
"""
    out = ask("Return JSON only unless instructed.", prompt)
    try:
        rows = json.loads(out); df=pd.DataFrame(rows)
        for c in schema:
            if c not in df.columns: df[c]=""
        df=df[schema]
    except Exception:
        df=pd.DataFrame(columns=schema)
    st.dataframe(df, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                       "specwise_submittal_log.csv", "text/csv")

with tabs[3]:
    st.subheader("Bid Assistant (v1)")
    topics = ["unusual materials","special testing","access / phasing","schedule constraints","permits","warranty length","submittal frequency","inspection requirements"]
    prompt = f"""Analyze this spec and list items that could impact bid cost or risk, organized by:
{", ".join(topics)}. Short, actionable bullets. Cite section numbers if present.
Text:
{text[:15000]}
"""
    st.write(ask("Be practical and contractor-focused.", prompt))
