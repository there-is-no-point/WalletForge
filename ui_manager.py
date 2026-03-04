import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
import pyfiglet

# Инициализация консоли Rich
console = Console()

# --- 1. ЦВЕТОВАЯ ГАММА ---
COLOR_MAIN = "#00FF00"  # Зеленый (Успех/Основной)
COLOR_ACCENT = "#00FFFF"  # Голубой (Цифры/Акценты/Никнейм)
COLOR_WARNING = "#FFFF00"  # Желтый (Предупреждения)
COLOR_ERROR = "#FF0000"  # Красный (Ошибки)
COLOR_MUTED = "#808080"  # Серый (Инструкции)

# --- 2. НАСТРОЙКИ ПРИЛОЖЕНИЯ ---
APP_NAME = "WalletForge"
AUTHOR_NICK = "there-is-no-point"

# Описание без ссылок, только текст и цвет
APP_DESCRIPTION = (
    f"Secure Multi-Chain Wallet Generator by "
    f"[bold {COLOR_ACCENT}]{AUTHOR_NICK}[/bold {COLOR_ACCENT}]"
)

# --- 3. СТИЛЬ QUESTIONARY ---
custom_style = Style([
    ('qmark', f'fg:{COLOR_MAIN} bold'),
    ('question', 'bold'),
    ('answer', f'fg:{COLOR_ACCENT} bold'),
    ('pointer', f'fg:{COLOR_MAIN} bold'),
    ('highlighted', f'fg:black bg:{COLOR_MAIN} bold'),
    ('selected', f'fg:{COLOR_MAIN}'),
    ('separator', f'fg:{COLOR_MAIN}'),
    ('instruction', f'fg:{COLOR_MUTED} italic'),
    ('text', f'fg:{COLOR_MAIN}'),
    ('completion-menu', 'bg:#202020 fg:white'),
])


# --- 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def print_banner(extra_info=""):
    """
    Выводит ASCII заголовок и описание.
    """
    console.clear()

    # Генерируем ASCII баннер
    try:
        # Шрифт 'slant' - наклонный, 'rectangles' - строгий, 'standard' - классика
        ascii_art = pyfiglet.figlet_format(APP_NAME, font="slant")
    except:
        ascii_art = f"{APP_NAME}\n"

    # Выводим баннер (Зеленым)
    console.print(f"[bold {COLOR_MAIN}]{ascii_art}[/bold {COLOR_MAIN}]")

    # Выводим описание в рамке
    console.print(Panel.fit(
        f"[bold white]{APP_DESCRIPTION}[/bold white]",
        border_style=COLOR_MAIN,
        padding=(0, 2)
    ))


def print_success(text):
    console.print(f"[bold {COLOR_MAIN}]✅ {text}[/bold {COLOR_MAIN}]")


def print_error(text):
    console.print(f"[bold {COLOR_ERROR}]❌ {text}[/bold {COLOR_ERROR}]")


def print_info(text):
    console.print(f"[bold {COLOR_ACCENT}]ℹ️  {text}[/bold {COLOR_ACCENT}]")


def print_step(text):
    console.print(f"\n[{COLOR_WARNING}]➤ {text}[/{COLOR_WARNING}]")


def print_warning(text):
    console.print(f"[bold {COLOR_WARNING}]⚠️  {text}[/bold {COLOR_WARNING}]")