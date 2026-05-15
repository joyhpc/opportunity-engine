import pytest

from prototypes.storybook.pipeline_v2 import (
    ChildProfile,
    PageContent,
    StoryConfig,
    build_pages_from_tool_input,
)


def _child() -> ChildProfile:
    return ChildProfile(
        name="Aiden",
        age=6,
        gender="boy",
        appearance={"hair": "short black", "glasses": True},
        outfit="blue jacket",
        language="en",
    )


def _valid_tool_input() -> dict:
    return {
        "pages": [
            {
                "page_num": 1,
                "text": "Aiden looked up at the bright moon.",
                "scene": "boy with glasses holding a telescope near a window",
                "emotion": "curious",
            },
            {
                "page_num": 2,
                "text": "He smiled and drew a little star map.",
                "scene": "boy drawing stars at a desk with colored pencils",
                "emotion": "proud",
            },
        ]
    }


def test_build_pages_from_tool_input_accepts_valid_pages():
    pages, issues = build_pages_from_tool_input(
        _valid_tool_input(),
        _child(),
        StoryConfig(theme="Moon Map", pages=2, style="flat_cartoon"),
    )

    assert issues == []
    assert [page.page_num for page in pages] == [1, 2]
    assert all(isinstance(page, PageContent) for page in pages)
    assert "boy drawing stars" in pages[1].illustration_prompt
    assert "no text, no words" in pages[1].illustration_prompt


@pytest.mark.parametrize(
    ("tool_input", "config_pages", "expected"),
    [
        ({}, 2, "missing required 'pages' field"),
        ({"pages": []}, 2, "must be a non-empty list"),
        (_valid_tool_input(), 3, "Requested 3 pages, got 2"),
        ({"pages": [{"page_num": 1, "text": "Hi", "emotion": "happy"}]}, 1, "missing required fields: scene"),
        ({"pages": [{"page_num": "1", "text": "Hi", "scene": "desk", "emotion": "happy"}]}, 1, "page_num' must be an integer"),
        ({"pages": [{"page_num": 1, "text": " ", "scene": "desk", "emotion": "happy"}]}, 1, "text' must be a non-empty string"),
    ],
)
def test_build_pages_from_tool_input_rejects_invalid_pages(tool_input, config_pages, expected):
    pages, issues = build_pages_from_tool_input(
        tool_input,
        _child(),
        StoryConfig(theme="Moon Map", pages=config_pages),
    )

    assert pages == []
    assert any(issue.startswith("CRITICAL:") and expected in issue for issue in issues)
