import os

IS_COLAB = False
BASE_PATH = None
BUCKET_NAME = None
STORAGE_CLIENT = None
BUCKET_REF = None


def init(project: str, bucket: str = None, credential_path: str = None):
    """
    Initialize environment, set base project folder, and optionally connect to a GCS bucket.
    """
    global IS_COLAB, BASE_PATH, BUCKET_NAME, STORAGE_CLIENT, BUCKET_REF

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

    if bucket:
        BUCKET_NAME = bucket
        if IS_COLAB:
            _ensure_gcs_authenticated()

        from google.cloud import storage
        if credential_path:
            STORAGE_CLIENT = storage.Client.from_service_account_json(credential_path)
        else:
            STORAGE_CLIENT = storage.Client()

        BUCKET_REF = STORAGE_CLIENT.bucket(BUCKET_NAME)
        print(f"Connected to GCS Bucket: {BUCKET_NAME}")


def _ensure_drive_mounted():
    """Mount Google Drive only if not already mounted."""
    from google.colab import drive

    # This is the correct check
    if not os.path.ismount('/content/drive'):
        drive.mount('/content/drive')


def _ensure_gcs_authenticated():
    """Perform user authentication inside Google Colab environment."""
    try:
        from google.colab import auth
        auth.authenticate_user()
        print("Successfully authenticated Google Account in Colab.")
    except Exception as e:
        print(f"Warning: Colab GCS authentication failed: {e}")


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


def gcs_upload(filename: str, gcs_filename: str = None) -> str:
    """
    Upload a local file inside the project directory to GCS.
    """
    if BUCKET_REF is None:
        raise RuntimeError("GCS storage is not initialized. Pass `bucket='...'` to init().")

    local_path = disk(filename)

    if gcs_filename is None:
        gcs_filename = filename

    # Standardize path separators for GCS
    gcs_filename = gcs_filename.replace("\\", "/")

    blob = BUCKET_REF.blob(gcs_filename)
    blob.upload_from_filename(local_path)

    gcs_uri = f"gs://{BUCKET_NAME}/{gcs_filename}"
    print(f"Uploaded: {local_path} -> {gcs_uri}")
    return gcs_uri


def gcs_download(gcs_filename: str, filename: str = None) -> str:
    """
    Download a file from GCS to the local project directory.
    """
    if BUCKET_REF is None:
        raise RuntimeError("GCS storage is not initialized. Pass `bucket='...'` to init().")

    if filename is None:
        filename = gcs_filename

    gcs_filename = gcs_filename.replace("\\", "/")
    local_path = disk(filename)

    blob = BUCKET_REF.blob(gcs_filename)
    if not blob.exists():
        raise FileNotFoundError(f"Blob gs://{BUCKET_NAME}/{gcs_filename} does not exist.")

    blob.download_to_filename(local_path)
    print(f"Downloaded: gs://{BUCKET_NAME}/{gcs_filename} -> {local_path}")
    return local_path


def gcs_list(prefix: str = None) -> list:
    """
    List blobs in the GCS bucket under the matching prefix.
    """
    if BUCKET_REF is None:
        raise RuntimeError("GCS storage is not initialized. Pass `bucket='...'` to init().")

    if prefix:
        prefix = prefix.replace("\\", "/")

    blobs = STORAGE_CLIENT.list_blobs(BUCKET_NAME, prefix=prefix)
    return [blob.name for blob in blobs]


def gcs_sync(direction: str = "both"):
    """
    Synchronize the local/Drive project folder with the GCS bucket.

    Directions:
      - "to_gcs": Upload newer/missing local files to GCS.
      - "from_gcs": Download newer/missing GCS files to local/Drive.
      - "both": Two-way synchronization (compare modification times, newer wins).
    """
    if BUCKET_REF is None:
        raise RuntimeError("GCS storage is not initialized. Pass `bucket='...'` to init().")

    if BASE_PATH is None:
        raise RuntimeError("Call init(project=...) before syncing.")

    if IS_COLAB:
        _ensure_drive_mounted()

    import datetime

    ignore_patterns = [
        ".ipynb_checkpoints",
        "__pycache__",
        ".git",
        ".DS_Store",
        "tmp",
    ]

    def should_ignore(path: str) -> bool:
        parts = path.replace("\\", "/").split("/")
        for pattern in ignore_patterns:
            if pattern in parts or any(pattern in part for part in parts):
                return True
        return False

    # 1. Gather all local files
    local_files = {}
    if os.path.exists(BASE_PATH):
        for root, dirs, files in os.walk(BASE_PATH):
            dirs[:] = [d for d in dirs if not should_ignore(d)]
            for file in files:
                full_path = os.path.join(root, file)
                if should_ignore(full_path):
                     continue
                rel_path = os.path.relpath(full_path, BASE_PATH)
                rel_path_gcs = rel_path.replace("\\", "/")
                local_files[rel_path_gcs] = {
                    "full_path": full_path,
                    "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(full_path), tz=datetime.timezone.utc)
                }

    # 2. Gather all GCS files
    gcs_files = {}
    blobs = STORAGE_CLIENT.list_blobs(BUCKET_NAME)
    for blob in blobs:
        if should_ignore(blob.name):
            continue
        gcs_files[blob.name] = {
            "blob": blob,
            "mtime": blob.updated
        }

    print(f"Sync starting (direction: {direction})...")
    print(f"Local files found: {len(local_files)}")
    print(f"GCS files found: {len(gcs_files)}")

    all_keys = set(local_files.keys()).union(gcs_files.keys())

    uploads = []
    downloads = []

    for rel_path in sorted(all_keys):
        in_local = rel_path in local_files
        in_gcs = rel_path in gcs_files

        if in_local and not in_gcs:
            if direction in ("to_gcs", "both"):
                uploads.append(rel_path)
        elif in_gcs and not in_local:
            if direction in ("from_gcs", "both"):
                downloads.append(rel_path)
        else:
            local_time = local_files[rel_path]["mtime"]
            gcs_time = gcs_files[rel_path]["mtime"]

            time_diff = (local_time - gcs_time).total_seconds()
            if time_diff > 2:
                if direction in ("to_gcs", "both"):
                    uploads.append(rel_path)
            elif time_diff < -2:
                if direction in ("from_gcs", "both"):
                    downloads.append(rel_path)

    # Perform the uploads
    for rel_path in uploads:
        print(f"Sync -> Uploading: {rel_path}")
        gcs_upload(rel_path, rel_path)

    # Perform the downloads
    for rel_path in downloads:
        print(f"Sync <- Downloading: {rel_path}")
        gcs_download(rel_path, rel_path)

    print("Synchronization complete!")