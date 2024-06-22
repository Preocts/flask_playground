from __future__ import annotations

import time

import flask

__all__ = ["auth_bp"]

auth_bp = flask.Blueprint(
    name="auth_bp",
    import_name=__name__,
    template_folder="templates",
)


@auth_bp.route("/login", methods=["GET"])
def login() -> flask.Response:
    if "usersession" not in flask.session:
        return flask.make_response(flask.render_template("login.html"))

    return_route = flask.session.pop("return_url", default=flask.url_for("root"))

    return flask.make_response(flask.redirect(return_route))


@auth_bp.route("/login", methods=["POST"])
def login_postback() -> flask.Response:
    flask.session["usersession"] = {
        "username": flask.request.form["username"],
        "granted_at": int(time.time()),
    }

    return_route = flask.session.pop("return_url", default=flask.url_for("root"))

    return flask.make_response(flask.redirect(return_route))


@auth_bp.route("/logout", methods=["GET"])
def logout() -> flask.Response:
    flask.session.pop("usersession", default=None)

    if "return_url" in flask.session:
        return flask.make_response(flask.redirect(flask.url_for("login")))

    return flask.make_response(flask.render_template("logout.html"))
