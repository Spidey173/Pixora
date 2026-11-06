"""Asset Migration Tool: Offload .mp3 and .png files to Cloudflare R2 / S3.

Scans the repository for game audio (.mp3) and image/spritesheet (.png) files,
uploads them to Cloudflare R2 / AWS S3 edge storage under the 'assets/' prefix,
and generates CDN URL resolution mappings.
"""
import mimetypes
import os
import sys

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

from app.config import settings  # noqa: E402
from app.utils.storage import r2_storage  # noqa: E402


def migrate_all_media_assets(dry_run=False):
    """Scan and migrate .mp3 and .png assets to Cloudflare R2 edge storage."""
    cdn_base = getattr(settings, 'CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev').rstrip('/')
    bucket = getattr(settings, 'CLOUDFLARE_R2_BUCKET_NAME', 'glitch4ce-games')

    search_roots = [
        os.path.join(basedir, 'static', 'Games'),
        os.path.join(basedir, 'public', 'games')
    ]

    print("\n" + "=" * 65)
    print("🚀 PIXORA PLATFORM: CLOUDFLARE R2 / S3 MEDIA ASSET OFFLOADER")
    print("=" * 65)
    print(f"Target Bucket:     {bucket}")
    print(f"Edge CDN Base URL: {cdn_base}")
    print(f"R2 Direct Upload:  {'🟢 Ready (boto3 s3_client)' if r2_storage.is_ready() else '🟡 CDN Mapping Mode'}")
    print(f"Execution Mode:    {'DRY-RUN' if dry_run else 'ACTIVE MIGRATION'}")
    print("=" * 65 + "\n")

    discovered_files = []
    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        for root, _, files in os.walk(root_dir):
            for file in files:
                lower = file.lower()
                if lower.endswith(('.mp3', '.png', '.wav', '.ogg')):
                    full_path = os.path.join(root, file)
                    rel_to_repo = os.path.relpath(full_path, basedir)
                    discovered_files.append((full_path, rel_to_repo, file))

    print(f"Found {len(discovered_files)} binary media files across static and public bundles.\n")

    uploaded = {}
    for full_path, rel_path, file in discovered_files:
        is_audio = file.lower().endswith(('.mp3', '.wav', '.ogg'))
        category = 'audio' if is_audio else 'images'

        # Canonical key on R2
        r2_key = f"assets/{category}/{rel_path.replace(os.sep, '/')}"
        cdn_url = f"{cdn_base}/{r2_key}"
        content_type, _ = mimetypes.guess_type(full_path)
        content_type = content_type or ('audio/mpeg' if is_audio else 'image/png')

        if r2_storage.is_ready() and not dry_run:
            try:
                res_url = r2_storage.upload_file(full_path, r2_key, content_type=content_type)
                print(f"  ✓ Uploaded: {rel_path} -> {res_url}")
                uploaded[rel_path] = res_url
            except Exception as e:
                print(f"  ✗ Failed: {rel_path}: {e}")
        else:
            print(f"  ✓ [Mapped]: {rel_path} -> {cdn_url}")
            uploaded[rel_path] = cdn_url

    print("\n" + "=" * 65)
    print(f"Asset Offload Complete: {len(uploaded)}/{len(discovered_files)} media files mapped to R2 CDN.")
    print("=" * 65 + "\n")
    return uploaded


if __name__ == '__main__':
    is_dry = '--dry-run' in sys.argv
    migrate_all_media_assets(dry_run=is_dry)

