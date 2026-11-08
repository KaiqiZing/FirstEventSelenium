# FirstEventSelenium

Independent, self-contained Selenium UI automation suite for the system under test **FirstSeleniumUIEvent** (Vue 3 + Element Plus frontend, Flask backend).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-green.svg)](https://docs.pytest.org/)

English | [简体中文](README.zh-CN.md)

---

## Overview

The layered architecture is modeled after the `FiccAccountSelenium` style, but the code is **physically isolated** from both the system under test and the reference project — the import chain is fully self-contained, and no existing files of `FirstSeleniumUIEvent` or `FiccAccountSelenium` are modified.

**Data flow:** `case (pytest) → business (orchestration) → handle (scenario operations) → base (element lookup) + common (waits)`, with `util/` (driver factory, screenshot, API client, scenario support) as cross-cutting support.

## Project Structure

```
FirstEventSelenium/
├── config/                 # Configuration layer
│   ├── settings.yaml       # base_url / timeout / browser params / download dir / screenshot path
│   └── *Element.ini        # 6 locator files, 37 scenario sections ([module] key=by>value)
├── base/
│   └── find_element.py     # Scenario code -> (INI, Section) mapping + by>value parsing with cache
├── common/
│   ├── exceptions.py       # ElementNotFoundError etc.
│   └── webdriver_wait_common.py  # Explicit waits and element operation wrappers
├── util/
│   ├── driver_factory.py   # Driver creation (incl. download-dir prefs)
│   ├── screenshot_util.py  # Failure screenshots
│   ├── read_ini.py         # INI parsing
│   ├── api_client.py       # requests.Session helper to talk to the backend
│   ├── scenario_support.py # open_scenario / result_logs / wait_result_contains / preflight_services
│   ├── amount_util.py      # Amount text -> Decimal cleaning (¥/thousand separators/parenthesized negatives), cents->yuan, tolerance compare
│   ├── sqlite_source.py    # Read-only SQLite access (I-18 page vs DB; E-03 ciphertext vault vs page plaintext)
│   └── allure_compat.py    # Allure decorator compatibility wrapper
├── handle/
│   ├── base_scenario_handle.py  # Scenario operation base class (locate/wait/input/result-area assertions)
│   ├── action_support.py        # Cross-scenario platform actions (iframe/window/Shadow DOM/dialogs/drag/upload/rich text/lazy load)
│   └── *_handles.py             # Per-group element-level operation flows
├── business/
│   └── *_business.py      # Per-group orchestration (allure.step wrapped, with API/retry where needed)
├── case/
│   ├── conftest.py         # driver fixture / session-level health preflight / auto screenshot on failure
│   └── test_*.py           # 37 test cases, all asserting the bottom "operation result" area
├── run_tests.py            # Multi-mode entry point
├── requirements.txt
└── pytest.ini
```

## Getting Started

### 1. System under test (started manually by the user)

```bash
# Frontend (Vite proxies /api -> backend, same-origin, no CORS needed)
cd FirstSeleniumUIEvent/frontend && npm install && npm run dev   # :5174

# Backend (in-memory data, reset on restart)
cd FirstSeleniumUIEvent/backend && python app.py                 # 127.0.0.1:5000
```

> This project neither starts the services under test nor modifies their code. If the services are not running, tests fail fast with an explicit message (session-level health preflight via `GET /api/health` and frontend reachability).
>
> The frontend URL defaults to `http://localhost:5174` (`settings.yaml env.*.base_url`). When the Vite port is taken, the preflight auto-probes `5173 / 5174` and warns on switch — no config change needed.

### 2. Runtime environment

- Python 3.11+ (verified on Python 3.13); `webdriver-manager` auto-fits drivers (installed with `requirements.txt`)

**Supported browsers** (via `settings.yaml browser.type`, overridable with `pytest --browser`):

| Browser | OS | Driver |
| --- | --- | --- |
| Chrome | Windows / macOS / Linux | ChromeDriver (webdriver-manager) |
| Edge | Windows / macOS / Linux | EdgeDriver (webdriver-manager) |
| Firefox | Windows / macOS / Linux | GeckoDriver (webdriver-manager) |
| chromium (360 Secure/Speed, QQ, Qianxin, etc.) | All platforms | ChromeDriver + `browser.binary_path` pointing to the browser executable |
| Safari | macOS only | safaridriver (run `safaridriver --enable` first) |

> Sandbox flags (`--no-sandbox` / `--disable-dev-shm-usage`) are injected only on Linux (CI/Docker); startup args stay clean on Windows/macOS. Paths and drivers adapt to the current OS automatically.

```bash
cd FirstEventSelenium
python -m venv .venv
.venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

## Running Tests

### Full run

```bash
python run_tests.py --mode all
# equivalent to
python -m pytest case/ -v
```

### Other modes

```bash
python run_tests.py --mode smoke        # smoke: I-01 / I-02 / W-01 (marker=smoke)
python run_tests.py --mode regression   # regression (marker=regression)
python run_tests.py --mode allure       # generate Allure results and render an HTML report
```

### Single scenario / group

```bash
python -m pytest case/test_interact.py -q          # page interaction group
python -m pytest case/test_crypt.py -q             # data encryption group (E-01~E-04)
python -m pytest case/test_window.py -q            # multi-window group
python -m pytest "case/test_interact.py::test_i01_not_interactable" -q
python -m pytest case/ --tb=short -q               # short traceback
```

> Each case navigates directly via `open_scenario(driver, "/i/01")` — no manual navigation needed.

### Browser matrix (`--browser`)

Re-run the same suite on another browser; the CLI value overrides `browser.type` in `settings.yaml`:

```bash
python run_tests.py --mode smoke --browser chrome
python run_tests.py --mode smoke --browser edge
python run_tests.py --mode smoke --browser firefox
python run_tests.py --mode smoke --browser chromium      # 360/QQ etc.: set binary_path in settings.yaml first
python -m pytest case/ -q --browser firefox              # plain pytest works too
```

> `--browser` accepts `chrome` / `edge` / `firefox` / `chromium` / `safari`; aliases like `360` / `qq` are normalized to `chromium`. Without `--browser`, the configured default applies (default `chrome`).

## Scenario Coverage (37 cases)

### Page interaction `I-01 ~ I-18` (`case/test_interact.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| I-01 | Element not interactable | handover record saved |
| I-02 | Click intercepted (overlay / fixed header) | saved |
| I-03 | Stale element reference | refreshed |
| I-04 | iframe nested lookup | submitted |
| I-05 | Shadow DOM controls | applied |
| I-06 | Dynamic ID / class | bound |
| I-07 | Native + custom dual dropdown | selected |
| I-08 | Hover menu | switched |
| I-09 | Drag-and-drop sorting | adjusted |
| I-10 | File upload | upload succeeded |
| I-11 | Native alert/confirm/prompt | done |
| I-12 | Rich text editing | published |
| I-13 | Fade-in animation | played |
| I-14 | Scroll lazy loading | all loaded |
| I-15 | Offset container coordinates | captured |
| I-16 | Controlled input + async suggestions | suggestions filled back |
| I-17 | Parent-child amount reconciliation (collapse / same-name columns / rounding gap) | all parents expanded / recalculation done / amounts match |
| I-18 | Page numbers vs database (pagination / "cents" unit / summary drift / NULL / stale reads) | database rebuilt / details persisted / summary recalculated from details / page data not auto-refreshed |

#### How I-18 consistency checking works

The system under test persists to `backend/data/settlement.db` (not purely in-memory). `util/sqlite_source.py` connects read-only and compares "raw DB rows" against "page-rendered numbers" one by one:

| Check | Page side | Database side | Script handling |
| --- | --- | --- | --- |
| Unit | `¥862,300.00` (yuan) | `amount_cents=86230000` (cents) | convert via `cents_to_yuan` before compare |
| Pagination | 5 rows rendered at a time | 15 detail rows total | `collect_all_details` walks all 3 pages |
| Summary drift | summary card sums the "bill summary field" | `settle_bill.total_amount_cents` ≠ sum of `settle_detail` | two data sources fetched and compared separately |
| Unsettled | shown as "—" | `amount_cents=NULL` | `amount_of` returns `None`, summed as 0 |
| Stale reads | snapshot time unchanged | persisted after posting | assert old value first, refresh, then compare |
| Negative format | `(¥98,000.00)` | `-9800000` | `parse_amount` turns parentheses into a minus |
| Write latency | returns immediately after save | readable ~0.6s later | `wait_db_equals` / `wait_db_changed` polling |

The DB file path comes from the endpoint `/api/dbconsistency/db/meta` (no hardcoded absolute path); both ends of the case call `/api/dbconsistency/reset` to rebuild, so it is re-runnable.

**Design principles:** (1) no hardcoded amounts/counts — everything is derived from dynamic data (`COUNT(*)` vs page summary card cross-check, expected amounts always `cents_to_yuan` of DB cents, special rows picked by role: `ROLE_UNSETTLED`, `ROLE_NEGATIVE`, `pick_detail_in_matched_bill`); (2) the check is driven by a full business loop — *adjust detail amount → recalc summary → bill summary total changes → page ⇔ database*, with the static full scan (per-detail, summary card, funding accounts, NULL, negative format) as a pre-check.

### Waits & responses `W-01 ~ W-05` (`case/test_wait.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| W-01 | Slow API + loading overlay | data loaded |
| W-02 | SPA route change without refresh | switched |
| W-03 | 10s async export job | export finished + downloaded artifact exists |
| W-04 | Save/persist race | appeared in list |
| W-05 | Flaky API retry tolerance | eventually succeeded |

### Multi-window & tabs `M-01 ~ M-04` (`case/test_window.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| M-01 | Opens in a new tab | new tab opened |
| M-02 | OAuth popup auto-returns and closes | authorized and auto-closed |
| M-03 | New window with embedded iframe | master record registered |
| M-04 | Non-user-gesture `window.open` interception counter | intercepted/succeeded |

### Browser compatibility `C-01 ~ C-02` (`case/test_compat.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| C-01 | Native date-time picker | schedule submitted |
| C-02 | Runtime environment info check | current browser environment captured |

### Tricky cases `X-01 ~ X-04` (`case/test_misc.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| X-01 | CAPTCHA (universal code 1234) | captcha verified |
| X-02 | webdriver detection (read-only, no bypass) | environment check done / restricted notice |
| X-03 | Session cookie login state | logged in / logged out |
| X-04 | Server-side data seeding (self-create, self-clean) | server generated ticket |

### Data encryption `E-01 ~ E-04` (`case/test_crypt.py`)

| ID | Scenario | Assertion keywords (illustrative) |
| --- | --- | --- |
| E-01 | Transport-field encryption (RSA-OAEP, async public key, digest compare) | server decrypted ok / plaintext submit rejected / encrypted submit failed |
| E-02 | Sensitive-field masking (mask + time-limited reveal + cooldown) | profile list refreshed / auto-collapsed / view... failed |
| E-03 | Ciphertext-at-rest verification (AES-256-GCM + multi key versions) | registered / 2 ciphertexts for same plaintext / decrypted ok / decryption failed |
| E-04 | API payload encryption + timestamp/signature verification | decrypted locally / signature verified / signature invalid |

**Unified assertion approach for the encryption group** — nothing visible on the page is trusted as the source of truth:

1. **E-01 transport encryption**: DOM `value` is plaintext, the wire payload is ciphertext, and OAEP random padding makes every ciphertext different → equality assertions on ciphertext are forbidden; "same plaintext, two different ciphertexts" proves randomness. The backend no longer echoes the plaintext password (`CRYPTO_ECHO_PLAINTEXT=False`), so the stable assertion point is the **digest of the server-side decryption result** (`serverDigest`, first 16 uppercase hex of SHA-256), recomputed independently with `hashlib` and cross-checked across `#local-digest` / `#server-digest`. On non-secure contexts (no Web Crypto) it degrades to server-side digest only. The public key is an **async resource** (0.3–0.8s): wait for the fingerprint to be ready before submitting; old ciphertexts die after key rotation (1003); after a plaintext-channel submit the digest area must be cleared. **Network-level forensics**: since `#request-body` is self-rendered by the frontend, the CDP `Network` domain (`util/network_recorder.py`) additionally captures real request/response bodies to prove no plaintext on the wire and no `revealedPassword` echo. Chromium-only; other browsers degrade to the API-layer fallback automatically. Set `UIEVENT_DISABLE_PERF_LOG=1` to disable.
2. **E-02 masking**: the page shows masks, but some rows carry a `data-raw` plaintext attribute (a common leak in real projects) → that attribute exists only on some rows and is a **dirty path**; the primary assertion always uses `GET /api/crypto/masked/raw` full plaintext. The drawer reveals plaintext for 5 seconds then auto-collapses; a repeat request within cooldown returns 1002.
3. **E-03 ciphertext at rest**: the page shows server-decrypted values, the DB stores AES ciphertext + random IV + HMAC digest column → read SQLite `cust_profile` and `/api/crypto/vault/db/query` directly, decrypt **per `key_version`**, then compare with the page. "Never registered (page '—', API 2003)" and "key revoked (page 'decryption failed')" are asserted separately; the list paginates 5 per page so paging must collect all; the same plaintext always yields different ciphertext, so equality search relies on the digest column.
4. **E-04 payload encryption**: the API returns an encrypted envelope — **decryption success ≠ verification pass** → expired timestamp (2001) and tampered signature (2002) are asserted separately, and both envelopes still decrypt into 5 detail rows; decryption and signature verification must use **the same envelope** (each call generates a fresh random IV and timestamp), so `ts/sign/enc/iv` are read from the page and the server-side decrypt channel recomputes amounts with a tolerance compare against the page's thousand-separated text.

Business failure codes (1001/1002/1003/2001/2002/2003) return HTTP 200 with the message carried by an auto-dismissing ElMessage, so all assertions read the bottom "operation result" log area.

## Test Results

With both services running, `python -m pytest case/ -q`:

```
32 passed, 1 failed in ~5m30s
```

- **32 scenarios passed**, covering `I-01~I-18`, `W-01~W-05`, `M-01~M-04`, `C-01/C-02`, `X-01/X-02/X-03` (the interaction group measured `18 passed in 3m00s` including the new I-18).
- **X-04 (server-side seeding) failed** due to a **backend defect of the system under test**, unrelated to the automation code — see below.
- The encryption group `E-01~E-04` is counted separately via `python -m pytest case/test_crypt.py -q`.

### Known blocker on X-04

The backend `POST /api/seed/new` of the system under test consistently returns **HTTP 500**:

- Both direct `http://127.0.0.1:5000/api/seed/new` and via the frontend proxy `http://localhost:5174/api/seed/new` return 500;
- `GET /api/seed/list` in the same file works (`{"records": []}`);
- The backend source `backend/api/slow_api.py::seed_new` looks correct — the running backend process is likely stale / not restarted (the service is in-memory, a restart resets it).

**Fix:** restart the backend (`cd backend && python app.py`) so the latest `slow_api.py` takes effect, then rerun `python -m pytest case/test_misc.py::test_x04_seed_data -q`.

## Browser & OS Compatibility

| Browser | Platforms | Driver | Status |
| --- | --- | --- | --- |
| Chrome | Windows / macOS / Linux | ChromeDriver (webdriver-manager / Selenium Manager) | implemented & regression-tested |
| Edge | Windows / macOS / Linux | EdgeDriver (webdriver-manager) | implemented & regression-tested (Windows) |
| Firefox | Windows / macOS / Linux | GeckoDriver (webdriver-manager) | implemented & regression-tested (Windows) |
| chromium (360 Secure/Speed, QQ, Qianxin, etc.) | All platforms | ChromeDriver + `binary_path` | implemented, verify on machines with those browsers |
| Safari | macOS only | safaridriver | implemented, verify on macOS |

Domestic Chromium-based browsers: choose `chromium` and point `binary_path` at the executable:

```yaml
browser:
  type: chromium
  binary_path: "C:\\Program Files (x86)\\360\\360se6\\Application\\360se.exe"   # 360 Secure Browser
  # binary_path: "C:\\Program Files (x86)\\360\\360Chrome\\Chrome\\Application\\360chrome.exe"  # 360 Speed Browser
  driver_path: ""   # recommended: an explicit chromedriver matching the browser's kernel version
```

> 360 kernels often differ from the local Chrome's major version, so an explicit `browser.driver_path` is the safest; you can also try `--browser 360` (normalized to `chromium`) first.

Safari (macOS only): run `safaridriver --enable` once and allow remote automation under *System Settings → Privacy & Security → Developer Tools*; Safari has no headless mode (the flag is ignored with a warning); choosing `safari` on Windows/Linux raises a clear `ConfigError`.

## Non-Bypass Red Lines

The system under test documents scenarios that must not be bypassed; this suite never works around them and only asserts observable results through the allowed UI:

- **X-01 CAPTCHA**: uses the backend universal code `1234`; no OCR.
- **X-02 / C-02 webdriver detection**: only performs the check and asserts the result; no `AutomationControlled` or similar anti-automation feature injection.
- **M-04 popup interception**: keeps the browser's default popup policy to reproduce the interception, then asserts the counter.
- **C-01 date-time picker**: fills and submits via the native control.
- **I-15 offset container**: only "expand the full area, then click", and reads rect / DPR.
- **W-03 export download**: verifies the artifact exists in the browser's download directory.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.

## License

This project is licensed under the [MIT License](LICENSE).
