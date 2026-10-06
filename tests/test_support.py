"""Redirect module-level application initialization away from user data."""
import atexit
import os
import tempfile

bootstrap = tempfile.TemporaryDirectory(prefix='mosaic-test-bootstrap-')
os.environ.setdefault('APP_DATA_DIR', bootstrap.name)
atexit.register(bootstrap.cleanup)
