"""Challenge domain: team competitions, privacy-aware leaderboards and badge-rule ownership."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import and_, delete, exists, func, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from challenge_service.models import BadgeRuleRow, Challenge, Participant
from challenge_service.schemas import (
    MAX_DURATION_DAYS,
    BadgeRuleIn,
    ChallengeCreate,
    ChallengeOut,
    ChallengeStatus,
    ChallengeUpdate,
    LeaderboardEntry,
    LeaderboardOut,
    TeamStanding,
    status_for,
)
from teampulse_common.db import utcnow
from teampulse_common.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from teampulse_common.events import EventEnvelope, EventType, enqueue
from teampulse_common.events.contracts import (
    DEFAULT_BADGE_RULES,
    BadgeRule,
    BadgeRulesChanged,
    Category,
    ChallengeCreated,
    ChallengeGoalReached,
    ChallengeJoined,
    ProgressUpdated,
)
from teampulse_common.pagination import Page, PageParams
from teampulse_common.security import Principal

SOURCE = "challenge-service"
ANONYMOUS = "Anonymous participant"
ADMIN_BACKDATE_DAYS = 14


def visible_to(principal: Principal):  # type: ignore[no-untyped-def]
    """Org-wide challenges, the caller's team, and (for managers/admins) teams they oversee."""
    if principal.is_admin:
        return true()
    clauses = [Challenge.team_id.is_(None)]
    if principal.team_id:
        clauses.append(Challenge.team_id == principal.team_id)
    if principal.managed_team_ids:
        clauses.append(Challenge.team_id.in_(principal.managed_team_ids))
    return or_(*clauses)


