"""Public CLI contract: real session transitions and real core side effects."""

from dataclasses import FrozenInstanceError

import pytest

from core import BattleStatus
from rpg_cli import Button, ConsoleAdapter, InputButton, Session, create_session
from cli_helpers import Adventure, SLOTS, StaticScreen, ids


def test_custom_screen_buttons_transition_and_close():
    destination = StaticScreen('Destination')
    session = Session(StaticScreen(buttons=(
        Button('next', 'Next', lambda: destination),)))
    assert session.select('next').text == 'Destination'
    session.close()
    assert session.view() is None


def test_render_does_not_execute_actions_or_create_character():
    adventure = Adventure()
    first = adventure.session.view()
    assert adventure.session.view() == first
    assert not adventure.game.store.characters
    assert not adventure.created


def test_screen_view_is_immutable():
    view = StaticScreen().view()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        view.text = 'Changed'


def test_invalid_button_does_not_execute_action():
    destination = StaticScreen('Action executed')
    session = Session(StaticScreen('Original', (Button('valid', 'Go', lambda: destination),)))
    session.select('missing')
    assert 'valid' in ids(session.view())
    assert 'Action executed' not in session.view().text


def test_integer_input_is_parsed_before_callback():
    session = Session(StaticScreen(buttons=(InputButton(
        'number', 'Number', 'How many?', int,
        lambda number: StaticScreen(f'{number + 1}')),)))
    assert session.select('number').input_prompt == 'How many?'
    session.submit_input(' 41 ')
    assert session.view().text == '42'
    assert session.view().input_prompt is None


def test_bad_integer_keeps_pending_until_valid_input():
    session = Session(StaticScreen(buttons=(InputButton(
        'number', 'Number', 'How many?', int,
        lambda number: StaticScreen(f'Accepted {number}')),)))
    session.select('number')
    session.submit_input('not an integer')
    assert session.view().input_prompt == 'How many?'
    assert 'Accepted' not in session.view().text
    assert session.submit_input('7').text == 'Accepted 7'


def test_programming_errors_are_not_swallowed():
    def broken():
        raise RuntimeError('programming error')
    session = Session(StaticScreen(buttons=(Button('broken', 'Broken', broken),)))
    with pytest.raises(RuntimeError, match='programming error'):
        session.select('broken')


def test_creation_strips_name_and_registers_exactly_once():
    adventure = Adventure()
    session = adventure.session
    session.select('name')
    session.submit_input('  Алиса  ')
    session.select('preset:sword')
    session.view()
    session.select('home')
    assert adventure.character.name == 'Алиса'
    assert len(adventure.created) == len(adventure.game.store.characters) == 1


def test_blank_name_stays_pending_without_creation():
    adventure = Adventure()
    adventure.session.select('name')
    adventure.session.submit_input('   ')
    assert adventure.session.view().input_prompt
    assert not adventure.created


def test_back_preserves_confirmed_name():
    adventure = Adventure()
    adventure.session.select('name')
    adventure.session.submit_input('Лея')
    adventure.session.select('back')
    adventure.home()
    assert adventure.character.name == 'Лея'


def test_back_cancels_pending_input_without_callback():
    adventure = Adventure()
    adventure.session.select('name')
    adventure.session.submit_input('/back')
    assert adventure.session.view().input_prompt is None
    assert not adventure.created
    adventure.home()
    assert adventure.character.name == 'Герой'


def test_home_during_pending_input_uses_defaults():
    adventure = Adventure(default='staff', default_name='Странник')
    adventure.session.select('name')
    adventure.session.submit_input('/home')
    assert adventure.character.name == 'Странник'
    assert adventure.game.character_equipment(adventure.character).weapon.id == 'healing_staff'


def test_explicit_preset_overrides_default():
    adventure = Adventure(default='staff')
    adventure.session.select('name')
    adventure.session.submit_input('Воин')
    adventure.session.select('preset:sword')
    assert adventure.game.character_equipment(adventure.character).weapon.id == 'steel_sword'


def test_close_before_creation_creates_nobody():
    adventure = Adventure()
    adventure.session.select('name')
    adventure.session.close()
    assert not adventure.game.store.characters
    assert adventure.session.view() is None


@pytest.mark.parametrize('kind', ['empty', 'duplicate', 'unknown-default'])
def test_invalid_preset_configuration_is_rejected(kind):
    adventure = Adventure()
    presets = [] if kind == 'empty' else list(adventure.presets)
    if kind == 'duplicate':
        presets.append(presets[0])
    default = 'absent' if kind == 'unknown-default' else 'sword'
    with pytest.raises(ValueError):
        create_session(adventure.world, adventure.game, presets, default)


def test_home_and_inventory_expose_all_six_slots():
    adventure = Adventure()
    view = adventure.home()
    assert adventure.character.name in view.text
    assert {'inventory', 'locations', 'exit'} <= ids(view)
    view = adventure.session.select('inventory')
    assert {f'slot:{slot}' for slot in SLOTS} <= ids(view)


def test_duplicate_instances_are_distinct_and_other_slot_is_hidden():
    adventure = Adventure()
    adventure.home()
    character = adventure.character
    duplicate = character.inventory.add_item('power_ring')
    adventure.session.select('inventory')
    view = adventure.session.select('slot:accessory2')
    assert f'equip:{character.slots.accessory1}' not in ids(view)
    assert f'equip:{duplicate}' in ids(view)
    adventure.session.select(f'equip:{duplicate}')
    assert character.slots.accessory2 == duplicate
    adventure.session.select('slot:accessory1')
    view = adventure.session.view()
    assert f'equip:{duplicate}' not in ids(view)


