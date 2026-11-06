# Архитектура игрового ядра

## Принципы

- **Composition over inheritance**: персонаж, моб и босс создают одинаковый `BattleParticipant` с комплектом `Equipment`. Нет отдельных боевых подклассов `Warrior`, `Mage`, `Slime`.
- **Single Responsibility**: `models.py` описывает состояния, `engine.py` проверяет и рассчитывает боевые переходы, `world.py` содержит генераторы встреч и добычи, `service.py` координирует сценарии. Независимый `rpg_content` владеет определениями и проверкой внешнего JSON, а `core/content_adapter.py` переводит их в боевые модели.
- **Open/Closed**: новые мобы, оружие, локации и таблицы добычи добавляются определениями в каталог. Новый тип принципиально другого эффекта потребует отдельного обработчика.
- **Dependency direction**: `engine` зависит от моделей, но не от консоли/Telegram/хранилища. Внешний код вызывает `GameService`.
- **Domain snapshots**: сражение содержит собственный набор объектов экипировки, поэтому замена снаряжения персонажа не влияет на идущий ход; во время боя смена экипировки запрещена.

`Character.slots` доступен только для чтения и содержит неизменяемый `EquippedSlots`, который запрещает повторение одного UUID предмета в нескольких слотах. `GameService.equip` проверяет владение, тип предмета и ограничения боя перед заменой набора слотов.

`Inventory.consumables` показывает общее количество расходников через отображение только для чтения. При создании PvE исходный запас выбранного зелья резервируется за ID участника без уменьшения общего количества. Обычный `consume` использует только свободный остаток; пополнения во время боя не увеличивают боевой запас. При разрешении хода участник списывает зелье из своего резерва и общего количества. Неиспользованный резерв освобождается при гибели, выходе или завершении/отмене боя. События описывают результат и не служат командами повторного списания.

## Предметы и персонажи

```mermaid
classDiagram
    direction TB
    class ItemDefinition {
        +id: str
        +name: str
        +bonus: StatBonus
    }
    class Weapon {
        +attack_type: AttackType
        +support_heal: int
    }
    class Armor {
        +guard_multiplier: float
    }
    class Accessory
    class Superpower {
        +effect_bonus: StatBonus
        +duration: int
        +cooldown: int
    }
    class Potion {
        +heal_amount: int
        +cooldown: int
    }
    class Equipment {
        +weapon: Weapon
        +armor: Armor
        +accessory1: Accessory
        +accessory2: Accessory
        +superpower: Superpower
        +potion: Potion
    }
    class Character {
        +id: UUID
        +inventory: Inventory
        +slots: EquippedSlots
    }
    class Inventory {
        +items: dict
        +consumables: Mapping
    }
    class EquippedSlots {
        +weapon: UUID
        +armor: UUID
        +accessory1: UUID
        +accessory2: UUID
        +superpower: UUID
        +potion_id: str
    }
    class ItemInstance {
        +id: UUID
        +definition_id: str
    }
    ItemDefinition <|-- Weapon
    ItemDefinition <|-- Armor
    ItemDefinition <|-- Accessory
    ItemDefinition <|-- Superpower
    ItemDefinition <|-- Potion
    Equipment o-- ItemDefinition
    Character *-- Inventory
    Character *-- EquippedSlots
    Inventory o-- ItemInstance
```

## Бой и правила

```mermaid
classDiagram
    direction TB
    class Battle {
        +id: UUID
        +participants: dict
        +actions: dict
        +round_number: int
        +status: BattleStatus
        +winner_team: str
        +ready() bool
    }
    class BattleParticipant {
        +id: UUID
        +team_id: str
        +equipment: Equipment
        +current_hp: int
        +potions_left: int
        +potion_ready_round: int
        +effects: list
        +active: bool
        +stats(round) Stats
    }
    class BattleEngine {
        +validate(battle,actor,action)
        +submit_action(battle,actor,action) events
        +resolve_turn(battle) events
        +leave(battle,actor) events
        +request_cancel(battle,actor) events
    }
    class CombatCalculator {
        +attack_power(actor,round,mode) int
        +defense_rating(target,guard,round) Decimal
        +damage(base,target,guard,round) int
    }
    class ActiveEffect {
        +bonus: StatBonus
        +starts_round: int
        +ends_round: int
    }
    class Attack {
        +target_id: UUID
        +mode: AttackMode
    }
    class Guard
    class UseSuperpower {
        +target_id: UUID
    }
    class DrinkPotion
    Battle *-- BattleParticipant
    BattleParticipant o-- ActiveEffect
    BattleParticipant --> Equipment
    BattleEngine --> Battle
    BattleEngine --> CombatCalculator
    Battle o-- Attack
    Battle o-- Guard
    Battle o-- UseSuperpower
    Battle o-- DrinkPotion
```

**Все действия коммитятся одновременно:** по начальным данным хода высчитываются атаки/хил, фиксируются дельты HP, затем они применяются *один раз*. Эффект суперсилы начинает работать на следующий ход. Команды выигрывают, если после конца хода у другой команды не осталось живых активных бойцов. При гибели обеих команд одновременно — ничья.

При переходе к следующему ходу участник удаляет истёкшие эффекты и ограничивает текущие HP новым максимумом. Уменьшение максимума не лечит и не воскрешает участника.

## Мир и application