class ChallengeService:
    def __init__(
        self,
        session: AsyncSession,
        on_commit: Callable[[], None] = lambda: None,
        today: Callable[[], date] | None = None,
    ) -> None:
        self.session = session
        self._on_commit = on_commit
        self._today = today or (lambda: utcnow().date())

    async def _commit(self) -> None:
        await self.session.commit()
        self._on_commit()

    # ------------------------------------------------------------------ read models
    async def _to_out(self, challenges: list[Challenge], principal: Principal) -> list[ChallengeOut]:
        if not challenges:
            return []
        ids = [c.id for c in challenges]
        counts = dict(
            (
                await self.session.execute(
                    select(Participant.challenge_id, func.count())
                    .where(Participant.challenge_id.in_(ids))
                    .group_by(Participant.challenge_id)
                )
            ).all()
        )
        mine = {
            p.challenge_id: p
            for p in (
                await self.session.scalars(
                    select(Participant).where(
                        Participant.challenge_id.in_(ids), Participant.user_id == principal.user_id
                    )
                )
            ).all()
        }
        today = self._today()
        out = []
        for c in challenges:
            me = mine.get(c.id)
            out.append(
                ChallengeOut(
                    id=c.id,
                    title=c.title,
                    description=c.description,
                    category=Category(c.category) if c.category else None,
                    team_id=c.team_id,
                    team_name=c.team_name,
                    starts_on=c.starts_on,
                    ends_on=c.ends_on,
                    target_count=c.target_count,
                    status=status_for(c.starts_on, c.ends_on, today),
                    created_by=c.created_by,
                    created_at=c.created_at,
                    participant_count=counts.get(c.id, 0),
                    joined=me is not None,
                    my_score=me.score if me else None,
                    my_goal_reached=bool(me and me.goal_reached_at),
                    show_on_leaderboard=me.show_on_leaderboard if me else None,
                )
            )
        return out

    async def _get_visible(self, principal: Principal, challenge_id: uuid.UUID) -> Challenge:
        challenge = await self.session.scalar(
            select(Challenge).where(Challenge.id == challenge_id, visible_to(principal))
        )
        if challenge is None:
            raise NotFoundError("Challenge not found")
        return challenge

    async def list(
        self,
        principal: Principal,
        *,
        status: ChallengeStatus | None,
        category: Category | None,
        search: str | None,
        joined: bool | None,
        date_from: date | None,
        date_to: date | None,
        page: PageParams,
    ) -> Page[ChallengeOut]:
        today = self._today()
        stmt = select(Challenge).where(visible_to(principal))
        if status is ChallengeStatus.UPCOMING:
            stmt = stmt.where(Challenge.starts_on > today)
        elif status is ChallengeStatus.ACTIVE:
            stmt = stmt.where(Challenge.starts_on <= today, Challenge.ends_on >= today)
        elif status is ChallengeStatus.COMPLETED:
            stmt = stmt.where(Challenge.ends_on < today)
        if category:
            stmt = stmt.where(Challenge.category == category.value)
        if search:
            stmt = stmt.where(func.lower(Challenge.title).like(f"%{search.lower()}%"))
        if date_from:
            stmt = stmt.where(Challenge.ends_on >= date_from)
        if date_to:
            stmt = stmt.where(Challenge.starts_on <= date_to)
        if joined is not None:
            membership = exists().where(
                and_(Participant.challenge_id == Challenge.id, Participant.user_id == principal.user_id)
            )
            stmt = stmt.where(membership if joined else ~membership)
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            (
                await self.session.scalars(
                    stmt.order_by(Challenge.starts_on.desc(), Challenge.created_at.desc())
                    .offset(page.offset)
                    .limit(page.size)
                )
            ).all()
        )
        return Page(items=await self._to_out(rows, principal), total=total, page=page.page, size=page.size)

    async def get(self, principal: Principal, challenge_id: uuid.UUID) -> ChallengeOut:
        return (await self._to_out([await self._get_visible(principal, challenge_id)], principal))[0]

    # ------------------------------------------------------------------ commands
    async def create(self, principal: Principal, data: ChallengeCreate) -> ChallengeOut:
        if principal.is_manager and data.team_id is not None and not principal.manages(data.team_id):
            raise ForbiddenError(
                "Managers can only create challenges for teams they manage", code="not_your_team"
            )
        # Admins may backdate (≤ 14 days) to align with a campaign that is already running.
        earliest = self._today() - timedelta(days=ADMIN_BACKDATE_DAYS if principal.is_admin else 0)
        if data.starts_on < earliest:
            raise UnprocessableError("starts_on is too far in the past", code="invalid_dates")
        team_name = principal.team_name if data.team_id and data.team_id == principal.team_id else None
        challenge = Challenge(
            title=data.title,
            description=data.description,
            category=data.category.value if data.category else None,
            team_id=data.team_id,
            team_name=team_name,
            starts_on=data.starts_on,
            ends_on=data.ends_on,
            target_count=data.target_count,
            created_by=principal.user_id,
        )
        self.session.add(challenge)
        await self.session.flush()
        enqueue(
            self.session,
            EventEnvelope.create(
                EventType.CHALLENGE_CREATED,
                SOURCE,
                ChallengeCreated(
                    challenge_id=challenge.id,
                    title=challenge.title,
                    team_id=challenge.team_id,
                    starts_on=challenge.starts_on,
                    ends_on=challenge.ends_on,
                    created_by=principal.user_id,
                ),
            ),
        )
        await self._commit()
        return (await self._to_out([challenge], principal))[0]

    def _ensure_can_manage(self, principal: Principal, challenge: Challenge) -> None:
        if not (principal.is_admin or challenge.created_by == principal.user_id):
            raise ForbiddenError("Only the creator or an administrator can change this challenge")

    async def update(
        self, principal: Principal, challenge_id: uuid.UUID, data: ChallengeUpdate
    ) -> ChallengeOut:
        challenge = await self._get_visible(principal, challenge_id)
        self._ensure_can_manage(principal, challenge)
        if status_for(challenge.starts_on, challenge.ends_on, self._today()) is ChallengeStatus.COMPLETED:
            raise UnprocessableError("Completed challenges are read-only", code="challenge_completed")
        changes = data.model_dump(exclude_unset=True)
        if "ends_on" in changes:
            if changes["ends_on"] < max(challenge.starts_on, self._today()):
                raise UnprocessableError(
                    "ends_on must be today or later and not before starts_on", code="invalid_dates"
                )
            # Same limit as on create: an edit must not stretch a challenge past the maximum length.
            if changes["ends_on"] - challenge.starts_on > timedelta(days=MAX_DURATION_DAYS):
                raise UnprocessableError(
                    f"challenges can last at most {MAX_DURATION_DAYS} days", code="invalid_dates"
                )
        for field, value in changes.items():
            setattr(challenge, field, value)
        await self._commit()
        return await self.get(principal, challenge_id)

    async def delete(self, principal: Principal, challenge_id: uuid.UUID) -> None:
        challenge = await self._get_visible(principal, challenge_id)
        self._ensure_can_manage(principal, challenge)
        upcoming = (
            status_for(challenge.starts_on, challenge.ends_on, self._today()) is ChallengeStatus.UPCOMING
        )
        if not (upcoming or principal.is_admin):
            raise UnprocessableError(
                "Only upcoming challenges can be deleted by their creator", code="challenge_started"
            )
        await self.session.delete(challenge)
        await self._commit()

    async def join(
        self, principal: Principal, challenge_id: uuid.UUID, show_on_leaderboard: bool
    ) -> ChallengeOut:
        challenge = await self._get_visible(principal, challenge_id)
        if challenge.team_id is not None and challenge.team_id != principal.team_id:
            raise ForbiddenError("This challenge is limited to another team", code="not_your_team")
        if status_for(challenge.starts_on, challenge.ends_on, self._today()) is ChallengeStatus.COMPLETED:
            raise UnprocessableError("This challenge has already finished", code="challenge_completed")
        self.session.add(
            Participant(
                challenge_id=challenge.id,
                user_id=principal.user_id,
                team_id=principal.team_id,
                team_name=principal.team_name,
                display_name=principal.name,
                show_on_leaderboard=show_on_leaderboard,
            )
        )
        enqueue(
            self.session,
            EventEnvelope.create(
                EventType.CHALLENGE_JOINED,
                SOURCE,
                ChallengeJoined(challenge_id=challenge.id, title=challenge.title, user_id=principal.user_id),
                subject=f"user:{principal.user_id}",
            ),
        )
        try:
            await self._commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("You have already joined this challenge", code="already_joined") from exc
        return await self.get(principal, challenge_id)

    async def _my_participation(self, principal: Principal, challenge_id: uuid.UUID) -> Participant:
        await self._get_visible(principal, challenge_id)
        participant = await self.session.scalar(
            select(Participant).where(
                Participant.challenge_id == challenge_id, Participant.user_id == principal.user_id
            )
        )
        if participant is None:
            raise NotFoundError("You have not joined this challenge", code="not_joined")
        return participant

    async def set_visibility(self, principal: Principal, challenge_id: uuid.UUID, show: bool) -> ChallengeOut:
        participant = await self._my_participation(principal, challenge_id)
        participant.show_on_leaderboard = show
        await self._commit()
        return await self.get(principal, challenge_id)

    async def leave(self, principal: Principal, challenge_id: uuid.UUID) -> None:
        participant = await self._my_participation(principal, challenge_id)
        await self.session.delete(participant)
        await self._commit()

    # ------------------------------------------------------------------ leaderboard
    async def leaderboard(self, principal: Principal, challenge_id: uuid.UUID, limit: int) -> LeaderboardOut:
        challenge = await self._get_visible(principal, challenge_id)
        participants = list(
            (
                await self.session.scalars(
                    select(Participant).where(Participant.challenge_id == challenge.id)
                )
            ).all()
        )
        # Ties: whoever reached the goal first, then whoever joined first. People who have not reached
        # the goal sort after those who have (no "far future" date needed, so 29 February is safe).
        participants.sort(
            key=lambda p: (
                -p.score,
                p.goal_reached_at is None,
                p.goal_reached_at or p.joined_at,
                p.joined_at,
            )
        )

        individuals: list[LeaderboardEntry] = []
        my_rank: int | None = None
        rank = 0
        previous_score: int | None = None
        for position, p in enumerate(participants, start=1):
            if p.score != previous_score:  # standard competition ranking (1, 2, 2, 4)
                rank, previous_score = position, p.score
            is_me = p.user_id == principal.user_id
            if is_me:
                my_rank = rank
            if position <= limit or is_me:
                visible = p.show_on_leaderboard
                individuals.append(
                    LeaderboardEntry(
                        rank=rank,
                        display_name=p.display_name if visible else ANONYMOUS,
                        team_name=p.team_name if visible else None,
                        score=p.score,
                        goal_reached=p.goal_reached_at is not None,
                        is_me=is_me,
                    )
                )

        by_team: dict[uuid.UUID | None, list[Participant]] = defaultdict(list)
        for p in participants:
            by_team[p.team_id].append(p)
        standings = sorted(
            (
                TeamStanding(
                    rank=0,
                    team_id=tid,
                    team_name=(members[0].team_name or "No team"),
                    participants=len(members),
                    total_score=sum(m.score for m in members),
                    average_score=round(sum(m.score for m in members) / len(members), 2),
                )
                for tid, members in by_team.items()
            ),
            key=lambda t: (-t.average_score, -t.total_score, t.team_name),
        )
        for i, standing in enumerate(standings, start=1):
            standing.rank = i
        return LeaderboardOut(
            challenge_id=challenge.id, my_rank=my_rank, individuals=individuals, teams=standings
        )

    # ------------------------------------------------------------------ badge rules
    async def list_rules(self) -> list[BadgeRule]:
        rows = (await self.session.scalars(select(BadgeRuleRow).order_by(BadgeRuleRow.threshold))).all()
        return [rule_from_row(r) for r in rows]

    async def upsert_rule(self, code: str, data: BadgeRuleIn) -> BadgeRule:
        rule = BadgeRule(code=code, **data.model_dump())  # validates the code format
        row = await self.session.get(BadgeRuleRow, code)
        values = rule.model_dump(mode="json")
        if row is None:
            self.session.add(BadgeRuleRow(**values))
        else:
            for field, value in values.items():
                setattr(row, field, value)
        await self.session.flush()
        await self._publish_rules()
        await self._commit()
        return rule

    async def delete_rule(self, code: str) -> None:
        result = await self.session.execute(delete(BadgeRuleRow).where(BadgeRuleRow.code == code))
        if not result.rowcount:  # type: ignore[attr-defined]
            raise NotFoundError("Badge rule not found")
        await self._publish_rules()
        await self._commit()

    async def _publish_rules(self) -> None:
        enqueue(
            self.session,
            EventEnvelope.create(
                EventType.BADGE_RULES_CHANGED, SOURCE, BadgeRulesChanged(rules=await self.list_rules())
            ),
        )

    async def seed_and_publish_rules(self) -> None:
        if not await self.session.scalar(select(func.count()).select_from(BadgeRuleRow)):
            self.session.add_all(BadgeRuleRow(**r.model_dump(mode="json")) for r in DEFAULT_BADGE_RULES)
            await self.session.flush()
        # Re-published on every start: idempotent state transfer that self-heals the processor's copy.
        await self._publish_rules()
        await self._commit()


