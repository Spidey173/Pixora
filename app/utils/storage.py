"""Cloudflare R2 Object Storage Manager for Pixora Games."""
import logging
import mimetypes
import os

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    Config = None
    ClientError = Exception
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class CloudflareR2Storage:
    """Handles uploading, syncing, and listing game assets on Cloudflare R2."""

    def __init__(self, app=None):
        self.s3_client = None
        self.bucket_name = None
        self.public_url = None
        self.enabled = False

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize R2 client with Flask application config."""
        self.enabled = app.config.get('CLOUDFLARE_R2_ENABLED', False)
        self.bucket_name = app.config.get('CLOUDFLARE_R2_BUCKET_NAME')
        self.public_url = (app.config.get('CLOUDFLARE_R2_PUBLIC_URL') or '').rstrip('/')
        endpoint_url = app.config.get('CLOUDFLARE_R2_ENDPOINT_URL')
        access_key = app.config.get('CLOUDFLARE_R2_ACCESS_KEY_ID')
        secret_key = app.config.get('CLOUDFLARE_R2_SECRET_ACCESS_KEY')

        if not BOTO3_AVAILABLE or not self.enabled or not (endpoint_url and access_key and secret_key):
            logger.info("Cloudflare R2 is disabled or boto3 not available; running in local fallback mode.")
            return

        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name='auto',
                config=Config(s3={'addressing_style': 'path'})
            )
            logger.info("Cloudflare R2 Storage client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare R2 client: {e}")
            self.s3_client = None

    def is_ready(self) -> bool:
        """Check if R2 is configured and ready."""
        return bool(self.enabled and self.s3_client and self.bucket_name)

    @property
    def is_configured(self) -> bool:
        """Check if R2 is configured and ready."""
        return self.is_ready()

    def upload_file(self, local_path: str, r2_key: str, content_type: str | None = None) -> str | None:
        """Upload a single file to Cloudflare R2 and return its public CDN URL."""
        if not self.is_ready():
            return None

        if not content_type:
            content_type, _ = mimetypes.guess_type(local_path)
            content_type = content_type or 'application/octet-stream'

        try:
            with open(local_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=r2_key,
                    Body=f,
                    ContentType=content_type
                )
            return f"{self.public_url}/{r2_key}"
        except ClientError as e:
            logger.error(f"Error uploading {local_path} to R2: {e}")
            return None

    def upload_directory(self, local_dir: str, r2_prefix: str) -> dict[str, str]:
        """
        Upload an entire game directory (assets, index.html, scripts) to Cloudflare R2.
        Returns a dictionary mapping relative paths to public CDN URLs.
        """
        if not self.is_ready():
            return {}

        uploaded = {}
        r2_prefix = r2_prefix.strip('/')

        for root, _, files in os.walk(local_dir):
            for file in files:
                if file.startswith('.'):
                    continue  # skip .DS_Store etc.
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, local_dir)
                r2_key = f"{r2_prefix}/{rel_path}".replace('\\', '/')

                content_type, _ = mimetypes.guess_type(full_path)
                if file.endswith('.wasm'):
                    content_type = 'application/wasm'
                elif file.endswith('.js'):
                    content_type = 'application/javascript'
                elif file.endswith('.css'):
                    content_type = 'text/css'
                elif file.endswith('.html'):
                    content_type = 'text/html'
                
                url = self.upload_file(full_path, r2_key, content_type=content_type)
                if url:
                    uploaded[rel_path] = url

        return uploaded

    def get_public_url(self, r2_key: str) -> str:
        """Get public CDN URL for a given object key."""
        r2_key = r2_key.lstrip('/')
        return f"{self.public_url}/{r2_key}"


# Global instance
r2_storage = CloudflareR2Storage()
