import os

IS_COLAB = False
BASE_PATH = None

def init(project: str):
    """
    Initialize environment and set base project folder.
    """
    global IS_COLAB, BASE_PATH

    try:
        import google.colab  # noqa
        IS_COLAB = True
        print("Notebook Tools Initialized! (Colab)")
    except ImportError:
        IS_COLAB = False
        print("Notebook Tools Initialized! (Local)")

    if IS_COLAB:
        BASE_PATH = os.path.join("/content/drive/MyDrive", project)
    else:
        BASE_PATH = os.path.join(".", project)

    print(f"Project folder set to: {BASE_PATH}")


def _ensure_drive_mounted():
    """Mount Google Drive only if not already mounted."""
    from google.colab import drive

    # This is the correct check
    if not os.path.ismount('/content/drive'):
        drive.mount('/content/drive')


def disk(filename: str) -> str:
    """
    Returns full path inside the project folder.
    Mounts Google Drive if needed.
    """
    if BASE_PATH is None:
        raise RuntimeError("Call init(project=...) before using disk().")

    if IS_COLAB:
        _ensure_drive_mounted()

    path = os.path.join(BASE_PATH, filename)

    # Ensure directory exists AFTER mount
    os.makedirs(os.path.dirname(path), exist_ok=True)

    return path