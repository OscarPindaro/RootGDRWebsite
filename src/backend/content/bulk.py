"""Idempotent bulk import/export of a whole world.

Export produces a stable bundle; importing it back into an empty database (or
the same one) reproduces the world. Items are matched by a natural key — name
for characters/NPCs/places/sessions/stories, slug for pages — so a round trip
updates rather than duplicates.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..characters.models import CharacterModel
from ..db.enums import WorldRole
from ..npcs.models import NpcModel
from ..pages.models import PageModel
from ..pages.schemas import slugify
from ..places.models import PlaceModel
from ..schemas import AppBaseModel
from ..sessions.models import SessionModel
from ..stories.models import StoryModel, StoryStatus
from ..users.models import UserModel
from ..users.schemas import User
from ..worlds.models import WorldMembershipModel, WorldModel
from ..worlds.schemas import WorldCreate, WorldMemberInput
from ..worlds.service import create_world
from .constants import ContentKind
from .references import refresh_references


class BundleMember(AppBaseModel):
    email: str
    role: WorldRole = WorldRole.PLAYER


class BundleWorld(AppBaseModel):
    name: str
    description: str = ""
    members: list[BundleMember] = Field(default_factory=list)


class BundleCharacter(AppBaseModel):
    name: str
    owner_email: str | None = None
    title: str | None = None
    short_description: str = ""
    body: str = ""
    tint: str = "p1"
    animal: str = "🐈"
    is_draft: bool = False
    locked: bool = False


class BundleNpc(AppBaseModel):
    name: str
    title: str | None = None
    short_description: str = ""
    body: str = ""
    tint: str = "p1"
    animal: str = "🐈"
    is_draft: bool = False
    locked: bool = False


class BundlePlace(AppBaseModel):
    name: str
    short_description: str = ""
    body: str = ""
    tint: str = "p1"
    shape: str = "cerchio"
    is_draft: bool = False
    locked: bool = False


class BundleSession(AppBaseModel):
    title: str
    in_world_date: str
    real_date: date | None = None
    short_description: str = ""
    body: str = ""
    tint: str = "p1"
    is_draft: bool = False
    locked: bool = False


class BundleStory(AppBaseModel):
    title: str
    short_description: str = ""
    period_label: str | None = None
    status: StoryStatus = StoryStatus.OPEN
    tint: str = "p1"
    body: str = ""
    session_titles: list[str] = Field(default_factory=list)
    is_draft: bool = False
    locked: bool = False


class BundlePage(AppBaseModel):
    title: str
    slug: str
    short_description: str = ""
    menu_position: int = 0
    tint: str = "p3"
    body: str = ""
    is_draft: bool = False
    locked: bool = False


class WorldBundle(AppBaseModel):
    version: Annotated[int, Field(default=1)] = 1
    world: BundleWorld
    characters: list[BundleCharacter] = Field(default_factory=list)
    npcs: list[BundleNpc] = Field(default_factory=list)
    places: list[BundlePlace] = Field(default_factory=list)
    sessions: list[BundleSession] = Field(default_factory=list)
    stories: list[BundleStory] = Field(default_factory=list)
    pages: list[BundlePage] = Field(default_factory=list)


async def _emails(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    users = (await db.scalars(select(UserModel).where(UserModel.id.in_(ids)))).all()
    return {user.id: user.email for user in users}


async def export_world(db: AsyncSession, world: WorldModel) -> WorldBundle:
    """Serialise a world and all of its content into a stable bundle."""
    memberships = list(
        (
            await db.scalars(
                select(WorldMembershipModel).where(
                    WorldMembershipModel.world_id == world.id
                )
            )
        ).all()
    )
    emails = await _emails(db, {m.user_id for m in memberships})

    characters = list(
        (
            await db.scalars(
                select(CharacterModel).where(CharacterModel.world_id == world.id)
            )
        ).all()
    )
    owner_emails = await _emails(db, {c.owner_id for c in characters})
    npcs = list(
        (await db.scalars(select(NpcModel).where(NpcModel.world_id == world.id))).all()
    )
    places = list(
        (
            await db.scalars(select(PlaceModel).where(PlaceModel.world_id == world.id))
        ).all()
    )
    sessions = list(
        (
            await db.scalars(
                select(SessionModel).where(SessionModel.world_id == world.id)
            )
        ).all()
    )
    stories = list(
        (
            await db.scalars(select(StoryModel).where(StoryModel.world_id == world.id))
        ).all()
    )
    pages = list(
        (
            await db.scalars(select(PageModel).where(PageModel.world_id == world.id))
        ).all()
    )
    session_titles = {s.id: s.title for s in sessions}

    return WorldBundle(
        world=BundleWorld(
            name=world.name,
            description=world.description,
            members=[
                BundleMember(email=emails.get(m.user_id, ""), role=m.role)
                for m in memberships
                if m.user_id != world.created_by_id and emails.get(m.user_id)
            ],
        ),
        characters=[
            BundleCharacter(
                name=c.name,
                owner_email=owner_emails.get(c.owner_id),
                title=c.title,
                short_description=c.short_description,
                body=c.body,
                tint=c.tint,
                animal=c.animal,
                is_draft=c.is_draft,
                locked=c.locked,
            )
            for c in characters
        ],
        npcs=[
            BundleNpc(
                name=n.name,
                title=n.title,
                short_description=n.short_description,
                body=n.body,
                tint=n.tint,
                animal=n.animal,
                is_draft=n.is_draft,
                locked=n.locked,
            )
            for n in npcs
        ],
        places=[
            BundlePlace(
                name=p.name,
                short_description=p.short_description,
                body=p.body,
                tint=p.tint,
                shape=p.shape,
                is_draft=p.is_draft,
                locked=p.locked,
            )
            for p in places
        ],
        sessions=[
            BundleSession(
                title=s.title,
                in_world_date=s.in_world_date,
                real_date=s.real_date,
                short_description=s.short_description,
                body=s.body,
                tint=s.tint,
                is_draft=s.is_draft,
                locked=s.locked,
            )
            for s in sessions
        ],
        stories=[
            BundleStory(
                title=s.title,
                short_description=s.short_description,
                period_label=s.period_label,
                status=s.status,
                tint=s.tint,
                body=s.body,
                session_titles=[
                    session_titles[i]
                    for i in (x.id for x in s.sessions)
                    if i in session_titles
                ],
                is_draft=s.is_draft,
                locked=s.locked,
            )
            for s in stories
        ],
        pages=[
            BundlePage(
                title=p.title,
                slug=p.slug,
                short_description=p.short_description,
                menu_position=p.menu_position,
                tint=p.tint,
                body=p.body,
                is_draft=p.is_draft,
                locked=p.locked,
            )
            for p in pages
        ],
    )


async def _user_by_email(db: AsyncSession, email: str | None) -> UserModel | None:
    if not email:
        return None
    return (
        await db.scalars(select(UserModel).where(UserModel.email == email))
    ).one_or_none()


async def import_world(
    db: AsyncSession, bundle: WorldBundle, actor: UserModel
) -> WorldModel:
    """Create or update a world from a bundle, keyed by name and natural keys."""
    world = (
        await db.scalars(
            select(WorldModel).where(
                WorldModel.name == bundle.world.name,
                WorldModel.created_by_id == actor.id,
            )
        )
    ).one_or_none()
    if world is None:
        member_ids: list[WorldMemberInput] = []
        for member in bundle.world.members:
            user = await _user_by_email(db, member.email)
            if user is not None:
                member_ids.append(WorldMemberInput(user_id=user.id, role=member.role))
        world = await create_world(
            db,
            WorldCreate(
                name=bundle.world.name,
                description=bundle.world.description or bundle.world.name,
                members=member_ids,
            ),
            actor_schema(actor),
        )
    else:
        world.description = bundle.world.description or world.description

    await _import_characters(db, world, bundle, actor)
    await _import_npcs(db, world, bundle, actor)
    await _import_places(db, world, bundle, actor)
    await _import_sessions(db, world, bundle, actor)
    await _import_stories(db, world, bundle, actor)
    await _import_pages(db, world, bundle, actor)
    await db.flush()
    return world


def actor_schema(actor: UserModel) -> User:
    return User.model_validate(actor)


async def _import_characters(db, world, bundle, actor) -> None:
    existing = {
        c.name: c
        for c in (
            await db.scalars(
                select(CharacterModel).where(CharacterModel.world_id == world.id)
            )
        ).all()
    }
    for item in bundle.characters:
        owner = await _user_by_email(db, item.owner_email) or actor
        model = existing.get(item.name)
        if model is None:
            model = CharacterModel(
                world_id=world.id, owner_id=owner.id, name=item.name, body=item.body
            )
            db.add(model)
        model.title = item.title
        model.short_description = item.short_description
        model.body = item.body
        model.tint = item.tint
        model.animal = item.animal
        model.is_draft = item.is_draft
        model.locked = item.locked
        await db.flush()
        await refresh_references(
            db, world.id, ContentKind.CHARACTER, model.id, model.body
        )


async def _import_npcs(db, world, bundle, actor) -> None:
    existing = {
        n.name: n
        for n in (
            await db.scalars(select(NpcModel).where(NpcModel.world_id == world.id))
        ).all()
    }
    for item in bundle.npcs:
        model = existing.get(item.name)
        if model is None:
            model = NpcModel(
                world_id=world.id,
                created_by_id=actor.id,
                name=item.name,
                body=item.body,
            )
            db.add(model)
        model.title = item.title
        model.short_description = item.short_description
        model.body = item.body
        model.tint = item.tint
        model.animal = item.animal
        model.is_draft = item.is_draft
        model.locked = item.locked
        await db.flush()
        await refresh_references(db, world.id, ContentKind.NPC, model.id, model.body)
    await db.flush()


async def _import_places(db, world, bundle, actor) -> None:
    existing = {
        p.name: p
        for p in (
            await db.scalars(select(PlaceModel).where(PlaceModel.world_id == world.id))
        ).all()
    }
    for item in bundle.places:
        model = existing.get(item.name)
        if model is None:
            model = PlaceModel(
                world_id=world.id,
                created_by_id=actor.id,
                name=item.name,
                body=item.body,
            )
            db.add(model)
        model.short_description = item.short_description
        model.body = item.body
        model.tint = item.tint
        model.shape = item.shape
        model.is_draft = item.is_draft
        model.locked = item.locked
        await db.flush()
        await refresh_references(db, world.id, ContentKind.PLACE, model.id, model.body)
    await db.flush()


async def _import_sessions(db, world, bundle, actor) -> None:
    existing = {
        s.title: s
        for s in (
            await db.scalars(
                select(SessionModel).where(SessionModel.world_id == world.id)
            )
        ).all()
    }
    for item in bundle.sessions:
        model = existing.get(item.title)
        if model is None:
            model = SessionModel(
                world_id=world.id,
                created_by_id=actor.id,
                title=item.title,
                in_world_date=item.in_world_date,
                body=item.body,
            )
            db.add(model)
        model.in_world_date = item.in_world_date
        model.real_date = item.real_date
        model.short_description = item.short_description
        model.body = item.body
        model.tint = item.tint
        model.is_draft = item.is_draft
        model.locked = item.locked
        await db.flush()
        await refresh_references(
            db, world.id, ContentKind.SESSION, model.id, model.body
        )
    await db.flush()


async def _import_stories(db, world, bundle, actor) -> None:
    existing = {
        s.title: s
        for s in (
            await db.scalars(select(StoryModel).where(StoryModel.world_id == world.id))
        ).all()
    }
    for item in bundle.stories:
        model = existing.get(item.title)
        if model is None:
            model = StoryModel(
                world_id=world.id,
                created_by_id=actor.id,
                title=item.title,
                body=item.body,
            )
            db.add(model)
        model.short_description = item.short_description
        model.period_label = item.period_label
        model.status = item.status
        model.tint = item.tint
        model.body = item.body
        model.is_draft = item.is_draft
        model.locked = item.locked
    await db.flush()
    # Link sessions by title once every session exists.
    sessions = {
        s.title: s
        for s in (
            await db.scalars(
                select(SessionModel).where(SessionModel.world_id == world.id)
            )
        ).all()
    }
    for item in bundle.stories:
        story = (
            existing.get(item.title)
            or (
                await db.scalars(
                    select(StoryModel).where(
                        StoryModel.world_id == world.id, StoryModel.title == item.title
                    )
                )
            ).one()
        )
        story.sessions = [
            sessions[title] for title in item.session_titles if title in sessions
        ]
        await db.flush()
        await refresh_references(db, world.id, ContentKind.STORY, story.id, story.body)
    await db.flush()


async def _import_pages(db, world, bundle, actor) -> None:
    existing = {
        p.slug: p
        for p in (
            await db.scalars(select(PageModel).where(PageModel.world_id == world.id))
        ).all()
    }
    for item in bundle.pages:
        slug = item.slug or slugify(item.title)
        model = existing.get(slug)
        if model is None:
            model = PageModel(
                world_id=world.id,
                created_by_id=actor.id,
                title=item.title,
                slug=slug,
                body=item.body,
            )
            db.add(model)
        model.title = item.title
        model.short_description = item.short_description
        model.menu_position = item.menu_position
        model.tint = item.tint
        model.body = item.body
        model.is_draft = item.is_draft
        model.locked = item.locked
        await db.flush()
        await refresh_references(db, world.id, ContentKind.PAGE, model.id, model.body)
    await db.flush()
