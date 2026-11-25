"""Key-value port for the analytics single table (DynamoDB in AWS).

The streak processor (Lambda) is the only writer; the Insight Service is the only reader. Adapters:

* ``DynamoDBAnalyticsStore`` — AWS (or DynamoDB Local in Docker Compose)
* ``SqlAnalyticsStore``      — zero-infrastructure local mode (SQLite file emulating the table)
* ``MemoryAnalyticsStore``   — unit tests

Items are dicts of attributes keyed by (``pk``, ``sk``). Counters are numbers, ``*_users`` style
attributes are string sets (DynamoDB ``SS``) so distinct counting is idempotent.

``transact()`` applies several writes all-or-nothing (DynamoDB ``TransactWriteItems``): if any
condition fails, or the store fails half-way, none of the writes is applied.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import JSON, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from teampulse_common.db import Database, new_metadata


@dataclass(frozen=True)
class Put:
    """Write a whole item inside ``transact()``.

    ``if_absent``: only if the item does not exist yet. ``if_version``: only if the item's ``version``
    attribute equals this number; ``0`` means "no version yet", which also covers a missing item.
    """

    pk: str
    sk: str
    attrs: dict[str, Any]
    if_absent: bool = False
    if_version: int | None = None

    def __post_init__(self) -> None:  # one condition per write, so every adapter checks the same thing
        if self.if_absent and self.if_version is not None:
            raise ValueError("use either if_absent or if_version, not both")


@dataclass(frozen=True)
class Increment:
    """Add to number attributes and add members to string sets inside ``transact()``."""

    pk: str
    sk: str
    counters: dict[str, float]
    add_to_sets: dict[str, set[str]] | None = None


Write = Put | Increment


class TransactionConflictError(Exception):
    """A condition in ``transact()`` failed, so nothing was written.

    ``keys`` holds the ``(pk, sk)`` of each write whose condition failed. It is empty when the store
    cannot say which one (DynamoDB reports a clash with another transaction that way).
    """

    def __init__(self, keys: Iterable[tuple[str, str]] = ()) -> None:
        self.keys = frozenset(keys)
        super().__init__(f"transaction condition failed for {sorted(self.keys) or 'a concurrent write'}")


def _check_unique_keys(writes: Sequence[Write]) -> None:
    keys = [(w.pk, w.sk) for w in writes]
    if len(keys) != len(set(keys)):
        raise ValueError("a transaction may touch each item only once")  # DynamoDB rule too


def _condition_ok(write: Write, item: dict[str, Any] | None) -> bool:
    if not isinstance(write, Put):
        return True
    if write.if_absent and item is not None:
        return False
    if write.if_version is not None:
        current = (item or {}).get("version")
        return current is None if write.if_version == 0 else current == write.if_version
    return True


class AnalyticsStore(Protocol):
    async def get(self, pk: str, sk: str) -> dict[str, Any] | None: ...
    async def put(self, pk: str, sk: str, attrs: dict[str, Any]) -> None: ...
    async def put_if_absent(self, pk: str, sk: str, attrs: dict[str, Any]) -> bool: ...
    async def delete(self, pk: str, sk: str) -> None: ...
    async def query(
        self, pk: str, *, sk_prefix: str | None = None, sk_between: tuple[str, str] | None = None
    ) -> list[dict[str, Any]]: ...
    async def increment(
        self,
        pk: str,
        sk: str,
        counters: dict[str, float],
        *,
        add_to_sets: dict[str, set[str]] | None = None,
        set_attrs: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    async def transact(self, writes: Sequence[Write]) -> None: ...
    async def close(self) -> None: ...


def _in_range(sk: str, sk_prefix: str | None, sk_between: tuple[str, str] | None) -> bool:
    if sk_prefix is not None and not sk.startswith(sk_prefix):
        return False
    return not (sk_between is not None and not (sk_between[0] <= sk <= sk_between[1]))


def _apply_increment(
    item: dict[str, Any],
    counters: dict[str, float],
    add_to_sets: dict[str, set[str]] | None,
    set_attrs: dict[str, Any] | None,
) -> dict[str, Any]:
    for key, delta in counters.items():
        item[key] = item.get(key, 0) + delta
    for key, values in (add_to_sets or {}).items():
        item[key] = set(item.get(key, set())) | set(values)
    item.update(set_attrs or {})
    return item


# ----------------------------------------------------------------------------------------- memory
class MemoryAnalyticsStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, pk: str, sk: str) -> dict[str, Any] | None:
        item = self._items.get((pk, sk))
        return copy.deepcopy(item) if item is not None else None

    async def put(self, pk: str, sk: str, attrs: dict[str, Any]) -> None:
        self._items[(pk, sk)] = {**copy.deepcopy(attrs), "pk": pk, "sk": sk}

    async def put_if_absent(self, pk: str, sk: str, attrs: dict[str, Any]) -> bool:
        async with self._lock:
            if (pk, sk) in self._items:
                return False
            await self.put(pk, sk, attrs)
            return True

    async def delete(self, pk: str, sk: str) -> None:
        self._items.pop((pk, sk), None)

    async def query(
        self, pk: str, *, sk_prefix: str | None = None, sk_between: tuple[str, str] | None = None
    ) -> list[dict[str, Any]]:
        rows = [
            copy.deepcopy(v)
            for (p, s), v in self._items.items()
            if p == pk and _in_range(s, sk_prefix, sk_between)
        ]
        return sorted(rows, key=lambda r: r["sk"])

    async def increment(self, pk, sk, counters, *, add_to_sets=None, set_attrs=None):  # type: ignore[no-untyped-def]
        async with self._lock:
            item = self._items.setdefault((pk, sk), {"pk": pk, "sk": sk})
            _apply_increment(item, counters, add_to_sets, set_attrs)
            return copy.deepcopy(item)

    async def transact(self, writes: Sequence[Write]) -> None:
        _check_unique_keys(writes)
        async with self._lock:
            failed = [(w.pk, w.sk) for w in writes if not _condition_ok(w, self._items.get((w.pk, w.sk)))]
            if failed:
                raise TransactionConflictError(failed)
            for w in writes:
                if isinstance(w, Put):
                    self._items[(w.pk, w.sk)] = {**copy.deepcopy(w.attrs), "pk": w.pk, "sk": w.sk}
                else:
                    item = self._items.setdefault((w.pk, w.sk), {"pk": w.pk, "sk": w.sk})
                    _apply_increment(item, w.counters, w.add_to_sets, None)

    async def close(self) -> None:
        return None


# ----------------------------------------------------------------------------------------- SQL
class _AnalyticsBase(DeclarativeBase):
    metadata = new_metadata()


class AnalyticsItem(_AnalyticsBase):
    __tablename__ = "analytics_items"

    pk: Mapped[str] = mapped_column(String(200), primary_key=True)
    sk: Mapped[str] = mapped_column(String(200), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


def _encode(attrs: dict[str, Any]) -> dict[str, Any]:
    return {k: {"__set__": sorted(v)} if isinstance(v, set) else v for k, v in attrs.items()}


def _decode(row: AnalyticsItem) -> dict[str, Any]:
    out = {k: set(v["__set__"]) if isinstance(v, dict) and "__set__" in v else v for k, v in row.data.items()}
    return {**out, "pk": row.pk, "sk": row.sk}


class SqlAnalyticsStore:
    def __init__(self, url: str) -> None:
        self._db = Database(url)
        self._ready = False
        self._lock = asyncio.Lock()

    async def _ensure(self) -> None:
        if not self._ready:
            async with self._db.engine.begin() as conn:
                await conn.run_sync(_AnalyticsBase.metadata.create_all)
            self._ready = True

    async def get(self, pk: str, sk: str) -> dict[str, Any] | None:
        await self._ensure()
        async with self._db.session_factory() as s:
            row = await s.get(AnalyticsItem, (pk, sk))
            return _decode(row) if row else None

    async def put(self, pk: str, sk: str, attrs: dict[str, Any]) -> None:
        await self._ensure()
        async with self._db.session_factory() as s, s.begin():
            await s.merge(
                AnalyticsItem(
                    pk=pk, sk=sk, data=_encode({k: v for k, v in attrs.items() if k not in ("pk", "sk")})
                )
            )

    async def put_if_absent(self, pk: str, sk: str, attrs: dict[str, Any]) -> bool:
        await self._ensure()
        try:
            async with self._db.session_factory() as s, s.begin():
                s.add(AnalyticsItem(pk=pk, sk=sk, data=_encode(attrs)))
            return True
        except IntegrityError:
            return False

    async def delete(self, pk: str, sk: str) -> None:
        await self._ensure()
        async with self._db.session_factory() as s, s.begin():
            row = await s.get(AnalyticsItem, (pk, sk))
            if row:
                await s.delete(row)

    async def query(
        self, pk: str, *, sk_prefix: str | None = None, sk_between: tuple[str, str] | None = None
    ) -> list[dict[str, Any]]:
        await self._ensure()
        stmt = select(AnalyticsItem).where(AnalyticsItem.pk == pk)
        if sk_prefix is not None:
            stmt = stmt.where(AnalyticsItem.sk.startswith(sk_prefix, autoescape=True))
        if sk_between is not None:
            stmt = stmt.where(AnalyticsItem.sk.between(*sk_between))
        async with self._db.session_factory() as s:
            rows = (await s.scalars(stmt.order_by(AnalyticsItem.sk))).all()
            return [_decode(r) for r in rows]

    async def increment(self, pk, sk, counters, *, add_to_sets=None, set_attrs=None):  # type: ignore[no-untyped-def]
        await self._ensure()
        async with self._lock, self._db.session_factory() as s, s.begin():
            row = await s.get(AnalyticsItem, (pk, sk))
            current = {k: v for k, v in _decode(row).items() if k not in ("pk", "sk")} if row else {}
            updated = _apply_increment(current, counters, add_to_sets, set_attrs)
            if row:
                row.data = _encode(updated)
            else:
                s.add(AnalyticsItem(pk=pk, sk=sk, data=_encode(updated)))
            return {**updated, "pk": pk, "sk": sk}

    async def transact(self, writes: Sequence[Write]) -> None:
        _check_unique_keys(writes)
        await self._ensure()
        try:
            # One database transaction: an error anywhere (including a failed condition) rolls back all.
            async with self._lock, self._db.session_factory() as s, s.begin():
                rows = {(w.pk, w.sk): await s.get(AnalyticsItem, (w.pk, w.sk)) for w in writes}
                current = {key: (_decode(row) if row else None) for key, row in rows.items()}
                failed = [(w.pk, w.sk) for w in writes if not _condition_ok(w, current[(w.pk, w.sk)])]
                if failed:
                    raise TransactionConflictError(failed)
                for w in writes:
                    row = rows[(w.pk, w.sk)]
                    if isinstance(w, Put):
                        data = _encode({k: v for k, v in w.attrs.items() if k not in ("pk", "sk")})
                    else:
                        before = {
                            k: v for k, v in (current[(w.pk, w.sk)] or {}).items() if k not in ("pk", "sk")
                        }
                        data = _encode(_apply_increment(before, w.counters, w.add_to_sets, None))
                    if row:
                        row.data = data
                    else:
                        s.add(AnalyticsItem(pk=w.pk, sk=w.sk, data=data))
        except IntegrityError as exc:  # another process created one of the items first
            raise TransactionConflictError() from exc

    async def close(self) -> None:
        await self._db.dispose()


# ----------------------------------------------------------------------------------------- DynamoDB
def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    if isinstance(value, set):
        return {_from_dynamo(v) for v in value}
    return value


class DynamoDBAnalyticsStore:
    def __init__(self, table_name: str, region: str, endpoint_url: str | None = None) -> None:
        import boto3

        self._table = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url).Table(
            table_name
        )
        # A plain client for transactions. (``self._table.meta.client`` converts Python values to
        # DynamoDB's format by itself, so values serialized by ``transact`` would be converted twice.)
        self._client = boto3.client("dynamodb", region_name=region, endpoint_url=endpoint_url)

    async def get(self, pk: str, sk: str) -> dict[str, Any] | None:
        resp = await asyncio.to_thread(self._table.get_item, Key={"pk": pk, "sk": sk})
        item = resp.get("Item")
        return _from_dynamo(item) if item else None

    async def put(self, pk: str, sk: str, attrs: dict[str, Any]) -> None:
        await asyncio.to_thread(self._table.put_item, Item=_to_dynamo({**attrs, "pk": pk, "sk": sk}))

    async def put_if_absent(self, pk: str, sk: str, attrs: dict[str, Any]) -> bool:
        from botocore.exceptions import ClientError

        try:
            await asyncio.to_thread(
                self._table.put_item,
                Item=_to_dynamo({**attrs, "pk": pk, "sk": sk}),
                ConditionExpression="attribute_not_exists(pk)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    async def delete(self, pk: str, sk: str) -> None:
        await asyncio.to_thread(self._table.delete_item, Key={"pk": pk, "sk": sk})

    async def query(
        self, pk: str, *, sk_prefix: str | None = None, sk_between: tuple[str, str] | None = None
    ) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        cond = Key("pk").eq(pk)
        if sk_prefix is not None:
            cond = cond & Key("sk").begins_with(sk_prefix)
        elif sk_between is not None:
            cond = cond & Key("sk").between(*sk_between)
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": cond}
        while True:
            resp = await asyncio.to_thread(self._table.query, **kwargs)
            items.extend(_from_dynamo(i) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        if sk_prefix is not None and sk_between is not None:
            items = [i for i in items if _in_range(i["sk"], None, sk_between)]
        return items

    async def increment(self, pk, sk, counters, *, add_to_sets=None, set_attrs=None):  # type: ignore[no-untyped-def]
        names: dict[str, str] = {}
        values: dict[str, Any] = {}
        adds, sets = [], []
        for i, (key, delta) in enumerate(counters.items()):
            names[f"#c{i}"], values[f":c{i}"] = key, _to_dynamo(float(delta))
            adds.append(f"#c{i} :c{i}")
        for i, (key, members) in enumerate((add_to_sets or {}).items()):
            if members:
                names[f"#s{i}"], values[f":s{i}"] = key, set(members)
                adds.append(f"#s{i} :s{i}")
        for i, (key, value) in enumerate((set_attrs or {}).items()):
            names[f"#a{i}"], values[f":a{i}"] = key, _to_dynamo(value)
            sets.append(f"#a{i} = :a{i}")
        expr = " ".join(
            p
            for p in (("ADD " + ", ".join(adds)) if adds else "", ("SET " + ", ".join(sets)) if sets else "")
            if p
        )
        resp = await asyncio.to_thread(
            self._table.update_item,
            Key={"pk": pk, "sk": sk},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return _from_dynamo(resp.get("Attributes", {}))

    async def transact(self, writes: Sequence[Write]) -> None:
        """One ``TransactWriteItems`` call (at most 100 writes, all applied or none)."""
        from boto3.dynamodb.types import TypeSerializer
        from botocore.exceptions import ClientError

        _check_unique_keys(writes)
        serializer = TypeSerializer()

        def av(value: Any) -> Any:  # Python value → DynamoDB attribute value ({"S": ...}, {"N": ...})
            return serializer.serialize(_to_dynamo(value))

        table = self._table.name
        items: list[dict[str, Any]] = []
        sent: list[Write] = []  # the writes behind ``items``, in the same order
        for w in writes:
            if isinstance(w, Put):
                op: dict[str, Any] = {
                    "TableName": table,
                    "Item": {k: av(v) for k, v in {**w.attrs, "pk": w.pk, "sk": w.sk}.items()},
                }
                if w.if_absent:
                    op["ConditionExpression"] = "attribute_not_exists(pk)"
                elif w.if_version == 0:
                    op["ConditionExpression"] = "attribute_not_exists(#ver)"
                    op["ExpressionAttributeNames"] = {"#ver": "version"}
                elif w.if_version is not None:
                    op["ConditionExpression"] = "#ver = :ver"
                    op["ExpressionAttributeNames"] = {"#ver": "version"}
                    op["ExpressionAttributeValues"] = {":ver": av(w.if_version)}
                items.append({"Put": op})
            else:
                names: dict[str, str] = {}
                values: dict[str, Any] = {}
                adds: list[str] = []
                for i, (key, delta) in enumerate(w.counters.items()):
                    names[f"#c{i}"], values[f":c{i}"] = key, av(float(delta))
                    adds.append(f"#c{i} :c{i}")
                for i, (key, members) in enumerate((w.add_to_sets or {}).items()):
                    if members:  # DynamoDB has no empty sets
                        names[f"#s{i}"], values[f":s{i}"] = key, av(set(members))
                        adds.append(f"#s{i} :s{i}")
                if not adds:
                    continue
                items.append(
                    {
                        "Update": {
                            "TableName": table,
                            "Key": {"pk": av(w.pk), "sk": av(w.sk)},
                            "UpdateExpression": "ADD " + ", ".join(adds),
                            "ExpressionAttributeNames": names,
                            "ExpressionAttributeValues": values,
                        }
                    }
                )
            sent.append(w)
        if not items:
            return
        try:
            await asyncio.to_thread(self._client.transact_write_items, TransactItems=items)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = [r.get("Code") for r in exc.response.get("CancellationReasons", [])]
            failed = [
                (w.pk, w.sk)
                for w, code in zip(sent, reasons, strict=False)
                if code == "ConditionalCheckFailed"
            ]
            if failed or "TransactionConflict" in reasons:
                raise TransactionConflictError(failed) from exc
            raise

    async def close(self) -> None:
        return None


def build_analytics_store(
    driver: str, *, table_name: str, region: str, endpoint_url: str | None, sql_url: str
) -> AnalyticsStore:
    if driver == "dynamodb":
        return DynamoDBAnalyticsStore(table_name, region, endpoint_url)
    if driver == "sql":
        return SqlAnalyticsStore(sql_url)
    return MemoryAnalyticsStore()
