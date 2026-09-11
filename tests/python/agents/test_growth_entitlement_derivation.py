from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.api.app.routes import agents as agents_routes


class FakeCatalog:
    def __init__(self, products: dict[str, object]) -> None:
        self.products = products

    async def get_product_by_key(self, session: object, product_key: str) -> object | None:
        del session
        return self.products.get(product_key)


class FakeEntitlements:
    def __init__(
        self,
        entitlements: dict[object, object],
        locations: dict[object, list[object]],
    ) -> None:
        self.entitlements = entitlements
        self.location_rows = locations

    async def get_by_product(
        self, session: object, organization_id: object, product_id: object
    ) -> object | None:
        del session, organization_id
        return self.entitlements.get(product_id)

    async def locations(
        self, session: object, organization_id: object, entitlement_id: object
    ) -> list[object]:
        del session, organization_id
        return self.location_rows.get(entitlement_id, [])


def product() -> object:
    return SimpleNamespace(id=uuid4())


def entitlement(status: str = "active") -> object:
    return SimpleNamespace(id=uuid4(), status=status)


@pytest.mark.asyncio
async def test_growth_allows_explicit_effective_entitlement(monkeypatch: pytest.MonkeyPatch) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    growth = product()
    growth_entitlement = entitlement()
    fake = SimpleNamespace(
        catalog=FakeCatalog({"growth": growth}),
        entitlements=FakeEntitlements({growth.id: growth_entitlement}, {}),
    )
    monkeypatch.setattr(agents_routes, "administration", fake)

    await agents_routes.require_product_entitlement(
        object(), organization_id, location_id, "growth"
    )


@pytest.mark.asyncio
async def test_growth_derives_access_from_effective_source_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    growth = product()
    seo = product()
    seo_entitlement = entitlement()
    fake = SimpleNamespace(
        catalog=FakeCatalog({"growth": growth, "seo": seo}),
        entitlements=FakeEntitlements({seo.id: seo_entitlement}, {}),
    )
    monkeypatch.setattr(agents_routes, "administration", fake)

    await agents_routes.require_product_entitlement(
        object(), organization_id, location_id, "growth"
    )


@pytest.mark.asyncio
async def test_growth_derivation_respects_location_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    other_location_id = uuid4()
    growth = product()
    seo = product()
    seo_entitlement = entitlement()
    fake = SimpleNamespace(
        catalog=FakeCatalog({"growth": growth, "seo": seo}),
        entitlements=FakeEntitlements(
            {seo.id: seo_entitlement},
            {seo_entitlement.id: [SimpleNamespace(location_id=other_location_id)]},
        ),
    )
    monkeypatch.setattr(agents_routes, "administration", fake)

    with pytest.raises(HTTPException) as exc:
        await agents_routes.require_product_entitlement(
            object(), organization_id, location_id, "growth"
        )

    assert exc.value.status_code == 409
    assert "effective SEO, Content, GBP, or Reviews entitlement" in exc.value.detail


@pytest.mark.asyncio
async def test_growth_rejects_when_no_effective_source_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    growth = product()
    seo = product()
    seo_entitlement = entitlement("suspended")
    fake = SimpleNamespace(
        catalog=FakeCatalog({"growth": growth, "seo": seo}),
        entitlements=FakeEntitlements({seo.id: seo_entitlement}, {}),
    )
    monkeypatch.setattr(agents_routes, "administration", fake)

    with pytest.raises(HTTPException) as exc:
        await agents_routes.require_product_entitlement(
            object(), organization_id, location_id, "growth"
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_non_growth_agent_still_requires_its_own_entitlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    seo = product()
    fake = SimpleNamespace(
        catalog=FakeCatalog({"seo": seo}),
        entitlements=FakeEntitlements({}, {}),
    )
    monkeypatch.setattr(agents_routes, "administration", fake)

    with pytest.raises(HTTPException) as exc:
        await agents_routes.require_product_entitlement(
            object(), organization_id, location_id, "seo"
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Product entitlement is not effective"