```mermaid
classDiagram
    direction LR
    class Catalog {
        +items: dict
        +monsters: dict
        +locations: dict
        +loot_tables: dict
        +equip(spec) Equipment
    }
    class MonsterDefinition {
        +id: str
        +loadouts: dict
        +loot_table_id: str
    }
    class LocationDefinition {
        +spawns: tuple
        +rarity_weights: dict
    }
    class EncounterGenerator {
        +generate(location_id) MonsterSpawn
    }
    class LootGenerator {
        +roll(monster_id,rarity) list
    }
    class MonsterAI {
        +choose(battle,actor) BattleAction
    }
    class GameService {
        +register_character(character)
        +equip(character_id,slot,item_id)
        +create_pve(character_id,location_id) Battle
        +submit_action(battle_id,actor_id,action) events
        +leave(battle_id,actor_id) events
        +cancel(battle_id,actor_id) events
    }
    class InMemoryStore {
        +characters: dict
        +battles: dict
    }
    GameService --> Catalog
    GameService --> InMemoryStore
    GameService --> BattleEngine
    GameService --> EncounterGenerator
    GameService --> LootGenerator
    GameService --> MonsterAI
    Catalog o-- MonsterDefinition
    Catalog o-- LocationDefinition
```

`GameService` используется и из `main.py`, и будущим Telegram-адаптером. `InMemoryStore` — только первый вариант хранилища, его следует заменить реализацией Repository + Unit of Work при интеграции настоящего сервера. Для начала не стоит создавать абстрактные слои там, где нет второй реализации.

## Переход одного хода

```mermaid
sequenceDiagram
    actor Human as Пользователь
    participant App as GameService
    participant AI as MonsterAI
    participant Engine as BattleEngine
    participant Store as InMemoryStore
    Human->>App: submit_action(battle_id, actor, action)
    App->>AI: choose(current state)
    Note over AI: Не смотрит на pending actions
    App->>Engine: submit_action(...)
    Engine->>Engine: validate + add pending action
    alt Не все выбрали
        Engine-->>App: []
    else Все выбрали
        Engine->>Engine: calculate every action from round snapshot
        Engine->>Engine: combine HP deltas, clamp
        Engine->>Engine: consume potions, add next-turn buffs
        Engine->>Engine: determine winner or next round
        Engine-->>App: CombatEvent[]
    end
    App->>Store: grant finished rewards once
    App-->>Human: events and updated battle
```

В реализации `_fill_ai_actions` обычно вызывается при создании боя и после разрешения предыдущего хода, так что в обычном однопользовательском PvE ИИ уже сделал скрытый выбор до показа очередного меню.

## Следующее расширение

1. Выделить порт `BattleRepository` и транзакционный `UnitOfWork` для безопасных конкурентных запросов.
2. Описать эффекты декларативными спецификациями и добавить `EffectResolver` с явно заданными стадиями хода.
3. Расширить `UseSuperpower` с одного дружественного таргета на различные ограничения целей.
4. Добавить use-cases `create_pvp`, `create_raid`, подключение новых игроков, отображение команд, авторизацию действий и сохранение состояния.

## Независимый пакет контента

Distribution `rpg-content` (`packages/rpg_content`) содержит только стандартную
библиотеку, неизменяемые definitions, JSON parser, проверку графа, add-only merge,
контекст и CLI. Все шесть секций имеют публичные ordered read-only mappings.
Конструкторы, parser и проверка используют общие правила полей; `ContentWorld`
проверяет полный граф даже при ручном создании и защищает вложенные коллекции
defensive copies. Narrative-ссылки могут образовывать циклы без исполнения сценария.

`core.Catalog` — производная боевая проекция четырёх механических секций.
`to_catalog(world)` создаёт собственные игровые объекты и вложенные коллекции,
преобразует ссылки в ID, строки редкости/типа атаки в игровые enum. Локации
`mode=narrative`, описания, NPC и сюжет не входят в боевую проекцию; они доступны
presentation adapter через исходный world. Catalog не служит вторым источником
редактирования мира. `NpcDefinition` не хранит runtime состояние игрока и боя.

```mermaid
flowchart TD
    File["Явный путь JSON"] --> Root["main: load один раз"]
    Root --> World["ContentWorld snapshot"]
    World --> Adapter["core.content_adapter.to_catalog"]
    Adapter --> Game["GameService + Catalog"]
    World --> CLI["run_cli(world, game, support)"]
    Game --> CLI
    World --> Telegram["Будущий Telegram adapter(world, game)"]
    Game --> Telegram
```

`main` привязывает путь `content/demo.json` к `__file__`, сохраняя запуск из
другого рабочего каталога. `create_content()` остаётся обёрткой с прежней
сигнатурой, загружающей новый snapshot и возвращающей новый Catalog.
Presentation adapter читает все локации/NPC через `world.locations`, `world.npcs`,
`resolve` и `npcs_at`, а команды передаёт GameService. Transport IDs принадлежат
адаптеру/хранилищу приложения и не входят в схему контента. Реального Telegram
SDK, quest execution, runtime NPC instances и новых боевых правил пакет не вводит.

`python -m rpg_content` использует тот же публичный API, что внешний потребитель.
`context` выбирает одну секцию, явные refs/index и лимит Unicode-символов;
ресурсы правил и примеров читает сам пакет через `importlib.resources`.
Никаких обращений к нейросетевым API в runtime нет. Автор сохраняет ответ внешней
модели в отдельный JSON, проверяет `validate --base` и объединяет `merge --output`.
Примеры установки и авторского цикла находятся в README.

Мир всегда выбирается явным файлом. Wheel контента не содержит demo или `core`,
wheel игры содержит `core` и зависимость `rpg-content>=0.1,<0.2`.
Hot reload отсутствует: новый JSON используется при создании нового приложения;
существующий snapshot, игра и независимые потребители сами не обновляются.
