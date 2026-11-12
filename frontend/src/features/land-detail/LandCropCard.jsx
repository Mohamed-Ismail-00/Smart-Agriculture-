/**
 * LandCropCard — which crop is in the field.
 * Shows the crop the farmer confirmed, otherwise the current rule-based estimate,
 * clearly marked as temporary until the trained crop model replaces it.
 */

import CropConfirmModal from "./CropConfirmModal";
import { cropName } from "./landDetailUtils";

export default function LandCropCard({
  cropDetection,
  cropConfirmOpen,
  setCropConfirmOpen,
  declaringCrop,
  onDeclareCrop,
}) {
  const declared = cropName(cropDetection?.declared_crop);
  const estimate = cropName(cropDetection?.detected_crop_type);
  const confidence = cropDetection?.confidence;

  return (
    <section className="land-detail__section land-crop-card card">
      <div className="land-crop-card__body">
        <div className="land-crop-card__icon" aria-hidden>🌾</div>
        <div className="land-crop-card__main">
          <div className="land-crop-card__label">{declared ? "Crop (confirmed by you)" : "Crop (estimate)"}</div>
          <div className="land-crop-card__name">{declared || estimate || "Not detected yet"}</div>
          <div className="land-crop-card__note">
            {declared
              ? estimate && estimate.toLowerCase() !== declared.toLowerCase()
                ? `The satellite estimate says ${estimate}.`
                : "Thank you, this helps check the crop model."
              : estimate
                ? `Temporary estimate from the NDVI curve${confidence != null ? `, ${Math.round(confidence * 100)}% fit` : ""}. The trained crop model will replace it.`
                : "No satellite observations yet."}
          </div>
        </div>
        <button type="button" className="btn btn--secondary btn--sm" onClick={() => setCropConfirmOpen(true)}>
          {declared ? "Change crop" : "Confirm your crop"}
        </button>
      </div>

      <CropConfirmModal
        open={cropConfirmOpen}
        onClose={() => setCropConfirmOpen(false)}
        onConfirm={onDeclareCrop}
        cropDetection={cropDetection}
        declaredCrop={cropDetection?.declared_crop}
        saving={declaringCrop}
      />
    </section>
  );
}
