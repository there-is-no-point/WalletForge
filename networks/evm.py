import re
from bip_utils import Bip44, Bip44Coins, Bip44Changes


class NetworkGenerator:
    NAME = "EVM (Ethereum, BNB, Polygon)"
    SYMBOL = "ETH"

    @staticmethod
    def generate(seed_bytes):
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        """Проверка валидности EVM адреса (0x + 40 hex символов)."""
        if not address.startswith("0x"):
            return False, "Адрес должен начинаться с 0x"
        if len(address) != 42:
            return False, f"Длина {len(address)}, ожидается 42"
        if not re.match(r'^0x[0-9a-fA-F]{40}$', address):
            return False, "Невалидные hex символы"
        return True, "OK"