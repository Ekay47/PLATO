from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    kind: str
    user_message: str
    detail: str


def classify_error(exc: Exception) -> ErrorInfo:
    detail = str(exc or "").strip() or exc.__class__.__name__
    low = detail.lower()

    if "config" in low or "setting" in low:
        return ErrorInfo(
            code="CONFIG_INVALID",
            kind="config",
            user_message="Configuration is invalid. Please check backend settings.",
            detail=detail,
        )

    if (
        "corenlp" in low
        or "coref" in low
        or "spacy" in low
        or "fastcoref" in low
        or "plantuml" in low
        or "dependency unavailable" in low
        or "httpx.readtimeout" in low
        or "httpstatuserror" in low
        or "connection" in low
        or "timeout" in low
        or "dependency parse request failed" in low
    ):
        return ErrorInfo(
            code="DEPENDENCY_UNAVAILABLE",
            kind="dependency",
            user_message="Required NLP dependency is unavailable or timed out.",
            detail=detail,
        )

    if "json" in low or "parse" in low or "format" in low:
        return ErrorInfo(
            code="OUTPUT_INVALID",
            kind="output",
            user_message="Model output format is invalid and cannot be parsed.",
            detail=detail,
        )

    return ErrorInfo(
        code="PIPELINE_FAILED",
        kind="pipeline",
        user_message="Pipeline execution failed due to an internal error.",
        detail=detail,
    )


def to_error_payload(exc: Exception) -> dict:
    info = classify_error(exc)
    return {
        "error": info.user_message,
        "error_code": info.code,
        "error_type": info.kind,
        "detail": info.detail,
    }
