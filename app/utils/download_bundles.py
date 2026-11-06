"""Cloudflare R2 / CDN Game Bundle Downloader.

Allows production containers or build pipelines to fetch game bundles and heavy
binary assets from Cloudflare R2 or CDN rather than storing them in Git repository.
"""
import os
import sys
import urllib.request
import urllib.error

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app.config import settings  # noqa: E402
from app.utils.seed_games import CATALOG_GAMES  # noqa: E402


def download_bundle_if_missing(game_slug: str, cdn_base_url: str = None) -> bool:
    """Download game bundle index and assets from CDN if not already cached locally."""
    cdn_base = cdn_base_url or getattr(settings, 'CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev')
    local_dir = os.path.join(base_dir, 'public', 'games', game_slug)
    os.makedirs(local_dir, exist_ok=True)

    index_file = os.path.join(local_dir, 'index.html')
    if os.path.isfile(index_file) and os.path.getsize(index_file) > 0:
        return True

    remote_url = f"{cdn_base.rstrip('/')}/games/{game_slug}/index.html"
    try:
        urllib.request.urlretrieve(remote_url, index_file)
        print(f"✓ Downloaded '{game_slug}' bundle from CDN: {remote_url}")
        return True
    except Exception as e:
        print(f"⚠️ Could not pull '{game_slug}' from CDN: {e}")
        return False


def download_all_missing_bundles():
    """Fetch all catalog game bundles from CDN if missing."""
    print("🚀 Verifying / Fetching remote CDN game bundles...")
    success = 0
    for game in CATALOG_GAMES:
        slug = game['slug']
        if download_bundle_if_missing(slug):
            success += 1
    print(f"Bundle fetch complete: {success}/{len(CATALOG_GAMES)} games ready.")
    return success


if __name__ == '__main__':
    download_all_missing_bundles()
