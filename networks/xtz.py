from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    NAME = "Tezos (XTZ)"
    SYMBOL = "XTZ"

    @staticmethod
    def generate(seed_bytes, config=None):
        # Trust Wallet & Temple Wallet используют путь 4-х уровней: m/44'/1729'/0'/0'
        # В то время как bip_utils по умолчанию делает 5 уровней: m/44'/1729'/0'/0'/0'
        from bip_utils import Bip32Slip10Ed25519, XtzAddrEncoder, XtzAddrPrefixes
        
        ctx = Bip32Slip10Ed25519.FromSeed(seed_bytes)
        der = ctx.DerivePath("m/44'/1729'/0'/0'")
        
        # Для Ed25519 публичный ключ начинается с 0x00 в bip_utils, отрезаем его для TezosEncoder
        pub_bytes = der.PublicKey().RawCompressed().ToBytes()[1:]
        address = XtzAddrEncoder.EncodeKey(pub_bytes, prefix=XtzAddrPrefixes.TZ1)

        return {
            "address": address,
            "private_key": der.PrivateKey().Raw().ToHex()
        }

    @staticmethod
    def validate(address):
        import re
        if not address or len(address) != 36:
            return False, f"Длина {len(address) if address else 0}, ожидается 36"
        if not (address.startswith('tz1') or address.startswith('tz2') or address.startswith('tz3')):
            return False, "Адрес должен начинаться с 'tz1', 'tz2' или 'tz3'"
        if not re.match(r'^tz[123][1-9A-HJ-NP-Za-km-z]{33}$', address):
            return False, "Невалидные Base58 символы"
        return True, "OK"
