from __future__ import annotations

import csv
import dataclasses
from collections.abc import Iterable
from contextlib import closing
from sqlite3 import Connection
from sqlite3 import DatabaseError
from threading import Lock

_STORE_FILENAME = "pizza.sqlite3"
_SALES_CSV = "pizza.csv"


@dataclasses.dataclass(frozen=True, slots=True)
class Order:
    date: str
    time: str
    name: str
    size: str
    style: str
    price: str
    order_id: int | None = None


class PizzaStore:
    """A datastore for pizza sales using an SQLite3 database."""

    _write_lock = Lock()

    def __init__(self, db_file: str = _STORE_FILENAME) -> None:
        """Initialize the datastore object."""
        self.db_file = db_file
        self._connection: Connection | None = None

    @property
    def connection(self) -> Connection:
        if not self._connection:
            raise DatabaseError("No connection available, did you forget to connect?")
        return self._connection

    def connect(self) -> PizzaStore:
        """
        Connect to the database, creates file if not exist.

        Raises:
            DatabaseError: When connection is already opened
        """
        if self._connection:
            raise DatabaseError("Connection is already opened.")

        self._connection = Connection(self.db_file, check_same_thread=False)

        return self

    def disconnect(self) -> None:
        """Disconnects the databse."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def health_check(self) -> None:
        """Run check. Raises ValueError on failure."""
        try:
            with closing(self.connection.cursor()) as cursor:
                cursor.execute("SELECT 1 FROM sales")

        except Exception as err:
            raise ValueError("Health check failed") from err

    def _build_table(self) -> None:
        """Build the table if needed."""
        wal = "PRAGMA journal_mode=WAL;"
        sql = """\
            CREATE TABLE IF NOT EXISTS sales
            (
                date TEXT,
                time TEXT,
                name TEXT,
                size TEXT,
                style TEXT,
                price TEXT
            )"""

        with self._write_lock:
            self.connection.execute(wal)
            self.connection.execute(sql)
            self.connection.commit()

    def get_sales_count(self) -> int:
        """Return the count of rows for the sales table."""
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("SELECT COUNT(*) FROM sales")
            return cursor.fetchone()[0]

    def get_recent(self, row_count: int = 10) -> list[Order]:
        """Return the most recent Orders from the table."""
        sql = """\
            SELECT
                date,
                time,
                name,
                size,
                style,
                price,
                ROWID
            FROM sales
            ORDER BY
                date DESC,
                time DESC,
                ROWID DESC
            LIMIT(?);
        """
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(sql, [row_count])
            results = cursor.fetchall()

        return [Order(*result) for result in results]

    def save_orders(self, orders: Iterable[Order]) -> None:
        """Save multiple orders to the table."""
        sql = """\
            INSERT INTO sales
            (
                date,
                time,
                name,
                size,
                style,
                price
            )
            VALUES
            (?,?,?,?,?,?);
        """
        values = ((o.date, o.time, o.name, o.size, o.style, o.price) for o in orders)
        with self._write_lock:
            with closing(self.connection.cursor()) as cursor:
                cursor.executemany(sql, values)

            self.connection.commit()

    def save_order(self, order: Order) -> None:
        """Save an order to the table."""
        self.save_orders((order,))

    def flush_orders(self) -> None:
        """Flush sales table. USE WITH CAUTION."""
        with self._write_lock:
            with closing(self.connection.cursor()) as cursor:
                cursor.execute("DELETE FROM sales")

            self.connection.commit()

    def build_sales_from_csv(self, filename: str, *, flush: bool = False) -> None:
        """
        Fill the sales table from a csv file input.

        Headers are required in the csv. The following columns are required:

        - id
        - date
        - time
        - name
        - size
        - type
        - price

        Args:
            filename: Path and name of the csv to load
            flush: When true the sales table will be flushed first
        """
        with open(filename, "r") as csv_in:
            reader = csv.DictReader(csv_in)
            orders = (
                Order(
                    date=r["date"],
                    time=r["time"],
                    name=r["name"],
                    size=r["size"],
                    style=r["type"],
                    price=r["price"],
                )
                for r in reader
            )

            self._build_table()
            if flush:
                self.flush_orders()
            self.save_orders(orders)


if __name__ == "__main__":
    print("This will purge the existing sales table and refill it.")
    if input(f"Load {_SALES_CSV} into pizzastore? (y/N) ").upper() not in ("Y", "YES"):
        raise SystemExit(0)

    store = PizzaStore().connect()
    store.build_sales_from_csv(_SALES_CSV, flush=True)
    print(f"Sales table now has {store.get_sales_count()} rows.")
