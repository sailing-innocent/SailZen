import sys


class Colors:
    """终端颜色"""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    END = "\033[0m"
    BOLD = "\033[1m"


def colorize(text: str, color: str) -> str:
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            return text
    return f"{color}{text}{Colors.ENDC}"


def print_separator(char: str = "─", width: int = 70):
    print(char * width)


def print_header(title: str, color: str = Colors.CYAN):
    print()
    print_separator("═")
    print(f"  {colorize(title, Colors.BOLD + color)}")
    print_separator("═")


def read_file(file_path: str) -> str:
    """读取文件并自动检测编码"""
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "gb2312", "utf-16", "big5"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"无法解析文件编码: {file_path}")


def format_number(n: int) -> str:
    """格式化数字，添加千位分隔符"""
    return f"{n:,}"
