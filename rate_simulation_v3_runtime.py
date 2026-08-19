# SBRate Rate Simulation V3 runtime wiring
# - Direct stable assets for PC dashboard
# - Prevent stale dashboard HTML after deploy
# - Load V4 layout/label polish on both PC and mobile
# - Load V5 mobile selector alignment polish
# - Load V6 market-basis selector and readable layout polish
# - Load V7 unified period/product condition subpanel
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
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)

                # PC receives V3 assets here. Mobile already has the V3 assets
                # directly in its template, so the marker prevents duplication.
                v3_marker = "data-sbrate-rate-simulation-v2=\"v3\""
                if request.path == "/" and v3_marker not in html:
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

                # V4 remains a separate override, with an explicit cache bump
                # whenever PC/mobile layout polish changes.
                v4_marker = "data-sbrate-rate-simulation-v4=\"1\""
                if v4_marker not in html:
                    v4_css = (
                        '<link data-sbrate-rate-simulation-v4="1" '
                        'rel="stylesheet" '
                        'href="/static/css/rate_simulation_v4_polish.css?v=20260820v2">'
                    )
                    v4_js = (
                        '<script data-sbrate-rate-simulation-v4="1" '
                        'src="/static/js/rate_simulation_v4_polish.js?v=20260820v1"></script>'
                    )
                    html = html.replace("</head>", v4_css + "\n</head>", 1)
                    html = html.replace("</body>", v4_js + "\n</body>", 1)

                # V5 aligns the mobile selector-card left/right geometry with
                # the rate cards below. V6 can still reduce its height later.
                v5_marker = "data-sbrate-rate-simulation-v5=\"1\""
                if v5_marker not in html:
                    v5_css = (
                        '<link data-sbrate-rate-simulation-v5="1" '
                        'rel="stylesheet" '
                        'href="/static/css/rate_simulation_v5_mobile_align.css?v=20260820v1">'
                    )
                    html = html.replace("</head>", v5_css + "\n</head>", 1)

                # V6 is loaded after earlier layers so its smaller selector cards,
                # larger PC text and market-basis selector win over old polish.
                v6_marker = "data-sbrate-rate-simulation-v6=\"1\""
                if v6_marker not in html:
                    v6_css = (
                        '<link data-sbrate-rate-simulation-v6="1" '
                        'rel="stylesheet" '
                        'href="/static/css/rate_simulation_v6.css?v=20260820v1">'
                    )
                    v6_js = (
                        '<script data-sbrate-rate-simulation-v6="1" '
                        'src="/static/js/rate_simulation_v6.js?v=20260820v2"></script>'
                    )
                    html = html.replace("</head>", v6_css + "\n</head>", 1)
                    html = html.replace("</body>", v6_js + "\n</body>", 1)

                # V7 groups period/product into one secondary condition panel.
                # It is loaded last and only changes layout, not simulation math.
                v7_marker = "data-sbrate-rate-simulation-v7=\"1\""
                if v7_marker not in html:
                    v7_css = (
                        '<link data-sbrate-rate-simulation-v7="1" '
                        'rel="stylesheet" '
                        'href="/static/css/rate_simulation_v7_condition_panel.css?v=20260820v1">'
                    )
                    v7_js = (
                        '<script data-sbrate-rate-simulation-v7="1" '
                        'src="/static/js/rate_simulation_v7_condition_panel.js?v=20260820v1"></script>'
                    )
                    html = html.replace("</head>", v7_css + "\n</head>", 1)
                    html = html.replace("</body>", v7_js + "\n</body>", 1)

                response.set_data(html)
                response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Rate Simulation V3 runtime error:", error)
        return response

    app_module._rate_simulation_v3_runtime_installed = True
    print("Rate Simulation V3 runtime installed")
    return True
