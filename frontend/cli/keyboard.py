import sys
import select
import time

try:
    import tty
    import termios
    has_termios = True
except ImportError:
    has_termios = False
    tty = None
    termios = None

class KeyPressReader:
    """Reads a single keypress from standard input without blocking."""
    def __init__(self):
        self.fd = sys.stdin.fileno()
        if has_termios and termios is not None:
            try:
                self.old_settings = termios.tcgetattr(self.fd)
            except Exception:
                self.old_settings = None
        else:
            self.old_settings = None

    def set_raw(self):
        if has_termios and tty is not None:
            tty.setraw(self.fd)

    def restore_normal(self):
        if has_termios and termios is not None and self.old_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def __enter__(self):
        self.set_raw()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_normal()

    def get_key(self, timeout=0.1):
        if not has_termios or self.old_settings is None:
            if timeout is not None:
                time.sleep(timeout)
            else:
                time.sleep(0.1)
            return None
        
        try:
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                ch = sys.stdin.read(1)
                # Check for escape sequence
                if ch == '\x1b':
                    rlist2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if rlist2:
                        ch2 = sys.stdin.read(2)
                        return '\x1b' + ch2
                return ch
        except Exception:
            return None
        return None
