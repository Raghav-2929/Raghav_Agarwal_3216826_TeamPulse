"""Demo organisation (idempotent): 3 teams, 3 managers, 10 employees, 1 admin."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy import func, select

from identity_service.models import Team, User
from identity_service.service import hash_password, user_event
from teampulse_common.events import EventType, enqueue
from teampulse_common.security import Role

logger = logging.getLogger("identity.seed")

TEAMS = {
    "Engineering": ("Builds the TeamPulse product", "maya.patel@teampulse.io"),
    "Marketing": ("Brand, campaigns and content", "omar.haddad@teampulse.io"),
    "Operations": ("People, finance and facilities", "priya.nair@teampulse.io"),
}

USERS: list[tuple[str, str, Role, str | None]] = [
    ("admin@teampulse.io", "Ada Admin", Role.ADMIN, None),
    ("maya.patel@teampulse.io", "Maya Patel", Role.MANAGER, "Engineering"),
    ("omar.haddad@teampulse.io", "Omar Haddad", Role.MANAGER, "Marketing"),
    ("priya.nair@teampulse.io", "Priya Nair", Role.MANAGER, "Operations"),
    ("alice.johnson@teampulse.io", "Alice Johnson", Role.EMPLOYEE, "Engineering"),
    ("ben.carter@teampulse.io", "Ben Carter", Role.EMPLOYEE, "Engineering"),
    ("chloe.kim@teampulse.io", "Chloe Kim", Role.EMPLOYEE, "Engineering"),
    ("dev.sharma@teampulse.io", "Dev Sharma", Role.EMPLOYEE, "Engineering"),
    ("emma.davis@teampulse.io", "Emma Davis", Role.EMPLOYEE, "Marketing"),
    ("felix.wong@teampulse.io", "Felix Wong", Role.EMPLOYEE, "Marketing"),
    ("grace.lee@teampulse.io", "Grace Lee", Role.EMPLOYEE, "Marketing"),
    ("henry.lopez@teampulse.io", "Henry Lopez", Role.EMPLOYEE, "Operations"),
    ("isla.brown@teampulse.io", "Isla Brown", Role.EMPLOYEE, "Operations"),
    ("jack.wilson@teampulse.io", "Jack Wilson", Role.EMPLOYEE, "Operations"),
]


async def seed_demo_data(app: FastAPI) -> None:
    settings = app.state.settings
    if not settings.seed_demo_data:
        return
    async with app.state.db.session_factory() as session:
        if (await session.scalar(select(func.count(User.id)))) or 0:
            return
        password_hash = await hash_password(settings.demo_password, app.state.bcrypt_rounds)
        teams = {name: Team(name=name, description=desc) for name, (desc, _) in TEAMS.items()}
        session.add_all(teams.values())
        await session.flush()
        users: dict[str, User] = {}
        for email, name, role, team in USERS:
            user = User(
                email=email,
                full_name=name,
                role=role.value,
                password_hash=password_hash,
                team_id=teams[team].id if team else None,
            )
            session.add(user)
            users[email] = user
        await session.flush()
        for name, (_, manager_email) in TEAMS.items():
            teams[name].manager_id = users[manager_email].id
        for user in users.values():
            await session.refresh(user, ["team"])
            enqueue(session, user_event(EventType.USER_REGISTERED, user))
        await session.commit()
    logger.info("seed.completed", extra={"teams": len(TEAMS), "users": len(USERS)})
