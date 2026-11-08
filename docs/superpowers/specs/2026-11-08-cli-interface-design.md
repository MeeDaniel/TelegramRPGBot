# Independent CLI interface for the existing RPG core

Approved in chat on 2026-11-08; execution explicitly requested. This specification
supersedes the initial idea of an interface embedded in the root distribution.

## Package boundary

Create independently installable `rpg-cli` under `packages/rpg_cli/src/rpg_cli`.
Dependencies: `telegram-rpg-core>=0.1,<0.2`, `rpg-content>=0.1,<0.2`.
Core never imports CLI. CLI may use the existing core directly. No new abstract
game port, repositories, FSA dependency, Telegram or web adapters.
Every new class has its own file; existing core files are not split.

Public entry point: `run_cli(world, game, presets, default_preset_id,
default_name='Герой')`. Public `CharacterPreset(id, label, create)` contains
`create(name) -> Character`, returning a character already registered in the
supplied game with starting inventory. Call once when creation completes;
do not register twice. Validate nonempty presets, unique IDs and default ID.
Do not import main, load demo JSON, assume cwd, or hardcode demo content IDs.
Demo supplies all world loading, RNG, argument parsing and starting equipment.
Preserve `main.create_content`, `main.create_player(game,support)` (extend with
optional name), and `main.run_cli(world,game,support)` as thin compatibility
functions. Demo exposes sword and staff presets; --support selects the default.

## FSA and OOP

Session operations: view(), select(button_id), submit_input(raw), close().
Session owns current Screen and a single pending input; GameContext owns world,
game, creation draft, character and active battle. No duplicated HP/status.
Screen.view returns immutable ScreenView(text, buttons, input_prompt=None).
Button(id,label,callback) returns next Screen or None (close).
InputButton[T](id,label,prompt,parser,callback) is a separate type: parse str to T,
then call callback(T). Bad input keeps waiting without callback. One shared
pending state suffices; /back cancels input and /home follows home navigation.
Rendering is pure. ConsoleAdapter alone prints and reads; positive menu numbers
map to stable IDs; while input_prompt exists all input is data except /back and
/home. Invalid IDs/indices do not run actions. close is idempotent; EOF and
KeyboardInterrupt close the session, surrendering an active battle first.
Expected input and game errors are shown; programming errors are not swallowed.

## Screens and gameplay

NameScreen: button requests stripped nonempty name, then WeaponScreen (generic
preset selection using supplied labels). Back preserves confirmed draft name.
Home during creation finalizes with confirmed or default name and default preset.
Closing before completion creates nobody. Explicit preset selection wins.
HomeScreen: name, equipment-derived stats, six slots; inventory/locations/exit.
InventoryScreen(context,slot=None): six slots or compatible owned candidates,
remove/back/home. Hide items equipped in another slot. Distinguish duplicate
instances in labels and UUID button IDs. Potions require positive stock to select;
the selected potion with zero stock remains visible. equip via GameService.
Success returns to slot list, error retains candidate screen.
LocationsScreen: all game.catalog.locations (encounter only), descriptions from
world, button immediately creates random PvE. Empty lists explain and allow home.
BattleScreen: solo PvE only. Show HP, stats, round, effects, potion count and
cooldowns, last events; never pending hidden AI actions. Attack, guard, superpower
on self, potion; support weapon has basic enemy attack and self-heal separately.
InvalidAction does not advance round. Natural finish uses same screen for
victory/defeat/draw, loot and home. No cancel button. Home from active battle
immediately leaves without confirmation and displays defeat at home. One cleanup
operation checks WAITING before leave for home/close; core alone grants rewards.
Multiple encounters retain inventory/potions and begin at full HP. No saves,
unlock progression or settings; all encounter locations are open.

## Acceptance

Public-session tests: creation once/defaults, string and integer input/error/
back/home, invalid choices and pure render, all slots/duplicates/empty choices,
support/cooldowns, victory/defeat/draw, repeated encounters, loot once,
idempotent cleanup and EOF/interrupt. Subprocess smoke: demo UTF-8 and seed.
Install UI wheel with declared core/content dependencies in a clean environment;
run outside checkout without main or demo files using different IDs/presets.
Ensure UI wheel has no demo data and core works without CLI. No sys.path tricks.
Run complete pytest suite and independent final OOP/code review.
