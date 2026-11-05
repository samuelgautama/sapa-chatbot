"""
check_index_fresh.py
--------------------
Monitor apakah vector store sudah stale (dokumen source sudah berubah).
Integrasikan ke app startup dan jalankan sebelum evaluate.py.

Deteksi stale index dengan:
1. Compare mtime file dokumen vs timestamp index
2. Compare file hash (optional: cek isi dokumen berubah)
3. Warn kalau source lebih baru dari index
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_PATH = Path("data")
VECTOR_STORE_PATH = Path("vector_store")
INDEX_MANIFEST = VECTOR_STORE_PATH / "index_manifest.json"


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash dari file untuk detect content change."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def record_index_metadata():
    """Catat metadata index (file mtime, hash, timestamp) ke index_manifest.json."""
    if not DATA_PATH.exists():
        logger.warning(f"[check_index] Data path tidak ada: {DATA_PATH}")
        return

    VECTOR_STORE_PATH.mkdir(exist_ok=True)

    docs = {}
    for txt_file in DATA_PATH.glob("**/*.txt"):
        rel_path = str(txt_file.relative_to(DATA_PATH))
        docs[rel_path] = {
            "mtime": txt_file.stat().st_mtime,
            "size": txt_file.stat().st_size,
            "hash": compute_file_hash(txt_file),
        }

    manifest = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "docs": docs,
    }

    with INDEX_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"[check_index] Index manifest recorded: {len(docs)} dokumen")


def check_index_fresh(warn_only: bool = True) -> bool:
    """
    Cek apakah vector store masih fresh.
    
    Indikator utama adalah konten file (hash SHA256). Perubahan mtime tanpa perubahan
    hash isi file TIDAK dianggap stale (mencegah false positive karena touch/copy file).
    
    Returns:
        True jika fresh (atau no manifest), False jika stale.
    
    Args:
        warn_only: Jika True, hanya log warning; jika False, raise exception jika stale.
    """
    if not INDEX_MANIFEST.exists():
        logger.info("[check_index] Index manifest tidak ada (index baru atau belum di-record)")
        return True

    if not (VECTOR_STORE_PATH / "index.faiss").exists():
        logger.warning("[check_index] Vector store file tidak ditemukan")
        return False

    try:
        with INDEX_MANIFEST.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logger.warning(f"[check_index] Error membaca manifest: {e}")
        return True

    recorded_docs = manifest.get("docs", {})
    current_txt_files = set(str(p.relative_to(DATA_PATH)) for p in DATA_PATH.glob("**/*.txt"))
    recorded_paths = set(recorded_docs.keys())

    # Check 1: Dokumen yang tercatat sudah dihapus?
    missing = recorded_paths - current_txt_files
    if missing:
        msg = f"[check_index] Dokumen tercatat sudah dihapus: {missing}"
        if warn_only:
            logger.warning(msg)
        else:
            raise RuntimeError(msg)
        return False

    # Check 2: Dokumen baru ditambah?
    added = current_txt_files - recorded_paths
    if added:
        msg = f"[check_index] Dokumen baru ditemukan (index stale): {added}"
        if warn_only:
            logger.warning(msg)
        else:
            raise RuntimeError(msg)
        return False

    # Check 3: Dokumen existing berubah kontennya (hash mismatch)?
    # mtime saja tidak dijadikan penyebab error bila hash sama (mencegah false positive).
    for rel_path in current_txt_files:
        current_file = DATA_PATH / rel_path
        recorded_meta = recorded_docs.get(rel_path, {})

        if "hash" in recorded_meta:
            current_hash = compute_file_hash(current_file)
            if current_hash != recorded_meta["hash"]:
                msg = f"[check_index] Dokumen '{rel_path}' isi berubah (hash mismatch)"
                if warn_only:
                    logger.warning(msg)
                else:
                    raise RuntimeError(msg)
                return False
        else:
            # Fallback ke mtime jika manifest lama tidak punya hash
            current_mtime = current_file.stat().st_mtime
            recorded_mtime = recorded_meta.get("mtime", 0)
            if current_mtime > recorded_mtime:
                msg = f"[check_index] Dokumen '{rel_path}' lebih baru dari index (mtime)"
                if warn_only:
                    logger.warning(msg)
                else:
                    raise RuntimeError(msg)
                return False

    logger.info("[check_index] Vector store fresh ✅")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        record_index_metadata()
    else:
        fresh = check_index_fresh(warn_only=True)
        sys.exit(0 if fresh else 1)
