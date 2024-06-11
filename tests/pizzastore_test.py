from __future__ import annotations

import os
import threading
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


def test_raise_when_connection_already_open(store: PizzaStore) -> None:
    store.connect()

    with pytest.raises(DatabaseError):
        store.connect()


def test_disconnect_does_nothing_with_no_connection(store: PizzaStore) -> None:
    store.disconnect()

    assert True


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


def _writer(
    thread: int,
    rows_to_write: int,
    flag: threading.Event,
    pizza_store: PizzaStore,
) -> None:
    flag.wait()
    for idx in range(rows_to_write):
        order_id = f"{idx}-{thread}-mock"
        order = Order(order_id, "mock", "mock", "mock", "mock", "mock", "mock")
        pizza_store.save_order(order)


def test_writing_lock_on_database(tmpdir) -> None:
    number_of_threads = 50
    rows_to_write = 10
    tempfile = tmpdir.join("test.db")
    store = PizzaStore(tempfile)
    store.connect()

    threads = []
    start_flag = threading.Event()

    try:
        for thread_number in range(number_of_threads):
            args = (thread_number, rows_to_write, start_flag, store)
            thread = threading.Thread(target=_writer, args=args)
            threads.append(thread)
            thread.start()

        start_flag.set()

        for thread in threads:
            thread.join()

        results = store.connection.execute("SELECT COUNT(*) FROM sales")
        count = results.fetchone()[0]

        assert count == number_of_threads * rows_to_write

    finally:
        os.remove(tempfile)
        store.disconnect()
