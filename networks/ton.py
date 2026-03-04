import questionary
import ui_manager
from bip_utils import Bip32Slip10Ed25519
from nacl.signing import SigningKey
from tonsdk.contract.wallet import WalletVersionEnum, Wallets


class NetworkGenerator:
    NAME = "TON (Toncoin)"
    SYMBOL = "TON"

    # Доступные версии кошельков
    WALLET_VERSIONS = {
        "v4R2": WalletVersionEnum.v4r2,
        "v3R2": WalletVersionEnum.v3r2,
        "v3R1": WalletVersionEnum.v3r1,
    }

    @staticmethod
    def configure():
        choice = questionary.select(
            "🔷 Выберите версию кошелька TON:",
            choices=[
                questionary.Choice("Wallet v4R2 — Рекомендуется (Tonkeeper, MyTonWallet)", value="v4R2"),
                questionary.Choice("Wallet v3R2 — Старый стандарт", value="v3R2"),
                questionary.Choice("Wallet v3R1 — Устаревший", value="v3R1"),
            ],
            style=ui_manager.custom_style
        ).ask()

        if not choice:
            return None

        return {"wallet_version": choice}

    @staticmethod
    def generate(seed_bytes, config=None):
        """
        TON с BIP39 мнемоникой использует:
        - Ed25519 (SLIP-0010) для ключей
        - Путь деривации: m/44'/607'/0'
        - Адрес = хэш StateInit контракта кошелька + публичный ключ
        - Адрес зависит от версии контракта (v3r1/v3r2/v4r2)
        Совместимо с Tonkeeper при импорте BIP39 мнемоники.
        """
        version_name = config.get("wallet_version", "v4R2") if config else "v4R2"
        wallet_version = NetworkGenerator.WALLET_VERSIONS.get(version_name, WalletVersionEnum.v4r2)

        try:
            # 1. Ed25519 SLIP-0010 деривация
            bip32 = Bip32Slip10Ed25519.FromSeed(seed_bytes)
            key = bip32.DerivePath("m/44'/607'/0'")
            priv_key_bytes = key.PrivateKey().Raw().ToBytes()

            # 2. Вычисление публичного ключа через PyNaCl
            sk = SigningKey(priv_key_bytes)
            pub_key_bytes = sk.verify_key.encode()

            # 3. Создание кошелька через tonsdk
            WalletClass = Wallets.ALL[wallet_version]
            wallet = WalletClass(public_key=pub_key_bytes, private_key=priv_key_bytes, wc=0)

            # 4. Адрес в user-friendly формате (non-bounceable — как в Tonkeeper)
            address = wallet.address.to_string(True, True, False)

            return {
                "address": address,
                "private_key": priv_key_bytes.hex(),
                "public_key": pub_key_bytes.hex(),
                "path": "m/44'/607'/0'",
                "type": f"TON (Wallet {version_name})"
            }
        except Exception as e:
            ui_manager.print_error(f"TON Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def validate(address):
        """Проверка валидности TON адреса (user-friendly формат)."""
        if not address:
            return False, "Пустой адрес"
        # User-friendly формат: EQ... или UQ... (base64url, 48 символов)
        if not (address.startswith("EQ") or address.startswith("UQ")):
            return False, f"Ожидается EQ или UQ, получено: {address[:3]}"
        if len(address) != 48:
            return False, f"Длина {len(address)}, ожидается 48"
        return True, "OK"
