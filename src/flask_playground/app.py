"""
Notes:

All secured pages should use the @requires_login and @check_expired decorators

Routes intended to be called internally should be prefixed with an underscore the same
as an internal function. This allows decorators to determine how to redirect the client
when needed. We don't want to redirect a client to an internal route which only renders
a partial tempalte.


"""

from __future__ import annotations

import csv
import datetime
import os
import pathlib
import secrets
import time
from collections.abc import Generator
from typing import Any

import flask
import svcs

from ._constants import SECRET_KEY_ENV
from ._constants import TEMP_FILE_DIRECTORY
from ._decorators import check_expired
from ._decorators import require_login
from .pizzastore import Order
from .pizzastore import PizzaStore


def _database_factory() -> Generator[PizzaStore, None, None]:
    """Generate a PizzaStore object for svcs."""
    store = PizzaStore()
    yield store.connect()
    store.disconnect()


def construct_app() -> flask.Flask:
    """Build an app with all the things."""
    app = flask.Flask(__name__)
    app.secret_key = os.getenv(SECRET_KEY_ENV, secrets.token_hex(32))

    store = PizzaStore()
    svcs.flask.init_app(app)
    svcs.flask.register_factory(
        app=app,
        svc_type=PizzaStore,
        factory=_database_factory,
        ping=store.health_check,
        on_registry_close=store.disconnect,
    )

    (pathlib.Path(app.root_path) / TEMP_FILE_DIRECTORY).mkdir(exist_ok=True)

    return app


app = construct_app()


@app.errorhandler(404)
def not_found(_: Any) -> flask.Response:
    return flask.make_response(flask.render_template("notfound.html"))


@app.errorhandler(Exception)
def failure(error: Any) -> flask.Response:
    return flask.make_response(flask.render_template("error.html", error=error))


@app.route("/", methods=["GET"])
@require_login
@check_expired
def root() -> flask.Response:
    session = flask.session["usersession"]

    return flask.make_response(
        flask.render_template(
            "index.html",
            username=session["username"],
        )
    )


@app.route("/_total_orders", methods=["GET"])
@require_login
@check_expired
def _total_orders() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    return flask.make_response(
        flask.render_template_string(
            '<span hx-trigger="order-placed-event from:body" hx-get="/_total_orders" hx-swap="outerHTML">{{ total_orders }}</span>',
            total_orders=store.get_sales_count(),
        )
    )


@app.route("/_orders_table", methods=["GET"])
@require_login
@check_expired
def _orders_table() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    return flask.make_response(
        flask.render_template(
            "partial/order_table.html",
            total_rows=store.get_sales_count(),
            sale_rows=store.get_recent(25),
        )
    )


@app.route("/_place_order", methods=["POST"])
@require_login
@check_expired
def _place_order() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    order = Order(
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        time=datetime.datetime.now().strftime("%H:%M:%S"),
        name=flask.request.form["name"],
        size=flask.request.form["size"],
        style=flask.request.form["style"],
        price="20.00",
    )

    store.save_order(order)

    resp = flask.Response(status=204)
    resp.headers["HX-Trigger"] = "order-placed-event"

    return resp


@app.route("/pagetwo", methods=["GET"])
@require_login
@check_expired
def pagetwo() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    stats = {
        "total_orders": store.get_sales_count(),
        "by_style": store.get_percent_by_column("style"),
        "by_name": store.get_percent_by_column("name"),
        "by_size": store.get_percent_by_column("size"),
    }

    return flask.make_response(
        flask.render_template(
            "pagetwo/index.html",
            stats=stats,
        )
    )


@app.route("/pagetwo/_report", methods=["GET"])
@require_login
@check_expired
def _report() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    rows = store.get_recent(0)

    timestamp = time.strftime("%Y.%m.%d-%H.%M")
    file_path = pathlib.Path(app.root_path) / TEMP_FILE_DIRECTORY
    file_name = file_path / f"{timestamp}_pizza_orders.csv"

    if not file_name.exists():
        with open(file_name, "w", encoding="utf-8") as report_file:
            csvwriter = csv.DictWriter(report_file, list(rows[0].asdict().keys()))
            csvwriter.writeheader()
            csvwriter.writerows((row.asdict() for row in rows))

    download_url = flask.url_for("_download", filename=file_name.name)

    return flask.make_response(
        flask.render_template(
            template_name_or_list="pagetwo/partial_download_link.html",
            url=download_url,
            filename=file_name.name,
        )
    )


@app.route("/pagetwo/_download/<string:filename>")
@require_login
@check_expired
def _download(filename: str) -> flask.Response:
    print(f"{app.root_path=}")
    return flask.send_from_directory(TEMP_FILE_DIRECTORY, filename, as_attachment=True)


@app.route("/pagethree", methods=["GET"])
@require_login
@check_expired
def pagethree() -> flask.Response:
    raise ValueError("The egg has gone bad.")


@app.route("/login", methods=["GET"])
def login() -> flask.Response:
    if "usersession" not in flask.session:
        return flask.make_response(flask.render_template("auth/login.html"))

    return_route = flask.session.pop("return_url", default=flask.url_for("root"))

    return flask.make_response(flask.redirect(return_route))


@app.route("/login", methods=["POST"])
def login_postback() -> flask.Response:
    flask.session["usersession"] = {
        "username": flask.request.form["username"],
        "granted_at": int(time.time()),
    }

    return_route = flask.session.pop("return_url", default=flask.url_for("root"))

    return flask.make_response(flask.redirect(return_route))


@app.route("/logout", methods=["GET"])
def logout() -> flask.Response:
    flask.session.pop("usersession", default=None)

    if "return_url" in flask.session:
        return flask.make_response(flask.redirect(flask.url_for("login")))

    return flask.make_response(flask.render_template("auth/logout.html"))


if __name__ == "__main__":
    app.run("127.0.0.1", 3000, debug=True)
