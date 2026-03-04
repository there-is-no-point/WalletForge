"""Утилита для разделения и восстановления секрета (Shamir's Secret Sharing)."""
import base64
import os
import shamirs


def split_secret(secret_text: str, total_shares: int, threshold: int) -> list[str]:
    """
    Разбивает строку secret_text на total_shares частей.
    """
    if threshold > total_shares:
        raise ValueError("Порог (M) не может быть больше общего количества (N).")
    if threshold < 2:
        raise ValueError("Порог (M) должен быть не меньше 2.")

    secret_bytes = secret_text.encode('utf-8')
    
    # shamirs поддерживает числа до ~2^127 если явно не указать прайм
    # Разобьем байты на чанки по 16 байт (128 бит) чтобы точно влезть
    chunk_size = 15
    chunks = [secret_bytes[i:i+chunk_size] for i in range(0, len(secret_bytes), chunk_size)]
    
    # Для каждого чанка генерируем доли
    # [[(idx, val), (idx, val), ...], [[(idx, val), (idx, val), ...]]
    shares_per_chunk = []
    for chunk in chunks:
        chunk_int = int.from_bytes(chunk, byteorder='big')
        # Если чанк состоит из нулей, from_bytes вернет 0, это ок
        s = shamirs.shares(chunk_int, quantity=total_shares, threshold=threshold)
        shares_per_chunk.append(s)
        
    encoded_shares = []
    # Теперь собираем итоговые строки для каждого участника (от 1 до total_shares)
    for share_idx in range(total_shares):
        # Собираем значения для этого share_idx со всех чанков
        # В shamirs.shares возвращается список Share объектов,
        # где index = 1, 2, ..., total_shares
        
        # Индексы начинаются с 1
        current_index = share_idx + 1
        
        vals_hex = []
        for s_list in shares_per_chunk:
            # Находим долю с нужным индексом
            share_obj = next(s for s in s_list if s.index == current_index)
            # Конвертируем значение в hex фиксированной длины (так как чанки по 15 байт, 
            # значения могут быть чуть больше, используем динамический hex)
            # Проще просто сохранить hex строку
            vals_hex.append(hex(share_obj.value)[2:])
            
        # Объединяем значения через :
        merged_vals = ":".join(vals_hex)
        share_str = f"SHAMIR-{threshold}-{total_shares}-{current_index}-{merged_vals}"
        
        b64 = base64.b64encode(share_str.encode('ascii')).decode('ascii')
        encoded_shares.append(b64)
        
    return encoded_shares


def combine_shares(encoded_shares: list[str]) -> str:
    """Осколки -> текст"""
    if len(encoded_shares) < 2:
        raise ValueError("Для восстановления нужно минимум 2 части.")

    # парсим осколки: { chunk_id: [(index, value), (index, value)...] }
    chunks_data = {}
    threshold = None

    for b64 in encoded_shares:
        try:
            share_str = base64.b64decode(b64.encode('ascii')).decode('ascii')
            parts = share_str.split('-', maxsplit=4)
            if len(parts) != 5 or parts[0] != "SHAMIR":
                raise ValueError("Неверный формат осколка.")
                
            m = int(parts[1])
            if threshold is None:
                threshold = m
            
            idx = int(parts[3])
            vals = parts[4].split(':')
            
            for chunk_i, v_hex in enumerate(vals):
                if chunk_i not in chunks_data:
                    chunks_data[chunk_i] = []
                # Важно: shamirs.interpolate ожидает объекты share (с маленькой буквы)
                share_obj = shamirs.share(idx, int(v_hex, 16))
                chunks_data[chunk_i].append(share_obj)
                
        except Exception as e:
            raise ValueError(f"Ошибка парсинга осколка: {e}")

    # Восстанавливаем по чанкам
    recovered_bytes = bytearray()
    for chunk_i in sorted(chunks_data.keys()):
        shares = chunks_data[chunk_i]
        if len(shares) < threshold:
            raise ValueError("Недостаточно частей для восстановления!")
            
        # Передаем явно дефолтный модуль (2**127 - 1)
        MODULUS = (2 ** 127) - 1
        chunk_int = shamirs.interpolate(shares, modulus=MODULUS)
        
        # Так как ведущие нули могли быть потеряны при int.from_bytes,
        # нам нужно знать оригинальный размер. Последний чанк может быть меньше.
        # Поскольку мы не сохраняли длины, мы просто конвертируем обратно в минимально необходимое кол-во байт,
        # НО это может обрезать нули в начале чанка!
        # Решение: мы можем договориться обрезать нули только для первого байта,
        # но лучше мы используем фиксированный размер чанка 15 байт, кроме последнего.
        
        blen = (chunk_int.bit_length() + 7) // 8
        b = chunk_int.to_bytes(blen, byteorder='big')
        
        # Если это не последний чанк и длина < 15, добиваем нулями слева
        if chunk_i < len(chunks_data) - 1:
            while len(b) < 15:
                b = b'\x00' + b
                
        recovered_bytes.extend(b)

    return recovered_bytes.decode('utf-8')


