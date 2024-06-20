from __future__ import annotations

import os
import threading
from collections.abc import Generator
from sqlite3 import DatabaseError

import pytest

from flask_playground.pizzastore import Order
from flask_playground.pizzastore import PizzaStore


@pytest.fixture()
def store(tmpdir) -> Generator[PizzaStore, None, None]:
    tempfile = tmpdir.join("test.db")
    store = PizzaStore(tempfile)
    store.connect()

    try:
        store._build_table()
        store.disconnect()
        yield store

    finally:
        os.remove(tempfile)


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
    order = Order("mock", "mock", "mock", "mock", "mock", "mock")

    store.save_order(order)

    assert store.get_sales_count() == 1


def test_save_multiple_orders(store: PizzaStore) -> None:
    store.connect()
    orders = (
        Order("mock", "mock", "mock", "mock", "mock", "mock") for idx in range(10_000)
    )

    store.save_orders(orders)

    assert store.get_sales_count() == 10_000


def test_flush_orders(store: PizzaStore) -> None:
    store.connect()
    order = Order("mock", "mock", "mock", "mock", "mock", "mock")
    store.save_order(order)
    prior_count = store.get_sales_count()

    store.flush_orders()

    assert prior_count == 1
    assert store.get_sales_count() == 0


def test_get_recent(store: PizzaStore) -> None:
    store.connect()
    orders = [
        Order("2024/01/01", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/02", "12:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/02", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/03", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/04", "00:00:00", "mock", "mock", "mock", "mock"),
    ]
    expected_order = [5, 4, 2, 3, 1]
    store.save_orders(orders)

    results = store.get_recent(row_count=0)
    order = [result.order_id for result in results]

    assert order == expected_order


def test_get_recent_limits(store: PizzaStore) -> None:
    store.connect()
    orders = [
        Order("2024/01/01", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/02", "12:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/02", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/03", "00:00:00", "mock", "mock", "mock", "mock"),
        Order("2024/01/04", "00:00:00", "mock", "mock", "mock", "mock"),
    ]
    store.save_orders(orders)

    results = store.get_recent(1)

    assert len(results) == 1


def _writer(
    thread: int,
    rows_to_write: int,
    flag: threading.Event,
    store_file: str,
) -> None:
    store = PizzaStore(store_file)
    store.connect()
    flag.wait()
    for _ in range(rows_to_write):
        order = Order("mock", "mock", "mock", "mock", "mock", "mock")
        store.save_order(order)
    store.disconnect()


def test_writing_lock_on_database(store: PizzaStore) -> None:
    number_of_threads = 50
    rows_to_write = 10
    store.connect()

    threads = []
    start_flag = threading.Event()

    for thread_number in range(number_of_threads):
        args = (thread_number, rows_to_write, start_flag, store.db_file)
        thread = threading.Thread(target=_writer, args=args)
        threads.append(thread)
        thread.start()

    start_flag.set()

    for thread in threads:
        thread.join()

    assert store.get_sales_count() == number_of_threads * rows_to_write

    store.disconnect()
