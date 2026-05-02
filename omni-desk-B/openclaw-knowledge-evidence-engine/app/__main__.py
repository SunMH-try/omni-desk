import sys
import io

# Windows PowerShell 默认 GBK，强制 UTF-8 避免 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.cli import cli

if __name__ == "__main__":
    cli()
