import os
import time
import json
import importlib
import pkgutil
import inspect
from datetime import datetime
import questionary
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# Импортируем наш новый менеджер стилей
import ui_manager
from ui_manager import console, print_banner, print_success, print_error, print_info

# Библиотеки ядра
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip39WordsNum
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

# Подключение скрипта добавления сетей
add_network = None

# --- CONSTANTS ---
ENC_DIR = "wallets_encrypted"
CSV_DIR = "wallets_decrypted"

for folder in [ENC_DIR, CSV_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)


# --- 1. CORE FUNCTIONS ---

def load_networks():
    networks = {}
    package_name = 'networks'
    if not os.path.isdir(package_name):
        os.makedirs(package_name)
        with open(os.path.join(package_name, '__init__.py'), 'w') as f: pass
        return {}

    for _, module_name, _ in pkgutil.iter_modules([package_name]):
        try:
            module = importlib.import_module(f"{package_name}.{module_name}")
            if hasattr(module, 'NetworkGenerator'):
                networks[module.NetworkGenerator.NAME] = module.NetworkGenerator
        except Exception as e:
            pass
    return networks


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1, backend=default_backend())
    return kdf.derive(password.encode())


def encrypt_data(data_list, password):
    json_str = json.dumps(data_list)
    salt = os.urandom(16)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, json_str.encode(), None)
    return salt + nonce + ciphertext


def decrypt_data(filepath, password):
    try:
        with open(filepath, 'rb') as f:
            file_bytes = f.read()
        salt = file_bytes[:16]
        nonce = file_bytes[16:28]
        ciphertext = file_bytes[28:]
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)
        return json.loads(aesgcm.decrypt(nonce, ciphertext, None).decode())
    except Exception:
        return None


# --- 2. MAIN LOGIC ---

def run_generator():
    importlib.invalidate_caches()
    networks = load_networks()

    if not networks:
        print_error("Нет доступных сетей!")
        return

    while True:
        try:
            # Возвращает True только если юзер нажал "Назад" в самом начале
            if _run_generator_logic(networks):
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Действие отменено (Ctrl+C). Возврат к выбору сети...[/yellow]")
            import time
            time.sleep(1)
            continue

