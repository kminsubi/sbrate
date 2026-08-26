import sys


ASSET_VERSION = "20260826mi7"


def install_management_report_v5_runtime():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False
    if getattr(app_module, "_management_report_v5_runtime_installed", False):
        return True

    flask_app = app_module.app
    from flask import request

    @flask_app.after_request
    def management_report_v5_assets(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                if "management_report_v5_patch.css" not in html:
                    html = html.replace(
                        "</head>",
                        '<link rel="stylesheet" href="/static/css/management_report_v5_patch.css?v=20260826v8">\n</head>',
                        1,
                    )
                if "management_intelligence.css" not in html:
                    html = html.replace(
                        "</head>",
                        f'<link rel="stylesheet" href="/static/css/management_intelligence.css?v={ASSET_VERSION}">\n</head>',
                        1,
                    )
                if "management_report_bank_focus.css" not in html:
                    html = html.replace(
                        "</head>",
                        f'<link rel="stylesheet" href="/static/css/management_report_bank_focus.css?v={ASSET_VERSION}">\n</head>',
                        1,
                    )
                if "management_report_stability.css" not in html:
                    html = html.replace(
                        "</head>",
                        f'<link rel="stylesheet" href="/static/css/management_report_stability.css?v={ASSET_VERSION}">\n</head>',
                        1,
                    )
                if "management_report_v5_patch.js" not in html:
                    html = html.replace(
                        "</body>",
                        '<script src="/static/js/management_report_v5_patch.js?v=20260826v8"></script>\n</body>',
                        1,
                    )
                if "management_intelligence.js" not in html:
                    html = html.replace(
                        "</body>",
                        f'<script src="/static/js/management_intelligence.js?v={ASSET_VERSION}"></script>\n</body>',
                        1,
                    )
                if "management_intelligence_polish.js" not in html:
                    html = html.replace(
                        "</body>",
                        f'<script src="/static/js/management_intelligence_polish.js?v={ASSET_VERSION}"></script>\n</body>',
                        1,
                    )
                if "management_report_bank_focus.js" not in html:
                    html = html.replace(
                        "</body>",
                        f'<script src="/static/js/management_report_bank_focus.js?v={ASSET_VERSION}"></script>\n</body>',
                        1,
                    )
                if "management_report_stability.js" not in html:
                    html = html.replace(
                        "</body>",
                        f'<script src="/static/js/management_report_stability.js?v={ASSET_VERSION}"></script>\n</body>',
                        1,
                    )
                response.set_data(html)
                response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Management report V5 asset wiring error:", error)
        return response

    app_module._management_report_v5_runtime_installed = True
    print("Management Report V5 runtime installed")
    return True
