# drinks.py

BASE_ASSET_PATH = "assets"

drink_list = [
    {
        "name": "Rum & Coke",
        "image": f"{BASE_ASSET_PATH}/rum_and_coke.png",
        "ingredients": {"rum": 50, "coke": 150}
    },
    {
        "name": "Gin & Tonic",
        "image": f"{BASE_ASSET_PATH}/gin_and_tonic.png",
        "ingredients": {"gin": 50, "tonic": 150}
    },
    {
        "name": "Long Island",
        "image": f"{BASE_ASSET_PATH}/long_island.png",
        "ingredients": {
            "gin": 15, "rum": 15, "vodka": 15,
            "tequila": 15, "coke": 100, "oj": 30
        }
    },
    {
        "name": "Screwdriver",
        "image": f"{BASE_ASSET_PATH}/screwdriver.png",
        "ingredients": {"vodka": 50, "oj": 150}
    },
    {
        "name": "Margarita",
        "image": f"{BASE_ASSET_PATH}/margarita.png",
        "ingredients": {"tequila": 50, "mmix": 150}
    },
    {
        "name": "Gin & Juice",
        "image": f"{BASE_ASSET_PATH}/gin_and_juice.png",
        "ingredients": {"gin": 50, "oj": 150}
    },
    {
        "name": "Tequila Sunrise",
        "image": f"{BASE_ASSET_PATH}/tequila_sunrise.png",
        "ingredients": {"tequila": 50, "oj": 150}
    }
]

drink_options = [
    {"name": "Gin", "value": "gin"},
    {"name": "Rum", "value": "rum"},
    {"name": "Vodka", "value": "vodka"},
    {"name": "Tequila", "value": "tequila"},
    {"name": "Tonic Water", "value": "tonic"},
    {"name": "Coke", "value": "coke"},
    {"name": "Orange Juice", "value": "oj"},
    {"name": "Margarita Mix", "value": "mmix"}
]
