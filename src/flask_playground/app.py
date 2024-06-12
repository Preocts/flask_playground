from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import flask
import svcs

from .pizzastore import PizzaStore

SECRET_KEY = "hush now, this is secret"


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
    """Decorated functions will always require a valid session."""

    @functools.wraps(func)
    def login_enforement(*args: Any, **kwargs: Any) -> flask.Response:
        if not flask.session.get("username"):
            return flask.make_response(flask.redirect(flask.url_for("login")))

        return func(*args, **kwargs)

    return login_enforement


@app.route("/", methods=["GET"])
def root() -> flask.Response:
    store = svcs.flask.get(PizzaStore)

    if "username" in flask.session:
        return flask.make_response(
            f"""\
                <html>
                    <body>
                        <p>Welcome, {flask.session["username"]}</p>
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
    return flask.make_response(
        """\
            <html>
                <body>
                    <p>Welcome,</p>
                    <br><br>
                    <p><a href="/login">Login here</a></p>
                </body>
            </html>
        """
    )


@app.route("/pagetwo", methods=["GET"])
@require_login
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

    flask.session["username"] = flask.request.form["username"]
    return flask.make_response(flask.redirect(flask.url_for("root")))


@app.route("/logout", methods=["GET"])
def logout() -> flask.Response:
    flask.session.pop("username", default=None)
    return flask.make_response(flask.redirect(flask.url_for("root")))


if __name__ == "__main__":
    app.run("127.0.0.1", 3000)
