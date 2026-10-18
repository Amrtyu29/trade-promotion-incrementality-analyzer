"""Trade Promotion Incrementality Analyzer - interactive dashboard.

Reads the outputs written by scripts/ (run them first). Launch:  streamlit run app/streamlit_app.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PROC = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT))

# ----------------------------------------------------------------------------- theme
C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100", "magenta": "#e87ba4",
     "green": "#008300", "violet": "#6250d6", "red": "#e34948",
     "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7", "surface": "#fcfcfb"}
CAT_ORDER = ["BAG SNACKS", "COLD CEREAL", "FROZEN PIZZA", "ORAL HYGIENE PRODUCTS"]
CAT_COLOR = dict(zip(CAT_ORDER, [C["blue"], C["orange"], C["aqua"], C["yellow"]]))
TYPE_ORDER = ["feature+display+price", "feature+price", "feature+display", "display+price", "feature_only", "price_only", "display_only"]
METHOD_COLOR = {"A": C["blue"], "B": C["orange"]}

st.set_page_config(page_title="Promo Incrementality", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1280px;}
.kpi {border: 1px solid rgba(11,11,11,0.10); border-radius: 10px; padding: 14px 18px; background: #fcfcfb; height: 100%;}
.kpi .label {font-size: 0.78rem; color: #52514e; letter-spacing: .01em;}
.kpi .value {font-size: 2.0rem; font-weight: 650; color: #0b0b0b; line-height: 1.15; margin-top: 2px;}
.kpi .ci {font-size: 0.78rem; color: #898781; margin-top: 2px;}
.note {border-left: 3px solid #2a78d6; padding: 8px 14px; background: #f3f7fd; border-radius: 6px; margin: 8px 0 14px 0;}
h1 {font-weight: 700;} h2, h3 {font-weight: 650;}
</style>
""", unsafe_allow_html=True)


def layout(fig, h=380, **kw):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=10, r=10, t=36, b=10),
                      paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=C["ink2"], size=12),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
                      hoverlabel=dict(bgcolor="white", font_size=12), **kw)
    fig.update_xaxes(gridcolor=C["grid"], zerolinecolor=C["axis"], linecolor=C["axis"], tickfont=dict(color=C["muted"]), title_font=dict(color=C["ink2"]))
    fig.update_yaxes(gridcolor=C["grid"], zerolinecolor=C["axis"], linecolor=C["axis"], tickfont=dict(color=C["muted"]), title_font=dict(color=C["ink2"]))
    return fig


def kpi(col, label, value, ci=None):
    col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>'
                 f'<div class="ci">{ci or "&nbsp;"}</div></div>', unsafe_allow_html=True)


def pct(x, signed=False):
    return f"{x*100:+.1f}%" if signed else f"{x*100:.1f}%"


def err(fig_trace_kwargs, lo, hi, mid):
    return dict(type="data", symmetric=False, array=np.asarray(hi) - np.asarray(mid), arrayminus=np.asarray(mid) - np.asarray(lo),
                color=C["ink2"], thickness=1.2, width=4)


# ----------------------------------------------------------------------------- data
@st.cache_data
def load():
    d = {"p1": json.load(open(OUT / "phase1_summary.json")), "p2": json.load(open(OUT / "phase2_summary.json"))}
    d["p3"] = json.load(open(OUT / "phase3_summary.json")) if (OUT / "phase3_summary.json").exists() else None
    d["p4"] = json.load(open(OUT / "phase4_summary.json")) if (OUT / "phase4_summary.json").exists() else None
    d["prod"] = pd.read_csv(OUT / "phase1_lift_by_product.csv")
    d["cat"] = pd.read_csv(OUT / "phase1_lift_by_category.csv")
    d["types"] = pd.read_csv(OUT / "phase2_promo_type_lift.csv")
    d["tests"] = pd.read_csv(OUT / "phase2_promo_type_tests.csv")
    d["es"] = pd.read_csv(OUT / "phase2_event_study.csv")
    d["es_cat"] = pd.read_csv(OUT / "phase2_event_study_by_category.csv")
    d["elas"] = pd.read_csv(OUT / "phase3_elasticity.csv") if (OUT / "phase3_elasticity.csv").exists() else None
    d["alloc"] = pd.read_parquet(OUT / "phase4_allocations.parquet") if (OUT / "phase4_allocations.parquet").exists() else None
    d["ev"] = pd.read_parquet(PROC / "events_phase2.parquet",
                              columns=["category", "promo_type", "description", "upc", "incr_A", "baseline_units", "discount_depth",
                                       "n_post_clean", "post_incr", "driver", "run_length", "dln_hhs", "dln_uph", "dln_units"])
    return d


