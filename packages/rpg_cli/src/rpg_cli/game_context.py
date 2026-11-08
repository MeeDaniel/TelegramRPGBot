from core import BattleStatus


class GameContext:
    """Shared creation draft and references to authoritative game state."""

    def __init__(self, world, game, presets, default_preset_id, default_name):
        self.world = world
        self.game = game
        self.presets = {preset.id: preset for preset in presets}
        self.default_preset_id = default_preset_id
        self.default_name = default_name
        self.name = None
        self.character = None
        self.battle = None
        self.last_result = ''

    def finalize(self, preset_id=None):
        if self.character is None:
            preset = self.presets[preset_id or self.default_preset_id]
            self.character = preset.create(self.name or self.default_name)

    def cleanup_battle(self):
        if self.battle is not None and self.battle.status == BattleStatus.WAITING:
            self.game.leave(self.battle.id, self.player.id)
            self.last_result = 'ПОРАЖЕНИЕ! Вы покинули бой.'

    @property
    def player(self):
        return next(p for p in self.battle.participants.values()
                    if p.character_id == self.character.id)

    def home(self):
        from .home_screen import HomeScreen
        self.finalize()
        self.cleanup_battle()
        return HomeScreen(self)
