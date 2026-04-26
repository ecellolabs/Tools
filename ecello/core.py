import os

IS_COLAB = False
IS_MOUNTED = False
BASE_PATH = None

def init(project: str):
    """
    Initialize environment and set base project folder.
    
    Args:
        project (str): Folder name for this project
    """
    global IS_COLAB, BASE_PATH

    try:
        import google.colab
        IS_COLAB = True
        print("Notebook Tools Initialized! (Colab)")
    except ImportError:
        IS_COLAB = False
        print("Notebook Tools Initialized! (Local)")

    if IS_COLAB:
        BASE_PATH = os.path.join("/content/drive/MyDrive", project)
    else:
        BASE_PATH = os.path.join(".", project)

    # Ensure base folder exists
    os.makedirs(BASE_PATH, exist_ok=True)

    print(f"Project folder set to: {BASE_PATH}")


def disk(filename: str) -> str:
    """
    Returns full path inside the project folder.
    Mounts Google Drive if needed.
    """
    global IS_MOUNTED

    if BASE_PATH is None:
        raise RuntimeError("Call init(project=...) before using disk().")

    if IS_COLAB:
        from google.colab import drive

        if not IS_MOUNTED or not os.path.exists('/content/drive'):
            drive.mount('/content/drive')
            IS_MOUNTED = True

    path = os.path.join(BASE_PATH, filename)

    # Ensure subdirectories exist
    os.makedirs(os.path.dirname(path), exist_ok=True)

    return path