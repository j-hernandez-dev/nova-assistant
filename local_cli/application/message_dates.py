"""Optional owner-facing dates in saved copies; never inference or execution authority."""
from copy import deepcopy
from datetime import datetime

_FIELD = '_nova_display'


def display_dates(value):
    result = {}
    if not isinstance(value, dict):
        return result
    for key in ('createdAt', 'completedAt', 'savedAt'):
        text = value.get(key)
        if not isinstance(text, str) or len(text) > 64:
            continue
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is not None:
                result[key] = text
        except ValueError:
            pass
    return result


def saved_with_dates(messages, metadata):
    rows = deepcopy(messages)
    for index, row in enumerate(rows):
        row.pop(_FIELD, None)
        dates = display_dates(metadata.get(index))
        if dates and row.get('role') in ('user', 'assistant'):
            row[_FIELD] = dates
    return rows


def restored_with_dates(messages):
    rows = deepcopy(messages)
    metadata = {}
    for index, row in enumerate(rows):
        dates = display_dates(row.pop(_FIELD, None))
        if dates and row.get('role') in ('user', 'assistant'):
            metadata[index] = dates
    return rows, metadata
