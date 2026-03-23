"""Утилита экспорта кошельков в QR PDF и Paper Wallet."""
import os
import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _make_qr_image(data_str, box_size=4):
    """Генерирует QR-код как PIL Image."""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=box_size, border=1)
    qr.add_data(data_str)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image()


def _draw_qr(c, img, x, y, size):
    """Рисует QR-код PIL Image на canvas reportlab."""
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    c.drawImage(ImageReader(buf), x, y, width=size, height=size)





def export_qr_pdf(data, output_path, title="Wallets"):
    """
    Экспортирует список кошельков в PDF с QR-кодами.

    Каждый кошелёк = блок с:
    - Сеть и номер
    - QR адреса + текст адреса
    - QR приватного ключа + текст ключа
    - Мнемоника (текстом)

    По 1 кошельку на страницу A4. ДИНАМИЧЕСКИЙ РАСЧЕТ РАЗМЕРОВ.
    """
    w, h = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    # Стили
    bg_color = HexColor("#16213e")
    accent = HexColor("#e94560")
    label_color = HexColor("#00d2ff") # Яркий голубой цвет для заголовков секций
    text_color = HexColor("#ffffff")

    margin_x = 10 * mm

    for idx, wallet in enumerate(data):
        # Сплошная заливка страницы
        c.setFillColor(bg_color)
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # Заголовок страницы
        cy = h - 15 * mm
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 18)
        network = wallet.get("network", "???")
        title_text = f"#{idx + 1}  {network}"
        c.drawCentredString(w / 2.0, cy, title_text)

        # Сбор всех блоков данных кошелька
        blocks = []
        if wallet.get("address"):
            blocks.append(("PUBLIC ADDRESS", wallet["address"]))
        if wallet.get("private_key"):
            blocks.append(("PRIVATE KEY", wallet["private_key"]))

        # Специфичные поля для сетей
        if wallet.get("view_key"):
            blocks.append(("PRIVATE VIEW KEY", wallet["view_key"]))
            
        if wallet.get("private_key_hex"):
            blocks.append(("PRIVATE KEY HEX", wallet["private_key_hex"]))

        if wallet.get("mnemonic"):
            blocks.append(("SEED PHRASE / MNEMONIC", wallet["mnemonic"]))
        if wallet.get("staking_key"):
            blocks.append(("STAKING KEY", wallet["staking_key"]))

        if not blocks:
            c.showPage()
            continue

        # Математика пространства
        # Доступная высота = от нижнего края заголовка до нижней границы страницы (10mm)
        available_h = (cy - 10 * mm) - 10 * mm 
        num_blocks = len(blocks)
        
        # Высота, доступная для каждого блока на листе
        block_h = available_h / num_blocks

        # QR код не может быть больше высоты блока минус отступы на текст (15mm)
        # Также ограничиваем максимальный размер QR до 47mm
        max_qr_h = block_h - 15 * mm
        qr_size = min(47 * mm, max_qr_h)

        cy -= 15 * mm # Начальный Y для первого блока
        
        # Расчет ширины текста для переноса строк 
        # Courier 12 = ~7.2 points width per char
        text_x = margin_x + qr_size + 6 * mm
        available_text_w = w - text_x - margin_x
        chars_per_line = int(available_text_w / 7.2)

        for title_label, val in blocks:
            block_top = cy
            
            c.setFillColor(label_color)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin_x, block_top, title_label)
            
            qr_y = block_top - 5 * mm - qr_size
            text_y = block_top - 10 * mm
            
            c.setFillColor(text_color)
            c.setFont("Courier", 12)
            
            # Текст справа от QR. Разбиваем на строки
            if title_label == "SEED PHRASE / MNEMONIC":
                words = val.split()
                line = ""
                cur_y = text_y
                for word in words:
                    if len(line) + len(word) + 1 > chars_per_line - 6: 
                        c.drawString(text_x, cur_y, line)
                        cur_y -= 6 * mm
                        line = word
                    else:
                        line = f"{line} {word}".strip()
                if line:
                    c.drawString(text_x, cur_y, line)
            else:
                chunk = chars_per_line
                cur_y = text_y
                for i in range(0, len(val), chunk):
                    c.drawString(text_x, cur_y, val[i:i + chunk])
                    cur_y -= 6 * mm

            # Рисуем QR код
            qr_img = _make_qr_image(val)
            _draw_qr(c, qr_img, margin_x, qr_y, qr_size)
            
            # Сдвигаем Y для следующего блока 
            cy -= block_h

        c.showPage()

    c.save()


