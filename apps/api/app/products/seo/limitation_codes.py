"""The closed set of reasons a governed SEO decision can be refused.

`SEOEvidenceInvalidError` used to carry only a free-text `reason` sentence.
The frontend (`apps/web/src/lib/ui/search-intelligence.ts`) matched that
sentence by exact string equality to decide what to show the operator --
missing ten of the seventeen possible reasons (they rendered raw English) and
producing wrong guidance whenever a caught sentence happened to overlap
another meaning (e.g. "Check its mapping in Integrations" showing when
Integrations was never the problem).

`SEOLimitationCode` closes that set so the frontend can switch on a code
instead of parsing prose, matching the pattern established by
`administration.readiness_codes.ReadinessCode`. `LIMITATION_COPY` is the
exhaustive operator-facing sentence for each code; a code without an entry
is a type error, not a silent blank message.
"""

from __future__ import annotations

from enum import StrEnum


class SEOLimitationCode(StrEnum):
    """Every reason `resolve_decision` can refuse to certify an opportunity."""

    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    ORGANIZATION_SCOPE_INVALID = "ORGANIZATION_SCOPE_INVALID"
    SCORE_POLICY_STALE = "SCORE_POLICY_STALE"
    WEBSITE_MAPPING_UNAVAILABLE = "WEBSITE_MAPPING_UNAVAILABLE"
    PAGE_OUT_OF_SCOPE = "PAGE_OUT_OF_SCOPE"
    OBSERVATION_ID_MISSING = "OBSERVATION_ID_MISSING"
    OBSERVATION_ID_INVALID = "OBSERVATION_ID_INVALID"
    SOURCE_RECORD_UNSUPPORTED = "SOURCE_RECORD_UNSUPPORTED"
    SOURCE_RECORD_NOT_FOUND = "SOURCE_RECORD_NOT_FOUND"
    CRAWL_ISSUE_STALE = "CRAWL_ISSUE_STALE"
    SOURCE_QUALITY_INVALID = "SOURCE_QUALITY_INVALID"
    SEARCH_FACTS_CHANGED = "SEARCH_FACTS_CHANGED"
    CRAWL_FACTS_CHANGED = "CRAWL_FACTS_CHANGED"
    QUERY_DEMAND_CANNOT_TARGET_PAGE = "QUERY_DEMAND_CANNOT_TARGET_PAGE"
    BUSINESS_EVIDENCE_ID_INVALID = "BUSINESS_EVIDENCE_ID_INVALID"
    BUSINESS_EVIDENCE_OUT_OF_SCOPE = "BUSINESS_EVIDENCE_OUT_OF_SCOPE"
    BUSINESS_EVIDENCE_MISMATCH = "BUSINESS_EVIDENCE_MISMATCH"
    METRIC_VALUE_INVALID = "METRIC_VALUE_INVALID"
    EVIDENCE_SNAPSHOT_MISSING = "EVIDENCE_SNAPSHOT_MISSING"
    EVIDENCE_CHANGED_SINCE_APPROVAL = "EVIDENCE_CHANGED_SINCE_APPROVAL"
    APPROVED_TARGET_IDENTITY_UNAVAILABLE = "APPROVED_TARGET_IDENTITY_UNAVAILABLE"
    IMPLEMENTATION_TARGET_MISMATCH = "IMPLEMENTATION_TARGET_MISMATCH"
    IMPLEMENTATION_TASK_TARGET_CONFLICT = "IMPLEMENTATION_TASK_TARGET_CONFLICT"
    IMPLEMENTATION_WORKFLOW_SCOPE_INVALID = "IMPLEMENTATION_WORKFLOW_SCOPE_INVALID"
    OUTCOME_MUST_BE_MEASURED = "OUTCOME_MUST_BE_MEASURED"
    OPPORTUNITY_LOCATION_CHANGED = "OPPORTUNITY_LOCATION_CHANGED"
    OPPORTUNITY_NOT_OBSERVED_BY_RUN = "OPPORTUNITY_NOT_OBSERVED_BY_RUN"
    OPPORTUNITY_EVIDENCE_CHANGED_DURING_RUN = "OPPORTUNITY_EVIDENCE_CHANGED_DURING_RUN"