D = load()
p1, p2 = D["p1"], D["p2"]
pf = p2["pullforward"]
prodmap = D["ev"].drop_duplicates("upc").set_index("upc").description.to_dict()

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## Promo Incrementality")
    st.caption("dunnhumby 'Breakfast at the Frat'\n\n77 stores · 55 products · 156 weeks · 49,384 promotion runs")
    page = st.radio("", ["Overview", "Lift by product & promo type", "Event study & pull-forward", "Penetration vs volume",
                         "Price elasticity", "Allocation under budget"], label_visibility="collapsed")
    st.markdown("---")
    st.caption("Every estimate carries a 95% event-level bootstrap CI. Method A = gradient-boosting counterfactual; "
               "Method B = difference-in-differences against control stores.")
    st.caption("Built by Aarshad Rathod · full write-up in docs/methodology.md")

st.title("Trade Promotion Incrementality Analyzer")

# ============================================================================= OVERVIEW
if page == "Overview":
    st.markdown('<div class="note">When a retailer promotes a product the obvious sales lift overstates the true effect. '
                'This dashboard measures what would have sold anyway (two independent counterfactuals) and whether the lift '
                'survives the four weeks that follow.</div>', unsafe_allow_html=True)
    c = st.columns(4)
    kpi(c[0], "In-week lift, all 49,384 runs", pct(p1["overall"][0]["lift_pct"]), f"CI {pct(p1['overall'][0]['lift_lo'])} to {pct(p1['overall'][0]['lift_hi'])}")
    kpi(c[1], "Net lift incl. 4 post-weeks", pct(pf["net_lift_pct"]), f"CI {pct(pf['net_lift_lo'])} to {pct(pf['net_lift_hi'])} · n = {pf['n_events']:,}")
    kpi(c[2], "Pull-forward ratio", pct(pf["pullforward_ratio"], True), f"CI {pct(pf['pullforward_lo'], True)} to {pct(pf['pullforward_hi'], True)} · no dip")
    kpi(c[3], "Lift from more households", pct(p2["decomposition"]["pen_share_mean"]), f"{pct(p2['decomposition']['share_penetration_driven'])} of runs penetration-driven")

    st.markdown("")
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Naive in-week vs net lift, by category")
        rows = pd.DataFrame(p2["pullforward_by_category"])
        rows["in_week"] = rows.in_week_incr_mean; rows["net"] = rows.in_week_incr_mean + rows.post_incr_mean
        fig = go.Figure()
        fig.add_bar(name="In-week incremental units per run", x=rows.category.str.title(), y=rows.in_week, marker_color=C["blue"],
                    hovertemplate="%{x}<br>in-week %{y:.1f} units<extra></extra>")
        fig.add_bar(name="Net incl. 4 post-weeks", x=rows.category.str.title(), y=rows.net, marker_color=C["orange"],
                    hovertemplate="%{x}<br>net %{y:.1f} units<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, yaxis_title="incremental units per promotion run")
        st.plotly_chart(layout(fig, 340), use_container_width=True)
        st.caption("Net is never below in-week: post-promotion weeks sit slightly above baseline in every category.")
    with right:
        st.subheader("Two counterfactuals, same events")
        ov = pd.DataFrame(p1["overall"])
        fig = go.Figure()
        colors = [C["blue"], C["blue"], C["orange"]]
        fig.add_bar(x=ov.method, y=ov.lift_pct * 100, marker_color=colors,
                    error_y=err(None, ov.lift_lo * 100, ov.lift_hi * 100, ov.lift_pct * 100),
                    text=[pct(v) for v in ov.lift_pct], textposition="outside", textfont=dict(color=C["ink2"]),
                    hovertemplate="%{x}<br>lift %{y:.1f}%<extra></extra>")
        fig.update_layout(yaxis_title="lift, % of baseline units", showlegend=False, bargap=0.45)
        st.plotly_chart(layout(fig, 340), use_container_width=True)
        st.caption("On the 10,798 runs with valid control stores, Method A sits 8 points above Method B. That gap, not pull-forward, is the real uncertainty.")

    st.subheader("Validation at a glance")
    v = p1["validation"]["units"]
    c = st.columns(4)
    kpi(c[0], "Baseline RMSE, held-out clean weeks", f"{v['rmse_model']:.2f}", f"vs {v['rmse_naive']:.2f} naive week-of-year median ({(v['rmse_model']/v['rmse_naive']-1)*100:.0f}%)")
    kpi(c[1], "Calibration (actual / predicted)", f"{v['calibration']:.3f}", "1.000 = unbiased")
    kpi(c[2], "Placebo DiD at t-3", f"{p1['placebo_mean']:.2f} u/wk", f"CI {p1['placebo_lo']:.2f} to {p1['placebo_hi']:.2f} · real effect 7.8")
    kpi(c[3], "Runs with valid controls", pct(p1["share_with_controls"]), "mostly store-specific display events")

# ============================================================================= LIFT
elif page == "Lift by product & promo type":
    st.subheader("Lift by promotion type")
    t = D["types"].set_index("promo_type").reindex(TYPE_ORDER).reset_index().dropna(subset=["lift_pct"])
    fig = go.Figure()
    fig.add_bar(x=t.promo_type, y=t.lift_pct * 100, marker_color=C["blue"], error_y=err(None, t.lift_lo * 100, t.lift_hi * 100, t.lift_pct * 100),
                customdata=np.c_[t.n_events, t.incr_per_week, t.mean_discount * 100, t.mean_run_len],
                hovertemplate="%{x}<br>lift %{y:.0f}%<br>%{customdata[0]:,} runs · %{customdata[1]:.1f} incr units/wk<br>mean discount %{customdata[2]:.0f}% · mean run %{customdata[3]:.1f} wk<extra></extra>")
    fig.update_layout(yaxis_title="incremental lift, % of baseline units", bargap=0.4)
    st.plotly_chart(layout(fig, 360), use_container_width=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("Of 21 pairwise Welch t-tests on per-run lift, **18 survive Benjamini-Hochberg at 5%**. The three that do not are the "
                    "single-lever comparisons: a display alone, a feature alone and a price cut alone are statistically indistinguishable at about 50% lift.")
    with c2:
        with st.expander("Pairwise tests (Welch, BH-corrected)"):
            st.dataframe(D["tests"].style.format({"mean_a": "{:.2f}", "mean_b": "{:.2f}", "diff": "{:+.2f}", "t_welch": "{:.1f}", "p_raw": "{:.4f}", "p_bh": "{:.4f}"}), hide_index=True, height=300)

    st.subheader("Lift by discount depth")
    ld = pd.DataFrame(p2["lift_by_depth"])
    fig = go.Figure()
    fig.add_bar(x=ld.depth_bin, y=ld.lift_pct * 100, marker_color=C["blue"], error_y=err(None, ld.lift_lo * 100, ld.lift_hi * 100, ld.lift_pct * 100),
                customdata=ld.n_events, hovertemplate="%{x}<br>lift %{y:.0f}%<br>%{customdata:,} runs<extra></extra>")
    fig.update_layout(yaxis_title="lift, % of baseline units", xaxis_title="discount depth", bargap=0.45)
    st.plotly_chart(layout(fig, 300), use_container_width=True)

    st.subheader("Method A vs Method B by category, same events")
    cat = D["cat"]
    fig = go.Figure()
    for m in ["A", "B"]:
        s = cat[cat.method == m].set_index("category").reindex(CAT_ORDER)
        fig.add_bar(name=f"Method {m} ({'ML baseline' if m == 'A' else 'DiD'})", x=[k.title() for k in s.index], y=s.lift_pct * 100,
                    marker_color=METHOD_COLOR[m], error_y=err(None, s.lift_lo * 100, s.lift_hi * 100, s.lift_pct * 100),
                    hovertemplate="%{x}<br>Method " + m + ": %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="group", yaxis_title="lift, % of baseline units", bargap=0.35, bargroupgap=0.08)
    st.plotly_chart(layout(fig, 330), use_container_width=True)

    st.subheader("Lift by product, both methods")
    cats = st.multiselect("Category", CAT_ORDER, default=CAT_ORDER, format_func=str.title)
    pr = D["prod"].copy()
    pr["category"] = pr.upc.map(D["ev"].drop_duplicates("upc").set_index("upc").category)
    pr = pr[pr.category.isin(cats)].sort_values("lift_pct_A")
    fig = go.Figure()
    for m, dy in [("A", 0.18), ("B", -0.18)]:
        fig.add_scatter(name=f"Method {m}", mode="markers", y=pr.description, x=pr[f"lift_pct_{m}"] * 100,
                        marker=dict(color=METHOD_COLOR[m], size=8, line=dict(color="white", width=1.5)),
                        error_x=dict(type="data", symmetric=False, array=(pr[f"lift_hi_{m}"] - pr[f"lift_pct_{m}"]) * 100,
                                     arrayminus=(pr[f"lift_pct_{m}"] - pr[f"lift_lo_{m}"]) * 100, color=METHOD_COLOR[m], thickness=1, width=0),
                        customdata=pr.n_events_A, hovertemplate="%{y}<br>Method " + m + ": %{x:.0f}%<br>%{customdata} runs with controls<extra></extra>")
    fig.add_vline(x=0, line_color=C["axis"])
    fig.update_layout(xaxis_title="lift, % of baseline units (95% CI)", yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(layout(fig, max(400, 16 * len(pr) + 80)), use_container_width=True)

# ============================================================================= EVENT STUDY
elif page == "Event study & pull-forward":
    c = st.columns(4)
    kpi(c[0], "In-week lift (clean post-window runs)", pct(pf["in_week_lift_pct"]), f"CI {pct(pf['in_week_lift_lo'])} to {pct(pf['in_week_lift_hi'])}")
    kpi(c[1], "Net lift over run + 4 weeks", pct(pf["net_lift_pct"]), f"CI {pct(pf['net_lift_lo'])} to {pct(pf['net_lift_hi'])}")
    kpi(c[2], "Pull-forward ratio", pct(pf["pullforward_ratio"], True), f"CI {pct(pf['pullforward_lo'], True)} to {pct(pf['pullforward_hi'], True)}")
    adj = p2.get("pullforward_adjusted")
    kpi(c[3], "Adjusted for pre-promo residual", pct(adj["ratio"], True) if adj else "n/a", f"CI {pct(adj['lo'], True)} to {pct(adj['hi'], True)}" if adj else "")
    st.markdown("")
    st.subheader("Incremental units per week, 4 weeks before to 4 weeks after the promotion")
    sel = st.selectbox("Category", ["All categories"] + CAT_ORDER, format_func=str.title)
    es = D["es"] if sel == "All categories" else D["es_cat"][D["es_cat"].category == sel]
    x = [("promo" if v == 0 else f"{int(v):+d}") for v in es.rel_week]
    color = C["blue"] if sel == "All categories" else CAT_COLOR[sel]
    fig = go.Figure()
    fig.add_scatter(x=x, y=es.hi, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=x, y=es.lo, mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(42,120,214,0.15)", name="95% bootstrap CI", hoverinfo="skip")
    fig.add_scatter(x=x, y=es.mean_incr, mode="lines+markers", line=dict(color=color, width=2), marker=dict(size=8, line=dict(color="white", width=1.5)),
                    name="mean actual minus counterfactual", customdata=es.n, hovertemplate="week %{x}<br>%{y:.2f} units/week<br>n = %{customdata:,}<extra></extra>")
    fig.add_hline(y=0, line_color=C["axis"])
    fig.update_layout(yaxis_title="incremental units per store-product-week", xaxis_title="week relative to promotion run (post-weeks from run end, truncated at the next promotion)")
    st.plotly_chart(layout(fig, 380), use_container_width=True)

    l, r = st.columns([1, 1])
    with l:
        st.subheader("The post-window, zoomed")
        z = es[es.rel_week != 0]
        xz = [f"{int(v):+d}" for v in z.rel_week]
        fig = go.Figure()
        fig.add_bar(x=xz, y=z.mean_incr, marker_color=[C["muted"] if v < 0 else color for v in z.rel_week],
                    error_y=err(None, z.lo, z.hi, z.mean_incr), hovertemplate="week %{x}<br>%{y:+.2f} units/week<extra></extra>")
        fig.add_hline(y=0, line_color=C["axis"])
        fig.update_layout(yaxis_title="incremental units / week", bargap=0.4, showlegend=False)
        st.plotly_chart(layout(fig, 300), use_container_width=True)
        st.caption("Grey = pre-weeks (the local-demand residual), colour = post-weeks. A pantry-loading dip would show as bars below zero after the promotion.")
    with r:
        st.subheader("Pull-forward ratio by category")
        pc = pd.DataFrame(p2["pullforward_by_category"]).set_index("category").reindex(CAT_ORDER).reset_index()
        fig = go.Figure()
        fig.add_bar(x=[k.title() for k in pc.category], y=pc.pullforward_ratio * 100, marker_color=[CAT_COLOR[k] for k in pc.category],
                    error_y=err(None, pc.lo * 100, pc.hi * 100, pc.pullforward_ratio * 100), customdata=pc.n_events,
                    hovertemplate="%{x}<br>%{y:+.1f}%<br>%{customdata:,} runs<extra></extra>")
        fig.add_hline(y=0, line_color=C["axis"])
        fig.update_layout(yaxis_title="1 - net / in-week, %", bargap=0.45, showlegend=False)
        st.plotly_chart(layout(fig, 300), use_container_width=True)
        st.caption("Negative in every category: post-weeks carry over a little extra volume rather than giving any back.")

# ============================================================================= DECOMPOSITION
elif page == "Penetration vs volume":
    dec = p2["decomposition"]
    c = st.columns(3)
    kpi(c[0], "Households share of log lift", pct(dec["pen_share_mean"]), "mean over runs with log lift > 0.10")
    kpi(c[1], "Penetration-driven runs", pct(dec["share_penetration_driven"]), "more buyers, not bigger baskets")
    vp = p2.get("volume_vs_penetration", {})
    kpi(c[2], "Extra pull-forward, volume vs penetration", pct(vp.get("diff", 0), True), f"CI {pct(vp.get('lo', 0), True)} to {pct(vp.get('hi', 0), True)} · Welch p = {vp.get('welch_p', float('nan')):.3f}")
    st.markdown('<div class="note">ln(units / baseline) = ln(households / baseline households) + ln(units per household / baseline). '
                'Both baselines come from the same gradient-boosting design, so the identity holds exactly per run.</div>', unsafe_allow_html=True)
    l, r = st.columns([1.1, 1])
    with l:
        st.subheader("Each run's lift split into its two components")
        ok = D["ev"][D["ev"].driver != "no_lift"].sample(6000, random_state=0)
        fig = go.Figure()
        for drv, col in [("penetration", C["blue"]), ("volume", C["orange"])]:
            s = ok[ok.driver == drv]
            fig.add_scatter(name=f"{drv}-driven ({(D['ev'].driver == drv).sum():,} runs)", mode="markers", x=s.dln_hhs, y=s.dln_uph,
                            marker=dict(color=col, size=5, opacity=0.45), customdata=s.description,
                            hovertemplate="%{customdata}<br>households %{x:+.2f} · units/hh %{y:+.2f}<extra></extra>")
        fig.add_scatter(x=[-1, 2.5], y=[-1, 2.5], mode="lines", line=dict(color=C["muted"], dash="dash", width=1), name="equal contribution", hoverinfo="skip")
        fig.add_hline(y=0, line_color=C["axis"]); fig.add_vline(x=0, line_color=C["axis"])
        fig.update_layout(xaxis=dict(title="households component  ln(hhs / baseline)", range=[-1, 2.5]), yaxis=dict(title="units-per-household component", range=[-1, 1.5]))
        st.plotly_chart(layout(fig, 420), use_container_width=True)
    with r:
        st.subheader("Households share by category")
        bc = pd.DataFrame(dec["by_category"]).set_index("category").reindex(CAT_ORDER).reset_index()
        fig = go.Figure()
        fig.add_bar(x=[k.title() for k in bc.category], y=bc.pen_share_mean * 100, marker_color=[CAT_COLOR[k] for k in bc.category],
                    text=[pct(v) for v in bc.pen_share_mean], textposition="outside", textfont=dict(color=C["ink2"]),
                    customdata=bc.events, hovertemplate="%{x}<br>%{y:.0f}% of log lift from households<br>%{customdata:,} runs<extra></extra>")
        fig.update_layout(yaxis=dict(title="share of log lift from more households, %", range=[0, 110]), bargap=0.45, showlegend=False)
        st.plotly_chart(layout(fig, 300), use_container_width=True)
        st.subheader("Pull-forward by driver and category")
        bd = pd.DataFrame(dec["by_category_driver"])
        fig = go.Figure()
        for drv, col in [("penetration", C["blue"]), ("volume", C["orange"])]:
            s = bd[bd.driver == drv].set_index("category").reindex(CAT_ORDER)
            fig.add_bar(name=drv, x=[k.title() for k in s.index], y=s.pullforward_ratio * 100, marker_color=col,
                        error_y=err(None, s.lo * 100, s.hi * 100, s.pullforward_ratio * 100), customdata=s.n_events,
                        hovertemplate="%{x} · " + drv + "<br>%{y:+.1f}%<br>%{customdata:,} runs<extra></extra>")
        fig.add_hline(y=0, line_color=C["axis"])
        fig.update_layout(barmode="group", yaxis_title="pull-forward ratio, %", bargap=0.35)
        st.plotly_chart(layout(fig, 300), use_container_width=True)
    st.caption("Volume-driven runs lean toward positive pull-forward (cereal, oral care), as the stock-up mechanism predicts, but they are 5% of runs and the CIs are wide.")

# ============================================================================= ELASTICITY
elif page == "Price elasticity":
    if D["elas"] is None:
        st.info("Run scripts/30_phase3_elasticity.py first.")
    else:
        e = D["elas"].dropna(subset=["elasticity"])
        p3 = D["p3"]
        c = st.columns(4)
        kpi(c[0], "Median own-price elasticity", f"{p3['median_elasticity']:.2f}", f"{p3['n_products']} products, all negative")
        kpi(c[1], "In the -1 to -4 band", f"{p3['n_in_band']} / {p3['n_products']}", "typical promoted FMCG range")
        kpi(c[2], "Without feature/display controls", f"{p3['median_no_controls']:.2f}", "price absorbs display support")
        kpi(c[3], "Most price-sensitive category", min(p3["by_category"], key=lambda r: r["median"])["category"].title(), f"median {min(p3['by_category'], key=lambda r: r['median'])['median']:.2f}")
        st.markdown('<div class="note">Per product: ln(units) = a + b·ln(shelf price) + feature + display + store FE + week-of-year FE, '
                    'OLS with store-clustered SEs. Price is treated as exogenous conditional on the controls; it is not fully, and with cost '
                    'or competitor data I would instrument it.</div>', unsafe_allow_html=True)
        cats = st.multiselect("Category", CAT_ORDER, default=CAT_ORDER, format_func=str.title, key="elcat")
        s = e[e.category.isin(cats)].sort_values("elasticity", ascending=False)
        fig = go.Figure()
        fig.add_vrect(x0=-4, x1=-1, fillcolor="rgba(27,175,122,0.08)", line_width=0, annotation_text="typical band", annotation_position="top left", annotation_font_color=C["muted"])
        for cat in CAT_ORDER:
            q = s[s.category == cat]
            if q.empty:
                continue
            fig.add_scatter(name=cat.title(), mode="markers", y=q.description, x=q.elasticity, marker=dict(color=CAT_COLOR[cat], size=8, line=dict(color="white", width=1.5)),
                            error_x=dict(type="data", symmetric=False, array=q.ci_hi - q.elasticity, arrayminus=q.elasticity - q.ci_lo, color=CAT_COLOR[cat], thickness=1, width=0),
                            customdata=np.c_[q.elasticity_no_promo_controls, q.feature_effect, q.display_effect],
                            hovertemplate="%{y}<br>elasticity %{x:.2f}<br>without promo controls %{customdata[0]:.2f}<br>feature +%{customdata[1]:.2f} · display +%{customdata[2]:.2f} (ln units)<extra></extra>")
        fig.add_vline(x=0, line_color=C["axis"])
        fig.update_layout(xaxis_title="own-price elasticity (95% CI, clustered by store)", yaxis=dict(tickfont=dict(size=10)))
        st.plotly_chart(layout(fig, max(400, 16 * len(s) + 80)), use_container_width=True)

# ============================================================================= ALLOCATION
elif page == "Allocation under budget":
    if D["p4"] is None:
        st.info("Run scripts/40_phase4_allocation.py first.")
    else:
        a = D["p4"]["assumptions"]
        st.markdown(f'<div class="note">0-1 integer program (PuLP / CBC): choose at most one promotion type per store-product to maximise '
                    f'incremental gross margin under a weekly trade budget. Assumptions: margin {a["margin_rate"]:.0%} of shelf price, '
                    f'feature ${a["cost_feature"]:.0f} and display ${a["cost_display"]:.0f} per store-week, price cuts funded on every unit sold. '
                    f'Solved twice: on point-estimate lift and on the bootstrap lower bound (risk-averse).</div>', unsafe_allow_html=True)
        alloc = D["alloc"]; sweep = pd.DataFrame(D["p4"]["sweep"])
        budgets = sorted(alloc.budget.unique())
        l, r = st.columns([1, 2])
        b = l.select_slider("Weekly trade budget ($)", options=budgets, value=budgets[len(budgets) // 2], format_func=lambda v: f"${v:,.0f}")
        obj = r.radio("Objective", ["incr_margin", "incr_margin_lo"], format_func=lambda s: "Maximise expected margin" if s == "incr_margin" else "Maximise CI lower-bound margin (risk-averse)", horizontal=True)
        ch = alloc[(alloc.budget == b) & (alloc.objective == obj)]; other = alloc[(alloc.budget == b) & (alloc.objective != obj)]
        c = st.columns(4)
        kpi(c[0], "Promotions selected", f"{len(ch):,}", f"spend ${ch.cost.sum():,.0f}")
        kpi(c[1], "Expected incremental units / week", f"{ch.incr_units.sum():,.0f}", f"lower bound {ch.incr_units_lo.sum():,.0f}")
        kpi(c[2], "Expected incremental margin / week", f"${ch.incr_margin.sum():,.0f}", f"lower bound ${ch.incr_margin_lo.sum():,.0f}")
        kpi(c[3], "Return per $ of trade spend", f"{ch.incr_margin.sum()/max(1, ch.cost.sum()):.2f}", f"lower bound {ch.incr_margin_lo.sum()/max(1, ch.cost.sum()):.2f}")
        st.markdown("")
        l, r = st.columns([1.2, 1])
        with l:
            st.subheader("Budget frontier: expected vs guaranteed margin")
            fig = go.Figure()
            for o, lab, col in [("incr_margin", "point-estimate plan", C["blue"]), ("incr_margin_lo", "risk-averse plan", C["orange"])]:
                s = sweep[sweep.objective == o]
                fig.add_scatter(name=f"{lab}: expected", x=s.budget, y=s.incr_margin, mode="lines+markers", line=dict(color=col, width=2), marker=dict(size=8),
                                hovertemplate="$%{x:,.0f} budget<br>expected $%{y:,.0f}<extra>" + lab + "</extra>")
                fig.add_scatter(name=f"{lab}: lower bound", x=s.budget, y=s.incr_margin_lo, mode="lines+markers", line=dict(color=col, width=2, dash="dot"), marker=dict(size=6),
                                hovertemplate="$%{x:,.0f} budget<br>lower bound $%{y:,.0f}<extra>" + lab + "</extra>")
            fig.add_vline(x=b, line_color=C["axis"], line_dash="dash")
            fig.update_layout(xaxis=dict(title="weekly trade budget ($)", type="log"), yaxis_title="incremental gross margin ($ / week)")
            st.plotly_chart(layout(fig, 360), use_container_width=True)
        with r:
            st.subheader("Expected incremental units by category")
            cm = pd.DataFrame({"this plan": ch.groupby("category").incr_units.sum(), "other plan": other.groupby("category").incr_units.sum()}).reindex(CAT_ORDER).fillna(0)
            fig = go.Figure()
            fig.add_bar(name="selected plan", x=[k.title() for k in cm.index], y=cm["this plan"], marker_color=C["blue"], hovertemplate="%{x}<br>%{y:,.0f} units<extra>selected</extra>")
            fig.add_bar(name="other objective", x=[k.title() for k in cm.index], y=cm["other plan"], marker_color=C["orange"], hovertemplate="%{x}<br>%{y:,.0f} units<extra>other</extra>")
            fig.update_layout(barmode="group", bargap=0.35, yaxis_title="incremental units / week")
            st.plotly_chart(layout(fig, 360), use_container_width=True)
        mix = pd.DataFrame({"selected plan": ch.promo_type.value_counts(), "other objective": other.promo_type.value_counts()}).fillna(0).astype(int)
        st.markdown("Promotion mix (count of store-product promotions)"); st.dataframe(mix, use_container_width=False)

        st.subheader("Re-solve with your own assumptions")
        st.caption("Lift estimates are fixed from the data; costs and margin are assumptions. Each solve takes 5 to 15 seconds.")
        f1, f2, f3, f4 = st.columns(4)
        margin = f1.number_input("Margin rate", 0.05, 0.80, float(a["margin_rate"]), 0.05)
        cf = f2.number_input("Feature cost $/store-week", 0.0, 2000.0, float(a["cost_feature"]), 10.0)
        cd = f3.number_input("Display cost $/store-week", 0.0, 2000.0, float(a["cost_display"]), 10.0)
        bl = f4.number_input("Budget $/week", 500.0, 200000.0, float(b), 500.0)
        if st.button("Solve", type="primary"):
            from src import allocation as AL
            cand = pd.read_parquet(PROC / "allocation_candidates.parquet")
            cand["incr_margin"] = cand.incr_units * cand.price * margin
            cand["incr_margin_lo"] = cand.incr_units_lo * cand.price * margin
            cand["cost"] = (cand.promo_type.str.contains("feature") * cf + cand.promo_type.str.contains("display") * cd
                            + cand.discount * cand.price * (cand.baseline + cand.incr_units))
            cand = cand[cand.cost > 0]
            with st.spinner("Solving integer program (CBC)..."):
                live = AL.solve(cand, bl, objective=obj)
            s = AL.summarise_solution(live)
            g = st.columns(4)
            kpi(g[0], "Promotions", f"{s['n_promos']:,}", f"spend ${s['spend']:,.0f}")
            kpi(g[1], "Expected incremental units", f"{s['incr_units']:,.0f}", f"lower bound {s['incr_units_lo']:,.0f}")
            kpi(g[2], "Expected incremental margin", f"${s['incr_margin']:,.0f}", f"lower bound ${s['incr_margin_lo']:,.0f}")
            kpi(g[3], "Mix", ", ".join(f"{k} {v}" for k, v in s["mix"].items()), "")
        with st.expander("Selected promotions (precomputed grid)"):
            st.dataframe(ch[["store_num", "upc", "description", "category", "promo_type", "baseline", "lift_used", "lift_lo_used", "incr_units", "incr_units_lo", "cost", "incr_margin"]]
                         .sort_values("incr_margin", ascending=False).style.format({"lift_used": "{:.1%}", "lift_lo_used": "{:.1%}", "incr_units": "{:.1f}", "incr_units_lo": "{:.1f}", "cost": "${:,.0f}", "incr_margin": "${:,.0f}", "baseline": "{:.1f}"}),
                         hide_index=True, height=350)