def _run_generator_logic(networks):
    state = {
        "Сеть": "⏳ Ожидание...",
        "Количество": "⏳ Ожидание...",
        "Мнемоника": "⏳ Ожидание...",
        "Доп. пароль": "⏳ Ожидание...",
        "Шифрование БД": "⏳ Ожидание..."
    }

    def refresh_ui():
        ui_manager.print_breadcrumbs("🚀 Сгенерировать кошельки")
        ui_manager.print_config_card(state)

    refresh_ui()
    # A. Выбор сети
    net_name = questionary.select(
        "Выберите сеть:",
        choices=["🔙 Назад"] + list(networks.keys()),
        style=ui_manager.custom_style
    ).ask()

    # Истинный выход в главное меню
    if not net_name or "Назад" in net_name: return True

    GeneratorClass = networks[net_name]
    coin_symbol = GeneratorClass.SYMBOL
    state["Сеть"] = f"{net_name} ({coin_symbol})"
    net_config = {}

    # B. Настройка конкретной сети
    if hasattr(GeneratorClass, "configure"):
        try:
            refresh_ui()
            print_info(f"Настройка параметров {net_name}...")
            net_config = GeneratorClass.configure()
            if net_config is None: return

            if "symbol" in net_config: coin_symbol = net_config["symbol"]
            if "symbol_suffix" in net_config: coin_symbol += net_config["symbol_suffix"]
            state["Сеть"] = f"{net_name} ({coin_symbol})"
        except Exception as e:
            print_error(f"Ошибка настройки: {e}")
            return

    # C. Общие настройки
    refresh_ui()
    while True:
        count_str = questionary.text(
            "Количество кошельков:", 
            default="10", 
            validate=lambda x: x == "" or x.isdigit(),
            style=ui_manager.custom_style
        ).ask()
        
        if count_str is None:
            return
            
        if not count_str:
            print_error("Данные не введены. Укажите количество.")
            time.sleep(1)
            refresh_ui()
            continue
            
        if count_str == "0":
            return
            
        break
        
    count = int(count_str)
    state["Количество"] = str(count)

    # Пропускаем стандартный выбор если модуль сам управляет мнемоникой
    refresh_ui()
    if getattr(GeneratorClass, 'CUSTOM_MNEMONIC', False):
        mn_config = GeneratorClass.select_mnemonic()
        if mn_config is None: return
        net_config.update(mn_config)
        words_num = 12  # Заглушка для BIP39 fallback
        state["Мнемоника"] = "Управляется модулем"
    else:
        words_num_str = questionary.select("Длина мнемоники:", choices=["12", "15", "18", "24"], style=ui_manager.custom_style).ask()
        if not words_num_str: return
        words_num = int(words_num_str)
        state["Мнемоника"] = f"{words_num} слов"

    refresh_ui()
    passphrase_ans = questionary.confirm("Добавить Passphrase?", style=ui_manager.custom_style).ask()
    if passphrase_ans is None: return
    passphrase = ""
    if passphrase_ans:
        state["Доп. пароль"] = "⏳ Ожидание ввода..."
        refresh_ui()
        while True:
            passphrase = questionary.password("Введите Passphrase:", style=ui_manager.custom_style).ask()
            if passphrase is None: 
                return
            if not passphrase:
                print_error("Данные не введены (Passphrase).")
                time.sleep(1)
                refresh_ui()
                continue
            break
        state["Доп. пароль"] = "Установлен (Скрыт)"
    else:
        state["Доп. пароль"] = "Нет"

    refresh_ui()
    while True:
        save_pass = questionary.password(
            "Придумайте пароль для шифрования (от 4 символов):",
            style=ui_manager.custom_style
        ).ask()
        
        if save_pass is None:
            return
            
        if not save_pass or len(save_pass) < 4:
            print_error("Данные не введены (Слишком короткий пароль). Минимальная длина - 4 символа.")
            time.sleep(1)
            refresh_ui()
            continue
            
        break
        
    state["Шифрование БД"] = "Установлен"
    refresh_ui()

    # D. Процесс генерации
    wallets_data = []
    gen_errors = 0

    with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console
    ) as progress:
        task = progress.add_task(f"Генерация {coin_symbol}...", total=count)

        bip_words_enum = \
            {12: Bip39WordsNum.WORDS_NUM_12, 15: Bip39WordsNum.WORDS_NUM_15, 18: Bip39WordsNum.WORDS_NUM_18,
             24: Bip39WordsNum.WORDS_NUM_24}[words_num]

        for _ in range(count):
            try:
                # 1. ГЕНЕРАЦИЯ МНЕМОНИКИ
                mnemonic = Bip39MnemonicGenerator().FromWordsNumber(bip_words_enum)
                seed_bytes = Bip39SeedGenerator(mnemonic).Generate(passphrase)

                # 2. ПОЛУЧЕНИЕ КЛЮЧЕЙ (Dynamic argument inspection)
                w_keys = {}
                try:
                    # Get the function signature
                    sig = inspect.signature(GeneratorClass.generate)

                    # Prepare arguments based on what the function accepts
                    call_args = {'seed_bytes': seed_bytes}

                    # Add config if the function accepts it
                    if 'config' in sig.parameters:
                        call_args['config'] = net_config

                    # Add mnemonic if the function accepts it
                    if 'mnemonic' in sig.parameters:
                        call_args['mnemonic'] = str(mnemonic)

                    # Call the function with the appropriate arguments
                    w_keys = GeneratorClass.generate(**call_args)
                except Exception as e:
                    print(f"Error in generate: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

                if "error" in w_keys: continue

                # 3. ВАЛИДАЦИЯ АДРЕСА
                if hasattr(GeneratorClass, "validate"):
                    try:
                        v_sig = inspect.signature(GeneratorClass.validate)
                        if "config" in v_sig.parameters:
                            is_valid, v_msg = GeneratorClass.validate(w_keys.get("address"), config=net_config)
                        else:
                            is_valid, v_msg = GeneratorClass.validate(w_keys.get("address"))
                        if not is_valid:
                            gen_errors += 1
                            progress.advance(task)
                            continue
                    except Exception:
                        pass  # Ошибка валидатора не должна блокировать генерацию

                # 4. СОХРАНЕНИЕ
                entry = {
                    "network": net_name,
                    "address": w_keys.get("address"),
                    "private_key": w_keys.get("private_key"),
                    "mnemonic": str(mnemonic),
                    "passphrase": passphrase
                }
                for k, v in w_keys.items():
                    entry[k] = v

                wallets_data.append(entry)
                progress.advance(task)
            except Exception as e:
                gen_errors += 1
                progress.advance(task)

    if not wallets_data:
        print_error("Сбой генерации.")
        return

    if gen_errors > 0:
        print_error(f"Ошибок при генерации: {gen_errors} из {count}")

    # E. Preview
    console.print("\n[bold]🔍 Предпросмотр (Первый кошелек):[/bold]")
    preview_table = Table(show_header=True, header_style="bold magenta")
    preview_table.add_column("Address", style="green")
    preview_table.add_column("Mnemonic (Partial)", style="dim")

    mnem_preview = wallets_data[0]["mnemonic"].split()[:3]
    preview_table.add_row(wallets_data[0]["address"], " ".join(mnem_preview) + " ...")
    console.print(preview_table)

    # F. Сохранение
    console.print()
    # Проверяем, поддерживает ли текущая сеть Keystore (EVM, TRON)
    supports_keystore = False
    net_lower = net_name.lower()
    if "evm" in net_lower or "eth" in net_lower or "tron" in net_lower or "trx" in net_lower:
        supports_keystore = True
        
    save_format_choices = ["🔒 Зашифрованный архив (.enc)"]
    if supports_keystore:
        save_format_choices.append("💼 Индивидуальные Keystore V3 (.json / .txt)")
    save_format_choices.append("🔙 Назад")

    save_format = questionary.select(
        "Выберите формат для сохранения кошельков:",
        choices=save_format_choices,
        style=ui_manager.custom_style
    ).ask()
    if not save_format or "Назад" in save_format: return

    file_tag = questionary.text(
        "Добавить метку к имени файла? (Enter - пропустить):",
        style=ui_manager.custom_style
    ).ask()

    if file_tag:
        import re
        clean_tag = re.sub(r'[\\/*?:"<>|]', '_', file_tag)
        if clean_tag:
            file_tag = f"_{clean_tag}"
        else:
            file_tag = ""
    else:
        file_tag = ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if "Keystore V3" in save_format:
        from modules.keystore_utils import generate_keystore, generate_keystore_filename
        import json
        saved_count = 0
        
        # Создаем папку под батч если их много
        batch_dir = ENC_DIR
        if len(wallets_data) > 1:
            batch_dir = os.path.join(ENC_DIR, f"keystores_{coin_symbol}{file_tag}_{timestamp}")
            os.makedirs(batch_dir, exist_ok=True)
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Шифрование Keystore...[/bold cyan]"),
            BarColumn(),
            console=console
        ) as progress:
            ks_task = progress.add_task("Шифрование", total=len(wallets_data))
            
            for wallet in wallets_data:
                try:
                    addr = wallet.get('address', '')
                    priv = wallet.get('private_key', '')
                    if not addr or not priv:
                        continue
                        
                    # Генерируем структуру
                    keystore_dict = generate_keystore(priv, save_pass, addr)
                    
                    # Генерируем имя файла
                    ext = ".txt" if ("tron" in net_lower or "trx" in net_lower) else ".json"
                    ks_filename = generate_keystore_filename(addr) + ext
                    ks_path = os.path.join(batch_dir, ks_filename)
                    
                    with open(ks_path, "w", encoding='utf-8') as f:
                        json.dump(keystore_dict, f, indent=2)
                        
                    saved_count += 1
                except Exception as e:
                    print_error(f"Ошибка при сохранении Keystore: {e}")
                finally:
                    progress.advance(ks_task)

        print_success(f"Сохранено {saved_count} Keystore файлов.")
        console.print(f"📂 Директория: [underline]{batch_dir}[/underline]")
        
    else:
        filename = f"wallets_{coin_symbol}{file_tag}_{timestamp}.enc"
        full_path = os.path.join(ENC_DIR, filename)

        with open(full_path, "wb") as f:
            f.write(encrypt_data(wallets_data, save_pass))

        print_success(f"Сохранено {len(wallets_data)} шт. в один архив.")
        console.print(f"📂 Путь: [underline]{full_path}[/underline]")
        
    input("\nНажмите Enter в меню...")
