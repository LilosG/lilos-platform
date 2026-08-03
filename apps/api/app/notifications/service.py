"""Notification intent creation; providers execute only through durable jobs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.notifications.models import NotificationDelivery, NotificationEvent


class NotificationService:
    async def create_event(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        template_id: UUID,
        event_type: str,
        idempotency_key: str,
        context: dict[str, object],
        priority: str = "normal",
    ) -> NotificationEvent:
        existing = await session.scalar(
            select(NotificationEvent).where(
                NotificationEvent.organization_id == organization_id,
                NotificationEvent.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        event = NotificationEvent(
            organization_id=organization_id,
            template_id=template_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            context=context,
            priority=priority,
        )
        session.add(event)
        await session.flush()
        return event

    async def add_delivery(
        self,
        session: AsyncSession,
        event: NotificationEvent,
        recipient_reference: str,
        channel: str,
        *,
        suppressed: bool = False,
    ) -> NotificationDelivery:
        item = NotificationDelivery(
            organization_id=event.organization_id,
            event_id=event.id,
            recipient_reference=recipient_reference,
            channel=channel,
            status="suppressed" if suppressed and event.priority != "critical" else "pending",
            suppression_reason="preference"
            if suppressed and event.priority != "critical"
            else None,
        )
        session.add(item)
        await session.flush()
        return item