def export_paper_wallet(data, output_path):
    """
    Paper Wallet — один кошелёк на страницу (landscape A4).

    Дизайн с линией сгиба:
    - Верхняя часть (PUBLIC): адрес + QR адреса (можно показывать)
    - Нижняя часть (PRIVATE): приватный ключ + QR ключа + мнемоника (скрыть при сгибе)
    - Пунктирная линия сгиба посередине ✂️
    """
    h_port, w_port = A4  # landscape: w и h меняются местами
    w, h = w_port, h_port

    cc = canvas.Canvas(output_path, pagesize=(w, h))

    # Цвета
    bg = HexColor("#0f0f1a")
    pub_bg = HexColor("#0d2137")
    priv_bg = HexColor("#1a0a0a")
    green_accent = HexColor("#00e676")
    red_accent = HexColor("#ff1744")
    white = HexColor("#ffffff")
    dim = HexColor("#999999")
    fold_color = HexColor("#555555")

    qr_size = 42 * mm
    margin = 12 * mm
    mid_y = h / 2

    for idx, wallet in enumerate(data):
        network = wallet.get("network", "CRYPTO")
        addr = wallet.get("address", "")
        pk = wallet.get("private_key", "")
        mn = wallet.get("mnemonic", "")
        vk = wallet.get("view_key", "")

        # === ФОН СТРАНИЦЫ ===
        cc.setFillColor(bg)
        cc.rect(0, 0, w, h, fill=1, stroke=0)

        # === ВЕРХНЯЯ ЧАСТЬ — PUBLIC ===
        cc.setFillColor(pub_bg)
        cc.roundRect(margin, mid_y + 4 * mm, w - 2 * margin, mid_y - margin - 4 * mm, 6, fill=1, stroke=0)

        # Заголовок PUBLIC
        cy = h - margin - 8 * mm
        cc.setFillColor(green_accent)
        cc.setFont("Helvetica-Bold", 18)
        cc.drawString(margin + 8 * mm, cy, f"PUBLIC  —  {network}")
        cc.setFont("Helvetica", 10)
        cc.drawString(w - margin - 55 * mm, cy, f"Wallet #{idx + 1}")

        # Подпись
        cy -= 7 * mm
        cc.setFillColor(dim)
        cc.setFont("Helvetica", 8)
        cc.drawString(margin + 8 * mm, cy, "Этот адрес можно свободно показывать для получения средств")

        # QR адреса (слева)
        qr_y = mid_y + 12 * mm
        if addr:
            qr_img = _make_qr_image(addr, box_size=6)
            _draw_qr(cc, qr_img, margin + 8 * mm, qr_y, qr_size)

        # Текст адреса (справа от QR)
        tx = margin + 8 * mm + qr_size + 8 * mm
        tcy = qr_y + qr_size - 4 * mm
        cc.setFillColor(dim)
        cc.setFont("Helvetica-Bold", 9)
        cc.drawString(tx, tcy, "ADDRESS")
        tcy -= 6 * mm
        cc.setFillColor(white)
        cc.setFont("Courier-Bold", 9)
        # Разбиваем адрес на строки
        chunk = 46
        for i in range(0, len(addr), chunk):
            cc.drawString(tx, tcy, addr[i:i + chunk])
            tcy -= 5 * mm

        # === ЛИНИЯ СГИБА ===
        cc.setStrokeColor(fold_color)
        cc.setDash(6, 4)
        cc.setLineWidth(0.8)
        cc.line(margin, mid_y, w - margin, mid_y)
        cc.setDash()  # сброс

        # Ножницы ✂
        cc.setFillColor(fold_color)
        cc.setFont("Helvetica", 10)
        cc.drawString(margin + 2 * mm, mid_y - 4 * mm, "✂ — — — FOLD HERE / СОГНИТЕ ЗДЕСЬ — — —")

        # === НИЖНЯЯ ЧАСТЬ — PRIVATE ===
        cc.setFillColor(priv_bg)
        cc.roundRect(margin, margin, w - 2 * margin, mid_y - margin - 6 * mm, 6, fill=1, stroke=0)

        # Заголовок PRIVATE
        cy = mid_y - margin - 2 * mm
        cc.setFillColor(red_accent)
        cc.setFont("Helvetica-Bold", 18)
        cc.drawString(margin + 8 * mm, cy, "PRIVATE  —  KEEP SECRET!")

        # Предупреждение
        cy -= 7 * mm
        cc.setFillColor(dim)
        cc.setFont("Helvetica", 8)
        cc.drawString(margin + 8 * mm, cy, "⚠ НИКОМУ НЕ ПОКАЗЫВАЙТЕ! Сложите бумагу по линии сгиба чтобы скрыть эту часть")

        # QR ключа (слева)
        qr_y = margin + 6 * mm
        if pk:
            qr_img = _make_qr_image(pk, box_size=6)
            _draw_qr(cc, qr_img, margin + 8 * mm, qr_y, qr_size)

        # Текст ключа (справа от QR)
        tx = margin + 8 * mm + qr_size + 8 * mm
        tcy = qr_y + qr_size - 4 * mm
        cc.setFillColor(dim)
        cc.setFont("Helvetica-Bold", 9)
        cc.drawString(tx, tcy, "PRIVATE KEY")
        tcy -= 6 * mm
        cc.setFillColor(white)
        cc.setFont("Courier-Bold", 9)
        chunk_pk = 46
        for i in range(0, len(pk), chunk_pk):
            cc.drawString(tx, tcy, pk[i:i + chunk_pk])
            tcy -= 5 * mm

        # View Key (если есть, для XMR)
        if vk:
            tcy -= 2 * mm
            cc.setFillColor(dim)
            cc.setFont("Helvetica-Bold", 9)
            cc.drawString(tx, tcy, "VIEW KEY")
            tcy -= 6 * mm
            cc.setFillColor(white)
            cc.setFont("Courier-Bold", 9)
            for i in range(0, len(vk), chunk_pk):
                cc.drawString(tx, tcy, vk[i:i + chunk_pk])
                tcy -= 5 * mm

        # Мнемоника (под QR)
        if mn:
            mn_y = qr_y - 4 * mm
            cc.setFillColor(dim)
            cc.setFont("Helvetica-Bold", 9)
            cc.drawString(margin + 8 * mm, mn_y, "MNEMONIC")
            mn_y -= 5 * mm
            cc.setFillColor(white)
            cc.setFont("Courier-Bold", 9)
            words = mn.split()
            line = ""
            for word in words:
                if len(line) + len(word) + 1 > 70:
                    cc.drawString(margin + 8 * mm, mn_y, line)
                    mn_y -= 5 * mm
                    line = word
                else:
                    line = f"{line} {word}".strip()
            if line:
                cc.drawString(margin + 8 * mm, mn_y, line)

        cc.showPage()

    cc.save()