def run_decryptor():
    if not os.path.exists(ENC_DIR):
        print_error(f"Папка {ENC_DIR} не найдена!")
        return

    while True:
        try:
            if _run_decryptor_logic():
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Действие отменено (Ctrl+C). Возврат к выбору файла...[/yellow]")
            import time
            time.sleep(1)
            continue

def _run_decryptor_logic():
    ui_manager.print_breadcrumbs("🔓 Расшифровать файл")
    files = [f for f in os.listdir(ENC_DIR) if f.endswith('.enc')]
    if not files:
        questionary.select(
            "Выберите файл:",
            choices=[
                "🔙 Назад",
                questionary.Separator(f" \n  ❌ В папке {os.path.basename(ENC_DIR)} не обнаружено файлов для расшифровки.")
            ],
            style=ui_manager.custom_style
        ).ask()
        return True

    filename = questionary.select("Выберите файл:", choices=["🔙 Назад"] + files, style=ui_manager.custom_style).ask()
    if not filename or "Назад" in filename: return True

    while True:
        pwd = questionary.password("Пароль от файла:", style=ui_manager.custom_style).ask()
        if pwd is None: 
            return False
            
        if not pwd:
            print_error("Данные не введены. Пароль пуст.")
            import time
            time.sleep(1)
            continue
            
        break

    filepath = os.path.join(ENC_DIR, filename)
    data = decrypt_data(filepath, pwd)

    if data:
        print_success("Успешно расшифровано!")

        console.print()
        from rich.table import Table
        from rich.panel import Panel
        export_table = Table(show_header=False, box=None, padding=(0, 2))
        export_table.add_column("Опция", style="bold cyan")
        export_table.add_column("Описание", style="dim", overflow="fold")
        export_table.add_row("👀 Показать на экране", "Вывести первые 20 кошельков прямо в терминал")
        export_table.add_row("💾 Сохранить в CSV", "Выгрузить в удобную таблицу для Excel")
        export_table.add_row("📋 Сохранить в JSON", "Выгрузить в структурированный текстовый формат")
        export_table.add_row("🖨️  Сохранить в QR PDF", "Сгенерировать документ с 2 кошельками на страницу (с QR кодами)")
        export_table.add_row("📄 Paper Wallet PDF", "Бумажный кошелек с линией сгиба для безопасного хранения")
        console.print(Panel(export_table, expand=False, title="[bold white]Форматы экспорта[/bold white]", border_style="cyan"))
        console.print()

        act = questionary.select(
            "Действие:",
            choices=["👀 Показать на экране", "💾 Сохранить в CSV", "📋 Сохранить в JSON", "🖨️  Сохранить в QR PDF", "📄 Paper Wallet PDF", "🔙 Назад"],
            style=ui_manager.custom_style
        ).ask()

        if not act or "Назад" in act:
            return False

        if "Показать" in act:
            table = Table(title=filename, style="magenta")
            if len(data) > 0:
                # Добавляем колонки динамически
                for k in data[0].keys():
                    table.add_column(k, overflow="fold")
                # Добавляем строки (ограничим вывод 20 строками)
                for row in data[:20]:
                    table.add_row(*[str(row.get(k, "")) for k in data[0].keys()])

            console.print(table)
            if len(data) > 20:
                print_info(f"... и еще {len(data) - 20} строк")

        elif "CSV" in act:
            import csv
            base_name = os.path.basename(filename).replace(".enc", ".csv")
            csv_path = os.path.join(CSV_DIR, f"decrypted_{base_name}")

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            print_success(f"Сохранено: {csv_path}")

        elif "JSON" in act:
            base_name = os.path.basename(filename).replace(".enc", ".json")
            json_path = os.path.join(CSV_DIR, f"decrypted_{base_name}")

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print_success(f"Сохранено: {json_path}")

        elif "QR PDF" in act:
            from modules.pdf_export import export_qr_pdf
            base_name = os.path.basename(filename).replace(".enc", "_QR.pdf")
            pdf_path = os.path.join(CSV_DIR, f"decrypted_{base_name}")
            export_qr_pdf(data, pdf_path, title=filename)
            print_success(f"Сохранено: {pdf_path}")

        elif "Paper Wallet" in act:
            from modules.pdf_export import export_paper_wallet
            base_name = os.path.basename(filename).replace(".enc", "_PaperWallet.pdf")
            pdf_path = os.path.join(CSV_DIR, f"decrypted_{base_name}")
            export_paper_wallet(data, pdf_path)
            print_success(f"Сохранено: {pdf_path}")

        console.print()
        post_act = questionary.select(
            "Что делать дальше?",
            choices=["🔙 Назад (к выбору файла)", "🏠 В главное меню"],
            style=ui_manager.custom_style
        ).ask()
        
        if not post_act or "Назад" in post_act:
            return False
        return True
        
    else:
        print_error("Неверный пароль или битый файл!")
        import time
        time.sleep(1)

    return False


