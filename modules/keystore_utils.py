import os
import json
import codecs
from uuid import uuid4
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

def generate_keystore(private_key_hex: str, password: str, address: str) -> dict:
    """
    Генерирует стандартный Ethereum/EVM Keystore V3 JSON.
    Также отлично работает для TronLink, так как формат идентичен.
    
    :param private_key_hex: Приватный ключ в формате hex (без 0x)
    :param password: Пароль для шифрования
    :param address: Адрес кошелька
    :return: Словарь (dict), представляющий структуру Keystore V3
    """
    
    # Очистка ключа и адреса от '0x' если есть
    if private_key_hex.startswith('0x') or private_key_hex.startswith('0X'):
        private_key_hex = private_key_hex[2:]
        
    # Форматирование адреса. Keystore V3 требует HEX адрес. 
    # Для TRON TronLink ожидает адрес в HEX формате ВМЕСТЕ с префиксом 41 (42 символа).
    if address.startswith('T') and len(address) == 34:
        import base58
        try:
            # Превращаем Base58 в 42-символьный hex ('41...')
            address = base58.b58decode_check(address).hex()
        except Exception:
            pass
            
    if address.startswith('0x') or address.startswith('0X'):
        address = address[2:]
    
    # Конвертация ключа и пароля в bytes
    priv_key_bytes = bytes.fromhex(private_key_hex)
    pass_bytes = password.encode('utf-8')
    
    # 1. Генерация random salt (32 байта)
    salt = os.urandom(32)
    
    # 2. Key Derivation (KDF) через Scrypt
    # Стандартные параметры для V3 Keystore
    n = 262144
    r = 8
    p = 1
    dklen = 32
    
    kdf = Scrypt(
        salt=salt,
        length=dklen,
        n=n,
        r=r,
        p=p,
        backend=default_backend()
    )
    derived_key = kdf.derive(pass_bytes)
    
    # Ключ делится на две части: 
    # первые 16 байт - для шифрования (AES)
    # вторые 16 байт - для создания MAC подписи
    encrypt_key = derived_key[:16]
    mac_key = derived_key[16:32]
    
    # 3. Шифрование приватного ключа через AES-128-CTR
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(encrypt_key), modes.CTR(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(priv_key_bytes) + encryptor.finalize()
    
    # 4. Генерация MAC (Message Authentication Code) = Keccak256(mac_key + ciphertext)
    # Важно: Стандарт использует Keccak-256, не SHA3-256. Cryptography не имеет чистого Keccak,
    # но у нас установлен pysha3/sha3 через bip_utils.
    # Используем pysha3 или eth_hash, если есть, ИЛИ ручную конвертацию.
    # Однако стандартный web3/eth_keyfile использует SHA3_256 (на базе keccak).
    
    try:
        from Crypto.Hash import keccak
        k_hash = keccak.new(digest_bits=256)
        k_hash.update(mac_key + ciphertext)
        mac = k_hash.hexdigest()
    except ImportError:
        # Если pycryptodome недоступен, попробуем использовать хэш из bip_utils
        from bip_utils.utils.crypto.keccak import Keccak256
        mac = Keccak256.QuickDigest(mac_key + ciphertext).hex()
    
    # 5. Формирование структуры Keystore V3
    keystore_uuid = str(uuid4())
    
    keystore = {
        "crypto": {
            "cipher": "aes-128-ctr",
            "cipherparams": {
                "iv": iv.hex()
            },
            "ciphertext": ciphertext.hex(),
            "kdf": "scrypt",
            "kdfparams": {
                "dklen": dklen,
                "n": n,
                "p": p,
                "r": r,
                "salt": salt.hex()
            },
            "mac": mac
        },
        "id": keystore_uuid,
        "version": 3,
        "address": address
    }
    
    return keystore

def generate_keystore_filename(address: str) -> str:
    """Генерирует стандартное имя файла по формату UTC--<timestamp>--<address>"""
    if address.startswith('T') and len(address) == 34:
        import base58
        try:
            address = base58.b58decode_check(address).hex()
        except Exception:
            pass
            
    if address.startswith('0x') or address.startswith('0X'):
        address = address[2:]
        
    ts = datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S.%fZ')
    return f"UTC--{ts}--{address.lower()}"

