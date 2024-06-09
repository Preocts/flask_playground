from __future__ import annotations

import csv
import dataclasses
from collections.abc import Iterable
from contextlib import closing
from sqlite3 import Connection
from sqlite3 import DatabaseError
from threading import Lock

_STORE_FILENAME = "pizza.sqlite3"


@dataclasses.dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    date: str
    time: str
    name: str
    size: str
    style: str
    price: str


class PizzaStore:
    """A datastore for pizza sales using an SQLite3 database."""

    def __init__(self, db_file: str = _STORE_FILENAME) -> None:
        """Initialize the datastore object."""
        self.db_file = db_file
        self._write_lock = Lock()
        self._connection: Connection | None = None

    @property
    def connection(self) -> Connection:
        if not self._connection:
            raise DatabaseError("No connection available, did you forget to connect?")
        return self._connection

    def connect(self) -> None:
        """
        Connect to the database, creates file if not exist.

        Raises:
            DatabaseError: When connection is already opened
        """
        if self._connection:
            raise DatabaseError("Connection is already opened.")

        self._connection = Connection(self.db_file)
        self._build_table()

    def disconnect(self) -> None:
        """Disconnects the databse."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> PizzaStore:
        try:
            self.connect()
        except DatabaseError:
            pass

        return self

    # TODO: What are the annotations expected here?
    def __exit__(self, type_, value, traceback) -> None:  # type: ignore
        self.disconnect()

    def health_check(self) -> None:
        """Run check. Raises ValueError on failure."""
        try:
            with closing(self.connection.cursor()) as cursor:
                cursor.execute("SELECT 1 FROM sales")

        except Exception as err:
            raise ValueError("Health check failed") from err

    def _build_table(self) -> None:
        """Build the table if needed."""
        sql = """\
            CREATE TABLE IF NOT EXISTS sales
            (
                order_id STRING,
                date STRING,
                time STRING,
                name STRING,
                size STRING,
                style STRING,
                price STRING
            )"""

        self.connection.execute(sql)
        self.connection.commit()

    def save_orders(self, orders: Iterable[Order]) -> None:
        """Save multiple orders to the table."""
        sql = """\
            INSERT INTO sales
            (
                order_id,
                date,
                time,
                name,
                size,
                style,
                price
            )
            VALUES
            (?,?,?,?,?,?,?);
        """
        values = (
            (o.order_id, o.date, o.time, o.name, o.size, o.style, o.price)
            for o in orders
        )
        with self._write_lock:
            with closing(self.connection.cursor()) as cursor:
                cursor.executemany(sql, values)

        self.connection.commit()

    def save_order(self, order: Order) -> None:
        """Save an order to the table."""
        self.save_orders((order,))


if __name__ == "__main__":
    import os

    print("This will purge the existing database and build a new one.")
    if input("Load pizza.csv into pizzastore? (y/N) ").upper() not in ("Y", "YES"):
        raise SystemExit(0)

    if os.path.exists(_STORE_FILENAME):
        os.remove(_STORE_FILENAME)

    store = PizzaStore()
    store.connect()

    with open("pizza.csv", "r") as csv_in:
        reader = csv.DictReader(csv_in)
        orders = (
            Order(
                order_id=r["id"],
                date=r["date"],
                time=r["time"],
                name=r["name"],
                size=r["size"],
                style=r["type"],
                price=r["price"],
            )
            for r in reader
        )
        store.save_orders(orders)
