Правила locations: mode обязателен и равен encounter или narrative.
encounter требует непустой spawns: массив объектов {"monster":"monsters:id","weight":число}; weight конечное > 0, один monster не повторяется. rarity_weights обязателен: объект ровно из шести редкостей; веса конечные >= 0 и хотя бы один > 0.
narrative: spawns и rarity_weights отсутствуют или пусты; defaults [] и {}. Мирная локация не задаёт боевые встречи.
