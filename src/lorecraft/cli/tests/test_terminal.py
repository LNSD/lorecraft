"""The colour decision and the typed reading of the environment behind it."""

from typing import Final

import pytest

from ..output import ColorChoice
from ..terminal import ColorEnvironment, decide_color

_NOTHING_SET: Final[ColorEnvironment] = ColorEnvironment(force_color=False, no_color=False)
_FORCE_SET: Final[ColorEnvironment] = ColorEnvironment(force_color=True, no_color=False)
_NO_SET: Final[ColorEnvironment] = ColorEnvironment(force_color=False, no_color=True)
_BOTH_SET: Final[ColorEnvironment] = ColorEnvironment(force_color=True, no_color=True)


@pytest.mark.unit
class TestColorEnvironmentParse:
    def test_parse_with_a_non_empty_force_color_sets_force_color(self) -> None:
        #: Given
        environ = {'FORCE_COLOR': '1'}

        #: When
        environment = ColorEnvironment.parse(environ)

        #: Then
        assert environment == _FORCE_SET, 'a non-empty FORCE_COLOR asks for colour'

    def test_parse_with_a_non_empty_no_color_sets_no_color(self) -> None:
        #: Given
        environ = {'NO_COLOR': '1'}

        #: When
        environment = ColorEnvironment.parse(environ)

        #: Then
        assert environment == _NO_SET, 'a non-empty NO_COLOR asks for no colour'

    def test_parse_with_a_value_of_zero_counts_as_set(self) -> None:
        #: Given
        environ = {'FORCE_COLOR': '0', 'NO_COLOR': '0'}

        #: When
        environment = ColorEnvironment.parse(environ)

        #: Then
        assert environment == _BOTH_SET, 'both conventions read any non-empty value as a request, `0` included'

    def test_parse_with_empty_values_counts_both_as_unset(self) -> None:
        #: Given
        environ = {'FORCE_COLOR': '', 'NO_COLOR': ''}

        #: When
        environment = ColorEnvironment.parse(environ)

        #: Then
        assert environment == _NOTHING_SET, 'an empty value gives neither convention a request'

    def test_parse_with_neither_variable_sets_nothing(self) -> None:
        #: Given
        environ = {'TERM': 'xterm', 'COLORTERM': 'truecolor'}

        #: When
        environment = ColorEnvironment.parse(environ)

        #: Then
        assert environment == _NOTHING_SET, 'other variables, even colour-related ones, are ignored'


@pytest.mark.unit
class TestDecideColor:
    def test_decide_color_with_always_colours_a_pipe_whatever_the_environment_says(self) -> None:
        #: Given
        choice = ColorChoice.ALWAYS

        #: When
        color = decide_color(choice, _NO_SET, is_terminal=False)

        #: Then
        assert color is True, 'an explicit `--color always` beats NO_COLOR and the missing terminal'

    def test_decide_color_with_never_does_not_colour_a_terminal_even_with_force_color(self) -> None:
        #: Given
        choice = ColorChoice.NEVER

        #: When
        color = decide_color(choice, _FORCE_SET, is_terminal=True)

        #: Then
        assert color is False, 'an explicit `--color never` beats FORCE_COLOR and the terminal'

    def test_decide_color_with_auto_and_force_color_colours_a_pipe(self) -> None:
        #: Given
        choice = ColorChoice.AUTO

        #: When
        color = decide_color(choice, _FORCE_SET, is_terminal=False)

        #: Then
        assert color is True, 'FORCE_COLOR colours output that is not a terminal'

    def test_decide_color_with_auto_and_both_variables_lets_force_color_win(self) -> None:
        #: Given
        choice = ColorChoice.AUTO

        #: When
        color = decide_color(choice, _BOTH_SET, is_terminal=True)

        #: Then
        assert color is True, 'FORCE_COLOR beats NO_COLOR, as force-color.org orders them'

    def test_decide_color_with_auto_and_no_color_does_not_colour_a_terminal(self) -> None:
        #: Given
        choice = ColorChoice.AUTO

        #: When
        color = decide_color(choice, _NO_SET, is_terminal=True)

        #: Then
        assert color is False, 'NO_COLOR turns the colour of a terminal off'

    def test_decide_color_with_auto_and_nothing_set_colours_a_terminal(self) -> None:
        #: Given
        choice = ColorChoice.AUTO

        #: When
        color = decide_color(choice, _NOTHING_SET, is_terminal=True)

        #: Then
        assert color is True, 'with no variable, a terminal is coloured'

    def test_decide_color_with_auto_and_nothing_set_does_not_colour_a_pipe(self) -> None:
        #: Given
        choice = ColorChoice.AUTO

        #: When
        color = decide_color(choice, _NOTHING_SET, is_terminal=False)

        #: Then
        assert color is False, 'with no variable, a pipe is not coloured'

    def test_decide_color_with_auto_and_empty_variables_colours_a_terminal(self) -> None:
        #: Given
        choice = ColorChoice.AUTO
        environment = ColorEnvironment.parse({'FORCE_COLOR': '', 'NO_COLOR': ''})

        #: When
        color = decide_color(choice, environment, is_terminal=True)

        #: Then
        assert color is True, 'empty variables count as unset, so a terminal is coloured'

    def test_decide_color_with_auto_and_empty_variables_does_not_colour_a_pipe(self) -> None:
        #: Given
        choice = ColorChoice.AUTO
        environment = ColorEnvironment.parse({'FORCE_COLOR': '', 'NO_COLOR': ''})

        #: When
        color = decide_color(choice, environment, is_terminal=False)

        #: Then
        assert color is False, 'empty variables count as unset, so a pipe is not coloured'
