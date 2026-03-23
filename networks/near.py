from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    NAME = "NEAR (NEAR)"
    SYMBOL = "NEAR"

    @staticmethod
    def generate(seed_bytes, config=None):
        import base58
        
        # Как выяснилось, и официальные кошельки (Meteor, NEAR Wallet), 
        # и мультивалютные (Trust Wallet) используют ОДИНАКОВЫЙ путь деривации для NEAR: m/44'/397'/0'
        # Разница только в формате импорта приватного ключа.
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.NEAR_PROTOCOL)
        
        # Останавливаем деривацию на m/44'/397'/0'
        acc_obj = bip_obj.Purpose().Coin().Account(0)

        pk_bytes = acc_obj.PrivateKey().Raw().ToBytes()
        pub_bytes = acc_obj.PublicKey().RawCompressed().ToBytes()
        
        # Чистый 32-байтный публичный ключ (снятие нулевого байта от bip_utils)
        if len(pub_bytes) == 33 and pub_bytes[0] in (0, 1):
            pure_pub = pub_bytes[1:]
        else:
            pure_pub = pub_bytes
            
        addr_hex = pure_pub.hex()
        
        # Для родных NEAR кошельков нужен 64-байтный ключ (private + public) в Base58 с префиксом ed25519:
        full_sk = pk_bytes + pure_pub
        pk_export_base58 = "ed25519:" + base58.b58encode(full_sk).decode('utf-8')

        return {
            "address": addr_hex,
            "private_key": pk_export_base58,  # Для Meteor, MyNEARWallet...
            "private_key_hex": pk_bytes.hex() # Для Trust Wallet
        }

    @staticmethod
    def validate(address):
        import re
        if not address or len(address) != 64:
            return False, f"Длина {len(address) if address else 0}, ожидается 64"
        if not re.match(r'^[a-f0-9]{64}$', address):
            return False, "Невалидные hex символы"
        return True, "OK"
