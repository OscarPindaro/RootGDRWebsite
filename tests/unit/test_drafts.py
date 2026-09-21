from types import SimpleNamespace

from backend.content.view_helpers import split_published_drafts


def test_split_separates_visibility_filtered_items() -> None:
    published_item = SimpleNamespace(is_draft=False, name="published")
    draft_item = SimpleNamespace(is_draft=True, name="draft")

    published, drafts = split_published_drafts([published_item, draft_item])

    assert published == [published_item]
    assert drafts == [draft_item]
