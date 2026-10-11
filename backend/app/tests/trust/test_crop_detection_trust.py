"""Crop detection trust integration tests."""

from datetime import datetime, timezone
from decimal import Decimal

from app.crops import service as crop_service
from app.crops import user_crops as user_crop_service
from app.models.crop_zone import CropZone
from app.models.land import Land
from app.models.land_crop import LandCrop
from app.trust.types import DetectionMethod, TrustTier


def _seed_land_with_zone(db_session):
    land = Land(
        name="Trust Test Farm",
        latitude=Decimal("30.05"),
        longitude=Decimal("31.05"),
        area_hectares=Decimal("5"),
        status="active",
    )
    db_session.add(land)
    db_session.flush()

    zone = CropZone(
        land_id=land.land_id,
        crop_type="winter onion",
        area_pct=Decimal("80"),
        status="active",
        avg_confidence=Decimal("0.42"),
        latest_ndvi=Decimal("0.45"),
        detection_method=DetectionMethod.NDVI_PROFILE_MATCH.value,
        trust_tier=TrustTier.ESTIMATED.value,
        separation_score=Decimal("0.013"),
        ambiguous=True,
        suppressed=False,
    )
    db_session.add(zone)
    db_session.flush()

    db_session.add(
        LandCrop(
            land_id=land.land_id,
            zone_id=zone.zone_id,
            crop_type="winter onion",
            ndvi_value=Decimal("0.45"),
            confidence=Decimal("0.42"),
            timestamp=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    return land.land_id


class TestCropDetectionTrust:
    def test_returns_ndvi_profile_match_not_spectral_signature(self, db_session):
        land_id = _seed_land_with_zone(db_session)
        result = crop_service.get_crop_detection(db_session, land_id)
        assert result.detection_method == DetectionMethod.NDVI_PROFILE_MATCH.value
        assert result.trust_tier == TrustTier.ESTIMATED.value
        assert result.requires_confirmation is True
        assert result.confidence_band in ("low", "medium", "high")
        assert "confirm" in result.note.lower() or "uncertain" in result.note.lower()

    def test_ambiguous_zone_yields_low_band(self, db_session):
        land_id = _seed_land_with_zone(db_session)
        result = crop_service.get_crop_detection(db_session, land_id)
        assert result.confidence_band == "low"
        assert result.display_label == "Uncertain"

    def test_user_confirmed_overrides_tier(self, db_session):
        land_id = _seed_land_with_zone(db_session)
        user_crop_service.upsert_primary_declaration(
            db_session, land_id, "vegetables (mixed)", user_id=1
        )
        db_session.commit()
        result = crop_service.get_crop_detection(db_session, land_id)
        assert result.detection_method == DetectionMethod.USER_CONFIRMED.value
        assert result.trust_tier == TrustTier.VERIFIED.value
        assert result.declared_crop == "vegetables (mixed)"