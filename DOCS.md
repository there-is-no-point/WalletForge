# 📚 Документация разработчика KEY FORGE

Данный документ описывает внутреннюю архитектуру Key Forge и процесс создания кастомных модулей сетей.

---

## 🏗 Архитектура Проекта

### Структура файлов
* `main.py` — Точка входа. Содержит логику меню, цикл генерации и криптографию (AES-GCM).
* `ui_manager.py` — Управление выводом в консоль (цвета, баннеры, таблицы).
* `add_network.py` — "Wizard" для автоматического создания модулей.
* `networks/` — Папка с модулями генераторов. Каждый файл `.py` здесь — это отдельная сеть.
* `requirements.txt` — Список зависимостей с зафиксированными версиями.

### Ядро (Core Logic)
Ядро (`main.py`) использует **динамическую интроспекцию** (`inspect module`).
Это означает, что `main.py` не знает заранее, какие аргументы нужны вашему модулю. Перед вызовом генерации он проверяет сигнатуру метода `generate` в вашем классе и передает только требуемые данные.

---

## 🔌 Создание модуля сети

Любой файл `.py` в папке `networks/` считается модулем сети, если он содержит класс `NetworkGenerator`.

### Минимальный шаблон

```python
from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    # Имя в меню выбора
    NAME = "My Custom Network"
    # Тикер для имени файла и логов
    SYMBOL = "MCN"

    @staticmethod
    def generate(seed_bytes, config=None):
        """
        Функция генерации одного кошелька.
        """
        # Логика деривации (пример для EVM)
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().Raw().ToHex()
        }
```

### Расширенные возможности (Introspection)

Вы можете запрашивать дополнительные данные в методе `generate`, просто добавив аргументы:

1.  **`mnemonic`**: Если вашему модулю нужна мнемоника (строка), добавьте этот аргумент.
    ```python
    @staticmethod
    def generate(seed_bytes, mnemonic):
        # Теперь вам доступна переменная mnemonic
    ```
2.  **`config`**: Если вы реализовали метод `configure()`, его результат придет сюда.

---

## ⚙️ Метод `configure()`

Если вашей сети нужны настройки перед запуском (например, выбор префикса адреса или типа деривации), добавьте статический метод `configure`.

```python
import questionary

class NetworkGenerator:
    # ... NAME и SYMBOL ...

    @staticmethod
    def configure():
        # Спросить пользователя
        mode = questionary.select("Выберите режим:", choices=["Mode A", "Mode B"]).ask()
        
        if not mode: return None # Обработка отмены
        
        # Вернуть словарь конфигурации
        return {"mode": mode}

    @staticmethod
    def generate(seed_bytes, config):
        # config["mode"] доступен здесь
        if config["mode"] == "Mode A":
            # ...
```

---

## 🔐 Шифрование данных

Для сохранения результатов используется библиотека `cryptography`.

1.  **KDF (Key Derivation Function):** Пароль пользователя превращается в ключ шифрования с помощью алгоритма **Scrypt**. Это защищает от Brute-force атак.
2.  **Encryption:** Данные шифруются алгоритмом **AES-256-GCM**. Это обеспечивает не только конфиденциальность, но и целостность данных (проверку, что файл не был изменен).

---

## 📦 Зависимости

Проект жестко фиксирует версии библиотек для стабильности:
* `bip_utils`
* `cryptography`
* `PyNaCl`
* `rich`
* `questionary`
* `substrate-interface`
* `requests`
* `pyfiglet`

Полный список см. в `requirements.txt`.