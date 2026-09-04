"""Explicit bar labeling; timestamp divisibility alone never identifies bar semantics."""
import numpy as np


def normalized_opens(raw_seconds, convention):
    stamps=np.asarray(raw_seconds)
    if not np.issubdtype(stamps.dtype,np.number) or not np.isfinite(stamps).all():
        raise ValueError('Timestamps must be finite numeric UTC seconds')
    if (stamps % 60 != 0).any():
        raise ValueError('Expected exact minute timestamps')
    if convention not in ['open','close']:
        raise ValueError('Explicit open/close timestamp convention required')
    return stamps.astype(np.int64) - (60 if convention=='close' else 0)


def available_at(raw_seconds, convention):
    return normalized_opens(raw_seconds,convention)+60
