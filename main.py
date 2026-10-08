"""Entry point:  python main.py"""

import sys


def main():
    try:
        import config
        from gui import AttendanceApp
    except ImportError as error:
        print(f"A required package is missing: {error}\n"
              "Install the requirements with:  pip install -r requirements.txt\n"
              "(Tkinter ships with Python; on Linux install it with: sudo apt install python3-tk)")
        sys.exit(1)

    config.ensure_directories()
    try:
        app = AttendanceApp()
    except Exception as error:                   # e.g. corrupted CSV file
        print(f"The application could not start: {error}")
        sys.exit(1)
    app.mainloop()


if __name__ == "__main__":
    main()
