import hashlib
import os
import re
import tempfile
from pathlib import Path

from tender.config import Settings


class ObjectStore:
    """Immutable, content-addressed objects; artifacts share the same integrity contract."""

    def __init__(self, settings: Settings):
        self.root = settings.data_dir / "objects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.bucket = settings.s3_bucket
        self.client = None
        if settings.object_backend == "s3":
            import boto3

            self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url)

    def put(self, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        key = f"sha256/{digest[:2]}/{digest}"
        if self.client:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content, Metadata={"sha256": digest})
        else:
            path = self.root / key
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(content)
                    os.replace(tmp, path)
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
        return key

    def get(self, key: str) -> bytes:
        if not re.fullmatch(r"sha256/[a-f0-9]{2}/[a-f0-9]{64}", key):
            raise ValueError("Invalid object reference")
        if self.client:
            content = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        else:
            content = (self.root / key).read_bytes()
        if hashlib.sha256(content).hexdigest() != Path(key).name:
            raise ValueError("Stored object failed its integrity check")
        return content