# Exhaustive over SEOLimitationCode -- tests assert this registry covers
# every member, so a new code cannot ship without operator-facing copy.
LIMITATION_COPY: dict[SEOLimitationCode, str] = {
    SEOLimitationCode.REFERENCE_MISMATCH: ("Recommendation must cite its exact SEO opportunity."),
    SEOLimitationCode.ORGANIZATION_SCOPE_INVALID: (
        "Opportunity is outside the active organization scope."
    ),
    SEOLimitationCode.SCORE_POLICY_STALE: (
        "Opportunity has no governed source or score policy version."
    ),
    SEOLimitationCode.WEBSITE_MAPPING_UNAVAILABLE: "Website or location mapping is unavailable.",
    SEOLimitationCode.PAGE_OUT_OF_SCOPE: "Page is outside the website scope.",
    SEOLimitationCode.OBSERVATION_ID_MISSING: ("Search Console observation ID is unavailable."),
    SEOLimitationCode.OBSERVATION_ID_INVALID: "Search Console observation ID is invalid.",
    SEOLimitationCode.SOURCE_RECORD_UNSUPPORTED: (
        "No persisted scoped source record supports this opportunity."
    ),
    SEOLimitationCode.SOURCE_RECORD_NOT_FOUND: (
        "The source observation does not resolve in this scope."
    ),
    SEOLimitationCode.CRAWL_ISSUE_STALE: "The latest crawl does not support this technical issue.",
    SEOLimitationCode.SOURCE_QUALITY_INVALID: (
        "The source observation is not valid for a material decision."
    ),
    SEOLimitationCode.SEARCH_FACTS_CHANGED: (
        "Opportunity facts differ from persisted Search Console evidence."
    ),
    SEOLimitationCode.CRAWL_FACTS_CHANGED: (
        "Opportunity facts differ from persisted crawl evidence."
    ),
    SEOLimitationCode.QUERY_DEMAND_CANNOT_TARGET_PAGE: (
        "Query-only demand cannot be assigned a landing page."
    ),
    SEOLimitationCode.BUSINESS_EVIDENCE_ID_INVALID: "Business importance evidence ID is invalid.",
    SEOLimitationCode.BUSINESS_EVIDENCE_OUT_OF_SCOPE: (
        "Business importance evidence is outside the page scope."
    ),
    SEOLimitationCode.BUSINESS_EVIDENCE_MISMATCH: (
        "Business importance claim does not match source evidence."
    ),
    SEOLimitationCode.METRIC_VALUE_INVALID: "Opportunity metric is invalid.",
    SEOLimitationCode.EVIDENCE_SNAPSHOT_MISSING: (
        "Recommendation has no governed evidence snapshot."
    ),
    SEOLimitationCode.EVIDENCE_CHANGED_SINCE_APPROVAL: (
        "Recommendation evidence has changed; create a new revision."
    ),
    SEOLimitationCode.APPROVED_TARGET_IDENTITY_UNAVAILABLE: (
        "Approved target identity is unavailable."
    ),
    SEOLimitationCode.IMPLEMENTATION_TARGET_MISMATCH: (
        "Implementation target differs from approved decision."
    ),
    SEOLimitationCode.IMPLEMENTATION_TASK_TARGET_CONFLICT: (
        "Existing implementation task has another target."
    ),
    SEOLimitationCode.IMPLEMENTATION_WORKFLOW_SCOPE_INVALID: (
        "Implementation workflow is outside the location scope."
    ),
    SEOLimitationCode.OUTCOME_MUST_BE_MEASURED: (
        "SEO outcomes are projected from verified Growth measurement, not caller assertions."
    ),
    SEOLimitationCode.OPPORTUNITY_LOCATION_CHANGED: (
        "Opportunity location changed during Hermes reasoning."
    ),
    SEOLimitationCode.OPPORTUNITY_NOT_OBSERVED_BY_RUN: (
        "Opportunity was not observed by this Hermes run."
    ),
    SEOLimitationCode.OPPORTUNITY_EVIDENCE_CHANGED_DURING_RUN: (
        "Opportunity evidence changed during Hermes reasoning; start a new run."
    ),
}