def _detect_config(wallet):
    """Определяет config для повторной генерации на основе поля type."""
    wtype = wallet.get("type", "")
    config = {}

    # BTC: определяем mode из type
    if "BIP-84" in wtype or "Native" in wtype:
        config["mode"] = "NATIVE"
    elif "BIP-86" in wtype or "Taproot" in wtype:
        config["mode"] = "TAPROOT"
    elif "BIP-44" in wtype or "Legacy" in wtype:
        config["mode"] = "LEGACY"
    elif "BIP-49" in wtype or "Nested" in wtype:
        config["mode"] = "NESTED"

    # XMR: определяем mnemonic_type
    if "Legacy 25" in wtype:
        config["mnemonic_type"] = "legacy"
    elif "Polyseed" in wtype:
        config["mnemonic_type"] = "polyseed"
    elif "BIP39" in wtype and "Cake" in wtype:
        config["mnemonic_type"] = "bip39"

    return config


def run_verifier():
    """Верификация кошельков — проверяет что мнемоника → адрес совпадает."""
    
    while True:
        try:
            if _run_verifier_logic():
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Действие отменено (Ctrl+C). Возврат к выбору формата...[/yellow]")
            import time
            time.sleep(1)
            continue

def _run_verifier_logic():
    ui_manager.print_breadcrumbs("✅ Верифицировать кошельки")
    
    file_type = questionary.select(
        "Выберите формат файла для верификации:",
        choices=[
            "🔒 Зашифрованный (.enc)",
            "📄 CSV (.csv)",
            "📋 JSON (.json)",
            "🔙 Назад"
        ],
        style=ui_manager.custom_style
    ).ask()

    if not file_type or "Назад" in file_type:
        return True

    is_enc = ".enc" in file_type
    is_csv = ".csv" in file_type
    is_json = ".json" in file_type

    target_dir = ENC_DIR if is_enc else CSV_DIR
    ext = ".enc" if is_enc else ".csv" if is_csv else ".json"

    if not os.path.exists(target_dir):
        print_error(f"Папка {target_dir} не найдена!")
        return False

    files = [f for f in os.listdir(target_dir) if f.endswith(ext)]
    if not files:
        questionary.select(
            f"Выберите файл ({ext}):",
            choices=[
                "🔙 Назад",
                questionary.Separator(f" \n  ❌ В папке {os.path.basename(target_dir)} не обнаружено файлов {ext} для верификации.")
            ],
            style=ui_manager.custom_style
        ).ask()
        return False

    filename = questionary.select(f"Выберите файл ({ext}):", choices=["🔙 Назад"] + files, style=ui_manager.custom_style).ask()
    if not filename or "Назад" in filename: return False
    filepath = os.path.join(target_dir, filename)

    data = None
    if is_enc:
        while True:
            pwd = questionary.password("Пароль от файла:", style=ui_manager.custom_style).ask()
            if pwd is None: 
                return False
                
            if not pwd:
                print_error("Данные не введены.")
                import time
                time.sleep(1)
                continue
            break
        data = decrypt_data(filepath, pwd)
        if not data:
            print_error("Неверный пароль или битый файл!")
    elif is_csv:
        import csv
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        except Exception as e:
            print_error(f"Ошибка чтения CSV: {e}")
    elif is_json:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print_error(f"Ошибка чтения JSON: {e}")

    if not data:
        import time
        time.sleep(1)
        return False

    print_success(f"Загружено {len(data)} кошельков. Начинаю верификацию...")
    networks = load_networks()

    # Маппинг символа → модуль
    sym_to_module = {}
    for name, gen_cls in networks.items():
        sym_to_module[gen_cls.SYMBOL] = gen_cls
        sym_to_module[name] = gen_cls
        # Также маппим символ с суффиксом (BTC_TAPROOT и т.д.)
        for suffix in ["_NATIVE", "_TAPROOT", "_LEGACY", "_NESTED"]:
            sym_to_module[gen_cls.SYMBOL + suffix] = gen_cls
            sym_to_module[name + suffix] = gen_cls

    ok_count = 0
    fail_count = 0
    skip_count = 0

    results_table = Table(show_header=True, header_style="bold magenta")
    results_table.add_column("#", style="dim", width=4)
    results_table.add_column("Сеть", width=10)
    results_table.add_column("Адрес", style="dim", width=30, overflow="fold")
    results_table.add_column("Статус", width=12)

    for idx, wallet in enumerate(data):
        net_sym = wallet.get("network", "")
        stored_addr = wallet.get("address", "")
        mn_str = wallet.get("mnemonic", "")
        passphrase = wallet.get("passphrase", "")
        wtype = wallet.get("type", "")

        gen_cls = sym_to_module.get(net_sym)
        if not gen_cls:
            results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[yellow]⏭ SKIP[/yellow]")
            skip_count += 1
            continue

        config = _detect_config(wallet)

        try:
            # XMR Legacy/Polyseed — мнемоника не BIP39, пропускаем перегенерацию
            if config.get("mnemonic_type") in ("legacy", "polyseed"):
                # Для Legacy/Polyseed мы не можем перегенерировать из той же мнемоники
                # (они случайные), но мы можем проверить приватный ключ → адрес
                from bip_utils import Monero, MoneroCoins
                pk_hex = wallet.get("private_key", "")
                if pk_hex:
                    pk_bytes = bytes.fromhex(pk_hex)
                    xmr = Monero.FromSeed(pk_bytes, MoneroCoins.MONERO_MAINNET)
                    derived_addr = str(xmr.PrimaryAddress())
                    if derived_addr == stored_addr:
                        results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[green]✅ OK[/green]")
                        ok_count += 1
                    else:
                        results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[red]❌ FAIL[/red]")
                        fail_count += 1
                else:
                    results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[yellow]⏭ SKIP[/yellow]")
                    skip_count += 1
                continue

            # Стандартный путь: мнемоника → seed → generate → сравнение
            seed = Bip39SeedGenerator(mn_str).Generate(passphrase)

            sig = inspect.signature(gen_cls.generate)
            call_args = {'seed_bytes': seed}
            if 'config' in sig.parameters:
                call_args['config'] = config
            if 'mnemonic' in sig.parameters:
                call_args['mnemonic'] = mn_str

            result = gen_cls.generate(**call_args)
            derived_addr = result.get("address", "")

            if derived_addr == stored_addr:
                results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[green]✅ OK[/green]")
                ok_count += 1
            else:
                results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", "[red]❌ FAIL[/red]")
                fail_count += 1

        except Exception as e:
            results_table.add_row(str(idx + 1), net_sym, stored_addr[:25] + "...", f"[yellow]⚠ {str(e)[:15]}[/yellow]")
            skip_count += 1

    console.print()
    console.print(results_table)
    console.print()
    console.print(f"[bold green]✅ OK: {ok_count}[/bold green]  [bold red]❌ FAIL: {fail_count}[/bold red]  [yellow]⏭ SKIP: {skip_count}[/yellow]  [dim]Total: {len(data)}[/dim]")
    
    console.print()
    post_act = questionary.select(
        "Что делать дальше?",
        choices=["🔙 Назад (к выбору формата)", "🏠 В главное меню"],
        style=ui_manager.custom_style
    ).ask()
    
    if not post_act or "Назад" in post_act:
        return False
    return True


