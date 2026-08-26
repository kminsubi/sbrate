import sys


PREFERRED_FIELD_ORDER = [
    "total_assets",
    "household_loans",
    "corporate_loans",
    "total_loans",
    "bis_ratio",
    "npl_ratio",
    "delinquency_ratio",
    "net_income",
    "employees",
]


def install_management_report_v4_runtime():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_report_v4_runtime_installed", False):
        return True

    import management_report as mr

    field_map = {item[0]: item for item in mr.FIELDS}
    ordered = [field_map[key] for key in PREFERRED_FIELD_ORDER if key in field_map]
    ordered.extend(item for item in mr.FIELDS if item[0] not in PREFERRED_FIELD_ORDER)
    mr.FIELDS = ordered

    flask_app = app_module.app
    from flask import request

    @flask_app.after_request
    def management_report_v4_assets(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                html = html.replace(
                    "/static/css/management_report.css?v=20260825v2",
                    "/static/css/management_report.css?v=20260826v8",
                )
                html = html.replace(
                    "/static/js/management_report.js?v=20260825v2",
                    "/static/js/management_report.js?v=20260826v8",
                )
                if "management_report_v4.css" not in html:
                    html = html.replace(
                        "</head>",
                        '<link rel="stylesheet" href="/static/css/management_report_v4.css?v=20260826v8">\n</head>',
                        1,
                    )
                response.set_data(html)
                response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Management report V4 asset wiring error:", error)
        return response

    app_module._management_report_v4_runtime_installed = True
    print("Management Report V4 runtime installed")
    return True
