import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import TrustBadge from "../../components/TrustBadge";
import "./CropConfirmModal.css";

const CROP_OPTIONS = [
  "wheat(winter)",
  "barley",
  "winter onion",
  "garlic",
  "fava bean",
  "sugar beet",
  "corn / maize (summer)",
  "cotton",
  "rice",
  "tomato (summer)",
  "potato",
  "sunflower",
  "soybean",
  "citrus orchard",
  "mango orchard",
  "grapes/vineyard",
  "clover/berseem",
  "alfalfa (perennial)",
  "vegetables (mixed)",
  "other",
];

function formatCropLabel(crop) {
  return crop?.split("(")[0].trim() || "";
}

function pct(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function SignalChip({ label, value }) {
  return (
    <div className="crop-confirm-modal__signal">
      <div className="crop-confirm-modal__signal-label">{label}</div>
      <div className="crop-confirm-modal__signal-value">{value}</div>
    </div>
  );
}

export default function CropConfirmModal({
  open,
  onClose,
  onConfirm,
  cropDetection,
  declaredCrop,
  saving,
}) {
  const spectralEstimate = cropDetection?.detected_crop_type;
  const confidence = cropDetection?.confidence ?? 0;
  const band = cropDetection?.confidence_band || "low";
  const displayLabel = cropDetection?.display_label || "Suggested";
  const signals = cropDetection?.spectral_signals;
  const isHighBand = band === "high";

  const [mode, setMode] = useState(isHighBand ? "accept" : "choose");
  const [cropType, setCropType] = useState(declaredCrop || spectralEstimate || "");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (open) {
      setCropType(declaredCrop || spectralEstimate || "");
      setNotes("");
      setMode(isHighBand && !declaredCrop ? "accept" : "choose");
    }
  }, [open, declaredCrop, spectralEstimate, isHighBand]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.classList.add("crop-modal-open");
    return () => document.body.classList.remove("crop-modal-open");
  }, [open]);

  if (!open) return null;

  const cropDisplay = formatCropLabel(spectralEstimate);
  const confidencePct = Math.round(confidence * 100);
  const cardClass = `crop-confirm-modal__suggestion-card${
    band === "high" ? " crop-confirm-modal__suggestion-card--high" : ""
  }${band === "low" ? " crop-confirm-modal__suggestion-card--low" : ""}`;

  const handleAccept = () => {
    if (!spectralEstimate) return;
    onConfirm({ crop_type: spectralEstimate, notes: notes || null });
  };

  const handleChoose = () => {
    if (!cropType) return;
    onConfirm({ crop_type: cropType, notes: notes || null });
  };

  return createPortal(
    <div className="crop-confirm-modal__backdrop" role="presentation" onClick={onClose}>
      <div
        className="crop-confirm-modal"
        role="dialog"
        aria-labelledby="crop-confirm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="crop-confirm-modal__header">
          <div className="crop-confirm-modal__header-text">
            <h3 id="crop-confirm-title">
              {declaredCrop ? "Update your crop" : "Confirm field crop"}
            </h3>
            <p>
              Confirmed crops unlock verified health scores, harvest windows, and AI advice.
              Satellite detection is a suggestion until you confirm.
            </p>
          </div>
          <button
            type="button"
            className="crop-confirm-modal__close"
            onClick={onClose}
            aria-label="Close"
            disabled={saving}
          >
            ×
          </button>
        </div>

        <div className="crop-confirm-modal__body">
          {spectralEstimate && (
            <div className={cardClass}>
              <div className="crop-confirm-modal__suggestion-top">
                <span className="crop-confirm-modal__crop-name">{cropDisplay}</span>
                <span
                  className={`crop-confirm-modal__confidence-pill${
                    band === "high" ? " crop-confirm-modal__confidence-pill--high" : ""
                  }`}
                >
                  {displayLabel} · {confidencePct}%
                </span>
              </div>

              <div className="crop-confirm-modal__confidence-bar-wrap">
                <div className="crop-confirm-modal__confidence-bar-label">
                  <span>Spectral fit</span>
                  <span>{confidencePct}%</span>
                </div>
                <div className="crop-confirm-modal__confidence-bar">
                  <div
                    style={{
                      width: `${confidencePct}%`,
                      background:
                        band === "high"
                          ? "linear-gradient(90deg, var(--green-400), var(--green-600))"
                          : band === "medium"
                            ? "linear-gradient(90deg, var(--info), #60a5fa)"
                            : "linear-gradient(90deg, var(--warning-border), var(--amber-500))",
                    }}
                  />
                </div>
              </div>

              {signals && (
                <div className="crop-confirm-modal__signals">
                  <SignalChip label="NDVI profile" value={pct(signals.profile_fit)} />
                  <SignalChip label="Season" value={pct(signals.season_match)} />
                  <SignalChip label="Field agreement" value={pct(signals.field_agreement)} />
                  <SignalChip
                    label="Pattern clarity"
                    value={signals.profile_margin != null ? pct(signals.profile_margin) : "—"}
                  />
                </div>
              )}

              <p className="text-caption" style={{ margin: "12px 0 0", color: "var(--text-secondary)" }}>
                <TrustBadge tier="estimated" /> {cropDetection?.note}
              </p>
            </div>
          )}

          {!declaredCrop && spectralEstimate && (
            <div className="crop-confirm-modal__mode-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "accept"}
                className={`crop-confirm-modal__mode-tab${
                  mode === "accept" ? " crop-confirm-modal__mode-tab--active" : ""
                }`}
                onClick={() => setMode("accept")}
              >
                Accept {cropDisplay}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "choose"}
                className={`crop-confirm-modal__mode-tab${
                  mode === "choose" ? " crop-confirm-modal__mode-tab--active" : ""
                }`}
                onClick={() => setMode("choose")}
              >
                Choose different
              </button>
            </div>
          )}

          {(mode === "choose" || !spectralEstimate || declaredCrop) && (
            <>
              <div className="crop-confirm-modal__field">
                <label className="crop-confirm-modal__label" htmlFor="crop-type-select">
                  Primary crop
                </label>
                <select
                  id="crop-type-select"
                  className="crop-confirm-modal__select"
                  value={cropType}
                  onChange={(e) => setCropType(e.target.value)}
                >
                  <option value="">Select crop…</option>
                  {CROP_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {formatCropLabel(c)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="crop-confirm-modal__field">
                <label className="crop-confirm-modal__label" htmlFor="crop-notes">
                  Notes (optional)
                </label>
                <textarea
                  id="crop-notes"
                  className="crop-confirm-modal__textarea"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Mixed vegetables along the north edge"
                />
              </div>
            </>
          )}

          {mode === "accept" && spectralEstimate && !declaredCrop && (
            <div className="crop-confirm-modal__field">
              <label className="crop-confirm-modal__label" htmlFor="crop-notes-accept">
                Notes (optional)
              </label>
              <textarea
                id="crop-notes-accept"
                className="crop-confirm-modal__textarea"
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Anything we should know about this field?"
              />
            </div>
          )}

          <div className="crop-confirm-modal__actions">
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={onClose}
              disabled={saving}
            >
              Not now
            </button>
            {mode === "accept" && spectralEstimate && !declaredCrop ? (
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={saving}
                onClick={handleAccept}
              >
                {saving ? "Saving…" : `Accept ${cropDisplay}`}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={!cropType || saving}
                onClick={handleChoose}
              >
                {saving ? "Saving…" : declaredCrop ? "Update crop" : "Confirm crop"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}