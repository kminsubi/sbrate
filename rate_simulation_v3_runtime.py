# SBRate Rate Simulation V3 runtime wiring
# - Direct stable assets for PC dashboard
# - Prevent stale dashboard HTML after deploy
import sys


def install_rate_simulation_v3_runtime():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False

    app = app_module.app
    if getattr(app_module, "_rate_simulation_v3_runtime_installed", False):
        return True

    from flask import request

    @app.after_request
    def wire_rate_simulation_v3(response):
        try:
            if request.path in ("/", "/mobile"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

            if (
                request.path == "/"
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                marker = "data-sbrate-rate-simulation-v2=\"v3\""
                if marker not in html:
                    css = (
                        '<link data-sbrate-rate-simulation-v2="v3" '
                        'rel="stylesheet" '
                        'href="/static/css/rate_simulation_v3.css?v=20260819v3">'
                    )
                    js = (
                        '<script data-sbrate-rate-simulation-v2="v3" '
                        'src="/static/js/rate_simulation_v3.js?v=20260819v3"></script>'
                    )
                    guard = (
                        '<script data-sbrate-rate-simulation-v3-guard="1" '
                        'src="/static/js/rate_simulation_v3_guard.js?v=20260819v1"></script>'
                    )
                    html = html.replace("</head>", css + "\n</head>", 1)
                    html = html.replace("</body>", js + "\n" + guard + "\n</body>", 1)
                    response.set_data(html)
                    response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Rate Simulation V3 runtime error:", error)
        return response

    app_module._rate_simulation_v3_runtime_installed = True
    print("Rate Simulation V3 runtime installed")
    return True
