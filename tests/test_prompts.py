"""Tests for the prompt text itself.

A prompt is a product decision, not plumbing, so almost none of its effect is
unit-testable — whether the model actually complies can only be judged by reading
real output. What these tests *can* do is stop a future edit from silently
dropping a constraint that was added deliberately, which is exactly the failure
mode a prompt change is prone to.
"""

from __future__ import annotations

from raw_media_parser.prompts import SYSTEM_PROMPT, build_user_content


def test_excludes_promotional_content() -> None:
    """The exclusion rule must survive future prompt edits (issue #16)."""
    lowered = SYSTEM_PROMPT.lower()
    assert "promotional and call-to-action content" in lowered
    # The categories are named explicitly so the model needn't infer the boundary.
    for category in ("subscribe", "telegram", "patreon", "merch", "sponsor"):
        assert category in lowered, f"promo category dropped from the rule: {category}"


def test_keeps_the_four_informational_sections() -> None:
    """Action Items stays; the exclusion rule handles promo, not section removal."""
    for section in ("## TL;DR", "## Key Points", "## Notable Takeaways", "## Action Items"):
        assert section in SYSTEM_PROMPT


def test_still_forbids_speculation() -> None:
    """The new rule must not have displaced the existing faithfulness constraint."""
    assert "never speculate beyond what was said" in SYSTEM_PROMPT


def test_user_content_carries_context_and_transcript() -> None:
    content = build_user_content("some words", title="A Talk", uploader="A Channel")
    assert "A Talk" in content
    assert "A Channel" in content
    assert "some words" in content


def test_user_content_omits_creator_when_unknown() -> None:
    content = build_user_content("some words", title="A Talk")
    assert "Creator:" not in content
