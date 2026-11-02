"""Deterministic turn resolution; no IO, no Telegram, no persistence."""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from .models import (
    ActiveEffect,
    Attack,
    AttackMode,
    AttackType,
    Battle,
    BattleAction,
    BattleParticipant,
    BattleStatus,
    CombatEvent,
    Controller,
    DrinkPotion,
    Guard,
    UseSuperpower,
)


class InvalidAction(ValueError):
    """An illegal combat command; battle has not been mutated."""


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))  # noqa: FURB157


class CombatCalculator:
    """Stat calculations. Defense rating is not a literal percentage."""

    @staticmethod
    def attack_power(actor: BattleParticipant, round_number: int, mode: AttackMode) -> int:
        stats = actor.stats(round_number)
        if mode == AttackMode.BASIC:
            # Support's basic enemy attack is a normal melee stat-based attack.
            return stats.melee_damage
        weapon = actor.equipment.weapon
        kind = weapon.attack_type if weapon else AttackType.MELEE
        return {
            AttackType.MELEE: stats.melee_damage,
            AttackType.MAGIC: stats.magic_damage,
            AttackType.RANGED: stats.ranged_damage,
        }[kind]

    @staticmethod
    def defense_rating(target: BattleParticipant, guarding: bool, round_number: int) -> Decimal:
        if guarding:
            coefficient = target.equipment.armor.guard_multiplier if target.equipment.armor else 1.0
            return max(Decimal('0'), Decimal(target.stats(round_number).defense) * Decimal(str(coefficient)))  # noqa: FURB157
        armor = target.equipment.armor
        return Decimal(max(0, armor.bonus.defense if armor else 0))

    @classmethod
    def damage(cls, base_damage: int, target: BattleParticipant,
               guarding: bool, round_number: int) -> int:
        armor = cls.defense_rating(target, guarding, round_number)
        # Mitigation A/(A+100), so damage multiplier is 100/(A+100).
        return round_half_up(Decimal(base_damage) * 100 / (100 + armor))


