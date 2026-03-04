"""Утилита для генерации красивых (vanity) адресов через перебор."""
import time
import multiprocessing
import sys
from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum, Bip39SeedGenerator


def search_vanity_worker(network_name, config, patterns, search_mode, case_sensitive, stop_flag, counter, lock):
    """
    Рабочий процесс. Бесконечно генерирует кошельки, пока не найдет совпадение
    или пока не будет установлен stop_flag.
    
    patterns: список паттернов для мульти-поиска
    search_mode: 'prefix', 'suffix', 'contains'
    """
    from main import load_networks
    
    try:
        networks = load_networks()
        gen_cls = networks.get(network_name)
        if not gen_cls:
            return None
            
        import inspect
        sig = inspect.signature(gen_cls.generate)
        
        # Предварительно обрабатываем паттерны для case-insensitive
        if not case_sensitive:
            patterns = [p.lower() for p in patterns]
        
        while not stop_flag.value:
            local_count = 0
            for _ in range(50):
                if stop_flag.value:
                    break
                    
                # 1. Генерируем случайную мнемонику и seed
                mn_obj = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
                mn_str = str(mn_obj)
                seed = Bip39SeedGenerator(mn_obj).Generate("")
                
                # 2. Подготавливаем аргументы
                call_args = {'seed_bytes': seed}
                if 'config' in sig.parameters:
                    call_args['config'] = config
                if 'mnemonic' in sig.parameters:
                    call_args['mnemonic'] = mn_str
                    
                # 3. Генерируем кошелек
                try:
                    w_keys = gen_cls.generate(**call_args)
                    addr = w_keys.get("address", "")
                except Exception:
                    local_count += 1
                    continue
                    
                if not addr:
                    local_count += 1
                    continue
                    
                # 4. Проверяем паттерны
                check_addr = addr
                # Для EVM убираем "0x" при поиске в начале
                if addr.startswith("0x") and search_mode == "prefix":
                    check_addr = addr[2:]
                    
                if not case_sensitive:
                    check_addr = check_addr.lower()
                    
                found = False
                matched_pattern = ""
                for pat in patterns:
                    if search_mode == "prefix" and check_addr.startswith(pat):
                        found = True
                        matched_pattern = pat
                        break
                    elif search_mode == "suffix" and check_addr.endswith(pat):
                        found = True
                        matched_pattern = pat
                        break
                    elif search_mode == "contains" and pat in check_addr:
                        found = True
                        matched_pattern = pat
                        break
                    
                if found:
                    stop_flag.value = True
                    result = {
                        "network": network_name,
                        "address": addr,
                        "private_key": w_keys.get("private_key"),
                        "mnemonic": mn_str,
                        "passphrase": "",
                        "matched_pattern": matched_pattern
                    }
                    if "view_key" in w_keys:
                        result["view_key"] = w_keys["view_key"]
                    return result
                    
                local_count += 1
                
            # Добавляем к глобальному счетчику
            with lock:
                counter.value += local_count
                
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Worker Error: {e}")
        
    return None


def _format_time(seconds):
    """Форматирует секунды в читаемый вид: 1д 2ч 30м или 5м 12с."""
    if seconds < 60:
        return f"{seconds:.0f}с"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}м {s}с"
    elif seconds < 86400:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}ч {m}м"
    else:
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        return f"{d}д {h}ч"


