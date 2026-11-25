"""Small validation helpers shared by the services' request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import field_validator


def _reject_null(value: Any) -> Any:
    if value is None:
        raise ValueError("must not be null; leave the field out to keep its current value")
    return value


def forbid_null(*fields: str) -> Any:
    """For PATCH bodies: a field may be left out, but an explicit ``null`` is rejected with 422.

    Every field of a PATCH schema is optional (``None`` by default) so the client can send only what
    changes. Without this check, ``{"title": null}`` would pass validation and then fail in the
    database (a ``NOT NULL`` column), which gives a 500. Use it only for fields that can never be
    empty; fields where ``null`` has a meaning (such as "remove the manager") stay out of the list.

    Usage inside a model: ``_no_nulls = forbid_null("title", "category")``.
    """
    return field_validator(*fields)(_reject_null)
