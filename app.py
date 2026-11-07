from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from satnogs_client import SatNOGSError, fetch_observations, normalize_observations


st.set_page_config(
    page_title="PASS-TRACE | Ground Network Monitor",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
:root {
  --ink: #13252b;
  --muted: #54666d;
  --paper: #f3f6f4;
  --panel: #ffffff;
  --line: #dce5e1;
  --teal: #087f78;
  --teal-pale: #e2f2ef;
  --amber: #ae6b16;
  --amber-pale: #fff2dd;
  --red: #ae3b39;
  --red-pale: #fae9e7;
}
html, body, [class*="css"] { font-family: 'Source Sans 3', sans-serif; color: var(--ink); }
.stApp { background: var(--paper); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #e9efeb; border-right: 1px solid var(--line); }
[data-testid="stSidebar"] section { padding-top: 1.1rem; }
h1, h2, h3 { font-family: 'Barlow Condensed', sans-serif !important; letter-spacing: .01em; }
h1 { font-size: 2.8rem !important; line-height: .98 !important; margin-bottom: .15rem !important; }
h2 { font-size: 1.7rem !important; }
.eyebrow { color: var(--teal); font-size: .74rem; font-weight: 700; letter-spacing: .15em; text-transform: uppercase; }
.lede { color: var(--muted); max-width: 68ch; font-size: 1rem; margin: .35rem 0 1.2rem; }
.statusline { display:flex; gap:.55rem; align-items:center; color:var(--muted); font-size:.86rem; }
.live-dot { width:.55rem; height:.55rem; border-radius:50%; background:#188b67; display:inline-block; box-shadow:0 0 0 3px #d8eee5; }
.metric { background:var(--panel); border:1px solid var(--line); padding: .9rem 1rem; min-height: 94px; }
.metric-label { color:var(--muted); font-size:.75rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.metric-value { font-family:'Barlow Condensed',sans-serif; font-size:2.15rem; line-height:1.05; color:var(--ink); margin-top:.2rem; }
.metric-note { color:var(--muted); font-size:.78rem; margin-top:.18rem; }
.section-kicker { border-bottom:1px solid var(--line); padding-bottom:.45rem; margin:1.15rem 0 .55rem; color:var(--ink); font-weight:700; letter-spacing:.03em; }
.source-note { color:var(--muted); font-size:.78rem; line-height:1.5; border-top:1px solid var(--line); padding-top:.8rem; margin-top:1.5rem; }
.warning-note { background:var(--amber-pale); color:#74470f; padding:.7rem .85rem; font-size:.87rem; border:1px solid #f0d8b2; }
div[data-testid="stDataFrame"] { border:1px solid var(--line); }
div.stButton > button { border-radius:2px; font-weight:700; }
div[data-testid="stMetric"] { background:transparent; }
@media (max-width: 700px) {
  h1 { font-size:2.25rem !important; }
  .metric { min-height:80px; }
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600, show_spinner=False)
def load_data(start: date, end: date):
    raw, truncated = fetch_observations(start, end)
    return normalize_observations(raw), truncated


def metric(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


today_utc = datetime.now(timezone.utc).date()
st.sidebar.markdown('<div class="eyebrow">Query window · UTC</div>', unsafe_allow_html=True)
default_start = today_utc - timedelta(days=3)
start_date = st.sidebar.date_input("From", value=default_start, max_value=today_utc)
end_date = st.sidebar.date_input("Through", value=today_utc, min_value=start_date, max_value=today_utc)
if (end_date - start_date).days > 13:
    st.sidebar.error("Choose a range of 14 days or less.")
    st.stop()
if st.sidebar.button("Refresh live data", use_container_width=True):
    load_data.clear()

st.sidebar.markdown("---")
st.sidebar.markdown("**Data source**")
st.sidebar.markdown("SatNOGS Network public observations API")
st.sidebar.caption("Results are cached for 10 minutes. The API is queried only for the selected date range.")

st.markdown('<div class="eyebrow">Public ground-network observability</div>', unsafe_allow_html=True)
st.title("PASS-TRACE")
st.markdown("### Satellite pass & reception monitor")
st.markdown(
    '<p class="lede">Follow scheduled observation windows and the reports returned by volunteer ground stations. '
    'Filter by satellite or station, review signal evidence, and export the records.</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="warning-note"><strong>Scope:</strong> This dashboard reports SatNOGS observation records. '
    'It does not monitor spacecraft health, infer a fault from a missing public record, or use ISRO/ISTRAC data.</div>',
    unsafe_allow_html=True,
)

try:
    with st.spinner("Collecting public observation records…"):
        observations, truncated = load_data(start_date, end_date)
except (SatNOGSError, ValueError) as exc:
    st.error(str(exc))
    st.info("Check your connection or shorten the date range, then refresh.")
    st.stop()

fetched_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
st.markdown(
    f'<div class="statusline"><span class="live-dot"></span> API response received '
    f'<span>·</span> {len(observations):,} records loaded <span>·</span> refreshed {fetched_at}</div>',
    unsafe_allow_html=True,
)
if truncated:
    st.warning("The API returned more records than the page limit. Narrow the date range to load the complete result set.")

if observations.empty:
    st.info("No SatNOGS observation records were returned for this UTC date range. Try a wider range or another date.")
    st.markdown(
        '<div class="source-note">API data: <a href="https://network.satnogs.org/api/observations/">SatNOGS Network</a>. '
        'Open data is distributed under CC BY-SA. This is an independent student project.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

all_satellites = sorted(observations["norad_id"].dropna().astype(int).unique().tolist())
all_stations = sorted(observations["station"].dropna().astype(str).unique().tolist())
filter_col1, filter_col2 = st.columns([1, 1])
with filter_col1:
    selected_sat = st.selectbox("Satellite NORAD ID", ["All satellites"] + all_satellites)
with filter_col2:
    selected_station = st.selectbox("Ground station", ["All stations"] + all_stations)

filtered = observations.copy()
if selected_sat != "All satellites":
    filtered = filtered.loc[pd.to_numeric(filtered["norad_id"], errors="coerce") == int(selected_sat)]
if selected_station != "All stations":
    filtered = filtered.loc[filtered["station"] == selected_station]

statuses = filtered["status"].fillna("unknown").str.lower()
finalized = statuses.isin(["good", "bad"])
good_count = int(statuses.eq("good").sum())
bad_count = int(statuses.eq("bad").sum())
unknown_count = int(statuses.eq("unknown").sum())
signal_count = int(filtered["has_signal"].sum())
frame_count = int(filtered["demodulated_frames"].sum())
reviewed_count = int(finalized.sum())
good_rate = f"{100 * good_count / reviewed_count:.0f}%" if reviewed_count else "—"

kpis = st.columns(4)
with kpis[0]: metric("Observation records", f"{len(filtered):,}", "returned by SatNOGS")
with kpis[1]: metric("API status: good", f"{good_count:,}", f"{good_rate} of good/bad reviewed records")
with kpis[2]: metric("API status: bad", f"{bad_count:,}", "review outcome recorded by network")
with kpis[3]: metric("Signal / decoded frames", f"{signal_count:,} / {frame_count:,}", "with-signal records / demodulated frames")

left, right = st.columns([1.1, 1])
with left:
    st.markdown('<div class="section-kicker">Observation status</div>', unsafe_allow_html=True)
    status_summary = statuses.value_counts().rename_axis("API status").rename("Records").to_frame()
    if status_summary.empty:
        st.caption("No status data in the current selection.")
    else:
        st.bar_chart(status_summary, color="#087f78", horizontal=True, height=230)
with right:
    st.markdown('<div class="section-kicker">Station activity</div>', unsafe_allow_html=True)
    station_summary = (
        filtered.assign(_good=statuses.eq("good"), _bad=statuses.eq("bad"), _signal=filtered["has_signal"])
        .groupby("station", dropna=False)
        .agg(Attempts=("observation_id", "count"), Good=("_good", "sum"), Bad=("_bad", "sum"), WithSignal=("_signal", "sum"))
        .sort_values(["Bad", "Attempts"], ascending=[False, False])
        .head(8)
    )
    st.dataframe(station_summary, width="stretch", height=230)

st.markdown('<div class="section-kicker">Pass records · newest first</div>', unsafe_allow_html=True)
search = st.text_input("Find satellite, station, mode, or status", placeholder="e.g. ISS, good, BPSK")
if search.strip():
    term = search.strip().casefold()
    mask = filtered[["satellite", "station", "mode", "status", "waterfall_status"]].astype(str).apply(
        lambda column: column.str.casefold().str.contains(term, regex=False)
    ).any(axis=1)
    filtered = filtered.loc[mask]

display = filtered[[
    "start_utc", "satellite", "norad_id", "station", "status", "waterfall_status",
    "demodulated_frames", "max_altitude_deg", "mode", "observation_id",
]].copy()
display = display.rename(columns={
    "start_utc": "Start (UTC)", "satellite": "Satellite", "norad_id": "NORAD ID",
    "station": "Ground station", "status": "API status", "waterfall_status": "Signal evidence",
    "demodulated_frames": "Decoded frames", "max_altitude_deg": "Max elevation (°)",
    "mode": "Mode", "observation_id": "Observation ID",
})
st.dataframe(display, width="stretch", hide_index=True, height=430)

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download filtered records as CSV",
    data=csv_bytes,
    file_name=f"pass-trace-satnogs-{start_date}-to-{end_date}.csv",
    mime="text/csv",
)

with st.expander("How to interpret this dashboard"):
    st.markdown("""
    - **API status** is the status reported by SatNOGS; it is not a spacecraft fault diagnosis.
    - **Signal evidence** reflects the observation's waterfall status. A signal-bearing record is not by itself proof that a telemetry payload decoded correctly.
    - **Decoded frames** counts demodulated records attached to the observation response.
    - **No row returned** means the selected API query returned no observation record; it does not prove that a pass was missed or a spacecraft failed.
    - Data source: [SatNOGS Network API](https://docs.satnogs.org/projects/satnogs-network/en/latest/api.html), open data under CC BY-SA.
    """)

st.markdown(
    '<div class="source-note">Built as an independent student project using public SatNOGS Network data. '
    'No ISRO/ISTRAC operational telemetry or procedures are included. '
    '<a href="https://docs.satnogs.org/projects/satnogs-network/en/latest/api.html">API documentation</a> · '
    '<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA</a></div>',
    unsafe_allow_html=True,
)