def rule_from_row(row: BadgeRuleRow) -> BadgeRule:
    return BadgeRule(
        code=row.code,
        name=row.name,
        description=row.description,
        icon=row.icon,
        criterion=row.criterion,
        category=row.category,
        threshold=row.threshold,  # type: ignore[arg-type]
        is_active=row.is_active,
    )


async def apply_progress(envelope: EventEnvelope, session: AsyncSession | None) -> None:
    """``progress.updated`` → +1 for every joined challenge whose window and activity type match."""
    assert session is not None
    progress = ProgressUpdated.model_validate(envelope.data)
    rows = (
        await session.execute(
            select(Participant, Challenge)
            .join(Challenge, Challenge.id == Participant.challenge_id)
            .where(
                Participant.user_id == progress.user_id,
                Challenge.starts_on <= progress.completed_on,
                Challenge.ends_on >= progress.completed_on,
                or_(Challenge.category.is_(None), Challenge.category == progress.category.value),
            )
        )
    ).all()
    now = utcnow()
    for participant, challenge in rows:
        participant.score += 1
        participant.last_progress_at = now
        if participant.goal_reached_at is None and participant.score >= challenge.target_count:
            participant.goal_reached_at = now
            enqueue(
                session,
                EventEnvelope.create(
                    EventType.CHALLENGE_GOAL_REACHED,
                    SOURCE,
                    ChallengeGoalReached(
                        challenge_id=challenge.id,
                        title=challenge.title,
                        user_id=participant.user_id,
                        score=participant.score,
                    ),
                    subject=f"user:{participant.user_id}",
                ),
            )
