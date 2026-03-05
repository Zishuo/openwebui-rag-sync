import datetime

def log(tag, message):
    """Prints a formatted log message with timestamp, colorized aligned tag."""
    colors = {
        "CONFIG": "\033[94m",    # Blue
        "API": "\033[96m",       # Cyan
        "DISCOVERY": "\033[92m", # Green
        "VERSIONING": "\033[92m",# Green
        "UPLOAD": "\033[92m",    # Green
        "EXPORT": "\033[94m",    # Blue
        "CLEANUP": "\033[93m",   # Yellow
        "GIT": "\033[93m",       # Yellow
        "ERROR": "\033[91m",     # Red
        "FATAL": "\033[91m",     # Red
        "FINISH": "\033[92m"     # Green
    }
    reset = "\033[0m"
    color = colors.get(tag, "")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} {color}[{tag:<10}]{reset}: {message}")
