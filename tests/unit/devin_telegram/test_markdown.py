import pytest

from devin_telegram.telegram.markdown import render_markdown

pytestmark = pytest.mark.unit


def test_markdown_is_converted_to_native_telegram_entities() -> None:
    rendered = render_markdown(
        "**RootGDRWebsite** uses `uv` and [GitHub](https://github.com)."
    )

    assert len(rendered) == 1
    assert "**" not in rendered[0].text
    assert "`" not in rendered[0].text
    assert {entity.type for entity in rendered[0].entities} == {
        "bold",
        "code",
        "text_link",
    }


def test_long_markdown_is_split_without_data_loss() -> None:
    source = f"**{'word ' * 100}**"

    rendered = render_markdown(source, limit=80)

    assert len(rendered) > 1
    assert all(len(message.text) <= 80 for message in rendered)
    assert "".join(message.text for message in rendered) == source
