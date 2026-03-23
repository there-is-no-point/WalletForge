from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    NAME = "TRON (TRX)"
    SYMBOL = "TRX"

    @staticmethod
    def generate(seed_bytes, config=None):
        # Стандартная генерация для TRON
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        import re
        if not address or len(address) != 34:
            return False, f"Длина {len(address) if address else 0}, ожидается 34"
        if not address.startswith('T'):
            return False, "Адрес должен начинаться с 'T'"
        if not re.match(r'^T[1-9A-HJ-NP-Za-km-z]{33}$', address):
            return False, "Невалидные Base58 символы"
        return True, "OK"
