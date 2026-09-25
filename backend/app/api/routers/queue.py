from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_queue_service
from app.api.schemas.appointments import DailyQueueOut
from app.domain.models import User
from app.services.queue_service import QueueService

router = APIRouter(tags=["Queue"])


@router.get("/queue", response_model=DailyQueueOut)
def daily_queue(
    day: date | None = Query(None, alias="date"),
    actor: User = Depends(current_user),
    service: QueueService = Depends(get_queue_service),
) -> DailyQueueOut:
    return DailyQueueOut.from_domain(service.get(actor, day))
