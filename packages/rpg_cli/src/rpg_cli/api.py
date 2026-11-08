from .console_adapter import ConsoleAdapter
from .game_context import GameContext
from .name_screen import NameScreen
from .session import Session


def create_session(world, game, presets, default_preset_id, default_name='Герой'):
    """Build a session; preset factories must return registered characters."""
    presets = tuple(presets)
    identifiers = [preset.id for preset in presets]
    if not presets or len(set(identifiers)) != len(identifiers):
        raise ValueError('Presets must be nonempty and have unique IDs')
    if default_preset_id not in identifiers:
        raise ValueError('Unknown default preset')
    context = GameContext(world, game, presets, default_preset_id, default_name)
    return Session(NameScreen(context), on_close=context.cleanup_battle)


def run_cli(world, game, presets, default_preset_id, default_name='Герой'):
    session = create_session(world, game, presets, default_preset_id, default_name)
    ConsoleAdapter(session).run()
