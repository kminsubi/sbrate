import ssl
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter


BASE = "https://www.idbsb.com"
PAGE_URL = BASE + "/w2/itb/dps/inr/dpstInrstGuidance.xml"
API_URL = BASE + "/itb/dps/inr/selectDpstInrstGuidance.do"

DS_PARAM = {
    "sn": "",
    "inrstFdrmDpstDsmn": "10000000",
    "inrstBilDsmn": "10000000",
    "inrstFdrmSvingsMtPaymntAmt": "100000",
    "inrstIsaFdrmDpstDsmn": "10000000",
    "inrstGoodsInrstSeFdrmDpst": "1",
    "inrstGoodsInrstSeBil": "1",
    "inrstGoodsInrstSeFdrmSvings": "1",
    "inrstGoodsInrstSeNrmltyDpst": "1",
    "inrstGoodsInrstSeIsaFdrmDpst": "2",
    "inrstGoodsGoodsSeFdrmDpst": "01",
    "inrstGoodsGoodsSeBil": "11",
    "inrstGoodsGoodsSeFdrmSvings": "21",
    "inrstGoodsGoodsSeNrmltyDpst": "31",
    "inrstGoodsGoodsSeIsaFdrmDpst": "01",
}
PERIOD_MAP = {"3": "3m", "6": "6m", "12": "12m", "24": "24m", "36": "36m"}


class _DBTLSAdapter(HTTPAdapter):
    """DB site compatibility adapter used only after the normal TLS path fails."""

    def __init__(self, security_level=1, *args, **kwargs):
        self.security_level = int(security_level)
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # DB's current TLS endpoint can fail on OpenSSL 3 with
        # WRONG_SIGNATURE_TYPE. Lower the security level only for this
        # official DB domain and only after the normal TLS attempt failed.
        try:
            context.set_ciphers(f"DEFAULT@SECLEVEL={self.security_level}")
        except Exception:
            pass

        legacy_option = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0)
        if legacy_option:
            try:
                context.options |= legacy_option
            except Exception:
                pass

        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            **pool_kwargs,
        )


def _date(value):
    value = str(value or "").strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value or None


def _new_session(security_level=None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })

    if security_level is not None:
        session.mount(
            BASE,
            _DBTLSAdapter(security_level=security_level),
        )

    return session


def _request_official_data():
    errors = []

    # Normal TLS first. Compatibility modes are DB-domain-only fallbacks.
    modes = [
        ("normal", None),
        ("compat_seclevel1", 1),
        ("compat_seclevel0", 0),
    ]

    for mode_name, security_level in modes:
        session = _new_session(security_level)
        try:
            verify = security_level is None
            session.get(
                PAGE_URL,
                timeout=30,
                verify=verify,
                allow_redirects=True,
            ).raise_for_status()

            response = session.post(
                API_URL,
                json={"ds_param": DS_PARAM},
                headers={
                    "Origin": BASE,
                    "Referer": PAGE_URL,
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/json;charset=UTF-8",
                },
                timeout=30,
                verify=verify,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.json(), mode_name

        except Exception as error:
            errors.append(f"{mode_name}: {error}")
        finally:
            session.close()

    raise RuntimeError(
        "DB official API TLS/request failed | " + " | ".join(errors)
    )


def collect_db_isa():
    data, tls_mode = _request_official_data()

    if data.get("errorCode"):
        raise RuntimeError(
            f"{data.get('errorCode')}: {data.get('errorMessage')}"
        )

    rows = data.get("ds_inrstDtlIsaFdrmDpstList")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(
            "DB official response has no ds_inrstDtlIsaFdrmDpstList"
        )

    rates = {key: None for key in ("3m", "6m", "12m", "24m", "36m")}
    for row in rows:
        key = PERIOD_MAP.get(str(row.get("pd", "")).strip())
        value = row.get("intrtYy")
        if key and value not in (None, ""):
            rates[key] = float(value)

    def find_date(obj):
        if isinstance(obj, dict):
            if obj.get("isaStdde"):
                return _date(obj["isaStdde"])
            for value in obj.values():
                found = find_date(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = find_date(value)
                if found:
                    return found
        return None

    if rates.get("12m") is None:
        raise RuntimeError("DB official response has no ISA 12m rate")

    return {
        "bank": "DB",
        "product_type": "ISA",
        "product_name": "ISA정기예금",
        "rates": rates,
        "effective_date": find_date(data),
        "source": "official",
        "status": "verified_official",
        "source_url": PAGE_URL,
        "api_url": API_URL,
        "tls_mode": tls_mode,
    }


def collect_db():
    result = {
        "bank": "DB",
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ISA": None,
        "IRP": None,
        "errors": {},
    }
    try:
        result["ISA"] = collect_db_isa()
    except Exception as error:
        result["errors"]["ISA"] = str(error)
    return result


def main():
    result = collect_db()
    print("=" * 72)
    print("SBRateBot V5 - DB Official ISA Collector")
    print("=" * 72)

    if result["ISA"]:
        item = result["ISA"]
        print("ISA:", item["product_name"])
        print("  rates:", item["rates"])
        print("  effective_date:", item["effective_date"])
        print("  status:", item["status"])
        print("  tls_mode:", item.get("tls_mode"))
    else:
        print("ISA ERROR:", result["errors"].get("ISA"))

    print("IRP: 기존 pension_rates.py 공시 병합값 유지")
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
