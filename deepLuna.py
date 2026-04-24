#!/usr/bin/env python3
"""deepLuna — Main entry point (Modern GUI)"""
import sys
import tkinter as tk
from luna.ui.modern_window import ModernWindow


def main():
    root = tk.Tk()
    app = ModernWindow(root)

    # If a DB path was passed as argument, auto-load it
    if len(sys.argv) > 1:
        import os
        arg = sys.argv[1]
        if os.path.exists(arg) and arg.endswith(".json"):
            root.after(150, lambda: app._open_db_path(arg))

    root.mainloop()


if __name__ == "__main__":
    main()
