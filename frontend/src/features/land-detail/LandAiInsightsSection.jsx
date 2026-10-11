/**
 * LandAiInsightsSection — AI analysis panel for land detail
 */

import { LAND_DETAIL_SOURCES } from "./landDetailUtils";

export default function LandAiInsightsSection({
  landId,
  aiInsights,
  aiLoading,
  aiError,
  analyzingLandId,
  onTriggerAnalysis,
}) {
  return (
    <div className="anim-stagger" style={{ "--stagger-index": 1 }}>
      <div className="section-header land-section-header--mobile">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          <h2 className="section-header__title">AI Analysis</h2>
          <span className="ai-badge-inline">✨ Powered by Groq Vision</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          {aiInsights.length > 0 && <span className="badge badge--neutral">{aiInsights.length} insights</span>}
          <button
            className="ai-trigger-btn"
            onClick={onTriggerAnalysis}
            disabled={analyzingLandId === landId || aiLoading}
          >
            {analyzingLandId === landId ? "Analysis queued..." : "✨ Generate AI Analysis"}
          </button>
        </div>
      </div>

      {aiLoading ? (
        <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--text-secondary)" }}>
          Loading AI Insights...
        </div>
      ) : aiError ? (
        <div className="alert alert--error" style={{ margin: "var(--space-md) 0", padding: "var(--space-lg)" }}>
          <div style={{ fontWeight: 600, marginBottom: "var(--space-xs)" }}>AI Analysis Error</div>
          {aiError}
        </div>
      ) : aiInsights.length > 0 ? (
        <div className="insights-grid">
          {aiInsights.map((insight) => (
            <div className="insight-card" key={insight.insight_id} style={{ borderLeft: "3px solid #7c3aed" }}>
              <div className="insight-card__header">
                <div className="insight-card__icon" style={{ background: "#7c3aed22", color: "#7c3aed" }}>✨</div>
                <span className="insight-card__title">{insight.title}</span>
              </div>
              <p className="insight-card__body">{insight.body}</p>
              {insight.confidence != null && (
                <span className="badge badge--info" style={{ fontSize: 11 }}>
                  Confidence: {(insight.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
          <p className="text-body-sm">No AI insights generated yet. Click the button above to run an analysis.</p>
        </div>
      )}
      <p className="land-detail-section-footer text-caption">
        {LAND_DETAIL_SOURCES.ai}
      </p>
    </div>
  );
}