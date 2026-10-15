import unittest
from unittest.mock import Mock
from purple_dragon_agent.ui import GlowButton
from purple_dragon_agent.theme import COLORS

class ButtonTests(unittest.TestCase):
    def test_pointer_leave_preserves_disabled_face(self):
        button = GlowButton.__new__(GlowButton)
        button.button = Mock();button.edge = Mock();button.face = '#6334AA'
        button.button.cget.return_value = 'disabled'
        button._leave()
        button.button.configure.assert_called_once_with(bg=COLORS['panel_3'],relief='raised')
    def test_disabled_button_does_not_hover_or_press(self):
        button = GlowButton.__new__(GlowButton)
        button.button = Mock();button.edge = Mock()
        button.button.cget.return_value = 'disabled'
        button._hover();button._press()
        button.button.configure.assert_not_called()
        button.edge.configure.assert_not_called()
