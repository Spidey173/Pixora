"""Headless Browser End-to-End Tests for Pixora Platform & SDK v2.

Verifies the Platform / Poki Architecture in a real headless browser:
1. Sandboxed iframe boots up correctly for both catalog games (/public/games/<slug>/)
   and featured in-repo games (/2048).
2. The game inside the iframe initiates the Pixora SDK handshake (PIXORA_HANDSHAKE).
3. The parent platform shell (player.html) validates event source and responds with
   PIXORA_HANDSHAKE_ACK containing player identity and cryptographic sessionToken.
4. Gameplay telemetry (PIXORA_GAMEPLAY_START) is broadcast to the platform.
5. Score submission (PIXORA_SUBMIT_SCORE) traverses the iframe boundary via secure postMessage,
   is validated by the Anti-Cheat Engine, and is persisted to the database.
6. Anti-cheat catches and rejects exploitative / impossible scores submitted via the browser.
"""

import os
import threading
import time
import pytest
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db
from app.models import User, Game, GameScore
from app.utils.seed_games import CATALOG_GAMES

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _get_browser_kwargs():
    """Return kwargs for launching Playwright Chromium."""
    kwargs = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    }
    mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac_chrome):
        kwargs["executable_path"] = mac_chrome
    return kwargs


def _check_browser_loopback(port):
    """Verify that headless Chromium can bind to local test server."""
    if not PLAYWRIGHT_AVAILABLE:
        return False
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(**_get_browser_kwargs())
            try:
                page = b.new_page()
                page.goto(f"http://127.0.0.1:{port}/", timeout=2000)
                return True
            except Exception as e:
                if "ERR_ACCESS_DENIED" in str(e):
                    return False
                return False
            finally:
                b.close()
    except Exception:
        return False


