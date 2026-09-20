import uuid
from types import SimpleNamespace

from backend.content.view_helpers import split_published_drafts


def _item(is_draft: bool, author: uuid.UUID):
    return SimpleNamespace(is_draft=is_draft, created_by_id=author, name="x")


def test_split_separates_published_and_authored_drafts() -> None:
    me = uuid.uuid4()
    other = uuid.uuid4()
    items = [
        _item(False, other),
        _item(True, me),
        _item(True, other),
    ]

    published, drafts = split_published_drafts(items, SimpleNamespace(id=me))

    assert [item.is_draft for item in published] == [False]
    assert [item.is_draft for item in drafts] == [True]
    # Someone else's draft is neither published nor listed.
    assert len(published) + len(drafts) == 2


def test_split_supports_an_alternative_author_attribute() -> None:
    me = uuid.uuid4()
    item = SimpleNamespace(is_draft=True, owner_id=me, created_by_id=uuid.uuid4())

    published, drafts = split_published_drafts(
        [item], SimpleNamespace(id=me), author_attr="owner_id"
    )

    assert published == []
    assert drafts == [item]
