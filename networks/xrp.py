from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    NAME = "Ripple (XRP)"
    SYMBOL = "XRP"

    @staticmethod
    def generate(seed_bytes, config=None, mnemonic=None):
        import base58
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.RIPPLE)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        pk_bytes = acc_obj.PrivateKey().Raw().ToBytes()
        pk_hex = pk_bytes.hex().upper()  # Xaman and standard XRP wallets often expect uppercase HEX for direct Private Key imports.
        xaman_hex = "00" + pk_hex # Xaman expects 66 hex characters (00 prefix + 32-byte key)
        
        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": xaman_hex,       # 66 HEX chars для Xaman ("00" + 64 chars) 
            "private_key_hex": pk_hex       # 64 HEX chars для Trust Wallet
        }

    @staticmethod
    def validate(address):
        import re
        if not address or len(address) < 25 or len(address) > 35:
            return False, f"Длина {len(address) if address else 0}, ожидается 25-35"
        if not address.startswith('r'):
            return False, "Адрес должен начинаться с 'r'"
        # Ripple uses a custom Base58 alphabet but similar bounds
        if not re.match(r'^r[1-9A-HJ-NP-Za-km-z]{24,34}$', address):
            return False, "Невалидные Base58 символы"
        return True, "OK"
