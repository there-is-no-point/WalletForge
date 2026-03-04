import questionary
import ui_manager
from bip_utils import (
    Bip44, Bip44Coins, Monero, MoneroCoins, MoneroLanguages,
    MoneroMnemonicGenerator, MoneroWordsNum, MoneroSeedGenerator
)


# === МАППИНГ ЯЗЫКОВ ===

LEGACY_LANGUAGES = {
    "🇺🇸 English": MoneroLanguages.ENGLISH,
    "🇨🇳 Chinese (Simplified)": MoneroLanguages.CHINESE_SIMPLIFIED,
    "🇳🇱 Dutch": MoneroLanguages.DUTCH,
    "🇫🇷 French": MoneroLanguages.FRENCH,
    "🇩🇪 German": MoneroLanguages.GERMAN,
    "🇮🇹 Italian": MoneroLanguages.ITALIAN,
    "🇯🇵 Japanese": MoneroLanguages.JAPANESE,
    "🇵🇹 Portuguese": MoneroLanguages.PORTUGUESE,
    "🇷🇺 Russian": MoneroLanguages.RUSSIAN,
    "🇪🇸 Spanish": MoneroLanguages.SPANISH,
}

# Polyseed: модуль → (label, lang_module, lang_class_name)
POLYSEED_LANGUAGES = {
    "🇺🇸 English": ("polyseed.lang_en", "LanguageEnglish"),
    "🇨🇳 Chinese (Simplified)": ("polyseed.lang_zh_s", "LanguageChineseSimplified"),
    "🇨🇳 Chinese (Traditional)": ("polyseed.lang_zh_t", "LanguageChineseTraditional"),
    "🇨🇿 Czech": ("polyseed.lang_cs", "LanguageCzech"),
    "🇫🇷 French": ("polyseed.lang_fr", "LanguageFrench"),
    "🇮🇹 Italian": ("polyseed.lang_it", "LanguageItalian"),
    "🇯🇵 Japanese": ("polyseed.lang_jp", "LanguageJapanese"),
    "🇰🇷 Korean": ("polyseed.lang_ko", "LanguageKorean"),
    "🇵🇹 Portuguese": ("polyseed.lang_pt", "LanguagePortuguese"),
    "🇪🇸 Spanish": ("polyseed.lang_es", "LanguageSpanish"),
}


class NetworkGenerator:
    NAME = "Monero (XMR)"
    SYMBOL = "XMR"
    CUSTOM_MNEMONIC = True

    @staticmethod
    def select_mnemonic():
        """Кастомный выбор мнемоники вместо стандартного 12/15/18/24."""
        choice = questionary.select(
            "Тип мнемоники:",
            choices=[
                questionary.Choice("BIP39 (12 слов) — Совместим с Cake Wallet", value="bip39"),
                questionary.Choice("Polyseed (16 слов) — Новый формат Monero", value="polyseed"),
                questionary.Choice("Legacy (25 слов) — Нативный Monero, совместим со всеми XMR-кошельками", value="legacy"),
            ],
            style=ui_manager.custom_style
        ).ask()
        if not choice:
            return None

        config = {"mnemonic_type": choice}

        # Выбор языка для Polyseed и Legacy
        if choice == "legacy":
            lang = questionary.select(
                "Язык мнемоники:",
                choices=list(LEGACY_LANGUAGES.keys()),
                style=ui_manager.custom_style
            ).ask()
            if not lang:
                return None
            config["language"] = lang

        elif choice == "polyseed":
            lang = questionary.select(
                "Язык мнемоники:",
                choices=list(POLYSEED_LANGUAGES.keys()),
                style=ui_manager.custom_style
            ).ask()
            if not lang:
                return None
            config["language"] = lang

        return config

    @staticmethod
    def generate(seed_bytes, config=None):
        mnemonic_type = config.get("mnemonic_type", "bip39") if config else "bip39"
        language = config.get("language", "🇺🇸 English") if config else "🇺🇸 English"

        try:
            if mnemonic_type == "legacy":
                return NetworkGenerator._generate_legacy(language)
            elif mnemonic_type == "polyseed":
                return NetworkGenerator._generate_polyseed(language)
            else:
                return NetworkGenerator._generate_bip39(seed_bytes)
        except Exception as e:
            ui_manager.print_error(f"Monero Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def _generate_bip39(seed_bytes):
        """BIP39 режим: BIP44 secp256k1 деривация (Cake Wallet compatible)."""
        bip44 = Bip44.FromSeed(seed_bytes, Bip44Coins.MONERO_SECP256K1)
        derived = bip44.DeriveDefaultPath()
        priv_key = derived.PrivateKey().Raw().ToBytes()
        xmr = Monero.FromSeed(priv_key, MoneroCoins.MONERO_MAINNET)

        return {
            "address": str(xmr.PrimaryAddress()),
            "private_key": xmr.PrivateSpendKey().Raw().ToHex(),
            "view_key": xmr.PrivateViewKey().Raw().ToHex(),
            "path": "m/44'/128'/0'/0/0",
            "type": "Monero (BIP39 / Cake Wallet)"
        }

    @staticmethod
    def _generate_polyseed(language="🇺🇸 English"):
        """Polyseed режим: 16-словная мнемоника с встроенной датой."""
        import importlib
        from polyseed import generate as ps_generate

        # Регистрация выбранного языка
        mod_name, cls_name = POLYSEED_LANGUAGES.get(language, ("polyseed.lang_en", "LanguageEnglish"))
        mod = importlib.import_module(mod_name)
        lang_cls = getattr(mod, cls_name)
        lang_cls.register()

        ps = ps_generate()
        key = ps.keygen()
        phrase = ps.encode(lang_cls)

        xmr = Monero.FromSeed(key, MoneroCoins.MONERO_MAINNET)

        return {
            "address": str(xmr.PrimaryAddress()),
            "private_key": xmr.PrivateSpendKey().Raw().ToHex(),
            "view_key": xmr.PrivateViewKey().Raw().ToHex(),
            "mnemonic": phrase,
            "type": "Monero (Polyseed 16-word)"
        }

    @staticmethod
    def _generate_legacy(language="🇺🇸 English"):
        """Legacy режим: нативная 25-словная Monero мнемоника."""
        lang_enum = LEGACY_LANGUAGES.get(language, MoneroLanguages.ENGLISH)
        mn = MoneroMnemonicGenerator(lang_enum).FromWordsNumber(MoneroWordsNum.WORDS_NUM_25)
        mn_str = str(mn)

        seed = MoneroSeedGenerator(mn, lang_enum).Generate()
        xmr = Monero.FromSeed(seed, MoneroCoins.MONERO_MAINNET)

        return {
            "address": str(xmr.PrimaryAddress()),
            "private_key": xmr.PrivateSpendKey().Raw().ToHex(),
            "view_key": xmr.PrivateViewKey().Raw().ToHex(),
            "mnemonic": mn_str,
            "type": "Monero (Legacy 25-word)"
        }

    @staticmethod
    def validate(address):
        """Проверка валидности Monero адреса."""
        if not address:
            return False, "Пустой адрес"
        if len(address) != 95:
            return False, f"Длина {len(address)}, ожидается 95"
        if address[0] not in ('4', '8'):
            return False, f"Должен начинаться с 4 или 8, получено: {address[0]}"
        return True, "OK"
