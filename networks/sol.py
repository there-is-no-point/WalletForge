import questionary
import ui_manager
import base58
from bip_utils import Bip32Slip10Ed25519


class NetworkGenerator:
    NAME = "Solana (SOL)"
    SYMBOL = "SOL"

    @staticmethod
    def configure():
        choice = questionary.select(
            "🟣 Выберите формат пути Solana:",
            choices=[
                questionary.Choice("Phantom / Backpack / Solflare (m/44'/501'/0'/0')", value="MODERN"),
                questionary.Choice("Sollet / Устаревший (m/44'/501'/0')", value="LEGACY"),
                questionary.Choice("Кастомный путь", value="CUSTOM"),
            ],
            style=ui_manager.custom_style
        ).ask()

        if not choice:
            return None

        custom_path = None
        if choice == "CUSTOM":
            custom_path = questionary.text(
                "Введите кастомный путь деривации (например, m/44'/501'/0'):",
                style=ui_manager.custom_style
            ).ask()
            if not custom_path:
                return None

        return {
            "mode": choice,
            "custom_path": custom_path
        }

    @staticmethod
    def generate(seed_bytes, config=None):
        mode = config.get("mode", "MODERN") if config else "MODERN"
        custom_path = config.get("custom_path") if config else None

        bip32_obj = Bip32Slip10Ed25519.FromSeed(seed_bytes)

        if mode == "MODERN":
            acc_obj = bip32_obj.DerivePath("m/44'/501'/0'/0'")
            path_str = "m/44'/501'/0'/0'"
        elif mode == "LEGACY":
            acc_obj = bip32_obj.DerivePath("m/44'/501'/0'")
            path_str = "m/44'/501'/0'"
        elif mode == "CUSTOM" and custom_path:
            acc_obj = bip32_obj.DerivePath(custom_path)
            path_str = custom_path
        else:
            acc_obj = bip32_obj.DerivePath("m/44'/501'/0'/0'")
            path_str = "m/44'/501'/0'/0'"

        from nacl.signing import SigningKey

        priv_key_bytes = acc_obj.PrivateKey().Raw().ToBytes()
        sk = SigningKey(priv_key_bytes)
        vk = sk.verify_key

        pub_bytes = vk.encode()
        priv_bytes = sk.encode()

        address = base58.b58encode(pub_bytes).decode('ascii')

        secret_key_bytes = priv_bytes + pub_bytes
        priv_key_base58 = base58.b58encode(secret_key_bytes).decode('ascii')

        return {
            "address": address,
            "private_key": priv_key_base58,
            "path": path_str,
            "type": f"Solana ({mode})"
        }

    @staticmethod
    def validate(address):
        """Проверка валидности Solana адреса."""
        try:
            decoded = base58.b58decode(address)
            if len(decoded) != 32:
                return False, f"Длина {len(decoded)} байт, ожидается 32"
            return True, "OK"
        except Exception as e:
            return False, f"Невалидный Base58: {e}"