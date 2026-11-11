"""Explicit jurisdiction and venue eligibility gate.

A working REST endpoint is not evidence of lawful access. The operator must
record dated review results before a venue can be used for execution.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class VenueAssessment:
    venue_id: str
    jurisdiction: str
    local_legal_reviewed: bool
    spot_access_verified: bool
    perpetual_access_verified: bool = False
    perpetuals_permitted: bool = False
    fiu_registration_applicable: bool = False
    fiu_registration_verified: bool = False
    checked_on: date = None

    def eligibility(self, asset_class, today=None, max_age_days=90):
        today = today or datetime.now(timezone.utc).date()
        reasons = []
        if not self.local_legal_reviewed:
            reasons.append("local legal/access review is not recorded")
        if self.checked_on is None:
            reasons.append("venue review date is missing")
        elif (today - self.checked_on).days < 0 or (today - self.checked_on).days > max_age_days:
            reasons.append("venue review is stale; re-verify current terms and restrictions")
        if asset_class == "crypto_spot":
            if not self.spot_access_verified:
                reasons.append("spot access has not been verified for this jurisdiction")
        elif asset_class == "crypto_perpetual":
            if not self.perpetual_access_verified:
                reasons.append("perpetual access has not been verified for this jurisdiction")
            if not self.perpetuals_permitted:
                reasons.append("perpetual derivatives are not explicitly approved by the venue review")
        else:
            reasons.append("unsupported crypto asset class")
        if self.fiu_registration_applicable and not self.fiu_registration_verified:
            reasons.append("FIU-IND registration applicability was marked true but registration is unverified")
        return not reasons, tuple(reasons)