def test_duplicate_candidate_labels_distinguish_instances():
    adventure = Adventure()
    adventure.home()
    first = adventure.character.inventory.add_item('steel_sword')
    second = adventure.character.inventory.add_item('steel_sword')
    adventure.session.select('inventory')
    view = adventure.session.select('slot:weapon')
    labels = {button.id: button.label for button in view.buttons}
    assert labels[f'equip:{first}'] != labels[f'equip:{second}']


def test_unequip_changes_core_and_returns_slot_list():
    adventure = Adventure()
    adventure.home()
    adventure.session.select('inventory')
    adventure.session.select('slot:weapon')
    view = adventure.session.select('unequip')
    assert adventure.character.slots.weapon is None
    assert 'slot:armor' in ids(view)


def test_selected_zero_stock_potion_visible_but_unowned_potion_hidden():
    adventure = Adventure()
    adventure.home()
    inventory = adventure.character.inventory
    inventory.consume('healing_potion', 3)
    adventure.session.select('inventory')
    view = adventure.session.select('slot:potion_id')
    potion_name = adventure.game.catalog.items['healing_potion'].name
    assert potion_name in view.text or any(potion_name in b.label for b in view.buttons)
    assert 'unequip' in ids(view)
    assert not any(button.id.startswith('equip:') for button in view.buttons)


def test_empty_locations_explain_and_allow_home():
    adventure = Adventure(empty_locations=True)
    adventure.home()
    view = adventure.session.select('locations')
    assert view.text.strip()
    assert 'home' in ids(view)
    assert not any(button.id.startswith('location:') for button in view.buttons)


def test_location_opens_pve_and_render_does_not_advance_round():
    adventure = Adventure()
    adventure.home()
    battle, hero, enemy = adventure.battle()
    before = (battle.round_number, hero.current_hp, enemy.current_hp, dict(battle.actions))
    for _ in range(3):
        view = adventure.session.view()
    assert {'attack', 'guard', 'power', 'potion', 'home'} <= ids(view)
    assert not {'cancel', 'back'} & ids(view)
    assert (battle.round_number, hero.current_hp, enemy.current_hp, dict(battle.actions)) == before


def test_home_surrenders_active_battle_and_close_is_idempotent():
    adventure = Adventure()
    adventure.home()
    battle, _, _ = adventure.battle()
    view = adventure.home()
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == battle.enemy_team
    assert 'поражен' in view.text.lower() or 'поражён' in view.text.lower()
    adventure.session.close()
    adventure.session.close()
    assert battle.finish_reason == 'surrender'
    assert adventure.session.view() is None


def test_potion_cooldown_error_does_not_advance_round_or_consume():
    adventure = Adventure()
    adventure.home()
    battle, hero, _ = adventure.battle()
    adventure.session.select('potion')
    assert hero.potions_left == 2
    assert adventure.character.inventory.consumables['healing_potion'] == 2
    round_number = battle.round_number
    adventure.session.select('potion')
    assert battle.round_number == round_number
    assert hero.potions_left == 2
    assert adventure.session.view().text.strip()


def test_repeated_encounters_keep_stock_and_start_at_full_hp():
    adventure = Adventure()
    adventure.home()
    first, _, _ = adventure.battle()
    adventure.session.select('potion')
    adventure.home()
    second, hero, _ = adventure.battle()
    assert second.id != first.id
    assert hero.current_hp == hero.stats(1).max_health
    assert hero.potions_left == 2


def test_finished_victory_is_stable_and_rewards_are_not_repeated():
    adventure = Adventure()
    adventure.home()
    battle, _, _ = adventure.battle()
    for _ in range(100):
        if battle.status != BattleStatus.WAITING:
            break
        adventure.session.select('attack')
    assert battle.status == BattleStatus.FINISHED
    assert battle.winner_team == battle.player_team
    before = (dict(adventure.character.inventory.items), dict(adventure.character.inventory.consumables))
    view = adventure.session.view()
    assert 'побед' in view.text.lower()
    assert 'home' in ids(view)
    adventure.session.select('attack')
    adventure.home()
    assert (dict(adventure.character.inventory.items), dict(adventure.character.inventory.consumables)) == before


def test_support_has_enemy_attack_and_separate_self_heal():
    adventure = Adventure(default='staff')
    adventure.home()
    battle, hero, enemy = adventure.battle()
    assert 'heal' in ids(adventure.session.view())
    enemy_hp = enemy.current_hp
    adventure.session.select('attack')
    assert enemy.current_hp < enemy_hp
    hero.current_hp = 20
    adventure.session.select('heal')
    assert hero.current_hp > 20
    assert battle.round_number == 3


@pytest.mark.parametrize('interrupt', [EOFError, KeyboardInterrupt])
def test_console_interrupt_closes_and_surrenders(interrupt):
    adventure = Adventure()
    adventure.home()
    battle, _, _ = adventure.battle()
    output = []
    def read(prompt):
        raise interrupt()
    ConsoleAdapter(adventure.session, read=read, write=output.append).run()
    assert battle.status == BattleStatus.FINISHED
    assert battle.finish_reason == 'surrender'
    assert adventure.session.view() is None
    assert output


def test_console_maps_numbers_but_preserves_numbers_during_text_input():
    destination = StaticScreen('Saved 123', (Button('exit', 'Exit', lambda: None),))
    session = Session(StaticScreen(buttons=(InputButton(
        'name', 'Name', 'Name?', str,
        lambda value: destination if value == '123' else StaticScreen('Wrong name')),)))
    answers = iter(['0', '-1', '99', '1', '123', '1'])
    output = []
    ConsoleAdapter(session, read=lambda prompt: next(answers), write=output.append).run()
    assert any('Saved 123' in line for line in output)
    assert session.view() is None
