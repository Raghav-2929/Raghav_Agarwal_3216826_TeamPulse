"""Habit domain: private goals stay private; team-visible goals are shared with teammates only."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from habit_service.models import Habit
from habit_service.schemas import HabitCreate, HabitOut, HabitUpdate, Visibility, check_target
from teampulse_common.errors import NotFoundError, UnprocessableError
from teampulse_common.events import EventEnvelope
from teampulse_common.events.contracts import Category, Frequency, UserUpdated
from teampulse_common.pagination import Page, PageParams
from teampulse_common.security import Principal


class HabitService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _page(self, stmt, page: PageParams) -> Page[HabitOut]:  # type: ignore[no-untyped-def]
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            await self.session.scalars(
                stmt.order_by(Habit.is_archived, Habit.created_at.desc()).offset(page.offset).limit(page.size)
            )
        ).all()
        return Page(
            items=[HabitOut.model_validate(h) for h in rows], total=total, page=page.page, size=page.size
        )

    async def list_mine(
        self,
        principal: Principal,
        *,
        category: Category | None,
        visibility: Visibility | None,
        include_archived: bool,
        search: str | None,
        page: PageParams,
    ) -> Page[HabitOut]:
        stmt = select(Habit).where(Habit.owner_id == principal.user_id)
        if not include_archived:
            stmt = stmt.where(Habit.is_archived.is_(False))
        if category:
            stmt = stmt.where(Habit.category == category.value)
        if visibility:
            stmt = stmt.where(Habit.visibility == visibility.value)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(func.lower(Habit.title).like(like), func.lower(Habit.description).like(like))
            )
        return await self._page(stmt, page)

    async def list_team(
        self, principal: Principal, *, category: Category | None, search: str | None, page: PageParams
    ) -> Page[HabitOut]:
        if principal.team_id is None:
            return Page(items=[], total=0, page=page.page, size=page.size)
        stmt = select(Habit).where(
            Habit.team_id == principal.team_id,
            Habit.visibility == Visibility.TEAM.value,
            Habit.owner_id != principal.user_id,
            Habit.is_archived.is_(False),
        )
        if category:
            stmt = stmt.where(Habit.category == category.value)
        if search:
            stmt = stmt.where(func.lower(Habit.title).like(f"%{search.lower()}%"))
        return await self._page(stmt, page)

    async def get_visible(self, principal: Principal, habit_id: uuid.UUID) -> Habit:
        habit = await self.session.get(Habit, habit_id)
        visible = habit is not None and (
            habit.owner_id == principal.user_id
            or (
                habit.visibility == Visibility.TEAM.value
                and habit.team_id is not None
                and habit.team_id == principal.team_id
                and not habit.is_archived
            )
        )
        if not visible:
            # 404 rather than 403: never confirm that someone else's private habit exists.
            raise NotFoundError("Habit not found")
        return habit  # type: ignore[return-value]

    async def _get_owned(self, principal: Principal, habit_id: uuid.UUID) -> Habit:
        habit = await self.session.get(Habit, habit_id)
        if habit is None or habit.owner_id != principal.user_id:
            raise NotFoundError("Habit not found")
        return habit

    async def create(self, principal: Principal, data: HabitCreate) -> HabitOut:
        habit = Habit(
            owner_id=principal.user_id,
            owner_name=principal.name,
            team_id=principal.team_id,
            **data.model_dump(mode="json"),
        )
        self.session.add(habit)
        await self.session.commit()
        return HabitOut.model_validate(habit)

    async def update(self, principal: Principal, habit_id: uuid.UUID, data: HabitUpdate) -> HabitOut:
        habit = await self._get_owned(principal, habit_id)
        changes = data.model_dump(exclude_unset=True, mode="json")
        frequency = Frequency(changes.get("frequency", habit.frequency))
        target = changes.get(
            "target_per_period",
            1 if "frequency" in changes and frequency is Frequency.DAILY else habit.target_per_period,
        )
        try:
            check_target(frequency, target)
        except ValueError as exc:
            raise UnprocessableError(str(exc), code="invalid_target") from exc
        changes["target_per_period"] = target
        for field, value in changes.items():
            setattr(habit, field, value)
        habit.owner_name = principal.name
        await self.session.commit()
        return HabitOut.model_validate(habit)

    async def archive(self, principal: Principal, habit_id: uuid.UUID) -> None:
        habit = await self._get_owned(principal, habit_id)
        habit.is_archived = True
        await self.session.commit()


async def on_user_updated(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    """Keep the denormalised owner name / team in sync (eventual consistency via the event bus)."""
    assert session is not None
    data = UserUpdated.model_validate(envelope.data)
    await session.execute(
        update(Habit)
        .where(Habit.owner_id == data.user_id)
        .values(owner_name=data.display_name, team_id=data.team_id)
    )
