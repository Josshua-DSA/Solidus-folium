import sys
import select
from typing import Optional

try:
    import termios
    import tty
    has_termios = True
except ImportError:
    has_termios = False
    termios = None
    tty = None


class KeyPressReader:
    """Reads a single keypress from standard input without blocking."""
    def __init__(self):
        try:
            self.fd = sys.stdin.fileno()
            self.is_tty = sys.stdin.isatty() if self.fd is not None else False
        except Exception:
            self.fd = None
            self.is_tty = False

        self.old_settings = None
        if has_termios and termios is not None and self.fd is not None and self.is_tty:
            try:
                self.old_settings = termios.tcgetattr(self.fd)
            except Exception:
                self.old_settings = None

    def set_raw(self):
        """Sets terminal to raw mode to capture non-buffered keypresses."""
        if has_termios and tty is not None and self.fd is not None and self.is_tty:
            try:
                tty.setraw(self.fd)
            except Exception:
                pass

    def restore_normal(self):
        """Restores original terminal settings."""
        if has_termios and termios is not None and self.fd is not None and self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def get_key(self, timeout: Optional[float] = 0.05) -> Optional[str]:
        """Gets a single keypress if available within timeout window."""
        if not self.is_tty or self.fd is None:
            return None

        try:
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                key = sys.stdin.read(1)
                if key == '\x1b':
                    rlist_esc, _, _ = select.select([sys.stdin], [], [], 0.01)
                    if rlist_esc:
                        key += sys.stdin.read(2)
                return key
        except Exception:
            return None
        return None
