import "./TrustBadge.css";

const TIER_STYLES = {
  verified: { label: "Confirmed", className: "trust-badge--verified" },
  observed: { label: "Observed", className: "trust-badge--observed" },
  estimated: { label: "Estimated", className: "trust-badge--estimated" },
  unavailable: { label: "No data", className: "trust-badge--unavailable" },
};

export default function TrustBadge({ tier, title, className = "" }) {
  const key = (tier || "estimated").toLowerCase();
  const style = TIER_STYLES[key] || TIER_STYLES.estimated;
  return (
    <span
      className={`trust-badge ${style.className} ${className}`.trim()}
      title={title || `Data trust: ${style.label}`}
    >
      {style.label}
    </span>
  );
}