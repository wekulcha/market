import enum


class MealCategory(str, enum.Enum):
    FOOD = "FOOD"
    VEGETABLES_HERBS = "VEGETABLES_HERBS"
    FRUITS_BERRIES = "FRUITS_BERRIES"
    DAIRY_EGGS = "DAIRY_EGGS"
    DRIED_FRUITS_NUTS = "DRIED_FRUITS_NUTS"
    MEAT_POULTRY = "MEAT_POULTRY"
    FISH_SEAFOOD = "FISH_SEAFOOD"
    SAUSAGE = "SAUSAGE"
    PASTA_GRAINS = "PASTA_GRAINS"
    OILS_SAUCES_SPICES = "OILS_SAUCES_SPICES"
    CANNED_PICKLES = "CANNED_PICKLES"
    BREAD_BAKERY = "BREAD_BAKERY"
    SWEETS = "SWEETS"
    JUICES_SODAS = "JUICES_SODAS"

    # Legacy Kulcha categories are kept so old rows do not break reads/migrations.
    FIRST = "FIRST"
    SECOND = "SECOND"
    SOUP = "SOUP"
    SALAD = "SALAD"
    SIDE = "SIDE"
    BAKERY = "BAKERY"
    KEBAB = "KEBAB"
    GRILL = "GRILL"
    COMBO = "COMBO"
    SNACK = "SNACK"
    BREAKFAST = "BREAKFAST"
    DESSERT = "DESSERT"
    DRINK = "DRINK"
    SAUCE = "SAUCE"
    PLATTER = "PLATTER"


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    COOKING = "COOKING"
    DELIVERY = "DELIVERY"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class OrderType(str, enum.Enum):
    DELIVERY = "DELIVERY"
    DINE_IN = "DINE_IN"


class StaffPermission(str, enum.Enum):
    CAN_EDIT_MENU = "CAN_EDIT_MENU"
    CAN_LOOK_ORDERS = "CAN_LOOK_ORDERS"
