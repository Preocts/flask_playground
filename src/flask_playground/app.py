from __future__ import annotations

import datetime
import functools
import os
import secrets
import time
from collections.abc import Callable
from collections.abc import Generator
from typing import Any

import flask
import svcs

from .pizzastore import Order
from .pizzastore import PizzaStore

SECRET_KEY_ENV = "FLASK_APP_SECRET_KEY"
SESSION_LENGTH_SECONDS = 30


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

    return app


app = construct_app()


def require_login(func: Callable[..., flask.Response]) -> Callable[..., flask.Response]:
    """Decorated functions will always require a valid session user."""

    @functools.wraps(func)
    def login_enforement(*args: Any, **kwargs: Any) -> flask.Response:
        if not flask.session.get("usersession"):
            flask.session["return_url"] = flask.request.url
            return flask.make_response(flask.redirect(flask.url_for("login")))

        return func(*args, **kwargs)

    return login_enforement


def check_expired(func: Callable[..., flask.Response]) -> Callable[..., flask.Response]:
    """Decorated functions will always require an unexpired session."""

    @functools.wraps(func)
    def login_enforement(*args: Any, **kwargs: Any) -> flask.Response:
        granted_at = flask.session["usersession"].get("granted_at", 0)
        is_expired = int(time.time()) - granted_at > SESSION_LENGTH_SECONDS

        if is_expired:
            flask.session.pop("usersession", default=None)
            flask.session["return_url"] = flask.request.url
            return flask.make_response(flask.redirect(flask.url_for("logout")))

        return func(*args, **kwargs)

    return login_enforement


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
    store = svcs.flask.get(PizzaStore)

    session = flask.session["usersession"]

    return flask.make_response(
        flask.render_template(
            "index.html",
            username=session["username"],
            total_rows=store.get_sales_count(),
            sale_rows=store.get_recent(100),
        )
    )


@app.route("/total_orders", methods=["GET"])
@require_login
@check_expired
def total_orders() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    return flask.make_response(
        flask.render_template_string(
            '<span hx-trigger="order-placed-event from:body" hx-get="/total_orders" hx-swap="outerHTML">{{ total_orders }}</span>',
            total_orders=store.get_sales_count(),
        )
    )


@app.route("/order_table", methods=["GET"])
@require_login
@check_expired
def order_table() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    return flask.make_response(
        flask.render_template(
            "partial/order_table.html",
            total_rows=store.get_sales_count(),
            sale_rows=store.get_recent(25),
        )
    )


@app.route("/order", methods=["POST"])
@require_login
@check_expired
def place_order() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    order = Order(
        order_id="broken",
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        time=datetime.datetime.now().strftime("%H:%M:%S"),
        name=flask.request.form["name"],
        size=flask.request.form["size"],
        style=flask.request.form["style"],
        price="20.00",
    )

    store.save_order(order)
    resp = flask.make_response(flask.render_template("partial/order_form.html"))
    resp.headers["HX-Trigger"] = "order-placed-event"

    return resp


@app.route("/pagetwo", methods=["GET"])
@require_login
@check_expired
def pagetwo() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    return flask.make_response(
        flask.render_template(
            "pagetwo/index.html",
            count=store.get_sales_count(),
        )
    )


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
