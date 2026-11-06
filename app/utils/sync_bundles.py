"""Cloudflare R2 / AWS S3 Static Web Bundle Synchronizer.

Uploads self-contained game bundles from /public/games/ to Cloudflare R2 / AWS S3
matching the Poki / Platform Architecture:
  In DB: Game.play_url = 'https://cdn.pixora.com/games/neon-racer/index.html'
"""
import os
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import create_app  # noqa: E402
from app.utils.storage import r2_storage  # noqa: E402


def sync_all_bundles(dry_run=False):
    """Sync static game web bundles from /public/games/ to Cloudflare R2 Edge / AWS S3."""
    app = create_app('development')
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    public_games_dir = os.path.join(base_dir, 'public', 'games')

    if not os.path.exists(public_games_dir):
        print(f"Error: Public games directory not found at {public_games_dir}")
        return False

    with app.app_context():
        r2_ready = r2_storage.is_configured
        bucket = app.config.get('CLOUDFLARE_R2_BUCKET_NAME')
        public_url = app.config.get('CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev')

        print("\n" + "=" * 65)
        print("🚀 PIXORA PLATFORM // CLOUDFLARE R2 BUNDLE SYNCHRONIZER")
        print("=" * 65)
        print(f"Local Bundle Root:    {public_games_dir}")
        print(f"R2 Status:            {'🟢 Connected' if r2_ready else '🟡 Offline / Local-only'}")
        print(f"Target Bucket:        {bucket}")
        print("Production CDN Base:  https://cdn.pixora.com/games/")
        print(f"R2 Edge Base:         {public_url}/games/")
        print("=" * 65 + "\n")

        bundles = [d for d in os.listdir(public_games_dir) if os.path.isdir(os.path.join(public_games_dir, d))]
        bundles.sort()

        uploaded_count = 0
        for slug in bundles:
            game_dir = os.path.join(public_games_dir, slug)
            index_path = os.path.join(game_dir, 'index.html')
            has_index = os.path.isfile(index_path)
            file_count = len(os.listdir(game_dir))

            if not has_index:
                print(f"⚠️  [SKIP] '{slug}' is missing index.html")
                continue

            r2_prefix = f"games/{slug}"
            print(f"📦 Packaging '{slug}' ({file_count} files) -> {r2_prefix}/")

            if r2_ready and not dry_run:
                try:
                    res = r2_storage.upload_directory(game_dir, r2_prefix)
                    print(f"   ✓ Synced to CDN: {public_url}/{r2_prefix}/index.html ({len(res)} files)")
                    uploaded_count += 1
                except Exception as e:
                    print(f"   ✗ Upload error: {e}")
            else:
                mode_str = "DRY-RUN" if dry_run else "LOCAL BUNDLE READY"
                print(f"   ✓ [{mode_str}] Bundle verified: /public/games/{slug}/index.html")
                uploaded_count += 1

        print("\n" + "=" * 65)
        print(f"Synchronization complete: {uploaded_count}/{len(bundles)} bundles processed successfully.")
        print("=" * 65 + "\n")
        return True


if __name__ == '__main__':
    is_dry = '--dry-run' in sys.argv
    sync_all_bundles(dry_run=is_dry)
