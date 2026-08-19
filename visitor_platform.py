# ==========================================
# SBRate Visitor Platform Detection
# - Keep /mobile as mobile
# - Reclassify / requests from mobile browsers as mobile
# - Do not store User-Agent; inspect request only in memory
# ==========================================

import visitor_stats


def _is_mobile_request(request):
    mobile_hint = str(
        request.headers.get("Sec-CH-UA-Mobile", "")
    ).strip()

    if mobile_hint == "?1":
        return True

    ua = str(
        request.headers.get("User-Agent", "")
    ).lower()

    mobile_tokens = (
        "iphone",
        "ipod",
        "ipad",
        "android",
        "mobile",
        "windows phone",
        "opera mini",
        "opera mobi",
        "samsungbrowser",
    )

    return any(
        token in ua
        for token in mobile_tokens
    )


def enable_mobile_platform_detection():
    if getattr(
        visitor_stats,
        "_mobile_platform_detection_enabled",
        False
    ):
        return

    original_track_response = (
        visitor_stats._track_response
    )

    def track_response_with_device(
        response,
        platform,
        request,
        make_response
    ):
        resolved_platform = platform

        # A phone can open the root URL directly. In that case the old
        # route-only logic counted it as PC even though it is a mobile visit.
        if (
            platform == "pc"
            and _is_mobile_request(request)
        ):
            resolved_platform = "mobile"

        return original_track_response(
            response,
            resolved_platform,
            request,
            make_response
        )

    visitor_stats._track_response = (
        track_response_with_device
    )
    visitor_stats._mobile_platform_detection_enabled = True

    print(
        "Visitor Stats platform detection enabled"
    )
