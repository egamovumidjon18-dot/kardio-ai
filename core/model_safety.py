"""Validation at the model boundary; invalid output must never become low risk."""
import math
import json
import logging
from typing import Callable

import numpy as np

from core.evidence import Evidence, Provenance, Source

log = logging.getLogger("cardiopath.inference")


def age_error(age, minimum: float, maximum: float, unit: str) -> str | None:
    if age is None:
        return f"yosh ({unit}) kiritilmagan — model uchun yoshni aniqlash kerak"
    if not math.isfinite(age) or age < 0 or age > maximum:
        return f"yosh ({unit}) noto'g'ri — model xulosa bermadi"
    if age < minimum:
        return f"yosh {age:g} {unit}: model bu yoshda validatsiya qilinmagan (kattalar/yosh chegarasi: {minimum:g})"
    return None


def valid_probabilities(values, shape: tuple[int, ...]) -> bool:
    p = np.asarray(values)
    return p.shape == shape and bool(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all())


def guarded_inference(model, kind: str, predict: Callable[[], Evidence],
                      input_errors: tuple[type[Exception], ...] = ()) -> Evidence:
    """Contain a model failure, never persistence errors or input parser errors.

    An explicit abstention replaces a failed model's old result in the current
    assessment. Other models can still finish. Do not log input or exception
    text: backend exceptions can contain patient data or local file paths.
    """
    try:
        result = predict()
        if not isinstance(result, Evidence) or result.kind != kind or result.source != Source.MODEL:
            raise ValueError("invalid model evidence")
        json.dumps(result.to_dict(), allow_nan=False)
        return result
    except Exception as exc:
        if isinstance(exc, input_errors):
            raise
        log.error("inference failed: kind=%s error=%s", kind, type(exc).__name__)
        card = model.card
        return Evidence.abstain(kind, Source.MODEL,
                                Provenance(name=card.name, version=card.version, reference=card.task,
                                           dataset_license=card.dataset_license),
                                "AI hisoblashda texnik xato — natija olinmadi; shifokor tekshiruvi kerak")
