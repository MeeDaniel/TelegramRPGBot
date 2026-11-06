Правила monsters: обязательны loadouts и loot_table. loot_table — ссылка loot_tables:id. is_boss необязателен, bool, default false.
loadouts — объект ровно из шести редкостей, без fallback. Для каждой редкости объект слотов: каждый слот необязателен, ссылка items:id соответствующего kind или null, default null. Оба accessory-слота могут ссылаться на один предмет.
potion_count — целое >= 0, default 0. При potion_count > 0 обязателен potion; при отсутствии potion количество равно 0. Базовых характеристик монстра нет: их задают предметы.
