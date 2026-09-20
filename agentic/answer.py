"""Customer-facing answer intelligence over executed query results."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
import math
import pandas as pd


@dataclass
class AnswerArtifact:
    answer_type: str
    title: str
    summary: str
    kpis: list[dict[str, Any]] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    trends: list[dict[str, Any]] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    visualization: dict[str, Any] = field(default_factory=dict)
    insights: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    raw_result_available: bool = True
    row_count: int = 0

    def to_dict(self):
        return asdict(self)


def _clean_number(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _dimension_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in _numeric_columns(df)]


def _human(value: Any) -> str:
    n = _clean_number(value)
    if n is None:
        return str(value)
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.2f}K"
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,.2f}"


def _pick_view(question: str, df: pd.DataFrame) -> str:
    q = question.lower()
    numeric = _numeric_columns(df)
    dims = _dimension_columns(df)
    if df.empty:
        return "empty"
    if any(token in q for token in ("why", "driver", "reason", "what changed")):
        return "insight"
    if any(token in q for token in ("compare", "versus", "vs ", "difference between")) and dims and numeric:
        return "comparison"
    if any(token in q for token in ("over time", "trend", "monthly", "weekly", "daily", "quarterly", "last 12 months")) and dims and numeric:
        return "trend"
    if any(token in q for token in ("by ", "each ", "top ", "bottom ", "rank")) and dims and numeric:
        return "chart"
    if len(df) == 1 and numeric:
        return "kpi"
    if numeric and dims:
        return "chart"
    if len(df) <= 20:
        return "table"
    return "executive"


def build_answer(question: str, df: pd.DataFrame, *, plan: Any | None = None,
                 evidence: list[dict[str, Any]] | None = None) -> AnswerArtifact:
    evidence = evidence or []
    answer_type = _pick_view(question, df)
    if df.empty:
        return AnswerArtifact("empty", question.strip() or "No result", "The query returned no rows.",
                              evidence=evidence, confidence=0.88, row_count=0)

    numeric = _numeric_columns(df)
    dims = _dimension_columns(df)
    primary = numeric[0] if numeric else None
    kpis = []
    if primary:
        series = pd.to_numeric(df[primary], errors="coerce").dropna()
        if not series.empty:
            value = float(series.sum()) if len(series) > 1 else float(series.iloc[0])
            kpis.append({"label": primary.replace("_", " ").title(), "value": _human(value), "raw_value": value, "kind": "primary"})
            if len(series) > 1:
                first, latest = float(series.iloc[0]), float(series.iloc[-1])
                if first != 0:
                    delta = (latest - first) / abs(first) * 100
                    kpis.append({"label": "Change", "value": f"{delta:+.1f}%", "raw_value": delta, "kind": "change"})

    comparisons = []
    if dims and primary and len(df) >= 2:
        work = df[[dims[0], primary]].copy()
        work[primary] = pd.to_numeric(work[primary], errors="coerce")
        work = work.dropna().sort_values(primary, ascending=False)
        if len(work) >= 2:
            top, second = work.iloc[0], work.iloc[1]
            comparisons.append({
                "dimension": dims[0],
                "top": str(top[dims[0]]), "top_value": float(top[primary]),
                "second": str(second[dims[0]]), "second_value": float(second[primary]),
                "gap": float(top[primary] - second[primary]),
            })

    trends = []
    if dims and primary and len(df) >= 2:
        trends = [{"x": str(row[dims[0]]), "y": _clean_number(row[primary])} for _, row in df.iterrows()]

    anomalies = []
    if primary and len(df) >= 4:
        series = pd.to_numeric(df[primary], errors="coerce").dropna()
        std = float(series.std(ddof=0)) if len(series) else 0.0
        if std > 0:
            mean = float(series.mean())
            for idx, value in series.items():
                z = abs((float(value) - mean) / std)
                if z >= 2.0:
                    anomalies.append({"row": str(idx), "value": float(value), "z_score": round(z, 2)})

    insights = []
    summary = f"Returned {len(df):,} rows."
    if primary and len(df) == 1:
        summary = f"{primary.replace('_', ' ').title()} is {_human(df.iloc[0][primary])}."
    elif comparisons:
        c = comparisons[0]
        summary = f"{c['top']} leads {c['second']} by {_human(abs(c['gap']))} in {primary.replace('_', ' ')}."
        insights.append({"type": "fact", "text": summary, "supported_by": [c["top"], c["second"]]})
    elif primary and dims:
        summary = f"{len(df):,} grouped results returned for {primary.replace('_', ' ')}."
    if anomalies:
        insights.append({"type": "anomaly", "text": f"{len(anomalies)} result(s) are statistical outliers on {primary.replace('_', ' ')}.", "supported_by": anomalies})
    if answer_type == "insight" and not insights:
        insights.append({"type": "limitation", "text": "The result does not establish a causal driver by itself.", "supported_by": []})

    visualization = {"type": "none"}
    if answer_type in {"chart", "trend", "comparison"} and dims and primary:
        visualization = {"type": "line" if answer_type == "trend" else "bar", "x": dims[0], "y": primary, "rows": len(df)}

    confidence = 0.90 - (0.05 if not evidence else 0.0) - (0.08 if not numeric else 0.0)
    return AnswerArtifact(
        answer_type=answer_type,
        title=question.strip() or answer_type.replace("_", " ").title(),
        summary=summary,
        kpis=kpis,
        dimensions=dims,
        comparisons=comparisons,
        trends=trends,
        anomalies=anomalies,
        visualization=visualization,
        insights=insights,
        evidence=evidence,
        confidence=max(0.0, min(1.0, confidence)),
        row_count=len(df),
    )


def render_answer(artifact: AnswerArtifact, df: pd.DataFrame | None = None) -> None:
    import streamlit as st
    if artifact.answer_type == "empty":
        st.info(artifact.summary)
        return
    st.subheader("✨ Answer")
    st.write(artifact.summary)
    if artifact.kpis:
        cols = st.columns(min(4, len(artifact.kpis)))
        for idx, kpi in enumerate(artifact.kpis[:4]):
            cols[idx].metric(kpi["label"], kpi["value"])
    if artifact.insights:
        st.subheader("What matters")
        for insight in artifact.insights:
            if insight["type"] == "anomaly":
                st.warning(insight["text"])
            elif insight["type"] == "limitation":
                st.info(insight["text"])
            else:
                st.success(insight["text"])
    if artifact.visualization.get("type") in {"bar", "line"} and df is not None:
        x, y = artifact.visualization["x"], artifact.visualization["y"]
        if x in df.columns and y in df.columns:
            chart_df = df[[x, y]].copy()
            chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
            chart_df = chart_df.dropna()
            if not chart_df.empty:
                st.subheader("Visual")
                if artifact.visualization["type"] == "line":
                    st.line_chart(chart_df.set_index(x)[y])
                else:
                    st.bar_chart(chart_df.set_index(x)[y])
    if artifact.comparisons:
        st.subheader("Comparison")
        st.dataframe(pd.DataFrame(artifact.comparisons), use_container_width=True, hide_index=True)
    with st.expander("Evidence"):
        if artifact.evidence:
            st.json(artifact.evidence)
        else:
            st.info("No structured evidence was attached.")
    with st.expander("Raw data"):
        if df is not None:
            st.dataframe(df, use_container_width=True)
