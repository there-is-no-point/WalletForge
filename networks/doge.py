from bip_utils import Bip44, Bip44Coins, Bip44Changes
import re

class NetworkGenerator:
    NAME = "Dogecoin (DOGE)"
    SYMBOL = "DOGE"

    @staticmethod
    def generate(seed_bytes, config=None):
        # Генерация для Bitcoin-форка Dogecoin
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.DOGECOIN)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().ToWif(),
            "private_key_hex": acc_obj.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        # Базовая проверка Base58Check адреса (начинается с D, длина 34)
        if not address or len(address) < 25 or len(address) > 36:
            return False, f"Невалидная длина: {len(address)}"
        if not re.match(r'^D[a-km-zA-HJ-NP-Z1-9]+$', address):
            return False, "Невалидные символы Dogecoin адреса"
        return True, "OK"