class BattleEngine:
    """Single rules engine shared by PvE, PvP and group battles."""

    def validate(self, battle: Battle, actor_id, action: BattleAction) -> None:
        if battle.status != BattleStatus.WAITING:
            raise InvalidAction('Бой уже завершён.')
        actor = battle.participants.get(actor_id)
        if actor is None or not actor.is_alive():
            raise InvalidAction('Этот участник не может действовать.')
        if actor_id in battle.actions:
            raise InvalidAction('Действие в этом ходу уже выбрано.')
        if isinstance(action, Attack):
            target = battle.participants.get(action.target_id)
            if target is None or not target.is_alive():
                raise InvalidAction('Цель не существует или уже выбыла.')
            weapon = actor.equipment.weapon
            is_support = bool(weapon and weapon.attack_type == AttackType.SUPPORT)
            if action.mode == AttackMode.BASIC and not is_support:
                raise InvalidAction('Базовая атака отдельно доступна только саппорту.')
            should_target_ally = is_support and action.mode == AttackMode.WEAPON
            if (target.team_id == actor.team_id) != should_target_ally:
                raise InvalidAction('Для этого оружия выбрана недопустимая цель.')
        elif isinstance(action, UseSuperpower):
            if actor.equipment.superpower is None:
                raise InvalidAction('Суперсила не экипирована.')
            if battle.round_number < actor.superpower_ready_round:
                raise InvalidAction(f'Суперсила доступна с хода {actor.superpower_ready_round}.')
            target = battle.participants.get(action.target_id)
            if not target or not target.is_alive() or target.team_id != actor.team_id:
                raise InvalidAction('Пока суперсила может усиливать только живого союзника.')
        elif isinstance(action, DrinkPotion):
            if actor.equipment.potion is None or actor.potions_left == 0:
                raise InvalidAction('Нет экипированных зелий.')
            if battle.round_number < actor.potion_ready_round:
                raise InvalidAction(f'Зелье доступно с хода {actor.potion_ready_round}.')
        elif not isinstance(action, Guard):
            raise InvalidAction('Неизвестный тип действия.')

    def submit_action(self, battle: Battle, actor_id, action: BattleAction) -> list[CombatEvent]:
        self.validate(battle, actor_id, action)
        battle.actions[actor_id] = action
        if battle.ready():
            return self.resolve_turn(battle)
        return []

    def resolve_turn(self, battle: Battle) -> list[CombatEvent]:
        if not battle.ready():
            raise InvalidAction('Не все участники выбрали действия.')
        current_round = battle.round_number
        # No participant state is modified until all deltas have been computed.
        hp_delta: dict = defaultdict(int)
        buffs: list[tuple] = []
        events: list[CombatEvent] = []
        guards = {actor_id for actor_id, act in battle.actions.items() if isinstance(act, Guard)}
        actions = sorted(battle.actions.items(), key=lambda pair: str(pair[0]))

        for actor_id, action in actions:
            actor = battle.participants[actor_id]
            if isinstance(action, Guard):
                events.append(CombatEvent(f'{actor.name} защищается.', 'guard', actor_id))
            elif isinstance(action, Attack):
                target = battle.participants[action.target_id]
                weapon = actor.equipment.weapon
                support = bool(weapon and weapon.attack_type == AttackType.SUPPORT
                               and action.mode == AttackMode.WEAPON)
                if support:
                    amount = weapon.support_heal # type: ignore
                    hp_delta[target.id] += amount
                    events.append(CombatEvent(
                        f'{actor.name} поддерживает {target.name}: +{amount} HP.',
                        'heal', actor_id, target.id, amount,
                    ))
                else:
                    power = CombatCalculator.attack_power(actor, current_round, action.mode)
                    amount = CombatCalculator.damage(power, target, target.id in guards, current_round)
                    hp_delta[target.id] -= amount
                    events.append(CombatEvent(
                        f'{actor.name} атакует {target.name}: {amount} урона (до защиты {power}).',
                        'damage', actor_id, target.id, amount,
                    ))
            elif isinstance(action, DrinkPotion):
                potion = actor.equipment.potion
                assert potion is not None
                hp_delta[actor_id] += potion.heal_amount
                events.append(CombatEvent(
                    f'{actor.name} выпивает зелье: +{potion.heal_amount} HP (до ограничения).',
                    'potion_used', actor_id, actor_id, potion.heal_amount,
                ))
            elif isinstance(action, UseSuperpower):
                power = actor.equipment.superpower
                assert power is not None
                buffs.append((actor_id, action.target_id, power))
                target = battle.participants[action.target_id]
                events.append(CombatEvent(
                    f'{actor.name} применяет «{power.name}» к {target.name}. Эффект со следующего хода.',
                    'superpower', actor_id, target.id,
                ))

        # Apply all HP changes at once; there is exactly one clamp per target.
        for participant in battle.participants.values():
            if participant.is_alive():
                maximum = participant.stats(current_round).max_health
                participant.current_hp = max(0, min(maximum, participant.current_hp + hp_delta[participant.id]))

        # Expenses and cooldowns are charged even if the actor dies this turn.
        for actor_id, action in actions:
            actor = battle.participants[actor_id]
            if isinstance(action, DrinkPotion):
                actor.potions_left -= 1
                actor.potion_ready_round = current_round + actor.equipment.potion.cooldown # type: ignore
            elif isinstance(action, UseSuperpower):
                actor.superpower_ready_round = current_round + actor.equipment.superpower.cooldown # type: ignore

        for actor_id, target_id, power in buffs:
            target = battle.participants[target_id]
            if target.current_hp > 0:
                target.effects.append(ActiveEffect(
                    source_id=actor_id, bonus=power.effect_bonus,
                    starts_round=current_round + 1,
                    ends_round=current_round + power.duration,
                    name=power.name,
                ))

        battle.actions.clear()
        battle.cancel_votes.clear()
        self._finish_if_needed(battle, events)
        if battle.status == BattleStatus.WAITING:
            battle.round_number += 1
            for actor in battle.participants.values():
                actor.effects = [effect for effect in actor.effects
                                 if effect.ends_round >= battle.round_number]
        return events

    def leave(self, battle: Battle, actor_id) -> list[CombatEvent]:
        if battle.status != BattleStatus.WAITING:
            raise InvalidAction('Бой уже завершён.')
        actor = battle.participants.get(actor_id)
        if actor is None or not actor.is_alive():
            raise InvalidAction('Участник уже выбыл.')
        actor.active = False
        battle.actions.pop(actor_id, None)
        battle.cancel_votes.discard(actor_id)
        events = [CombatEvent(f'{actor.name} покидает бой.', 'leave', actor_id)]
        self._finish_if_needed(battle, events, empty_team_reason='surrender')
        # If the team remains and all remaining players have acted, resolve normally.
        if battle.ready():
            events.extend(self.resolve_turn(battle))
        return events

    def request_cancel(self, battle: Battle, actor_id) -> list[CombatEvent]:
        if battle.status != BattleStatus.WAITING:
            raise InvalidAction('Бой уже завершён.')
        actor = battle.participants.get(actor_id)
        if not actor or not actor.is_alive() or actor.controller != Controller.HUMAN:
            raise InvalidAction('Отмена доступна только активному игроку.')
        battle.cancel_votes.add(actor_id)
        voters = {p.id for p in battle.living() if p.controller == Controller.HUMAN}
        events = [CombatEvent(f'{actor.name} голосует за отмену боя.', 'cancel_vote', actor_id)]
        if voters <= battle.cancel_votes:
            battle.status = BattleStatus.CANCELLED
            battle.finish_reason = 'cancelled'
            battle.actions.clear()
            events.append(CombatEvent('Бой отменён, добыча не выдаётся.', 'cancelled'))
        return events

    @staticmethod
    def _finish_if_needed(battle: Battle, events: list[CombatEvent],
                          empty_team_reason: str = 'combat') -> None:
        teams = battle.teams_alive()
        if len(teams) > 1:
            return
        battle.status = BattleStatus.FINISHED
        battle.winner_team = next(iter(teams)) if teams else None
        battle.finish_reason = empty_team_reason
        if not teams:
            events.append(CombatEvent('Обе команды выбыли. Ничья.', 'finished'))
        else:
            events.append(CombatEvent(f'Команда {battle.winner_team} победила!', 'finished'))