def run_shamir_menu():
    """Интерфейс для работы с осколками."""
    import questionary
    import ui_manager
    import time
    import glob
    import json
    from ui_manager import console, print_info, print_success, print_error, print_warning
    from main import CSV_DIR, ENC_DIR, encrypt_data, decrypt_data
    
    console.clear()
    ui_manager.print_banner("🧩 Разделение секрета (Shamir)")
    
    action = questionary.select(
        "Что вы хотите сделать?",
        choices=[
            "🔪 Разбить секрет на части",
            "🧩 Восстановить из частей",
            "🔙 Назад"
        ],
        style=ui_manager.custom_style
    ).ask()
    
    if not action or "Назад" in action:
        return
        
    if "Разбить" in action:
        secret = questionary.password("Введите секрет (мнемоника, приватный ключ, пароль):", style=ui_manager.custom_style).ask()
        if not secret: return
        
        total_str = questionary.text("На сколько всего частей разбить (N)?", default="5", style=ui_manager.custom_style).ask()
        thresh_str = questionary.text("Сколько частей нужно для восстановления (M)?", default="3", style=ui_manager.custom_style).ask()
        
        try:
            total = int(total_str)
            thresh = int(thresh_str)
            shares = split_secret(secret, total, thresh)
            
            console.print()
            print_success(f"✅ Секрет успешно разбит на {total} частей!")
            print_info(f"Для восстановления потребуется **ЛЮБЫЕ {thresh} из {total}** частей.")
            console.print("[dim]Сохраните эти строки в разные надежные места. Потеряв более чем (N-M) частей секрет не восстановить![/dim]")
            
            console.print()
            for i, s in enumerate(shares):
                console.print(f"[bold cyan]Часть {i+1}:[/] {s}")
            console.print()
            
            # --- Выбор формата сохранения ---
            save_fmt = questionary.select(
                "Как сохранить части?",
                choices=[
                    "📂 Текстовые файлы (.txt) — без шифрования",
                    "🔒 Зашифрованные файлы (.enc) — каждая часть отдельно",
                    "⏩ Не сохранять (уже скопировал из консоли)"
                ],
                style=ui_manager.custom_style
            ).ask()
            
            if save_fmt and "Текстовые" in save_fmt:
                ts = int(time.time())
                save_dir = os.path.join(CSV_DIR, f"shamir_{ts}")
                os.makedirs(save_dir, exist_ok=True)
                
                for i, s in enumerate(shares):
                    path = os.path.join(save_dir, f"share_{i+1}_of_{total}.txt")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(f"SHAMIR SHARE {i+1} OF {total} (Requires {thresh} to restore)\n\n")
                        f.write(s)
                print_success(f"Все части сохранены в папку: {save_dir}")
                
            elif save_fmt and "Зашифрованные" in save_fmt:
                pwd = questionary.password("Пароль для шифрования частей:", style=ui_manager.custom_style).ask()
                if not pwd:
                    print_error("Пароль не указан, сохранение отменено.")
                else:
                    ts = int(time.time())
                    save_dir = os.path.join(ENC_DIR, f"shamir_{ts}")
                    os.makedirs(save_dir, exist_ok=True)
                    
                    for i, s in enumerate(shares):
                        share_data = [{"share_index": i + 1, "total": total, "threshold": thresh, "data": s}]
                        enc_bytes = encrypt_data(share_data, pwd)
                        path = os.path.join(save_dir, f"share_{i+1}_of_{total}.enc")
                        with open(path, "wb") as f:
                            f.write(enc_bytes)
                    print_success(f"🔒 Все части зашифрованы и сохранены в: {save_dir}")
                    print_info("Каждую часть можно хранить отдельно и расшифровать при восстановлении.")
                
        except Exception as e:
            print_error(f"Ошибка при разделении: {e}")
            
    elif "Восстановить" in action:
        # --- Выбор источника частей ---
        source = questionary.select(
            "Откуда загрузить части?",
            choices=[
                "📂 Из папки с файлами (.txt)",
                "🔒 Из папки с зашифрованными файлами (.enc)",
                "📁 Указать путь к папке вручную",
                "⌨️  Ввести вручную (вставить из буфера)"
            ],
            style=ui_manager.custom_style
        ).ask()
        if not source: 
            input("\nНажмите Enter...")
            return
            
        shares_input = []
        
        if "txt" in source:
            # Ищем папки shamir_* в CSV_DIR
            shamir_dirs = sorted(glob.glob(os.path.join(CSV_DIR, "shamir_*")))
            if not shamir_dirs:
                print_error(f"Нет папок shamir_* в {CSV_DIR}")
                input("\nНажмите Enter...")
                return
                
            dir_choice = questionary.select(
                "Выберите папку с частями:",
                choices=[os.path.basename(d) for d in shamir_dirs],
                style=ui_manager.custom_style
            ).ask()
            if not dir_choice:
                input("\nНажмите Enter...")
                return
                
            chosen_dir = os.path.join(CSV_DIR, dir_choice)
            txt_files = sorted(glob.glob(os.path.join(chosen_dir, "*.txt")))
            
            if not txt_files:
                print_error("Папка не содержит .txt файлов.")
                input("\nНажмите Enter...")
                return
            
            # Показываем найденные файлы, даем выбрать какие загрузить
            file_choices = [os.path.basename(f) for f in txt_files]
            selected = questionary.checkbox(
                "Выберите части для загрузки (нужно минимум M штук):",
                choices=file_choices,
                style=ui_manager.custom_style
            ).ask()
            
            if not selected or len(selected) < 2:
                print_error("Выберите минимум 2 части.")
                input("\nНажмите Enter...")
                return
            
            for fname in selected:
                fpath = os.path.join(chosen_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                # Берем последнюю непустую строку (сама доля идет после заголовка)
                lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
                if lines:
                    shares_input.append(lines[-1])
                    
            print_info(f"Загружено {len(shares_input)} частей из файлов.")
            
        elif "enc" in source:
            # Ищем папки shamir_* в ENC_DIR
            shamir_dirs = sorted(glob.glob(os.path.join(ENC_DIR, "shamir_*")))
            if not shamir_dirs:
                print_error(f"Нет папок shamir_* в {ENC_DIR}")
                input("\nНажмите Enter...")
                return
                
            dir_choice = questionary.select(
                "Выберите папку с зашифрованными частями:",
                choices=[os.path.basename(d) for d in shamir_dirs],
                style=ui_manager.custom_style
            ).ask()
            if not dir_choice:
                input("\nНажмите Enter...")
                return
                
            chosen_dir = os.path.join(ENC_DIR, dir_choice)
            enc_files = sorted(glob.glob(os.path.join(chosen_dir, "*.enc")))
            
            if not enc_files:
                print_error("Папка не содержит .enc файлов.")
                input("\nНажмите Enter...")
                return
            
            file_choices = [os.path.basename(f) for f in enc_files]
            selected = questionary.checkbox(
                "Выберите части для расшифровки (нужно минимум M штук):",
                choices=file_choices,
                style=ui_manager.custom_style
            ).ask()
            
            if not selected or len(selected) < 2:
                print_error("Выберите минимум 2 части.")
                input("\nНажмите Enter...")
                return
            
            pwd = questionary.password("Пароль для расшифровки:", style=ui_manager.custom_style).ask()
            if not pwd:
                print_error("Пароль не указан.")
                input("\nНажмите Enter...")
                return
            
            for fname in selected:
                fpath = os.path.join(chosen_dir, fname)
                try:
                    data = decrypt_data(fpath, pwd)
                    if data and len(data) > 0:
                        shares_input.append(data[0]["data"])
                except Exception as e:
                    print_error(f"Ошибка расшифровки {fname}: {e}")
                    
            print_info(f"Расшифровано и загружено {len(shares_input)} частей.")
            
        elif "путь" in source.lower():
            # Произвольная папка
            print_info("⚠ В папке желательно чтобы находились ТОЛЬКО файлы частей (shares).")
            folder_path = questionary.text(
                "Введите полный путь к папке с частями:",
                style=ui_manager.custom_style
            ).ask()
            
            if not folder_path or not os.path.isdir(folder_path):
                print_error("Папка не найдена или путь неверный.")
                input("\nНажмите Enter...")
                return
            
            # Ищем .txt и .enc файлы
            all_txt = sorted(glob.glob(os.path.join(folder_path, "*.txt")))
            all_enc = sorted(glob.glob(os.path.join(folder_path, "*.enc")))
            
            if not all_txt and not all_enc:
                print_error("В указанной папке нет .txt или .enc файлов.")
                input("\nНажмите Enter...")
                return
            
            if all_txt and all_enc:
                file_type = questionary.select(
                    "В папке найдены и .txt и .enc файлы. Что загрузить?",
                    choices=["📄 Текстовые (.txt)", "🔒 Зашифрованные (.enc)"],
                    style=ui_manager.custom_style
                ).ask()
                if not file_type:
                    input("\nНажмите Enter...")
                    return
                target_files = all_txt if "txt" in file_type else all_enc
                is_enc = "enc" in file_type
            elif all_enc:
                target_files = all_enc
                is_enc = True
            else:
                target_files = all_txt
                is_enc = False
            
            file_choices = [os.path.basename(f) for f in target_files]
            selected = questionary.checkbox(
                "Выберите части для загрузки (минимум M штук):",
                choices=file_choices,
                style=ui_manager.custom_style
            ).ask()
            
            if not selected or len(selected) < 2:
                print_error("Выберите минимум 2 части.")
                input("\nНажмите Enter...")
                return
            
            if is_enc:
                pwd = questionary.password("Пароль для расшифровки:", style=ui_manager.custom_style).ask()
                if not pwd:
                    print_error("Пароль не указан.")
                    input("\nНажмите Enter...")
                    return
                for fname in selected:
                    fpath = os.path.join(folder_path, fname)
                    try:
                        data = decrypt_data(fpath, pwd)
                        if data and len(data) > 0:
                            shares_input.append(data[0]["data"])
                    except Exception as e:
                        print_error(f"Ошибка расшифровки {fname}: {e}")
            else:
                for fname in selected:
                    fpath = os.path.join(folder_path, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
                    if lines:
                        shares_input.append(lines[-1])
            
            print_info(f"Загружено {len(shares_input)} частей из {folder_path}")

        else:
            # Ручной ввод
            print_info("Введите части по одной. Закончите ввод пустой строкой.")
            i = 1
            while True:
                s = questionary.text(f"Введите часть {i} (или Enter для завершения):", style=ui_manager.custom_style).ask()
                if not s:
                    break
                s = s.strip()
                if s:
                    shares_input.append(s)
                    i += 1
                
        if len(shares_input) < 2:
            print_error("Для восстановления нужно минимум 2 части.")
            input("\nНажмите Enter...")
            return
            
        try:
            secret = combine_shares(shares_input)
            console.print()
            print_success("✅ Секрет успешно восстановлен!")
            console.print()
            console.print(f"[bold magenta]Секрет:[/] [white]{secret}[/]")
            console.print()
        except Exception as e:
            print_error(f"Не удалось восстановить секрет: {e}")
            
    input("\nНажмите Enter...")
