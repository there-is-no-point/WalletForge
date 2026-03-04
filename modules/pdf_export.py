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

    По 2 кошелька на страницу A4.
    """
    w, h = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    # Стили
    bg_color = HexColor("#1a1a2e")
    card_bg = HexColor("#16213e")
    accent = HexColor("#e94560")
    text_color = HexColor("#ffffff")
    dim_color = HexColor("#a0a0a0")

    qr_size = 28 * mm
    card_h = h / 2 - 20 * mm
    margin = 15 * mm

    for idx, wallet in enumerate(data):
        slot = idx % 2  # 0 = верхний, 1 = нижний
        if slot == 0:
            # Новая страница — фон
            c.setFillColor(bg_color)
            c.rect(0, 0, w, h, fill=1, stroke=0)

        # Позиция карточки
        card_y = h - margin - (slot + 1) * card_h - slot * 10 * mm

        # Фон карточки
        c.setFillColor(card_bg)
        c.roundRect(margin, card_y, w - 2 * margin, card_h, 8, fill=1, stroke=0)

        # Заголовок
        cy = card_y + card_h - 12 * mm
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 14)
        network = wallet.get("network", "???")
        c.drawString(margin + 8 * mm, cy, f"#{idx + 1}  {network}")

        # --- ADDRESS ---
        cy -= 8 * mm
        c.setFillColor(dim_color)
        c.setFont("Helvetica", 8)
        c.drawString(margin + 8 * mm, cy, "ADDRESS")

        addr = wallet.get("address", "")
        cy -= 5 * mm
        c.setFillColor(text_color)
        c.setFont("Courier", 7)
        # Если адрес длинный — разбиваем на 2 строки
        if len(addr) > 50:
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy + 4 * mm, addr[:50])
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy - 1 * mm, addr[50:])
        else:
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy + 2 * mm, addr)

        # QR адреса
        if addr:
            qr_img = _make_qr_image(addr)
            _draw_qr(c, qr_img, margin + 8 * mm, cy - 18 * mm, qr_size)

        # --- PRIVATE KEY ---
        cy -= 28 * mm
        c.setFillColor(dim_color)
        c.setFont("Helvetica", 8)
        c.drawString(margin + 8 * mm, cy, "PRIVATE KEY")

        pk = wallet.get("private_key", "")
        cy -= 5 * mm
        c.setFillColor(text_color)
        c.setFont("Courier", 6)
        if len(pk) > 60:
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy + 4 * mm, pk[:60])
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy - 1 * mm, pk[60:])
        else:
            c.drawString(margin + 8 * mm + qr_size + 4 * mm, cy + 2 * mm, pk)

        # QR ключа - для приватников префиксы обычно не нужны
        if pk:
            qr_img = _make_qr_image(pk)
            _draw_qr(c, qr_img, margin + 8 * mm, cy - 18 * mm, qr_size)

        # --- MNEMONIC ---
        cy -= 28 * mm
        mn = wallet.get("mnemonic", "")
        if mn:
            c.setFillColor(dim_color)
            c.setFont("Helvetica", 8)
            c.drawString(margin + 8 * mm, cy, "MNEMONIC")
            cy -= 5 * mm
            c.setFillColor(text_color)
            c.setFont("Courier", 6.5)
            
            # Текст мнемоники правее от QR кода
            words = mn.split()
            line = ""
            text_cy = cy + 4 * mm
            for word in words:
                if len(line) + len(word) + 1 > 55:
                    c.drawString(margin + 8 * mm + qr_size + 4 * mm, text_cy, line)
                    text_cy -= 4.5 * mm
                    line = word
                else:
                    line = f"{line} {word}".strip()
            if line:
                c.drawString(margin + 8 * mm + qr_size + 4 * mm, text_cy, line)
                
            # QR мнемоники
            qr_img = _make_qr_image(mn)
            _draw_qr(c, qr_img, margin + 8 * mm, cy - 18 * mm, qr_size)

        # Если нижний слот заполнен — переход на новую страницу
        if slot == 1:
            c.showPage()

    # Если последняя страница имеет только 1 кошелёк
    if len(data) % 2 == 1:
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
        cc.setFont("Courier", 8)
        # Разбиваем адрес на строки
        chunk = 52
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
        cc.setFont("Courier", 7)
        chunk_pk = 60
        for i in range(0, len(pk), chunk_pk):
            cc.drawString(tx, tcy, pk[i:i + chunk_pk])
            tcy -= 4.5 * mm

        # View Key (если есть, для XMR)
        if vk:
            tcy -= 2 * mm
            cc.setFillColor(dim)
            cc.setFont("Helvetica-Bold", 9)
            cc.drawString(tx, tcy, "VIEW KEY")
            tcy -= 6 * mm
            cc.setFillColor(white)
            cc.setFont("Courier", 7)
            for i in range(0, len(vk), chunk_pk):
                cc.drawString(tx, tcy, vk[i:i + chunk_pk])
                tcy -= 4.5 * mm

        # Мнемоника (под QR)
        if mn:
            mn_y = qr_y - 4 * mm
            cc.setFillColor(dim)
            cc.setFont("Helvetica-Bold", 9)
            cc.drawString(margin + 8 * mm, mn_y, "MNEMONIC")
            mn_y -= 5 * mm
            cc.setFillColor(white)
            cc.setFont("Courier", 7)
            words = mn.split()
            line = ""
            for word in words:
                if len(line) + len(word) + 1 > 90:
                    cc.drawString(margin + 8 * mm, mn_y, line)
                    mn_y -= 4 * mm
                    line = word
                else:
                    line = f"{line} {word}".strip()
            if line:
                cc.drawString(margin + 8 * mm, mn_y, line)

        cc.showPage()

    cc.save()
