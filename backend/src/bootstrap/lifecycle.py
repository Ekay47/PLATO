import os
from contextlib import asynccontextmanager

from src.core.nlp_optional import validate_nlp_runtime


def build_lifespan(*, settings, corenlp):
    @asynccontextmanager
    async def lifespan(_app):
        if settings.get_bool("huggingface.hub_offline", True):
            os.environ["HF_HUB_OFFLINE"] = "1"
        if settings.get_bool("huggingface.transformers_offline", True):
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        await corenlp.ensure_started()
        await validate_nlp_runtime()
        try:
            yield
        finally:
            await corenlp.shutdown()

    return lifespan
