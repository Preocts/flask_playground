"""
Notes:

All secured pages should use the @requires_login and @check_expired decorators

Routes intended to be called internally should be prefixed with an underscore the same
as an internal function. This allows decorators to determine how to redirect the client
when needed. We don't want to redirect a client to an internal route which only renders
a partial tempalte.


"""

from __future__ import annotations

import datetime
import os
import secrets
from collections.abc import Generator
from typing import Any

import flask
import svcs

from ._constants import DOWNLOAD_DIRECTORY
from ._constants import SECRET_KEY_ENV
from ._decorators import check_expired
from ._decorators import require_login
from .auth.auth import auth_bp
from .file_store import FileStore
from .pizzastore import Order
from .pizzastore import PizzaStore
from .reports.reports import reports_bp


def _database_factory() -> Generator[PizzaStore, None, None]:
    """Generate a PizzaStore object for svcs."""
    store = PizzaStore()
    yield store.connect()
    store.disconnect()


def _filestore_factory() -> Generator[FileStore, None, None]:
    """Generate a FileStore ojbect for svcs."""
    store = FileStore(DOWNLOAD_DIRECTORY)
    store.setup()
    yield store
    store.teardown()


def construct_app() -> flask.Flask:
    """Build an app with all the things."""
    app = flask.Flask(__name__)
    app.register_blueprint(auth_bp)
    app.register_blueprint(reports_bp)

    app.secret_key = os.getenv(SECRET_KEY_ENV, secrets.token_hex(32))

    svcs.flask.init_app(app)
    svcs.flask.register_factory(
        app=app,
        svc_type=PizzaStore,
        factory=_database_factory,
        ping=lambda svc: svc.health_check(),
    )
    svcs.flask.register_factory(
        app=app,
        svc_type=FileStore,
        factory=_filestore_factory,
        ping=lambda svc: svc.health_check(),
    )

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


@app.route("/pagethree", methods=["GET"])
@require_login
@check_expired
def pagethree() -> flask.Response:
    raise ValueError("The egg has gone bad.")


if __name__ == "__main__":
    app.run("127.0.0.1", 3000, debug=True)
