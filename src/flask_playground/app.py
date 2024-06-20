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
import functools
import json
import os
import secrets
import tempfile
import time
from collections.abc import Callable
from collections.abc import Generator
from typing import Any

import flask
import svcs

from .pizzastore import Order
from .pizzastore import PizzaStore

SECRET_KEY_ENV = "FLASK_APP_SECRET_KEY"
SESSION_LENGTH_SECONDS = 300


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
            # Do not reroute a user to a private path on return from login
            if flask.request.path.startswith("/_"):
                flask.session["return_url"] = flask.request.url_root
            else:
                flask.session["return_url"] = flask.request.url

            # Return both a flask redirect and an htmx redirect header to cover both
            # cases of js users and js avoiders.
            resp = flask.make_response(flask.redirect(flask.url_for("login")))
            resp.headers["HX-Redirect"] = flask.url_for("login")
            return resp

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

            # Do not reroute a user to a private path on return from login
            if flask.request.path.startswith("/_"):
                flask.session["return_url"] = flask.request.url_root
                code = 403
            else:
                flask.session["return_url"] = flask.request.url
                code = 302

            # Return both a flask redirect and an htmx redirect header to cover both
            # cases of js users and js avoiders.
            resp = flask.make_response(flask.redirect(flask.url_for("logout"), code))
            resp.headers["HX-Redirect"] = flask.url_for("logout")
            resp.headers["HX-Refresh"] = "true"
            return resp

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
    file_name = "pizza_orders"
    format_ = flask.request.args.get("format")
    store = svcs.flask.get(PizzaStore)
    rows = store.get_recent(0)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8") as report_file:
        if format_ == "json":
            json.dump([row.asdict() for row in rows], report_file)
            file_name += ".json"

        else:
            csvwriter = csv.DictWriter(report_file, list(rows[0].asdict().keys()))
            csvwriter.writeheader()
            csvwriter.writerows((row.asdict() for row in rows))
            file_name += ".csv"

        time.sleep(2)

        return flask.send_file(
            path_or_file=report_file.name,
            as_attachment=True,
            download_name=file_name,
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
