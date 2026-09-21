"""World invites: email addresses added to a world before they have an account.

A world owner can add someone who is not in the app yet. The invite keeps the
email and the role; the first time a user with that email signs in, the invite
becomes a membership. This module knows nothing about authentication: it only
reads the user passed by the caller.
"""

from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import WorldRole
from ..users.models import UserModel
from .models import WorldInviteModel, WorldMembershipModel


async def pending_invites_for(db: AsyncSession, email: str) -> list[WorldInviteModel]:
    """Non-expired, non-accepted invites for one email."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(WorldInviteModel).where(
            WorldInviteModel.email == email,
            WorldInviteModel.accepted_at.is_(None),
            WorldInviteModel.expires_at > now,
        )
    )
    return list(result.scalars().all())


async def invite_email(
    db: AsyncSession,
    world_id: uuid.UUID,
    email: str,
    role: WorldRole,
    invited_by: uuid.UUID,
    expire_days: int = 30,
) -> WorldInviteModel:
    """Create or refresh the invite for ``email`` in one world."""
    existing = (
        await db.scalars(
            select(WorldInviteModel).where(
                WorldInviteModel.world_id == world_id,
                WorldInviteModel.email == email,
            )
        )
    ).one_or_none()
    expires_at = datetime.now(UTC) + timedelta(days=expire_days)
    if existing is not None:
        existing.role = role
        existing.expires_at = expires_at
        existing.accepted_at = None
        await db.flush()
        return existing
    invite = WorldInviteModel(
        world_id=world_id,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()
    return invite


async def list_world_invites(
    db: AsyncSession, world_id: uuid.UUID
) -> list[WorldInviteModel]:
    """Pending invites of one world, oldest first."""
    result = await db.execute(
        select(WorldInviteModel)
        .where(
            WorldInviteModel.world_id == world_id,
            WorldInviteModel.accepted_at.is_(None),
        )
        .order_by(WorldInviteModel.created_at)
    )
    return list(result.scalars().all())


async def revoke_world_invite(
    db: AsyncSession, world_id: uuid.UUID, email: str
) -> None:
    """Drop a pending invite; a no-op when there is none."""
    invite = (
        await db.scalars(
            select(WorldInviteModel).where(
                WorldInviteModel.world_id == world_id,
                WorldInviteModel.email == email,
            )
        )
    ).one_or_none()
    if invite is not None:
        await db.delete(invite)
        await db.flush()


async def apply_pending_invites(db: AsyncSession, user: UserModel) -> int:
    """Turn this user's pending world invites into memberships.

    Called after a user is resolved or created, so an invited person lands in
    the right world the first time they sign in. Returns how many were applied.
    """
    invites = await pending_invites_for(db, user.email)
    if not invites:
        return 0
    world_ids = [invite.world_id for invite in invites]
    existing = set(
        (
            await db.scalars(
                select(WorldMembershipModel.world_id).where(
                    WorldMembershipModel.user_id == user.id,
                    WorldMembershipModel.world_id.in_(world_ids),
                )
            )
        ).all()
    )
    now = datetime.now(UTC)
    for invite in invites:
        if invite.world_id not in existing:
            db.add(
                WorldMembershipModel(
                    world_id=invite.world_id,
                    user_id=user.id,
                    role=invite.role,
                )
            )
        invite.accepted_at = now
    await db.flush()
    return len(invites)
