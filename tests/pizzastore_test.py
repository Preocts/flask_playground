from __future__ import annotations

from collections.abc import Generator
from sqlite3 import DatabaseError

import pytest

from flask_playground.pizzastore import Order
from flask_playground.pizzastore import PizzaStore


@pytest.fixture()
def store() -> Generator[PizzaStore, None, None]:
    yield PizzaStore(":memory:")


def test_connection_raises_when_not_connected(store: PizzaStore) -> None:
    with pytest.raises(DatabaseError):
        store.connection


def test_connect_opens_a_connection(store: PizzaStore) -> None:
    store.connect()

    assert store.connection


def test_disconnect_does_nothing_with_no_connection(store: PizzaStore) -> None:
    store.disconnect()

    assert True


def test_context_manager_opens_and_closes_connection(store: PizzaStore) -> None:
    with store:
        assert store.connection
    with pytest.raises(DatabaseError):
        store.connection


def test_context_manager_uses_existing_connection(
    store: PizzaStore,
) -> None:
    store.connect()
    expected_conn = store.connection

    with store:
        assert store.connection is expected_conn


def test_health_check_passes(store: PizzaStore) -> None:
    store.connect()
    store.health_check()

    assert True


def test_health_check_fails(store: PizzaStore) -> None:
    with pytest.raises(ValueError):
        store.health_check()


def test_save_single_order(store: PizzaStore) -> None:
    store.connect()
    conn = store.connection
    order = Order("mock", "mock", "mock", "mock", "mock", "mock", "mock")

    store.save_order(order)
    results = conn.execute("SELECT COUNT(*) FROM sales")

    assert results.fetchone() == (1,)


def test_save_multiple_orders(store: PizzaStore) -> None:
    store.connect()
    conn = store.connection
    orders = (
        Order(str(idx), "mock", "mock", "mock", "mock", "mock", "mock")
        for idx in range(10_000)
    )

    store.save_orders(orders)
    results = conn.execute("SELECT COUNT(*) FROM sales")

    assert results.fetchone() == (10_000,)
