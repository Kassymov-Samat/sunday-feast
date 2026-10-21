// Справочник блюд ведического воскресного пира — вегетарианская кухня
// в духе книги Адираджа даса «Ведическое кулинарное искусство»:
// без мяса, рыбы, яиц, лука, чеснока, грибов и уксуса; основа — гхи, панир, дал, басмати, чапати, специи.
//
// Количество — НА ОДНОГО ГОСТЯ, в единицах продукта из prices.js (кг / л / шт).
// products — продукты, spices — специи (на сайте выводятся отдельным списком).
// Чтобы добавить блюдо — скопируйте любой блок и поменяйте состав; ключи продуктов — как в prices.js.
window.DISHES = [
  // ── рис и дал ──
  {
    id: "matar_pulao", name: "Матар пулао", category: "Рис и дал", emoji: "🍚",
    note: "Рис басмати с зелёным горошком, кешью и специями",
    products: { basmati: 0.08, peas: 0.03, ghee: 0.008, cashew: 0.005 },
    spices:   { cumin: 0.0008, turmeric: 0.0003, cardamom: 0.0001, cinnamon: 0.0002, bay_leaf: 0.0001, salt: 0.002 }
  },
  {
    id: "mung_dal", name: "Мунг дал", category: "Рис и дал", emoji: "🥣",
    note: "Суп из маша с имбирём, томатами и асафетидой",
    products: { mung: 0.05, tomato: 0.04, ginger: 0.003, ghee: 0.006, cilantro: 0.003, lemon: 0.01 },
    spices:   { turmeric: 0.0005, asafoetida: 0.0002, cumin: 0.0008, chili_ground: 0.0002, salt: 0.002 }
  },
  {
    id: "khichri", name: "Кичри", category: "Рис и дал", emoji: "🍲",
    note: "Рис с машем и овощами — мягкое и сытное блюдо",
    products: { basmati: 0.04, mung: 0.03, potato: 0.04, carrot: 0.03, ghee: 0.008, ginger: 0.002, cilantro: 0.002 },
    spices:   { cumin: 0.0006, turmeric: 0.0004, asafoetida: 0.0001, bay_leaf: 0.0001, salt: 0.002 }
  },
  // ── сабджи (овощные блюда) ──
  {
    id: "alu_gobi", name: "Алу гоби", category: "Сабджи", emoji: "🥔",
    note: "Цветная капуста с картофелем и специями",
    products: { cauliflower: 0.12, potato: 0.1, tomato: 0.03, ginger: 0.003, ghee: 0.012, cilantro: 0.003 },
    spices:   { turmeric: 0.0005, cumin: 0.0006, coriander: 0.0005, garam: 0.0004, asafoetida: 0.0001, chili_ground: 0.0002, salt: 0.002 }
  },
  {
    id: "matar_paneer", name: "Матар панир", category: "Сабджи", emoji: "🧀",
    note: "Панир с горошком в томатно-сливочном соусе",
    products: { paneer: 0.07, peas: 0.04, tomato: 0.06, cream: 0.02, ginger: 0.003, ghee: 0.01 },
    spices:   { garam: 0.0005, turmeric: 0.0003, coriander: 0.0005, asafoetida: 0.0001, chili_ground: 0.0002, salt: 0.002 }
  },
  {
    id: "zucchini_sabji", name: "Сабджи из кабачков и моркови", category: "Сабджи", emoji: "🥕",
    note: "Тушёные овощи с зирой и кориандром",
    products: { zucchini: 0.1, carrot: 0.05, pepper_bell: 0.05, tomato: 0.04, ghee: 0.01, cilantro: 0.002 },
    spices:   { cumin: 0.0006, coriander: 0.0005, turmeric: 0.0003, asafoetida: 0.0001, salt: 0.002 }
  },
  // ── закуски ──
  {
    id: "pakora", name: "Пакоры", category: "Закуски", emoji: "🍤",
    note: "Овощи в кляре из нутовой муки, жаренные в масле",
    products: { besan: 0.04, cauliflower: 0.04, potato: 0.04, zucchini: 0.04, oil: 0.05 },
    spices:   { turmeric: 0.0003, coriander: 0.0004, asafoetida: 0.0001, chili_ground: 0.0002, salt: 0.002 }
  },
  {
    id: "samosa", name: "Самосы", category: "Закуски", emoji: "🥟",
    note: "Пирожки с картофелем и горошком, жаренные в масле",
    products: { flour: 0.06, ghee: 0.01, potato: 0.08, peas: 0.02, ginger: 0.002, oil: 0.04, cilantro: 0.002 },
    spices:   { cumin: 0.0005, coriander: 0.0005, garam: 0.0004, asafoetida: 0.0001, chili_ground: 0.0002, salt: 0.002 }
  },
  {
    id: "vegetables", name: "Свежие овощи с лимоном", category: "Закуски", emoji: "🥒",
    note: "Огурцы, помидоры, перец, зелень",
    products: { cucumber: 0.08, tomato: 0.08, pepper_bell: 0.05, greens: 0.01, lemon: 0.01 },
    spices:   { salt: 0.0005, black_pepper: 0.0001 }
  },
  // ── хлеб ──
  {
    id: "chapati", name: "Чапати", category: "Хлеб", emoji: "🫓",
    note: "Лепёшки из цельнозерновой муки с гхи",
    products: { atta: 0.07, ghee: 0.006 },
    spices:   { salt: 0.0005 }
  },
  // ── соусы и чатни ──
  {
    id: "raita", name: "Райта из огурцов", category: "Чатни и райта", emoji: "🥛",
    note: "Йогурт с огурцами и жареной зирой",
    products: { yogurt: 0.1, cucumber: 0.06, cilantro: 0.002 },
    spices:   { cumin: 0.0005, black_pepper: 0.0002, salt: 0.001 }
  },
  {
    id: "tomato_chutney", name: "Томатный чатни", category: "Чатни и райта", emoji: "🍅",
    note: "Кисло-сладкий соус с изюмом и пряностями",
    products: { tomato: 0.05, sugar: 0.015, raisins: 0.005, ginger: 0.002, ghee: 0.003 },
    spices:   { mustard: 0.0003, chili_ground: 0.0002, cinnamon: 0.0001, cloves: 0.00005, salt: 0.0005 }
  },
  // ── сладости ──
  {
    id: "halava", name: "Халава", category: "Сладости", emoji: "🍮",
    note: "Манная халава на гхи с изюмом и кешью",
    products: { semolina: 0.04, ghee: 0.025, sugar: 0.04, milk: 0.08, raisins: 0.008, cashew: 0.006 },
    spices:   { cardamom: 0.0002 }
  },
  {
    id: "sweet_rice", name: "Сладкий рис (кхир)", category: "Сладости", emoji: "🍨",
    note: "Рис, томлённый в молоке, с кардамоном",
    products: { milk: 0.2, basmati: 0.015, sugar: 0.025, raisins: 0.005, cashew: 0.004 },
    spices:   { cardamom: 0.0002 }
  },
  {
    id: "fruits", name: "Фруктовая тарелка", category: "Сладости", emoji: "🍇",
    note: "Яблоки, виноград, мандарины, бананы",
    products: { apple: 0.1, grape: 0.08, mandarin: 0.08, banana: 0.06 },
    spices:   {}
  },
  // ── напитки ──
  {
    id: "lassi", name: "Ласси", category: "Напитки", emoji: "🥤",
    note: "Сладкий йогуртовый напиток с кардамоном",
    products: { yogurt: 0.15, sugar: 0.015, water: 0.05 },
    spices:   { cardamom: 0.0001 }
  },
  {
    id: "nimbu_pani", name: "Нимбу пани", category: "Напитки", emoji: "🍋",
    note: "Лимонад с имбирём",
    products: { lemon: 0.04, sugar: 0.02, water: 0.3, ginger: 0.002 },
    spices:   {}
  }
];

// Блюда, отмеченные при первом открытии сайта
window.DEFAULT_DISHES = ["matar_pulao", "mung_dal", "alu_gobi", "matar_paneer", "pakora", "chapati", "raita", "tomato_chutney", "halava", "fruits", "lassi"];
