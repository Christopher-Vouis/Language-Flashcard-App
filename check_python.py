"""Exit 0 if this Python can run faster-whisper (64-bit x86, 3.9-3.14)."""
import platform
import struct
import sys

ok = (
    (3, 9) <= sys.version_info[:2] <= (3, 14)
    and struct.calcsize("P") == 8
    and platform.machine().upper() in ("AMD64", "X86_64")
)
print(f"  Python {platform.python_version()} {struct.calcsize('P') * 8}-bit "
      f"{platform.machine()} -> {'OK' if ok else 'not compatible'}")
sys.exit(0 if ok else 1)
