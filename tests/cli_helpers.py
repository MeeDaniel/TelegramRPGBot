"""CLI acceptance fixtures and documented stable button IDs.

Creation: name (InputButton), preset:<id>; navigation: home, back,
inventory, locations, exit. Equipment: slot:<core slot name>,
equip:<instance UUID or potion definition ID>, unequip.
Encounters: location:<catalog ID>; combat: attack, guard, power, potion, heal.
"""

from cli_adventure import Adventure
from cli_static_screen import StaticScreen


SLOTS = ('weapon', 'armor', 'accessory1', 'accessory2', 'superpower', 'potion_id')


def ids(view):
    return {button.id for button in view.buttons}
