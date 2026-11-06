import logging, os
from fastembed import TextEmbedding


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code")
CACHE_DIR = os.getenv("FASTEMBED_CACHE", "/ioc/cache/fastembed")

_model: TextEmbedding | None = None

log = logging.getLogger("embedder")


def _load(*, local_only: bool, lazy: bool = False) -> TextEmbedding:
    return TextEmbedding(
        model_name=EMBEDDING_MODEL,
        cache_dir=CACHE_DIR,
        local_files_only=local_only,
        lazy_load=lazy,
    )


def _is_cached() -> bool:
    try:
        _load(local_only=True, lazy=True)
    except ValueError:
        return False
    return True


def get_dimension() -> int:
	return TextEmbedding.get_embedding_size(EMBEDDING_MODEL)


def download() -> None:

    if _is_cached():
        log.info("%s already cached in %s", EMBEDDING_MODEL, CACHE_DIR)
        return

    _load(local_only=False, lazy=True)
    log.info("Downloaded %s", EMBEDDING_MODEL)


def model() -> TextEmbedding:
	global _model
	if _model is None:
		_model = _load(local_only=True)
	return _model


# Run in embed-model-init
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s"
    )
    download()