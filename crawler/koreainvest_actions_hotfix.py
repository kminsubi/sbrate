import sys
import time


def _chrome_options():
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.page_load_strategy = "eager"
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1600,1400",
        "--ignore-certificate-errors",
        "--disable-popup-blocking",
        "--disable-notifications",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-features=Translate,MediaRouter",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-pipe",
    ):
        options.add_argument(arg)

    options.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        },
    )
    return options


def _edge_options():
    from selenium.webdriver.edge.options import Options

    options = Options()
    options.page_load_strategy = "eager"
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1600,1400",
        "--ignore-certificate-errors",
        "--disable-popup-blocking",
        "--disable-notifications",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-features=Translate,MediaRouter",
        "--no-first-run",
        "--no-default-browser-check",
    ):
        options.add_argument(arg)
    return options


def create_driver(prefer="Chrome"):
    """Use Chrome first on GitHub Actions/Linux, then Edge as a fallback."""
    from selenium import webdriver

    if sys.platform.startswith("linux"):
        browsers = ["Chrome", "Edge"]
    else:
        browsers = [prefer, "Chrome" if prefer == "Edge" else "Edge"]

    errors = []
    seen = set()

    for browser in browsers:
        if browser in seen:
            continue
        seen.add(browser)
        try:
            if browser == "Chrome":
                driver = webdriver.Chrome(options=_chrome_options())
            else:
                driver = webdriver.Edge(options=_edge_options())

            driver.set_page_load_timeout(28)
            driver.set_script_timeout(20)
            return driver, browser
        except Exception as error:
            errors.append(f"{browser}:{type(error).__name__}:{error}")

    raise RuntimeError(
        "한국투자 WebDriver 실행 실패 | " + " | ".join(errors)
    )


_EXTRACT_SCRIPT = r"""
const preferred = document.getElementById('mf_wfm_contents_intrGridView');
const selectors = [
  "[id*='intrGridView']",
  "[id*='intrgridview']",
  "[id*='gridView']",
  "[id*='contents']",
  "main",
  "body"
];
const roots = [];
if (preferred) roots.push(preferred);
for (const selector of selectors) {
  for (const el of document.querySelectorAll(selector)) {
    if (!roots.includes(el)) roots.push(el);
  }
}

function textOf(el) {
  return ((el && el.innerText) || '').replace(/\s+/g, ' ').trim();
}

function tableData(root) {
  return Array.from(root.querySelectorAll('table')).map((table, tableIndex) => ({
    tableIndex,
    rows: Array.from(table.querySelectorAll('tr')).map(row =>
      Array.from(row.querySelectorAll('th,td')).map(cell => ({
        text: textOf(cell),
        tag: cell.tagName,
        rowspan: cell.getAttribute('rowspan') || '1',
        colspan: cell.getAttribute('colspan') || '1'
      }))
    )
  }));
}

let best = null;
for (const root of roots) {
  const text = textOf(root);
  if (!text || text.length < 30) continue;
  const tables = tableData(root);
  const score =
    (text.includes('ISA') ? 4 : 0) +
    (text.includes('퇴직연금') ? 4 : 0) +
    (text.includes('개월') ? 2 : 0) +
    (text.includes('%') ? 2 : 0) +
    Math.min(tables.length, 5);
  if (!best || score > best.score) {
    best = {text, tables, score, rootId: root.id || root.tagName};
  }
}

if (!best) return null;

// Some WebSquare wrappers have the text but tables live under body.
if ((!best.tables || best.tables.length === 0) && document.body) {
  best.tables = tableData(document.body);
}
return best;
"""


def _extract_section(driver):
    try:
        return driver.execute_script(_EXTRACT_SCRIPT)
    except Exception:
        return None


def _diagnostic(driver):
    try:
        return driver.execute_script(
            r"""
            const body=((document.body && document.body.innerText) || '')
              .replace(/\s+/g,' ').trim().slice(0,700);
            const ids=Array.from(document.querySelectorAll('[id]'))
              .map(x=>x.id)
              .filter(x=>/intr|grid|content|prd|wfm/i.test(x))
              .slice(0,30);
            return {url:location.href,title:document.title,body,ids};
            """
        ) or {}
    except Exception as error:
        return {"diagnostic_error": f"{type(error).__name__}:{error}"}


def open_target(driver, target):
    """
    Resilient WebSquare navigation for GitHub Actions.
    The old collector waited for one fixed element id; this version accepts
    the fixed root when present and falls back to visible WebSquare content.
    """
    from selenium.common.exceptions import TimeoutException

    raw_url = str(target.get("url") or "").strip()
    expected = str(target.get("expected_title") or "").strip()
    urls = []
    for candidate in (raw_url, raw_url.rstrip("#")):
        if candidate and candidate not in urls:
            urls.append(candidate)

    last_error = None
    last_diag = {}

    for url in urls:
        try:
            try:
                driver.get(url)
            except TimeoutException:
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass

            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                section = _extract_section(driver)
                if isinstance(section, dict):
                    text = str(section.get("text") or "")
                    tables = section.get("tables") or []
                    product_hint = (
                        expected in text
                        or "ISA정기예금" in text
                        or "퇴직연금정기예금" in text
                        or "DC/IRP" in text
                    )
                    rate_hint = "%" in text and ("개월" in text or "년" in text)
                    if len(text) >= 50 and tables and (product_hint or rate_hint):
                        section["collector_mode"] = "actions_resilient_dom"
                        return section
                time.sleep(0.5)

            last_diag = _diagnostic(driver)
            last_error = RuntimeError(
                "WebSquare 금리영역 대기시간 초과"
            )

        except Exception as error:
            last_error = error
            last_diag = _diagnostic(driver)

    diag_text = (
        f"url={last_diag.get('url','-')} | "
        f"title={last_diag.get('title','-')} | "
        f"ids={last_diag.get('ids',[])} | "
        f"body={last_diag.get('body','')[:500]}"
    )
    raise RuntimeError(
        "한국투자 WebSquare DOM 수집 실패 | "
        f"{type(last_error).__name__ if last_error else 'Unknown'}:{last_error} | "
        + diag_text
    )


def apply(pr):
    pr.koreainvest_create_driver = create_driver
    pr._koreainvest_open_target = open_target
    return pr
