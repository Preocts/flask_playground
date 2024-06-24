from __future__ import annotations

import csv
import os
import time

import flask
import svcs

from .._decorators import check_expired
from .._decorators import require_login
from ..file_store import FileStore
from ..pizzastore import PizzaStore

reports_bp = flask.Blueprint(
    name="reports_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/reports",
)


@reports_bp.route("/", methods=["GET"])
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
            "reports.html",
            stats=stats,
        )
    )


@reports_bp.route("_report", methods=["GET"])
@require_login
@check_expired
def _report() -> flask.Response:
    store = svcs.flask.get(PizzaStore)
    file_directory = svcs.flask.get(FileStore).file_directory

    rows = store.get_recent(0)

    timestamp = time.strftime("%Y.%m.%d-%H.%M")
    file_name = f"{timestamp}_pizza_orders.csv"
    full_path = os.path.join(file_directory, file_name)

    if not os.path.exists(full_path):
        with open(full_path, "w", encoding="utf-8") as report_file:
            csvwriter = csv.DictWriter(report_file, list(rows[0].asdict().keys()))
            csvwriter.writeheader()
            csvwriter.writerows((row.asdict() for row in rows))

    download_url = flask.url_for("reports_bp._download", filename=file_name)

    return flask.make_response(
        flask.render_template(
            template_name_or_list="partial_download_link.html",
            url=download_url,
            filename=file_name,
        )
    )


@reports_bp.route("_download/<string:filename>")
@require_login
@check_expired
def _download(filename: str) -> flask.Response:
    file_directory = svcs.flask.get(FileStore).file_directory

    return flask.send_from_directory(
        directory=file_directory,
        path=filename,
        as_attachment=True,
    )
