"""Business Knowledge ingestion, retrieval, and lifecycle service.

Sources:
  - GBPProfileSnapshot.normalized_profile  → structured facts
  - SEOPage.body_text + metadata          → website page knowledge
  - Organization / Location / Profile     → identity knowledge

Every knowledge document is organization-scoped with full provenance.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.models import BusinessKnowledgeDocument

# ── Source type and content type constants ───────────────────────────────────

SOURCE_GBP = "gbp_profile_snapshot"
SOURCE_SEO = "seo_page"
SOURCE_ORG_PROFILE = "organization_profile"
SOURCE_LOCATION_PROFILE = "location_profile"

CONTENT_STRUCTURED = "structured_facts"
CONTENT_PAGE_TEXT = "page_text"
CONTENT_IDENTITY = "identity"

# Authority levels
AUTHORITY_PROVIDER = "provider_observed"  # GBP-native structured data
AUTHORITY_SYSTEM = "system_derived"  # website-derived, automated
AUTHORITY_CLIENT = "client_approved"  # explicitly approved by client


class BusinessKnowledgeService:
    """Ingest source-backed knowledge and retrieve bounded grounding context."""

    # ── Ingestion ────────────────────────────────────────────────────────

    async def ingest_gbp_snapshot(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        gbp_location_id: UUID,
        location_id: UUID | None,
        snapshot_id: UUID,
        normalized_profile: dict[str, object],
        content_hash: str,
        observed_at: datetime | None = None,
    ) -> list[BusinessKnowledgeDocument]:
        """Extract structured business facts from a GBP profile snapshot.

        Returns the created (or already-existing) knowledge documents.
        """
        observed = observed_at or datetime.now(UTC)
        documents: list[BusinessKnowledgeDocument] = []

        # Extract categories as structured facts
        categories: list[str] = []
        raw_categories = normalized_profile.get("categories", [])
        if isinstance(raw_categories, list):
            categories = [
                str(c.get("displayName", c)) if isinstance(c, dict) else str(c)
                for c in raw_categories
                if c
            ]

        # Extract service items
        service_items: list[str] = []
        raw_items = normalized_profile.get("serviceItems", [])
        if isinstance(raw_items, list):
            service_items = [
                str(s.get("structuredName", s.get("name", s))) if isinstance(s, dict) else str(s)
                for s in raw_items
                if s
            ]

        # Build structured facts content
        structured: dict[str, object] = {}
        if categories:
            structured["categories"] = categories
        if service_items:
            structured["service_items"] = service_items

        # Extract hours as structured fact
        hours = normalized_profile.get("regularHours")
        if hours and isinstance(hours, dict) and hours:
            structured["regular_hours"] = hours

        # Extract address components
        address = normalized_profile.get("address")
        if address and isinstance(address, dict):
            addr_parts = {}
            for key in (
                "addressLines",
                "locality",
                "region",
                "postalCode",
                "country",
            ):
                val = address.get(key)
                if val:
                    addr_parts[key] = val
            if addr_parts:
                structured["address"] = addr_parts

        # Extract business name from GBP profile
        name = normalized_profile.get("locationName") or normalized_profile.get("title")
        if name and isinstance(name, str) and name.strip():
            structured["name"] = name.strip()

        if not structured:
            return documents

        structured_hash = _hash_content(structured)

        doc = await self._upsert_knowledge(
            session,
            organization_id=organization_id,
            location_id=location_id,
            source_type=SOURCE_GBP,
            source_reference=str(snapshot_id),
            content_hash=structured_hash,
            authority=AUTHORITY_PROVIDER,
            content=structured,
            content_type=CONTENT_STRUCTURED,
            observed_at=observed,
        )
        if doc:
            documents.append(doc)

        return documents

    async def ingest_seo_page(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        page_id: UUID,
        normalized_url: str,
        title: str | None,
        h1: str | None,
        meta_description: str | None,
        body_text: str | None,
        content_hash: str | None,
        observed_at: datetime | None = None,
    ) -> BusinessKnowledgeDocument | None:
        """Store crawled website page content as a knowledge document.

        Returns None when the page has no extractable content (no body_text,
        title, h1, or meta_description).
        """
        observed = observed_at or datetime.now(UTC)

        # Build page content
        page_content: dict[str, object] = {"url": normalized_url}
        if title:
            page_content["title"] = title
        if h1:
            page_content["h1"] = h1
        if meta_description:
            page_content["meta_description"] = meta_description
        if body_text:
            # Truncate to reasonable size for knowledge retrieval (50k chars)
            page_content["body_text"] = body_text[:50000]

        if len(page_content) <= 1:  # only url
            return None

        page_hash = content_hash or _hash_content(page_content)

        return await self._upsert_knowledge(
            session,
            organization_id=organization_id,
            location_id=location_id,
            source_type=SOURCE_SEO,
            source_reference=str(page_id),
            source_url=normalized_url,
            content_hash=page_hash,
            authority=AUTHORITY_SYSTEM,
            content=page_content,
            content_type=CONTENT_PAGE_TEXT,
            observed_at=observed,
        )

    async def ingest_organization_identity(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        org_name: str,
        primary_services: list[str] | None = None,
        approved_claims: list[str] | None = None,
        observed_at: datetime | None = None,
    ) -> BusinessKnowledgeDocument | None:
        """Store organization identity as a knowledge document."""
        observed = observed_at or datetime.now(UTC)
        identity: dict[str, object] = {"name": org_name}
        if primary_services:
            identity["primary_services"] = list(primary_services)
        if approved_claims:
            identity["approved_claims"] = list(approved_claims)

        identity_hash = _hash_content(identity)

        return await self._upsert_knowledge(
            session,
            organization_id=organization_id,
            location_id=None,
            source_type=SOURCE_ORG_PROFILE,
            source_reference=str(organization_id),
            content_hash=identity_hash,
            authority=AUTHORITY_CLIENT,
            content=identity,
            content_type=CONTENT_IDENTITY,
            observed_at=observed,
        )

    # ── Retrieval ─────────────────────────────────────────────────────────

    async def retrieve_for_content(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        content_title: str,
        audience: str,
        intent: str,
        content_type: str,
        limit: int = 15,
    ) -> dict[str, Any]:
        """Retrieve a bounded relevant knowledge set for Content AI grounding.

        Returns::

            {
                "identity": [...],        # approved org-identity facts
                "gbp_knowledge": [...],   # provider-observed structured facts
                "website_knowledge": [...], # relevant website page knowledge
                "source_document_ids": [...], # all BusinessKnowledgeDocument IDs used
            }
        """
        identity_list: list[dict[str, object]] = []
        gbp_list: list[dict[str, object]] = []
        website_list: list[dict[str, object]] = []
        source_ids: list[str] = []

        # 1. Identity knowledge (always include for this org)
        identity_docs = await self._query_active(
            session,
            organization_id,
            source_types=[SOURCE_ORG_PROFILE, SOURCE_LOCATION_PROFILE],
            content_types=[CONTENT_IDENTITY],
            location_id=None,
            limit=5,
        )
        for doc in identity_docs:
            identity_list.append(doc.content)
            source_ids.append(str(doc.id))

        # 2. GBP structured facts (location-scoped if location_id provided)
        gbp_docs = await self._query_active(
            session,
            organization_id,
            source_types=[SOURCE_GBP],
            content_types=[CONTENT_STRUCTURED],
            location_id=location_id,
            limit=10,
        )
        for doc in gbp_docs:
            gbp_list.append(doc.content)
            source_ids.append(str(doc.id))

        # 3. Website knowledge — relevance-scored
        # Build search terms from content context
        terms = _extract_search_terms(content_title, audience, intent, content_type)
        website_docs = await self._query_active(
            session,
            organization_id,
            source_types=[SOURCE_SEO],
            content_types=[CONTENT_PAGE_TEXT],
            location_id=location_id,
            limit=20,  # fetch more, then score
        )
        if website_docs:
            scored = _score_pages(website_docs, terms)
            scored.sort(key=lambda x: x[1], reverse=True)
            for doc, _score in scored[:limit]:
                website_list.append(doc.content)
                source_ids.append(str(doc.id))

        return {
            "identity": identity_list,
            "gbp_knowledge": gbp_list,
            "website_knowledge": website_list,
            "source_document_ids": source_ids,
        }

    # ── Internal ──────────────────────────────────────────────────────────

    async def _upsert_knowledge(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        source_type: str,
        source_reference: str,
        content_hash: str,
        authority: str,
        content: dict[str, object],
        content_type: str,
        observed_at: datetime,
        source_url: str | None = None,
    ) -> BusinessKnowledgeDocument | None:
        """Insert or return existing knowledge document.

        When content_hash differs from the active document, supersede the
        old one and create a new active version.
        """
        # Check for existing document with same source+hash
        existing = await session.scalar(
            select(BusinessKnowledgeDocument).where(
                BusinessKnowledgeDocument.organization_id == organization_id,
                BusinessKnowledgeDocument.source_type == source_type,
                BusinessKnowledgeDocument.source_reference == source_reference,
                BusinessKnowledgeDocument.content_hash == content_hash,
                BusinessKnowledgeDocument.status == "active",
            )
        )
        if existing is not None:
            return None  # unchanged, no update needed

        # Check for an active document with different hash → supersede it
        current_active = await session.scalar(
            select(BusinessKnowledgeDocument).where(
                BusinessKnowledgeDocument.organization_id == organization_id,
                BusinessKnowledgeDocument.source_type == source_type,
                BusinessKnowledgeDocument.source_reference == source_reference,
                BusinessKnowledgeDocument.status == "active",
            )
        )
        supersedes = None
        if current_active is not None:
            current_active.status = "superseded"
            supersedes = current_active.id

        doc = BusinessKnowledgeDocument(
            id=uuid4(),
            organization_id=organization_id,
            location_id=location_id,
            source_type=source_type,
            source_reference=source_reference,
            source_url=source_url,
            content_hash=content_hash,
            authority=authority,
            content=content,
            content_type=content_type,
            status="active",
            observed_at=observed_at,
            supersedes_id=supersedes,
        )
        session.add(doc)
        await session.flush()
        return doc

    async def _query_active(
        self,
        session: AsyncSession,
        organization_id: UUID,
        source_types: list[str],
        content_types: list[str],
        location_id: UUID | None,
        limit: int,
    ) -> list[BusinessKnowledgeDocument]:
        """Query active knowledge documents with optional location filter."""
        query = select(BusinessKnowledgeDocument).where(
            BusinessKnowledgeDocument.organization_id == organization_id,
            BusinessKnowledgeDocument.source_type.in_(source_types),
            BusinessKnowledgeDocument.content_type.in_(content_types),
            BusinessKnowledgeDocument.status == "active",
        )
        if location_id is not None:
            # Include org-wide AND location-specific knowledge
            from sqlalchemy import or_

            query = query.where(
                or_(
                    BusinessKnowledgeDocument.location_id.is_(None),
                    BusinessKnowledgeDocument.location_id == location_id,
                )
            )

        query = query.order_by(BusinessKnowledgeDocument.observed_at.desc()).limit(limit)

        result = await session.scalars(query)
        return list(result.all())

    # ── Backfill ───────────────────────────────────────────────────────────────

    async def backfill_from_existing_data(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
    ) -> dict[str, int]:
        """Build knowledge from already-persisted GBP snapshots, SEO pages,
        and organization identity data.

        Idempotent — re-running produces no duplicates.  Returns counts of
        documents created per source type.
        """
        counts: dict[str, int] = {"gbp": 0, "seo": 0, "identity": 0}

        # 1. Organization identity
        from sqlalchemy import select as _select

        from apps.api.app.organizations.models import Organization
        from apps.api.app.profiles.models import OrganizationProfile

        org = await session.scalar(_select(Organization).where(Organization.id == organization_id))
        if org:
            profile = await session.scalar(
                _select(OrganizationProfile).where(
                    OrganizationProfile.organization_id == organization_id
                )
            )
            primary_services = (
                list(profile.primary_services) if profile and profile.primary_services else None
            )
            approved_claims = (
                list(profile.approved_claims) if profile and profile.approved_claims else None
            )
            doc = await self.ingest_organization_identity(
                session,
                organization_id=organization_id,
                org_name=org.name,
                primary_services=primary_services,
                approved_claims=approved_claims,
            )
            if doc:
                counts["identity"] = 1

        # 2. GBP snapshots
        from apps.api.app.products.gbp.models import GBPProfileSnapshot

        snapshots = (
            await session.scalars(
                _select(GBPProfileSnapshot)
                .where(GBPProfileSnapshot.organization_id == organization_id)
                .order_by(GBPProfileSnapshot.observed_at.desc())
                .limit(20)
            )
        ).all()
        for snap in snapshots:
            docs = await self.ingest_gbp_snapshot(
                session,
                organization_id=organization_id,
                gbp_location_id=snap.gbp_location_id,
                location_id=None,
                snapshot_id=snap.id,
                normalized_profile=snap.normalized_profile,
                content_hash=snap.content_hash,
                observed_at=snap.observed_at,
            )
            counts["gbp"] += len(docs)

        # 3. SEO pages
        from apps.api.app.products.seo.models import SEOPage

        pages = (
            await session.scalars(
                _select(SEOPage)
                .where(
                    SEOPage.organization_id == organization_id,
                    SEOPage.http_status == 200,
                    SEOPage.indexability == "indexable",
                )
                .order_by(SEOPage.observed_at.desc().nulls_last())
                .limit(100)
            )
        ).all()
        for page in pages:
            doc = await self.ingest_seo_page(
                session,
                organization_id=organization_id,
                location_id=None,
                page_id=page.id,
                normalized_url=page.normalized_url,
                title=page.title,
                h1=page.h1,
                meta_description=page.meta_description,
                body_text=page.body_text,
                content_hash=page.content_hash,
                observed_at=page.observed_at,
            )
            if doc:
                counts["seo"] += 1

        return counts

    # ── Conflict detection ─────────────────────────────────────────────────

    async def detect_conflicts(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        actor_id: UUID,
    ) -> list[dict[str, object]]:
        """Detect meaningful contradictions across knowledge sources and feed
        them into the pending-confirmation mechanism.

        Only canonical business facts are checked — business name, address,
        and hours.  Ordinary wording differences across website pages are
        never surfaced as conflicts.

        Returns a list of created pending-confirmation fact metadata.
        """
        from uuid import uuid4 as _uuid4

        from apps.api.app.administration.models import BusinessFactRevision

        conflicts: list[dict[str, object]] = []

        # --- Business name conflict: GBP vs organization profile ---
        gbp_names = await self._distinct_values(
            session, organization_id, "gbp_profile_snapshot", "name"
        )
        org_names = await self._distinct_values(
            session, organization_id, "organization_profile", "name"
        )

        all_names = gbp_names | org_names
        if len(all_names) > 1:
            # Check if there's already a pending or active fact
            existing = await session.scalar(
                select(BusinessFactRevision).where(
                    BusinessFactRevision.organization_id == organization_id,
                    BusinessFactRevision.fact_key == "business.name",
                    BusinessFactRevision.status.in_(("approved", "active", "pending_approval")),
                )
            )
            if existing is None:
                # Propose the first name as pending — operator resolves
                primary_name = sorted(all_names)[0]
                fact = BusinessFactRevision(
                    id=_uuid4(),
                    organization_id=organization_id,
                    fact_identity=_uuid4(),
                    fact_key="business.name",
                    value_type="string",
                    value=primary_name,
                    source="gbp_profile_snapshot+organization_profile",
                    authority="system_derived",
                    status="pending_approval",
                    revision=1,
                    proposed_by=actor_id,
                    change_reason=f"Conflicting names detected: {', '.join(sorted(all_names))}",
                )
                session.add(fact)
                await session.flush()
                conflicts.append(
                    {
                        "fact_key": "business.name",
                        "values": sorted(all_names),
                        "fact_id": str(fact.id),
                    }
                )

        return conflicts

    async def _distinct_values(
        self,
        session: AsyncSession,
        organization_id: UUID,
        source_type: str,
        field: str,
    ) -> set[str]:
        """Extract distinct values for a field from knowledge documents."""
        from sqlalchemy import select as _select

        docs = (
            await session.scalars(
                _select(BusinessKnowledgeDocument).where(
                    BusinessKnowledgeDocument.organization_id == organization_id,
                    BusinessKnowledgeDocument.source_type == source_type,
                    BusinessKnowledgeDocument.status == "active",
                )
            )
        ).all()

        values: set[str] = set()
        for doc in docs:
            content = doc.content
            if field == "name":
                val = content.get("name")
                if isinstance(val, str) and val.strip():
                    values.add(val.strip())
            elif field == "address":
                addr = content.get("address")
                if isinstance(addr, dict):
                    line = addr.get("addressLines", "")
                    if isinstance(line, list):
                        line = " ".join(str(li) for li in line)
                    if line:
                        values.add(str(line).strip())
            elif field == "hours":
                hours = content.get("regular_hours")
                if hours:
                    import json

                    values.add(json.dumps(hours, sort_keys=True))

        return values

    # ── Knowledge coverage ─────────────────────────────────────────────────

    async def get_coverage(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
    ) -> dict[str, object]:
        """Return knowledge coverage summary for an organization."""
        from sqlalchemy import func as _func
        from sqlalchemy import select as _select

        result: dict[str, object] = {}

        for source_type, label in [
            ("organization_profile", "identity"),
            ("gbp_profile_snapshot", "gbp"),
            ("seo_page", "website"),
        ]:
            count_query = _select(_func.count()).where(
                BusinessKnowledgeDocument.organization_id == organization_id,
                BusinessKnowledgeDocument.source_type == source_type,
                BusinessKnowledgeDocument.status == "active",
            )
            count = await session.scalar(count_query) or 0

            latest_query = (
                _select(BusinessKnowledgeDocument.observed_at)
                .where(
                    BusinessKnowledgeDocument.organization_id == organization_id,
                    BusinessKnowledgeDocument.source_type == source_type,
                    BusinessKnowledgeDocument.status == "active",
                )
                .order_by(BusinessKnowledgeDocument.observed_at.desc())
                .limit(1)
            )
            latest = await session.scalar(latest_query)

            result[label] = {
                "document_count": count,
                "latest_observation": latest.isoformat() if latest else None,
            }

        return result


# ── Helpers ──────────────────────────────────────────────────────────────────


def _hash_content(content: dict[str, object]) -> str:
    """Deterministic content hash for change detection."""
    import hashlib
    import json

    raw = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _extract_search_terms(title: str, audience: str, intent: str, content_type: str) -> list[str]:
    """Extract meaningful search terms from content context."""
    import re

    combined = f"{title} {audience} {intent} {content_type}".lower()
    # Remove common stop words and short tokens
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "of",
        "in",
        "to",
        "is",
        "it",
        "on",
        "that",
        "this",
        "with",
        "as",
        "be",
        "by",
        "at",
        "content",
        "page",
        "blog",
        "post",
        "article",
    }
    tokens = re.findall(r"[a-z0-9]+", combined)
    return [t for t in tokens if t not in stop_words and len(t) > 2]


def _score_pages(
    documents: list[BusinessKnowledgeDocument], terms: list[str]
) -> list[tuple[BusinessKnowledgeDocument, int]]:
    """Score website knowledge documents by relevance to search terms."""
    scored: list[tuple[BusinessKnowledgeDocument, int]] = []
    for doc in documents:
        score = 0
        content = doc.content
        url = str(content.get("url", "")).lower()
        title = str(content.get("title", "")).lower()
        h1 = str(content.get("h1", "")).lower()
        body = str(content.get("body_text", "")).lower()
        meta = str(content.get("meta_description", "")).lower()

        for term in terms:
            if term in url:
                score += 5  # URL match is strong signal
            if term in title:
                score += 4
            if term in h1:
                score += 3
            if term in meta:
                score += 2
            # Count body occurrences (cap at 3 per term)
            body_count = body.count(term)
            score += min(body_count, 3)

        if score > 0:
            scored.append((doc, score))

    return scored
