from bip_utils import Bip84, Bip84Coins, Bip44Changes
import re

class NetworkGenerator:
    NAME = "Litecoin (LTC)"
    SYMBOL = "LTC"

    @staticmethod
    def generate(seed_bytes, config=None):
        # Используем Native SegWit (BIP84) по умолчанию для LTC
        # Это приведет к генерации ltc1... адресов, как в Trust Wallet
        bip_obj = Bip84.FromSeed(seed_bytes, Bip84Coins.LITECOIN)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().ToWif(),
            "private_key_hex": acc_obj.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        # Проверка Litecoin адресов (Legacy L/M или Native SegWit ltc1...)
        if not address:
            return False, "Пустой адрес"
        
        # Native SegWit
        if address.startswith("ltc1"):
            if not re.match(r'^ltc1[a-z0-9]{38,58}$', address):
                return False, "Невалидный Native SegWit формат"
            return True, "OK"
            
        # Legacy/Nested
        if len(address) < 25 or len(address) > 36:
            return False, f"Невалидная длина: {len(address)}"
        if not re.match(r'^[LM][a-km-zA-HJ-NP-Z1-9]+$', address):
            return False, "Невалидные символы Litecoin адреса"
            
        return True, "OK"
