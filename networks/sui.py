import re
from bip_utils import Bip44, Bip44Coins, Bip44Changes


class NetworkGenerator:
    NAME = "SUI (SUI)"
    SYMBOL = "SUI"

    @staticmethod
    def generate(seed_bytes):
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.SUI)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        """Проверка валидности SUI адреса (0x + 64 hex символа)."""
        if not address.startswith("0x"):
            return False, "Адрес должен начинаться с 0x"
        if len(address) != 66:
            return False, f"Длина {len(address)}, ожидается 66"
        if not re.match(r'^0x[0-9a-fA-F]{64}$', address):
            return False, "Невалидные hex символы"
        return True, "OK"