def main_menu():
    print_banner("")

    from rich.table import Table
    from rich.panel import Panel

    desc_table = Table(show_header=False, box=None, padding=(0, 2))
    desc_table.add_column("Опция", style="bold cyan")
    desc_table.add_column("Описание", style="dim", overflow="fold")
    
    desc_table.add_row("🚀 Сгенерировать кошельки", "Массовое создание и жесткое шифрование новых кошельков")
    desc_table.add_row("🔓 Расшифровать файл", "Чтение архивов (.enc) и экспорт (CSV, JSON, PDF)")
    desc_table.add_row("✅ Верифицировать кошельки", "Сверка сгенерированных адресов с мнемонической фразой")
    desc_table.add_row("✨ Vanity-адрес генератор", "Поиск красивых адресов по слову (Использует все ядра CPU)")
    desc_table.add_row("🧩 Разделение секрета", "Разбить seed-фразу на части для безопасного хранения (Shamir)")
    
    console.print(Panel(desc_table, expand=False, title="[bold white]Навигация главного меню[/bold white]", border_style="cyan"))
    console.print()

    choices = ["🚀 Сгенерировать кошельки", "🔓 Расшифровать файл", "✅ Верифицировать кошельки", "✨ Vanity-адрес генератор", "🧩 Разделение секрета (Shamir)", "❌ Выход"]

    action = questionary.select("Выберите действие:", choices=choices, style=ui_manager.custom_style).ask()

    # --- ЛОГИКА ВЫХОДА ---
    if not action or "Выход" in action:
        return False  # Сигнал для остановки цикла

    # --- ОБРАБОТКА ДЕЙСТВИЙ ---
    if "Сгенерировать" in action:
        run_generator()
    elif "Расшифровать" in action:
        run_decryptor()
    elif "Верифицировать" in action:
        run_verifier()
    elif "Vanity" in action:
        from modules.vanity_gen import run_vanity_generator
        run_vanity_generator()
    elif "Shamir" in action:
        from modules.shamir_utils import run_shamir_menu
        run_shamir_menu()

    return True  # Сигнал, что нужно продолжить работу (показать меню снова)


if __name__ == "__main__":
    while True:
        try:
            # Если main_menu вернет False, мы прерываем цикл (break)
            should_continue = main_menu()
            if not should_continue:
                console.print("\n[green]Bye! 👋[/green]")
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Действие отменено (Ctrl+C). Возврат в главное меню...[/yellow]")
            time.sleep(1)
            continue