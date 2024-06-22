from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

import flask

from ._constants import SESSION_LENGTH_SECONDS


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
