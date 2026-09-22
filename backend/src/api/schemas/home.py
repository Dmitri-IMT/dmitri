from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.models.activity import ActivityKind
from api.schemas.read import FindingRead, ScanSummary


class HomeEventKind(str, Enum):
    box_offline = "box_offline"
    member_idle = "member_idle"
    machine_first_seen = "machine_first_seen"


class HomeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: HomeEventKind
    text: str
    occurred_at: datetime


class HomeActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ActivityKind
    occurred_at: datetime
    text: str


class HomeNoticeKind(str, Enum):
    failed_scan = "failed_scan"


class HomeNotice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: HomeNoticeKind
    text: str


class HomeListPage(BaseModel):
    """One page of a Home panel. Subclasses narrow `data` to their row type."""

    model_config = ConfigDict(extra="forbid")

    data: list
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]


class HomeAttentionPage(HomeListPage):
    data: list[FindingRead]


class HomeEventsPage(HomeListPage):
    data: list[HomeEvent]


class HomeActivityPage(HomeListPage):
    data: list[HomeActivityItem]


class HomeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_state: Literal["blank", "clear", "pending"]
    review_count: Annotated[int, Field(ge=0)]
    latest_successful_scan: ScanSummary | None
    notices: list[HomeNotice]
    attention: HomeAttentionPage
    events: HomeEventsPage
    activity: HomeActivityPage
