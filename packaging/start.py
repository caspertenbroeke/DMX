"""Startpunt voor de ingepakte app (PyInstaller)."""
import multiprocessing

from dmxdesk.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
