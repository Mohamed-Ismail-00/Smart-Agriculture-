/**
 * LandSoilCard — static topsoil profile from ISRIC SoilGrids (estimate at the field centre).
 */

import { useState } from "react";

function findProperty(profile, name) {
  return profile?.properties?.find((p) => p.name.toLowerCase().includes(name));
}

function formatValue(prop) {
  if (!prop || prop.topsoil_value == null) return "—";
  return `${prop.topsoil_value}${prop.unit ? ` ${prop.unit}` : ""}`;
}

export default function LandSoilCard({ soilProfile, onRetry, retrying }) {
  const [retryError, setRetryError] = useState(null);
  const available = soilProfile?.profile_available;

  async function handleRetry() {
    setRetryError(null);
    try {
      await onRetry();
    } catch (err) {
      setRetryError(err?.message || "Soil profile retry failed");
    }
  }

  const items = [
    ["Texture", soilProfile?.texture_class ? soilProfile.texture_class.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "—"],
    ["pH (0–5 cm)", formatValue(findProperty(soilProfile, "ph"))],
    ["Organic carbon", formatValue(findProperty(soilProfile, "soc") || findProperty(soilProfile, "organic"))],
    ["Clay", formatValue(findProperty(soilProfile, "clay"))],
    ["Sand", formatValue(findProperty(soilProfile, "sand"))],
  ];

  return (
    <section className="land-detail__section">
      <div className="section-header">
        <h2 className="section-header__title">Soil</h2>
        <span className="badge badge--neutral">estimate</span>
      </div>
      {available ? (
        <div className="card land-soil">
          {items.map(([label, value]) => (
            <div className="land-soil__item" key={label}>
              <span className="text-caption">{label}</span>
              <span className="land-soil__value">{value}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">The soil profile could not be fetched yet.</p>
          <button type="button" className="btn btn--primary btn--sm" onClick={handleRetry} disabled={retrying}>
            {retrying ? "Retrying…" : "Try again"}
          </button>
          {retryError && <p className="text-caption" style={{ marginTop: 8, color: "var(--error)" }}>{retryError}</p>}
        </div>
      )}
    </section>
  );
}
