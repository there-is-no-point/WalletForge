import os
import json
import requests
import questionary
import ui_manager

# Проверка наличия библиотеки
try:
    from substrateinterface import Keypair, KeypairType

    HAS_SUBSTRATE_LIB = True
except ImportError:
    HAS_SUBSTRATE_LIB = False

DATA_DIR = "data"
REGISTRY_FILE = os.path.join(DATA_DIR, "polkadot_registry.json")
REGISTRY_URL = "https://raw.githubusercontent.com/paritytech/ss58-registry/main/ss58-registry.json"


def load_registry():
    networks = {}
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for net in data.get("registry", []):
                    name = net.get("displayName", net.get("network"))
                    prefix = net.get("prefix")
                    if name and prefix is not None:
                        networks[f"{name} (ID:{prefix})"] = prefix
        except:
            pass
    return networks


def update_registry():
    ui_manager.print_info("Скачивание реестра ParityTech...")
    try:
        resp = requests.get(REGISTRY_URL, timeout=10)
        if resp.status_code != 200: return False, "Ошибка сервера"
        new_data = resp.json().get("registry", [])

        if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump({"registry": new_data}, f, indent=2)
        return True, f"Загружено {len(new_data)} сетей"
    except Exception as e:
        return False, str(e)


class NetworkGenerator:
    NAME = "Polkadot Ecosystem (Universal)"
    SYMBOL = "DOT"

    @staticmethod
    def configure():
        if not HAS_SUBSTRATE_LIB:
            ui_manager.print_error("Не установлена библиотека 'substrate-interface'!")
            ui_manager.print_info("pip install substrate-interface")
            return None

        action = questionary.select(
            "⚙️ Настройка Polkadot:",
            choices=[
                "🔍 Выбрать сеть из списка",
                "🔄 Обновить реестр (Интернет)",
                "🛠 Ввести ID вручную"
            ],
            style=ui_manager.custom_style
        ).ask()

        if not action: return None

        config = {"prefix": 0, "network_name": "Polkadot", "symbol": "DOT"}

        if "Обновить" in action:
            ok, msg = update_registry()
            if ok:
                ui_manager.print_success(msg)
            else:
                ui_manager.print_error(msg)
            return NetworkGenerator.configure()

        elif "Выбрать" in action:
            nets = load_registry()
            if not nets:
                ui_manager.print_error("Реестр пуст. Сначала обновите его.")
                return NetworkGenerator.configure()

            choice = questionary.autocomplete("Поиск сети:", choices=sorted(nets.keys()),
                                              style=ui_manager.custom_style).ask()
            if choice:
                config["prefix"] = nets[choice]
                config["network_name"] = choice.split(" (")[0]
                config["symbol"] = config["network_name"][:4].upper()
                return config

        elif "Ввести ID" in action:
            pid = questionary.text("SS58 Prefix (ID):", validate=lambda x: x.isdigit(),
                                   style=ui_manager.custom_style).ask()
            name = questionary.text("Название сети:", default="Custom", style=ui_manager.custom_style).ask()
            if pid:
                config["prefix"] = int(pid)
                config["network_name"] = name
                config["symbol"] = name[:4].upper()
                return config

        return config

    @staticmethod
    def generate(seed_bytes, config=None, mnemonic=None):
        """
        Теперь принимает mnemonic (строку). Это критично для совместимости с Talisman.
        """
        if not HAS_SUBSTRATE_LIB:
            return {"error": "No substrate-interface lib"}

        if not config: config = {"prefix": 0, "network_name": "Polkadot"}
        prefix = config.get("prefix", 0)

        try:
            # ЕСЛИ ЕСТЬ МНЕМОНИКА (Пришла из нового main.py)
            if mnemonic:
                kp = Keypair.create_from_mnemonic(
                    mnemonic=mnemonic,
                    ss58_format=prefix,
                    crypto_type=KeypairType.SR25519
                )

            # ЕСЛИ НЕТ (Fallback, на всякий случай)
            else:
                # Берем 32 байта, как раньше, но это менее надежно для Sr25519
                seed_32 = seed_bytes[:32]
                kp = Keypair.create_from_seed(
                    seed_hex=seed_32,
                    ss58_format=prefix,
                    crypto_type=KeypairType.SR25519
                )

            return {
                "address": kp.ss58_address,
                "private_key": kp.private_key.hex(),
                "public_key": kp.public_key.hex(),
                "ss58_prefix": prefix,
                "type": f"{config.get('network_name')} (Sr25519 / Mnemonic)"
            }
        except Exception as e:
            ui_manager.print_error(f"Polkadot Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def validate(address, config=None):
        """Проверка валидности SS58 адреса через substrate-interface."""
        if not HAS_SUBSTRATE_LIB:
            # Без библиотеки — базовая проверка длины
            if len(address) < 46 or len(address) > 48:
                return False, f"Невалидная длина SS58: {len(address)}"
            return True, "OK (без глубокой проверки)"
        try:
            # SS58 decode проверяет чексумму автоматически
            kp = Keypair(ss58_address=address)
            return True, "OK"
        except Exception as e:
            return False, f"Невалидный SS58 адрес: {e}"