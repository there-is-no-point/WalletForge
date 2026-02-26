import questionary
import ui_manager
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519

# Алфавит Base58 (согласно стандарту Bitcoin)
ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def encode_base58(b: bytes) -> str:
    """Простая функция кодирования байтов в строку Base58."""
    # Подсчет ведущих нулей
    nPad = 0
    for byte in b:
        if byte == 0:
            nPad += 1
        else:
            break
            
    # Конвертация в число
    v = int.from_bytes(b, byteorder='big')
    
    # Кодирование
    res = bytearray()
    while v > 0:
        v, mod = divmod(v, 58)
        res.append(ALPHABET[mod])
        
    res.extend(ALPHABET[0:1] * nPad)
    res.reverse()
    return res.decode('ascii')


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
        
        # Получаем сид ключа через Bip32 Slip10, который работает без зависаний
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
        else: # Fallback just in case
            acc_obj = bip32_obj.DerivePath("m/44'/501'/0'/0'")
            path_str = "m/44'/501'/0'/0'"

        # Генерируем ключи через PyNaCl для стабильности
        from nacl.signing import SigningKey
        
        # Берем 32 байта приватного ключа
        priv_key_bytes = acc_obj.PrivateKey().Raw().ToBytes()
        
        # Инициализируем SigningKey из nacl
        sk = SigningKey(priv_key_bytes)
        vk = sk.verify_key
        
        pub_bytes = vk.encode()
        priv_bytes = sk.encode()

        address = encode_base58(pub_bytes)
        
        secret_key_bytes = priv_bytes + pub_bytes
        priv_key_base58 = encode_base58(secret_key_bytes)

        return {
            "address": address,
            "private_key": priv_key_base58,
            "path": path_str,
            "type": f"Solana ({mode})"
        }