Правила items: обязательный kind определяет разрешённые дополнительные поля; поля других kind запрещены. rarity необязательна, default common. bonus — объект бонусов, default {}.
weapon: attack_type — melee/magic/ranged/support; support_heal целое >= 0 и положительно только для support.
armor: guard_multiplier — конечное число > 0. accessory не имеет дополнительных полей.
superpower: effect_bonus имеет правила bonus; duration целое >= 1, cooldown целое >= 0.
potion: heal_amount целое >= 0, cooldown целое >= 0.
Ниже приведены разрешённые поля каждого kind, их defaults и общий список бонусов из контракта пакета.
