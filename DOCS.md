# 📚 Документация разработчика WalletForge

Данный документ описывает внутреннюю архитектуру WalletForge и процесс создания кастомных модулей сетей.

---

## 🏗 Архитектура Проекта

### Структура файлов
* `main.py` — Точка входа. Логика меню, генерация, шифрование (AES-GCM), расшифровка и экспорт.
* `ui_manager.py` — Управление выводом в консоль (цвета, баннеры, стили).
* `modules/` — Подключаемые модули:
  * `vanity_gen.py` — Vanity-генератор адресов (мульти-паттерн, ETA, мультипроцессинг).
  * `shamir_utils.py` — Shamir Secret Sharing (разделение/восстановление секретов).
  * `pdf_export.py` — Экспорт кошельков в QR PDF и Paper Wallet PDF.
  * `add_network.py` — Wizard для создания модулей сетей.
* `networks/` — Папка с модулями генераторов. Каждый `.py` файл — отдельная сеть.
* `requirements.txt` — Список зависимостей.

### Ядро (Core Logic)
Ядро (`main.py`) использует **динамическую интроспекцию** (`inspect` module).
`main.py` не знает заранее, какие аргументы нужны вашему модулю. Перед вызовом генерации он проверяет сигнатуру метода `generate` и передаёт только требуемые данные.

Поддерживаемые аргументы `generate()`:
* `seed_bytes` — BIP39 seed (обязательный).
* `mnemonic` — строка мнемоники (для сетей использующих raw mnemonic).
* `config` — словарь конфигурации из `configure()`.

---

## 🔌 Создание модуля сети

Любой файл `.py` в папке `networks/` считается модулем сети, если он содержит класс `NetworkGenerator`.

### Минимальный шаблон

```python
from bip_utils import Bip44, Bip44Coins, Bip44Changes

class NetworkGenerator:
    NAME = "My Network (MCN)"  # Имя в меню выбора
    SYMBOL = "MCN"             # Тикер для логов и файлов

    @staticmethod
    def generate(seed_bytes, config=None):
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        acc_obj = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        return {
            "address": acc_obj.PublicKey().ToAddress(),
            "private_key": acc_obj.PrivateKey().Raw().ToHex()
        }
```

### Валидация адресов (опционально)

Добавьте метод `validate()` для поддержки верификации:

```python
    @staticmethod
    def validate(address):
        if not address.startswith("0x"):
            return False, "Адрес должен начинаться с 0x"
        return True, "OK"
```

### Кастомная мнемоника

Для сетей с нестандартной мнемоникой (Monero Polyseed, Legacy 25 слов):

```python
class NetworkGenerator:
    CUSTOM_MNEMONIC = True

    @staticmethod
    def select_mnemonic():
        # Интерактивный выбор типа мнемоники
        return {"mnemonic_type": "polyseed"}

    @staticmethod
    def generate(seed_bytes, config=None, mnemonic=None):
        # Логика с учетом config["mnemonic_type"]
        ...
```

---

## ⚙️ Метод `configure()`

Если сети нужны настройки перед генерацией (формат адреса, путь деривации):

```python
import questionary

class NetworkGenerator:
    NAME = "My Network (MCN)"
    SYMBOL = "MCN"

    @staticmethod
    def configure():
        mode = questionary.select("Выберите режим:", choices=["Mode A", "Mode B"]).ask()
        if not mode: return None
        return {"mode": mode}

    @staticmethod
    def generate(seed_bytes, config):
        if config["mode"] == "Mode A":
            # ...
```

---

## ✨ Vanity-генератор

Файл `vanity_gen.py` реализует многопроцессный поиск красивых адресов.

### Особенности:
* **Мультипроцессинг:** распараллеливание на N ядер (по выбору пользователя).
* **3 режима поиска:** Prefix, Suffix, Contains.
* **Мульти-паттерн:** поиск нескольких вариантов одновременно.
* **ETA:** расчёт по сумме вероятностей каждого паттерна.
* **Продолжение поиска:** после нахождения паттерна можно искать оставшиеся.
* **Звуковой сигнал** (Windows Beep API).
* **Валидация символов** под алфавит каждой сети.

### Функция воркера:
`search_vanity_worker()` — независимый процесс, генерирует BIP39 мнемоники в цикле и проверяет полученный адрес на совпадение с паттерном. При нахождении устанавливает `stop_flag` через shared memory.

---

## 🧩 Shamir Secret Sharing

Файл `shamir_utils.py` разбивает любой секрет (мнемоника, ключ, пароль) на N частей с порогом M.

### Алгоритм:
1. Секрет разбивается на чанки по 15 байт.
2. Каждый чанк обрабатывается `shamirs.shares()` с простым числом 2¹²⁷ - 1.
3. Результаты кодируются в Base64: `SHAMIR-{threshold}-{total}-{index}-{hex_values}`.

### Форматы сохранения:
* `.txt` — открытый текстовый файл.
* `.enc` — зашифрованный AES-256-GCM (каждая часть отдельно).

### Восстановление:
* Загрузка из папки `shamir_*` (автоматический поиск).
* Из произвольной папки (указать путь).
* Ручной ввод из буфера.

---

## 🖨️ PDF-экспорт

Файл `pdf_export.py` содержит два формата:

### QR PDF (`export_qr_pdf`)
* Портрет A4, 2 кошелька на страницу.
* QR-коды для: адреса (с URI-префиксом сети), приватного ключа, мнемоники.
* Текст рядом с QR для каждого поля.

### Paper Wallet (`export_paper_wallet`)
* Ландшафт A4, 1 кошелёк на страницу.
* Линия сгиба: PUBLIC сверху (адрес), PRIVATE снизу (ключ + мнемоника).
* URI-префиксы адресов (`monero:`, `bitcoin:`, `ethereum:` и т.д.).

---

## 🔐 Шифрование данных

1. **KDF:** Scrypt (n=2¹⁴, r=8, p=1) — пароль → 256-битный ключ.
2. **Encryption:** AES-256-GCM — конфиденциальность + целостность.
3. **Формат файла:** `[16 байт salt][12 байт nonce][ciphertext+tag]`.

---

## 📦 Зависимости

* `bip-utils` — BIP39/44/84/86 криптография.
* `PyNaCl` — Ed25519 (Solana).
* `cryptography` — AES-GCM шифрование.
* `substrate-interface` — Polkadot экосистема.
* `qrcode[pil]` — QR-коды.
* `reportlab` — PDF генерация.
* `shamirs` — Shamir Secret Sharing.
* `rich` & `questionary` — UI.
* `pyfiglet` — ASCII баннер.

Полный список см. в `requirements.txt`.