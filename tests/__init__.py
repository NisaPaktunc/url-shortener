"""Tests package.

This file runs before any test or app code is imported. The app refuses to
start without a SECRET_KEY, so we give it a fixed key made for tests.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-tests-0123456789")
