export interface ProductCategory {
  key: string;
  label: string;
  shortLabel: string;
  keywords: string[];
  background: string;
  accent: string;
  visual: string;
}

export const PRODUCT_CATEGORIES: ProductCategory[] = [
  {
    key: 'FOOD',
    label: 'Еда',
    shortLabel: 'Еда',
    keywords: ['еда', 'продукты', 'готовая еда'],
    background: '#fff4d8',
    accent: '#d18b24',
    visual: '🍽️ 🥗',
  },
  {
    key: 'VEGETABLES_HERBS',
    label: 'Овощи, грибы и зелень',
    shortLabel: 'Овощи, зелень, грибы',
    keywords: ['овощи', 'грибы', 'зелень', 'помидоры', 'огурцы'],
    background: '#e8f7b8',
    accent: '#8fb83e',
    visual: '🥬 🍅 🥒',
  },
  {
    key: 'FRUITS_BERRIES',
    label: 'Фрукты и ягоды',
    shortLabel: 'Фрукты, ягоды',
    keywords: ['фрукты', 'ягоды', 'яблоки', 'клубника'],
    background: '#ffe2e8',
    accent: '#e44d72',
    visual: '🍓 🫐 🍎',
  },
  {
    key: 'DAIRY_EGGS',
    label: 'Молочные продукты и яйца',
    shortLabel: 'Молоко, яйца',
    keywords: ['молоко', 'сыр', 'творог', 'яйца', 'кефир'],
    background: '#d9efff',
    accent: '#5a9dcc',
    visual: '🥛 🧀 🥚',
  },
  {
    key: 'DRIED_FRUITS_NUTS',
    label: 'Сухофрукты и орехи',
    shortLabel: 'Орехи, сухофрукты',
    keywords: ['орехи', 'сухофрукты', 'курага', 'изюм'],
    background: '#fff0bf',
    accent: '#c4892b',
    visual: '🥜 🌰',
  },
  {
    key: 'MEAT_POULTRY',
    label: 'Мясо и птица',
    shortLabel: 'Мясо, птица',
    keywords: ['мясо', 'птица', 'курица', 'говядина'],
    background: '#ffe0dd',
    accent: '#d95d4d',
    visual: '🥩 🍗',
  },
  {
    key: 'FISH_SEAFOOD',
    label: 'Рыбы и морепродукты',
    shortLabel: 'Рыбы, морепродукты',
    keywords: ['рыба', 'морепродукты', 'креветки'],
    background: '#d9f4f2',
    accent: '#2f9d96',
    visual: '🐟 🦐',
  },
  {
    key: 'SAUSAGE',
    label: 'Колбаса и сосиски',
    shortLabel: 'Колбаса, сосиски',
    keywords: ['колбаса', 'сосиски', 'ветчина'],
    background: '#ffe6d9',
    accent: '#bd6842',
    visual: '🌭 🥓',
  },
  {
    key: 'PASTA_GRAINS',
    label: 'Макароны и крупы',
    shortLabel: 'Макароны, крупы',
    keywords: ['макароны', 'крупы', 'рис', 'гречка'],
    background: '#f2e8cf',
    accent: '#a98237',
    visual: '🍝 🍚',
  },
  {
    key: 'OILS_SAUCES_SPICES',
    label: 'Масло, соусы и специи',
    shortLabel: 'Масло, соусы, специи',
    keywords: ['масло', 'соусы', 'специи', 'приправы'],
    background: '#f0ead6',
    accent: '#8d7a32',
    visual: '🫒 🌶️ 🧂',
  },
  {
    key: 'CANNED_PICKLES',
    label: 'Консервы и соленья',
    shortLabel: 'Консервы, соленья',
    keywords: ['консервы', 'соленья', 'маринады'],
    background: '#dff4c8',
    accent: '#5e9f44',
    visual: '🥫 🥒',
  },
  {
    key: 'BREAD_BAKERY',
    label: 'Хлеб и выпечка',
    shortLabel: 'Хлеб, выпечка',
    keywords: ['хлеб', 'выпечка', 'булочки'],
    background: '#ffe1bc',
    accent: '#bf7b2d',
    visual: '🍞 🥐',
  },
  {
    key: 'SWEETS',
    label: 'Десерты и сладости',
    shortLabel: 'Десерты, сладости',
    keywords: ['десерты', 'сладости', 'конфеты', 'шоколад', 'печенье'],
    background: '#f3ddff',
    accent: '#a35ac9',
    visual: '🍫 🍬',
  },
  {
    key: 'JUICES_SODAS',
    label: 'Соки и газировки',
    shortLabel: 'Соки, газировки',
    keywords: ['соки', 'газировки', 'напитки', 'лимонад'],
    background: '#dff6ff',
    accent: '#2d8cc4',
    visual: '🧃 🥤',
  },
];

export const PRODUCT_CATEGORY_KEYS = PRODUCT_CATEGORIES.map((category) => category.key);

export function productCategoryLabel(key: string | null | undefined): string {
  if (!key) return 'Другое';
  return PRODUCT_CATEGORIES.find((category) => category.key === key)?.label ?? key;
}

export function productCategoryShortLabel(key: string | null | undefined): string {
  if (!key) return 'Другое';
  return PRODUCT_CATEGORIES.find((category) => category.key === key)?.shortLabel ?? productCategoryLabel(key);
}

export function productCategoryRank(key: string | null | undefined): number {
  if (!key) return 999;
  const index = PRODUCT_CATEGORY_KEYS.indexOf(key);
  return index === -1 ? 999 : index;
}

export function findProductCategory(key: string | null | undefined): ProductCategory | null {
  if (!key) return null;
  return PRODUCT_CATEGORIES.find((category) => category.key === key) ?? null;
}
