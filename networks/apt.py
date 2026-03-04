import hashlib
import re
from bip_utils import Bip32Slip10Ed25519
import ui_manager


class NetworkGenerator:
    NAME = "Aptos (APT)"
    SYMBOL = "APT"

    @staticmethod
    def generate(seed_bytes, config=None):
        """
        Aptos использует:
        - Ed25519 (SLIP-0010)
        - Путь деривации: m/44'/637'/0'/0'/0'
        - Адрес = SHA3-256(public_key_32_bytes + 0x00)
        - 0x00 = схема single Ed25519
        """
        try:
            # 1. Ed25519 деривация
            bip32 = Bip32Slip10Ed25519.FromSeed(seed_bytes)
            key = bip32.DerivePath("m/44'/637'/0'/0'/0'")

            # 2. Публичный ключ (33 байта с префиксом 0x00, берём 32 без него)
            pub_compressed = key.PublicKey().RawCompressed().ToBytes()
            pub_key_32 = pub_compressed[1:]  # Убираем префикс-байт

            # 3. Адрес = SHA3-256(pub_key + scheme_byte)
            auth_key = hashlib.sha3_256(pub_key_32 + b'\x00').digest()
            address = "0x" + auth_key.hex()

            # 4. Приватный ключ
            private_key = key.PrivateKey().Raw().ToHex()

            return {
                "address": address,
                "private_key": private_key,
                "public_key": pub_key_32.hex(),
                "path": "m/44'/637'/0'/0'/0'",
                "type": "Aptos (Ed25519 / SHA3-256)"
            }
        except Exception as e:
            ui_manager.print_error(f"Aptos Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def validate(address):
        """Проверка валидности Aptos адреса (0x + 64 hex символа)."""
        if not address.startswith("0x"):
            return False, "Адрес должен начинаться с 0x"
        if len(address) != 66:
            return False, f"Длина {len(address)}, ожидается 66"
        if not re.match(r'^0x[0-9a-fA-F]{64}$', address):
            return False, "Невалидные hex символы"
        return True, "OK"
