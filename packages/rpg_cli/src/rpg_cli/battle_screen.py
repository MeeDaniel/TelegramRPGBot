from core import Attack, AttackMode, AttackType, BattleStatus, DrinkPotion, Guard, InvalidAction, UseSuperpower

from .button import Button
from .screen import Screen
from .screen_view import ScreenView


class BattleScreen(Screen):
    def __init__(self, context, events=(), error=''):
        self.context = context
        self.events = tuple(events)
        self.error = error

    def action(self, action):
        try:
            events = self.context.game.submit_action(
                self.context.battle.id, self.context.player.id, action)
        except InvalidAction as error:
            return BattleScreen(self.context, self.events, str(error))
        return BattleScreen(self.context, events)

    def attack(self):
        player = self.context.player
        enemy = next(p for p in self.context.battle.living() if p.team_id != player.team_id)
        weapon = player.equipment.weapon
        mode = AttackMode.BASIC if weapon and weapon.attack_type == AttackType.SUPPORT else AttackMode.WEAPON
        return self.action(Attack(enemy.id, mode))

    def result(self):
        battle = self.context.battle
        if battle.winner_team == battle.player_team:
            return 'ПОБЕДА!'
        if battle.winner_team is None:
            return 'НИЧЬЯ!'
        return 'ПОРАЖЕНИЕ!'

    def view(self):
        battle = self.context.battle
        player = self.context.player
        lines = [f'ХОД {battle.round_number}']
        for participant in battle.participants.values():
            stats = participant.stats(battle.round_number)
            lines.append(f'{participant.name}: {participant.current_hp}/{stats.max_health} HP | '
                         f'Защита {stats.defense} | Урон {stats.melee_damage}/{stats.magic_damage}/{stats.ranged_damage}')
            if participant.effects:
                lines.append('Эффекты: ' + ', '.join(f'{effect.name} (до хода {effect.ends_round})'
                                                    for effect in participant.effects))
        lines += [f'Зелья: {player.potions_left} (доступно с хода {player.potion_ready_round})',
                  f'Суперсила: {player.equipment.superpower.name if player.equipment.superpower else "нет"} '
                  f'(доступна с хода {player.superpower_ready_round})']
        lines.extend(event.text for event in self.events)
        if self.error:
            lines.append(self.error)
        buttons = []
        if battle.status == BattleStatus.WAITING:
            buttons = [Button('attack', 'Атаковать', self.attack),
                       Button('guard', 'Защититься', lambda: self.action(Guard())),
                       Button('power', 'Суперсила на себя', lambda: self.action(UseSuperpower(player.id))),
                       Button('potion', 'Выпить зелье', lambda: self.action(DrinkPotion()))]
            if player.equipment.weapon and player.equipment.weapon.attack_type == AttackType.SUPPORT:
                buttons.append(Button('heal', 'Лечение себя посохом',
                                      lambda: self.action(Attack(player.id))))
        else:
            lines.append(self.result())
            lines.append('Добыча: ' + (', '.join(
                f'{self.context.game.catalog.items[item_id].name} ×{amount}'
                for item_id, amount in battle.drops) or 'нет'))
        home_label = 'Сдаться и вернуться домой' if battle.status == BattleStatus.WAITING else 'Домой'
        buttons.append(Button('home', home_label, self.context.home))
        return ScreenView('\n'.join(lines), tuple(buttons))