def run_vanity_generator():
    """Главная функция для запуска vanity генератора из консоли."""
    import questionary
    import ui_manager
    from ui_manager import console, print_info, print_success, print_error
    from main import load_networks
    
    console.clear()
    ui_manager.print_banner("✨ Vanity Address Generator ✨")
    
    # 0. Выбор потоков
    num_cores = multiprocessing.cpu_count()
    threads = questionary.text(
        f"0. Сколько потоков использовать? (Доступно ядер: {num_cores}):",
        default=str(num_cores),
        validate=lambda x: x.isdigit() and int(x) > 0,
        style=ui_manager.custom_style
    ).ask()
    if not threads: return
    num_threads = int(threads)
    
    # 1. Выбор сети
    networks = load_networks()
    if not networks:
        print_error("Нет доступных сетей!")
        return
        
    net_name = questionary.select(
        "1. Выберите сеть для поиска:",
        choices=list(networks.keys()),
        style=ui_manager.custom_style
    ).ask()
    if not net_name: return
    
    GeneratorClass = networks[net_name]
    net_config = {}
    
    if hasattr(GeneratorClass, "configure"):
        print_info(f"Настройка параметров {net_name}...")
        net_config = GeneratorClass.configure()
        if net_config is None: return
        
    if net_name == "Monero (XMR)":
        if net_config.get("mnemonic_type") != "bip39":
            print_info("Для Vanity-генератора используется BIP39. Продолжаю...")
            net_config["mnemonic_type"] = "bip39"

    # 2. Режим поиска (Префикс / Суффикс / Содержит)
    search_mode = questionary.select(
        "2. Искать совпадение в:",
        choices=[
            questionary.Choice("Начале адреса (Префикс - '0xBAD...')", value="prefix"),
            questionary.Choice("Конце адреса (Суффикс - '...BAD')", value="suffix"),
            questionary.Choice("В любом месте адреса (Содержит - '...BAD...')", value="contains")
        ],
        style=ui_manager.custom_style
    ).ask()
    if not search_mode: return
    
    # 3. Подсказка по допустимым символам для выбранной сети
    net_lower = net_name.lower()
    if "evm" in net_lower or "eth" in net_lower:
        print_info("🔤 EVM адреса (hex): допустимы только 0-9 и a-f. Буквы g-z НЕ существуют в адресе!")
    elif "bitcoin" in net_lower or "btc" in net_lower:
        print_info("🔤 Bitcoin (Base58): допустимы 1-9, A-Z, a-z. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "solana" in net_lower or "sol" in net_lower:
        print_info("🔤 Solana (Base58): допустимы 1-9, A-Z, a-z. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "monero" in net_lower or "xmr" in net_lower:
        print_info("🔤 Monero: адреса начинаются с 4 или 8, используют Base58 (без 0, O, I, l)")
    elif "tron" in net_lower or "trx" in net_lower:
        print_info("🔤 TRON (Base58): адреса начинаются с T. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "ripple" in net_lower or "xrp" in net_lower:
        print_info("🔤 Ripple (Base58): адреса начинаются с r. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "dogecoin" in net_lower or "doge" in net_lower:
        print_info("🔤 Dogecoin (Base58): адреса начинаются с D. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "litecoin" in net_lower or "ltc" in net_lower:
        print_info("🔤 Litecoin (Base58): адреса начинаются с L или M. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "sui" in net_lower:
        print_info("🔤 SUI адреса (hex): допустимы только 0-9 и a-f. Буквы g-z НЕ существуют в адресе!")
    elif "aptos" in net_lower or "apt" in net_lower:
        print_info("🔤 Aptos адреса (hex): допустимы только 0-9 и a-f. Буквы g-z НЕ существуют в адресе!")
    elif "cardano" in net_lower or "ada" in net_lower:
        print_info("🔤 Cardano (Bech32): допустимы только a-z и 0-9 (без заглавных). Исключены: 1, b, i, o")
    elif "polkadot" in net_lower or "dot" in net_lower:
        print_info("🔤 Polkadot (Base58): допустимы 1-9, A-Z, a-z. Исключены: 0 (ноль), O, I, l (строчная L)")
    elif "near" in net_lower:
        print_info("🔤 NEAR адреса (hex): допустимы только 0-9 и a-f")
    elif "tezos" in net_lower or "xtz" in net_lower:
        print_info("🔤 Tezos (Base58): адреса начинаются с tz1. Исключены: 0 (ноль), O, I, l (строчная L)")
    else:
        print_info("🔤 Проверьте формат адреса выбранной сети перед вводом паттерна")
    
    # Ввод паттерна (мульти-паттерн через запятую)
    pattern_str = questionary.text(
        "3. Введите текст для поиска (через запятую для нескольких: bad,dead,cafe):",
        validate=lambda x: len(x.strip()) > 0,
        style=ui_manager.custom_style
    ).ask()
    if not pattern_str: return
    
    # Разбиваем на список паттернов
    patterns = [p.strip() for p in pattern_str.split(",") if p.strip()]
    if not patterns:
        print_error("Не указан ни один паттерн!")
        return
    
    if len(patterns) > 1:
        print_info(f"Мульти-поиск: ищу любой из {len(patterns)} паттернов: {', '.join(patterns)}")
    
    # 4. Регистрозависимость
    case_sensitive = questionary.confirm(
        "4. Строго учитывать размер букв? (Да - 'AbC' ищет 'AbC', Нет - найдет 'abc', 'ABC')",
        default=False,
        style=ui_manager.custom_style
    ).ask()
    
    # Определяем допустимый алфавит для каждой сети
    charset_size = 16  # для hex (ETH)
    hex_chars = set("0123456789abcdef")
    addr_charset = hex_chars
    avg_addr_len = 40  # длина EVM адреса без 0x
    
    if net_name == "Bitcoin (Multi-Format)":
        charset_size = 58 if net_config.get("mode", "NATIVE") != "NATIVE" else 32
        addr_charset = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        avg_addr_len = 34
    elif net_name == "Solana (SOL)":
        charset_size = 58
        addr_charset = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        avg_addr_len = 44
    
    # Проверяем паттерны на допустимые символы
    for pat in patterns:
        check_pat = pat if case_sensitive else pat.lower()
        invalid_chars = set(check_pat) - (addr_charset if case_sensitive else set(c.lower() for c in addr_charset))
        if invalid_chars:
            from ui_manager import print_warning
            print_warning(f"⚠ Паттерн '{pat}' содержит символы {invalid_chars} недопустимые для {net_name}!")
            print_warning(f"  Для этой сети разрешены только: {'hex (0-9, a-f)' if charset_size == 16 else 'Base58 (без 0, O, I, l)'}")
            if not questionary.confirm("Продолжить всё равно?", default=False, style=ui_manager.custom_style).ask():
                return
    
    # Расчёт сложности — суммируем вероятность каждого паттерна
    def _calc_complexity(pats, cs, mode, addr_len):
        """Считает реальную сложность по сумме вероятностей всех паттернов."""
        total_prob = 0.0
        for pat in pats:
            pat_complexity = cs ** len(pat)
            if mode == "contains":
                positions = max(1, addr_len - len(pat))
                prob = positions / pat_complexity
            else:
                prob = 1.0 / pat_complexity
            total_prob += prob
        if total_prob == 0:
            return 999_999_999
        return int(1.0 / total_prob)
    
    complexity = _calc_complexity(patterns, charset_size, search_mode, avg_addr_len)
    
    print_info(f"Примерная сложность: {complexity:,} попыток (в среднем).")
    
    if complexity > 10_000_000:
        if not questionary.confirm(
            "⚠️ Это может занять МНОГО времени (часы или дни). Продолжить?",
            default=False,
            style=ui_manager.custom_style
        ).ask():
            return
            
    # === ЦИКЛ ПОИСКА (для мульти-паттервна с продолжением) ===
    active_patterns = list(patterns)
    
    while active_patterns:
        complexity = _calc_complexity(active_patterns, charset_size, search_mode, avg_addr_len)
        
        print_info(f"🚀 Запускаем поиск на {num_threads} потоках... (Ctrl+C для отмены)")
        if len(active_patterns) > 1:
            print_info(f"Ищу паттерны: {', '.join(active_patterns)} | Сложность: ~{complexity:,}")
        
        manager = multiprocessing.Manager()
        stop_flag = manager.Value('b', False)
        counter = manager.Value('i', 0)
        lock = manager.Lock()
        
        pool = multiprocessing.Pool(processes=num_threads)
        results = []
        
        for _ in range(num_threads):
            res = pool.apply_async(
                search_vanity_worker,
                (net_name, net_config, active_patterns, search_mode, case_sensitive, stop_flag, counter, lock)
            )
            results.append(res)
            
        # Мониторинг прогресса с ETA
        start_time = time.time()
        found_wallet = None
        
        try:
            while not stop_flag.value:
                time.sleep(0.5)
                elapsed = time.time() - start_time
                count = counter.value
                speed = count / elapsed if elapsed > 0 else 0
                
                # Расчет ETA
                if speed > 0:
                    remaining = max(0, (complexity - count)) / speed
                    if count > complexity:
                        # Уже превысили среднее — пересчитываем от текущей позиции
                        # Вероятность — геометрическое распределение, среднее время = complexity
                        # Если уже прошло count > complexity, среднее оставшееся ≈ complexity
                        remaining = complexity / speed
                    if remaining > 1:
                        eta_str = _format_time(remaining)
                    else:
                        eta_str = "скоро..."
                else:
                    eta_str = "считаю..."
                
                status_text = (
                    f"\r\033[1;36m⏳ Поиск...\033[0m "
                    f"Проверено: \033[1;33m{count:,}\033[0m | "
                    f"Скорость: \033[1;32m{speed:,.0f} адр/сек\033[0m | "
                    f"Прошло: \033[2m{_format_time(elapsed)}\033[0m | "
                    f"ETA: \033[1;35m~{eta_str}\033[0m      "
                )
                sys.stdout.write(status_text)
                sys.stdout.flush()
                
                # Проверяем, не нашел ли кто-то
                for r in results:
                    if r.ready():
                        val = r.get()
                        if val is not None:
                            found_wallet = val
                            stop_flag.value = True
                            break
                            
        except KeyboardInterrupt:
            console.print("\n\n[red]Остановлено пользователем![/red]")
            stop_flag.value = True
            
            pool.close()
            time.sleep(1)
            try:
                pool.terminate()
                pool.join()
            except:
                pass
                
            input("\nНажмите Enter...")
            return
            
        sys.stdout.write("\n")
        pool.close()
        pool.join()
        
        # Вывод результата
        if found_wallet:
            elapsed = time.time() - start_time
            
            # 🔔 Звуковой сигнал!
            try:
                import winsound
                winsound.Beep(1000, 300)
                time.sleep(0.1)
                winsound.Beep(1500, 300)
                time.sleep(0.1)
                winsound.Beep(2000, 500)
            except Exception:
                sys.stdout.write('\a')
                sys.stdout.flush()
            
            matched = found_wallet.get("matched_pattern", active_patterns[0])
            print_success(f"🎉 НАЙДЕНО за {_format_time(elapsed)}! Паттерн: '{matched}' (Проверено {counter.value:,} адресов)")
            
            from rich.table import Table
            t = Table(show_header=False, box=None)
            t.add_column("Key", style="bold cyan")
            t.add_column("Value")
            
            t.add_row("Network:", found_wallet["network"])
            
            # Подсветка совпадения
            addr = found_wallet["address"]
            search_addr = addr
            if not case_sensitive:
                search_addr = addr.lower()
                matched_lower = matched.lower()
            else:
                matched_lower = matched
                
            if search_mode == "prefix" and addr.startswith("0x"):
                pos = 2
            elif search_mode == "prefix":
                pos = 0
            elif search_mode == "suffix":
                pos = len(addr) - len(matched)
            else:
                pos = search_addr.find(matched_lower)
                if pos < 0:
                    pos = 0
            
            hl_len = len(matched)
            highlight_addr = f"{addr[:pos]}[bold yellow]{addr[pos:pos+hl_len]}[/bold yellow]{addr[pos+hl_len:]}"
                
            t.add_row("Address:", highlight_addr)
            t.add_row("Mnemonic:", found_wallet["mnemonic"])
            t.add_row("Private Key:", found_wallet.get("private_key", ""))
            
            console.print(t)
            
            # Сохранение
            console.print()
            if questionary.confirm("Сохранить результат в файл?", default=True, style=ui_manager.custom_style).ask():
                import os
                from main import encrypt_data, CSV_DIR, ENC_DIR
                
                save_format = questionary.select(
                    "Формат сохранения:",
                    choices=["🔒 Зашифрованный (.enc)", "📋 JSON открытый (.json)"],
                    style=ui_manager.custom_style
                ).ask()
                
                from datetime import datetime
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_net = found_wallet["network"].replace(" ", "_").replace("(", "").replace(")", "")
                safe_pat = matched.replace(",", "_")
                
                if "Зашифрованный" in save_format:
                    pwd = questionary.password("Пароль для шифрования:", style=ui_manager.custom_style).ask()
                    filename = f"vanity_{safe_net}_{safe_pat}_{ts}.enc"
                    full_path = os.path.join(ENC_DIR, filename)
                    with open(full_path, "wb") as f:
                        f.write(encrypt_data([found_wallet], pwd))
                    print_success(f"Сохранено в: {full_path}")
                else:
                    import json
                    filename = f"vanity_{safe_net}_{safe_pat}_{ts}.json"
                    full_path = os.path.join(CSV_DIR, filename)
                    with open(full_path, "w", encoding='utf-8') as f:
                        json.dump([found_wallet], f, indent=2, ensure_ascii=False)
                    print_success(f"Сохранено в: {full_path}")
            
            # === Продолжить поиск оставшихся паттернов? ===
            # Убираем найденный паттерн из списка
            if matched in active_patterns:
                active_patterns.remove(matched)
            
            if active_patterns:
                remaining_list = ", ".join(active_patterns)
                console.print()
                print_info(f"Осталось ненайденных паттернов: {len(active_patterns)} → {remaining_list}")
                
                if questionary.confirm(
                    f"Продолжить поиск оставшихся паттернов?",
                    default=True,
                    style=ui_manager.custom_style
                ).ask():
                    console.print()
                    continue  # Следующая итерация цикла while
                else:
                    break  # Выход из цикла
            else:
                if len(patterns) > 1:
                    print_success("🏆 Все паттерны найдены!")
                break
        else:
            print_error("Ничего не найдено (поиск прерван).")
            break
        
    input("\nНажмите Enter...")
