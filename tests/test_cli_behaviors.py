"""Additional acceptance scenarios found at the CLI integration boundary."""

from dataclasses import replace

import pytest

from core import BattleStatus, StatBonus, Weapon
from core.world import EquipmentSpec
from rpg_cli import ConsoleAdapter, InputButton, Session
from cli_helpers import Adventure, StaticScreen, ids


@pytest.mark.parametrize('command', ['home', 'back'])
def test_public_navigation_works_while_name_input_is_pending(command):
    adventure = Adventure()
    adventure.session.select('name')
    view = adventure.session.select(command)
    assert view.input_prompt is None
    if command == 'home':
        assert len(adventure.created) == 1
        assert adventure.character.name == 'Герой'
        assert 'inventory' in ids(view)
    else:
        assert not adventure.created
        assert 'name' in ids(view)


def test_console_pending_input_explains_commands_without_numeric_menu():
    adventure = Adventure()
    output = []
    pending_output = []
    reads = 0
    checkpoint = 0
    def read(prompt):
        nonlocal reads, checkpoint
        reads += 1
        if reads == 1:
            checkpoint = len(output)
            return '1'
        pending_output.extend(output[checkpoint:])
        raise EOFError()
    ConsoleAdapter(adventure.session, read=read, write=output.append).run()
    text = '\n'.join(pending_output)
    assert '/back' in text and '/home' in text
    assert not any(line.startswith('[1]') for line in pending_output)


def test_active_battle_home_label_explains_surrender():
    adventure = Adventure()
    adventure.home()
    adventure.battle()
    home = next(button for button in adventure.session.view().buttons if button.id == 'home')
    assert 'сда' in home.label.lower()


def test_input_callback_value_error_is_not_mistaken_for_bad_input():
    def broken(value):
        raise ValueError('callback defect')
    session = Session(StaticScreen(buttons=(InputButton('value', 'Value', 'Value?', int, broken),)))
    session.select('value')
    with pytest.raises(ValueError, match='callback defect'):
        session.submit_input('7')


def test_close_callback_runs_once_and_closed_session_stays_closed():
    events = []
    session = Session(StaticScreen(), on_close=lambda: events.append('closed'))
    session.close()
    session.close()
    assert events == ['closed']
    assert session.select('unknown') is None
    assert session.submit_input('data') is None


def test_power_targets_self_and_cooldown_rejection_keeps_round():
    adventure = Adventure()
    adventure.home()
    battle, hero, enemy = adventure.battle()
    adventure.session.select('power')
    assert hero.effects
    assert not enemy.effects
    before = battle.round_number
    effects = list(hero.effects)
    adventure.session.select('power')
    assert battle.round_number == before
    assert hero.effects == effects
    assert 'Суперсила' in adventure.session.view().text


@pytest.mark.parametrize('outcome, label', [('defeat', 'ПОРАЖЕНИЕ!'), ('draw', 'НИЧЬЯ!')])
def test_natural_terminal_result_preserves_finished_screen(outcome, label):
    adventure = Adventure()
    weapon = Weapon(id='terminal_weapon', name='Оружие испытания',
                    bonus=StatBonus(melee_damage=10000,
                                    max_health=10000 if outcome == 'defeat' else 0))
    adventure.game.catalog.items[weapon.id] = weapon
    for key, monster in tuple(adventure.game.catalog.monsters.items()):
        adventure.game.catalog.monsters[key] = replace(monster, loadouts={
            rarity: EquipmentSpec(weapon=weapon.id) for rarity in monster.loadouts})
    adventure.home()
    if outcome == 'draw':
        item_id = adventure.character.inventory.add_item(weapon.id)
        adventure.game.equip(adventure.character.id, 'weapon', item_id)
    battle, _, _ = adventure.battle()
    for _ in range(10):
        if battle.status != BattleStatus.WAITING:
            break
        adventure.session.select('attack')
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == (battle.enemy_team if outcome == 'defeat' else None)
    view = adventure.session.view()
    assert label in view.text
    assert ids(view) == {'home'}
    assert not battle.drops
    adventure.session.close()
    assert battle.finish_reason != 'surrender'


def test_equipment_error_retains_candidate_screen_and_slot():
    adventure = Adventure()
    adventure.home()
    spare = adventure.character.inventory.add_item('steel_sword')
    original = adventure.character.slots.weapon
    adventure.session.select('inventory')
    adventure.session.select('slot:weapon')
    # A real core constraint rejects this stale screen after another caller starts PvE.
    battle = adventure.game.create_pve(adventure.character.id, next(iter(adventure.game.catalog.locations)))
    view = adventure.session.select(f'equip:{spare}')
    assert adventure.character.slots.weapon == original
    assert f'equip:{spare}' in ids(view)
    assert 'slot:armor' not in ids(view)
    hero = next(p for p in battle.participants.values() if p.character_id is not None)
    adventure.game.leave(battle.id, hero.id)


def test_empty_equipment_candidates_allow_back_and_home():
    adventure = Adventure()
    adventure.home()
    weapon_id = adventure.character.slots.weapon
    adventure.game.equip(adventure.character.id, 'weapon', None)
    del adventure.character.inventory.items[weapon_id]
    adventure.session.select('inventory')
    view = adventure.session.select('slot:weapon')
    assert not any(button.id.startswith('equip:') for button in view.buttons)
    assert {'back', 'home'} <= ids(view)
    assert 'slot:weapon' in ids(adventure.session.select('back'))
    assert 'inventory' in ids(adventure.session.select('home'))


@pytest.mark.parametrize('slot, definition', [
    ('weapon', 'steel_sword'), ('armor', 'travel_armor'),
    ('accessory1', 'power_ring'), ('accessory2', 'power_ring'),
    ('superpower', 'battle_rage'), ('potion_id', 'healing_potion'),
])
def test_each_equipment_slot_changes_real_core_selection(slot, definition):
    adventure = Adventure()
    adventure.home()
    adventure.game.equip(adventure.character.id, slot, None)
    candidate = definition if slot == 'potion_id' else adventure.character.inventory.add_item(definition)
    adventure.session.select('inventory')
    view = adventure.session.select(f'slot:{slot}')
    assert f'equip:{candidate}' in ids(view)
    view = adventure.session.select(f'equip:{candidate}')
    assert getattr(adventure.character.slots, slot) == candidate
    assert 'slot:armor' in ids(view)
