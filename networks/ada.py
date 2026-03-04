from bip_utils import (
    Cip1852, Cip1852Coins, Bip44Changes,
    CardanoIcarusSeedGenerator,
    CardanoShelley
)
import ui_manager


class NetworkGenerator:
    NAME = "Cardano (ADA)"
    SYMBOL = "ADA"

    @staticmethod
    def generate(seed_bytes, mnemonic=None, config=None):
        """
        Cardano Shelley использует:
        - CIP-1852 деривацию: m/1852'/1815'/0'/0/0
        - Icarus seed (из BIP39 мнемоники)
        - Ed25519-BIP32 (нестандартная кривая)
        - Base address = payment key + staking key
        Требует мнемонику (не seed bytes) для Icarus seed.
        """
        if not mnemonic:
            return {"error": "Cardano requires mnemonic (not just seed)"}

        try:
            # 1. Генерация Icarus seed из BIP39 мнемоники
            icarus_seed = CardanoIcarusSeedGenerator(mnemonic).Generate()

            # 2. CIP-1852 деривация до уровня Account
            cip = Cip1852.FromSeed(icarus_seed, Cip1852Coins.CARDANO_ICARUS)
            account = cip.Purpose().Coin().Account(0)

            # 3. Shelley: Account -> Change(external) -> AddressIndex(0)
            shelley = CardanoShelley.FromCip1852Object(account)
            addr_key = shelley.Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

            # 4. Адрес и ключи
            address = str(addr_key.PublicKeys().ToAddress())
            private_key = addr_key.PrivateKeys().AddressKey().Raw().ToHex()
            staking_key = addr_key.PrivateKeys().StakingKey().Raw().ToHex()

            return {
                "address": address,
                "private_key": private_key,
                "staking_key": staking_key,
                "path": "m/1852'/1815'/0'/0/0",
                "type": "Cardano Shelley (CIP-1852 / Icarus)"
            }
        except Exception as e:
            ui_manager.print_error(f"Cardano Gen Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def validate(address):
        """Проверка валидности Cardano Shelley адреса (Bech32, addr1...)."""
        if not address:
            return False, "Пустой адрес"
        if not address.startswith("addr1"):
            return False, f"Ожидается префикс 'addr1', получено: {address[:6]}"
        if len(address) < 50 or len(address) > 120:
            return False, f"Невалидная длина: {len(address)}"
        return True, "OK"
