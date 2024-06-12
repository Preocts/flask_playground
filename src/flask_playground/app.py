from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

import flask
import svcs

from .pizzastore import PizzaStore

SECRET_KEY = "hush now, this is secret to everyone"
SESSION_LENGTH_SECONDS = 10


def construct_app() -> flask.Flask:
    """Build an app with all the things."""

    app = flask.Flask(__name__)
    app.secret_key = SECRET_KEY

    store = PizzaStore()
    svcs.flask.init_app(app)
    svcs.flask.register_factory(
        app=app,
        svc_type=PizzaStore,
        factory=store.svcs_factory,
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
            return flask.make_response(flask.redirect(flask.url_for("login")))

        return func(*args, **kwargs)

    return login_enforement


@app.route("/", methods=["GET"])
@require_login
@check_expired
def root() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    session = flask.session["usersession"]
    return flask.make_response(
        f"""\
            <html>
                <body>
                    <p>Welcome, {session["username"]}</p>
                    <p>Session granted at: {session["granted_at"]}</p>
                    <br><br>
                    <p>Using store id: {id(store)}</p>
                    <p>Total rows: {store.get_sales_count()}</p>
                    <br><br>
                    <p><a href="/pagetwo">Page Two</a></p>
                    <br><br>
                    <p><a href="/logout">Logout here</a></p>
                </body>
            </html>
        """
    )


@app.route("/pagetwo", methods=["GET"])
@require_login
@check_expired
def pagetwo() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    return flask.make_response(
        f"""\
            <html>
                <body>
                    <p>This is page two</p>
                    <br><br>
                    <p>Using store id: {id(store)}</p>
                    <p>Total rows: {store.get_sales_count()}</p>
                    <br><br>
                    <p><a href="/">Return home</a></p>
                </body>
            </html>
        """
    )


@app.route("/login", methods=["POST", "GET"])
def login() -> flask.Response:
    if flask.request.method == "GET":
        return flask.make_response(
            """\
            <html>
                <body>
                    <form method="post">
                        <p>Please enter a username to login</p>
                        <p><input type="text" name="username"></p>
                        <p><input type="submit" value="Login"></p>
                    </form>
                </body>
            </html>
            """
        )

    flask.session["usersession"] = {
        "username": flask.request.form["username"],
        "granted_at": int(time.time()),
    }

    return flask.make_response(flask.redirect(flask.url_for("root")))


@app.route("/logout", methods=["GET"])
def logout() -> flask.Response:
    flask.session.pop("usersession", default=None)
    return flask.make_response(flask.redirect(flask.url_for("root")))


if __name__ == "__main__":
    app.run("127.0.0.1", 3000)
