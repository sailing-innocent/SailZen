"""
Tests for SailZen Feishu Bot - Cards Module
"""

import pytest
from bot.cards import (
    CardBuilder,
    CardColor,
    CardButton,
    ButtonType,
    create_welcome_card,
    create_session_status_card,
    create_task_result_card,
    create_confirmation_card,
    create_error_card,
    create_help_card,
)


class TestCardBuilder:
    """Test CardBuilder functionality."""

    def test_basic_card(self):
        """Test creating a basic card."""
        builder = CardBuilder("Test Card", CardColor.BLUE)
        builder.add_text("Hello World")

        card = builder.build()
        assert card["header"]["title"]["content"] == "Test Card"
        assert card["header"]["template"] == "blue"
        assert len(card["elements"]) == 1

    def test_card_with_markdown(self):
        """Test card with markdown."""
        builder = CardBuilder("Markdown Card")
        builder.add_markdown("**Bold** and *italic*")

        card = builder.build()
        assert card["elements"][0]["text"]["tag"] == "lark_md"
        assert "**Bold**" in card["elements"][0]["text"]["content"]

    def test_card_with_divider(self):
        """Test card with divider."""
        builder = CardBuilder("Card with Divider")
        builder.add_text("Before")
        builder.add_divider()
        builder.add_text("After")

        card = builder.build()
        assert len(card["elements"]) == 3
        assert card["elements"][1]["tag"] == "hr"

    def test_card_with_note(self):
        """Test card with note."""
        builder = CardBuilder("Card with Note")
        builder.add_note("This is a note")

        card = builder.build()
        assert card["elements"][0]["tag"] == "note"

    def test_card_with_button_group(self):
        """Test card with button group."""
        builder = CardBuilder("Card with Buttons")
        buttons = [
            CardButton("Start", "start", {"path": "/test"}),
            CardButton("Stop", "stop", {"path": "/test"}, ButtonType.DANGER),
        ]
        builder.add_button_group(buttons)

        card = builder.build()
        assert card["elements"][0]["tag"] == "action"
        assert len(card["elements"][0]["actions"]) == 2
        assert card["elements"][0]["actions"][0]["text"]["content"] == "Start"


class TestPrebuiltCards:
    """Test prebuilt card templates."""

    def test_welcome_card(self):
        """Test welcome card creation."""
        projects = [
            {"slug": "proj1", "label": "Project 1", "path": "/test1"},
            {"slug": "proj2", "label": "Project 2", "path": "/test2"},
        ]
        card = create_welcome_card("Test Bot", projects)

        assert "Test Bot" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "blue"
        assert len(card["elements"]) > 0

    def test_session_status_card(self):
        """Test session status card."""
        session_info = {
            "name": "Test Session",
            "path": "/test",
            "port": 4096,
            "pid": 1234,
            "process_status": "running",
        }
        card = create_session_status_card(session_info)

        assert "Test Session" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "green"
        # Should contain status, path, port, pid info
        elements_text = str(card["elements"])
        assert "4096" in elements_text or "1234" in elements_text

    def test_task_result_card(self):
        """Test task result card."""
        card = create_task_result_card(
            task="Write a function", result="Task completed successfully!", path="/test"
        )

        assert "任务完成" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "green"

    def test_confirmation_card(self):
        """Test confirmation card."""
        card = create_confirmation_card(
            title="Confirm Action",
            message="Are you sure?",
            action="confirm_delete",
            params={"id": "123"},
        )

        assert "Confirm Action" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "orange"
        assert "Are you sure?" in str(card["elements"])

    def test_error_card(self):
        """Test error card."""
        card = create_error_card(
            error_message="Something went wrong", suggestion="Try again later"
        )

        assert "发生错误" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "red"
        assert "Something went wrong" in str(card["elements"])

    def test_help_card(self):
        """Test help card."""
        projects = [{"slug": "test", "label": "Test", "description": "Test project"}]
        card = create_help_card("Test Bot", projects)

        assert "帮助" in card["header"]["title"]["content"]
        assert card["header"]["template"] == "blue"


class TestCardColors:
    """Test card color enum."""

    def test_color_values(self):
        """Test color enum values."""
        assert CardColor.BLUE.value == "blue"
        assert CardColor.GREEN.value == "green"
        assert CardColor.RED.value == "red"
        assert CardColor.ORANGE.value == "orange"


class TestButtonTypes:
    """Test button type enum."""

    def test_button_type_values(self):
        """Test button type enum values."""
        assert ButtonType.PRIMARY.value == "primary"
        assert ButtonType.SECONDARY.value == "secondary"
        assert ButtonType.DANGER.value == "danger"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