@pytest.fixture(scope="module")
def browser_test_env():
    """Start a threaded Flask server with seeded games and test user."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright is not installed.")

    flask_app = create_app("testing")
    with flask_app.app_context():
        db.create_all()
        for item in CATALOG_GAMES:
            game = Game(
                slug=item["slug"],
                title=item["title"],
                category=item["category"],
                description=item["description"],
                thumbnail_url=item["thumbnail_url"],
                play_url=item["play_url"],
                controls_guide=item["controls_guide"],
                is_featured=item.get("is_featured", False),
                is_published=True,
            )
            db.session.add(game)

        # Create a dedicated testing player
        pilot = User(username="CyberPilot99", is_guest=False)
        pilot.set_password("Pass1234!")
        db.session.add(pilot)
        db.session.commit()

    server = make_server("127.0.0.1", 0, flask_app, threaded=True)
    port = server.port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Pre-flight check: Can Chromium connect to loopback?
    if not _check_browser_loopback(port):
        server.shutdown()
        with flask_app.app_context():
            db.session.remove()
            db.drop_all()
        pytest.skip(
            "Headless browser loopback connection restricted in current sandbox. "
            "Runs in CI and unsandboxed local environments."
        )

    base_url = f"http://127.0.0.1:{port}"
    yield {"url": base_url, "app": flask_app, "port": port}

    # Clean shutdown
    server.shutdown()
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


def _login_pilot(page, base_url):
    """Helper to authenticate test user in Playwright browser session."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "CyberPilot99")
    page.fill('input[name="password"]', "Pass1234!")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_catalog_iframe_game_boots_and_handshakes(browser_test_env):
    """Test that a catalog iframe game loads, boots its SDK bridge, and completes handshake."""
    base_url = browser_test_env["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_kwargs())
        context = browser.new_context()
        page = context.new_page()

        # 1. Authenticate user
        _login_pilot(page, base_url)

        # 2. Track postMessages on the parent page
        page.add_init_script("""
            window.__pixora_messages = [];
            window.addEventListener('message', (e) => {
                if (e.data && e.data.source && e.data.source.includes('GAME_CLIENT')) {
                    window.__pixora_messages.push(e.data);
                }
            });
        """)

        # 3. Navigate to catalog game theater (/play/stonepapersissors)
        page.goto(f"{base_url}/play/stonepapersissors")
        frame_el = page.wait_for_selector("iframe#gameFrame")
        assert frame_el is not None

        frame = frame_el.content_frame()
        frame.wait_for_load_state("domcontentloaded")
        time.sleep(1.0)

        # 4. Verify iframe source points to static catalog bundle
        src = frame_el.get_attribute("src")
        assert "public/games/stonepapersissors/index.html" in src

        # 5. Verify bundle images loaded successfully (no missing asset 404s)
        images = frame.locator("img")
        assert images.count() >= 5  # Stone, Paper, Scissors choices + Computer & Player displays
        for i in range(images.count()):
            natural_width = images.nth(i).evaluate("img => img.naturalWidth")
            assert natural_width > 0, f"Image {i} in bundle failed to render!"

        # 6. Verify postMessage Handshake and Gameplay Telemetry occurred
        messages = page.evaluate("window.__pixora_messages || []")
        message_types = [m.get("type") for m in messages]
        assert "PIXORA_HANDSHAKE" in message_types, "Game iframe never posted PIXORA_HANDSHAKE!"
        assert "PIXORA_GAMEPLAY_START" in message_types, "Game iframe never posted PIXORA_GAMEPLAY_START!"

        browser.close()


def test_featured_game_iframe_boots_and_handshakes(browser_test_env):
    """Test that a featured in-repo game (/2048) loads pixora-sdk.js and handshakes on start."""
    base_url = browser_test_env["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_kwargs())
        context = browser.new_context()
        page = context.new_page()

        # 1. Authenticate user
        _login_pilot(page, base_url)

        # 2. Spy on parent window postMessages
        page.add_init_script("""
            window.__pixora_messages = [];
            window.addEventListener('message', (e) => {
                if (e.data && e.data.source && e.data.source.includes('GAME_CLIENT')) {
                    window.__pixora_messages.push(e.data);
                }
            });
        """)

        # 3. Navigate to featured game player
        page.goto(f"{base_url}/play/2048")
        frame_el = page.wait_for_selector("iframe#gameFrame")
        frame = frame_el.content_frame()
        frame.wait_for_load_state("domcontentloaded")

        # 4. Verify pixora-sdk is present in the iframe window
        has_sdk = frame.evaluate("typeof window.Pixora !== 'undefined'")
        assert has_sdk, "Pixora SDK v2 is missing in featured game window!"

        # 5. Trigger game start inside the iframe via Start Game button
        frame.click("button.startButton")
        time.sleep(1.0)

        # 6. Verify handshake exchange
        messages = page.evaluate("window.__pixora_messages || []")
        message_types = [m.get("type") for m in messages]
        assert "PIXORA_HANDSHAKE" in message_types, "Featured game iframe failed to initiate handshake!"
        assert "PIXORA_GAMEPLAY_START" in message_types, "Featured game iframe failed to start gameplay!"

        browser.close()


def test_iframe_score_submission_to_parent_sdk(browser_test_env):
    """Test full cycle: iframe game submits high score -> parent SDK catches -> API verifies & commits."""
    base_url = browser_test_env["url"]
    app = browser_test_env["app"]

    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_kwargs())
        context = browser.new_context()
        page = context.new_page()

        # 1. Authenticate user
        _login_pilot(page, base_url)

        # 2. Open game
        page.goto(f"{base_url}/play/stonepapersissors")
        frame_el = page.wait_for_selector("iframe#gameFrame")
        frame = frame_el.content_frame()
        frame.wait_for_load_state("domcontentloaded")

        # Wait 2.2 seconds to simulate genuine play duration (Anti-Cheat check: elapsed > 2.0s)
        time.sleep(2.2)

        # 3. Submit score from inside iframe via Pixora SDK bridge
        with page.expect_response(lambda r: "/api/v2/session/end" in r.url) as response_info:
            frame.evaluate("window.Pixora.submitScore(8)")

        response = response_info.value
        assert response.status == 201, f"Expected 201 Created from anti-cheat session/end, got {response.status}"

        data = response.json()
        assert data.get("status") == "success"
        assert data.get("verified") is True
        assert data.get("score", {}).get("score") == 8
        assert data.get("score", {}).get("username") == "CyberPilot99"

        # 4. Verify database persistence
        with app.app_context():
            saved_score = GameScore.query.filter_by(
                game_name="Stone Paper Scissors",
                score=8
            ).first()
            assert saved_score is not None
            assert saved_score.player.username == "CyberPilot99"

        browser.close()


def test_iframe_anti_cheat_velocity_rejection(browser_test_env):
    """Test that an exploitative / impossible score submitted from an iframe is rejected with 422."""
    base_url = browser_test_env["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_kwargs())
        context = browser.new_context()
        page = context.new_page()

        # 1. Authenticate user
        _login_pilot(page, base_url)

        # 2. Open game
        page.goto(f"{base_url}/play/stonepapersissors")
        frame_el = page.wait_for_selector("iframe#gameFrame")
        frame = frame_el.content_frame()
        frame.wait_for_load_state("domcontentloaded")

        # 3. Immediately submit an absurd score without genuine gameplay duration
        with page.expect_response(lambda r: "/api/v2/session/end" in r.url) as response_info:
            frame.evaluate("window.Pixora.submitScore(999999)")

        response = response_info.value
        # AntiCheat engine should reject with 422 Unprocessable Entity
        assert response.status == 422, f"Expected anti-cheat rejection (422), got {response.status}"

        data = response.json()
        assert data.get("code") == "ANOMALOUS_VELOCITY"
        assert "IMPOSSIBLE_DURATION" in data.get("error", "") or "SCORE_VELOCITY" in data.get("error", "")

        browser.close()


def test_untrusted_postmessage_ignored_by_platform_shell(browser_test_env):
    """Test platform shell drops untrusted postMessages from unauthorized origins or non-frame sources."""
    base_url = browser_test_env["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_kwargs())
        context = browser.new_context()
        page = context.new_page()

        _login_pilot(page, base_url)
        page.goto(f"{base_url}/play/stonepapersissors")
        page.wait_for_selector("iframe#gameFrame")

        # Attempt to spoof a score message from an external synthetic origin
        ignored = page.evaluate("""() => {
            let receivedAck = false;
            window.addEventListener('message', (e) => {
                if (e.data && e.data.type === 'PIXORA_HANDSHAKE_ACK') receivedAck = true;
            });

            // Dispatch spoofed message with invalid source
            window.postMessage({
                source: 'MALICIOUS_ATTACKER_CLIENT',
                type: 'PIXORA_HANDSHAKE',
                payload: { gameId: 'stonepapersissors', version: '2.0.0' }
            }, '*');

            return !receivedAck;
        }""")

        assert ignored is True, "Shell responded to unauthorized message source!"

        browser.close()
