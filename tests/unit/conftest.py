"""The ``app`` fixture mcp-app's HTTP test fixtures (``oauth_env``) expect."""

import pytest

from alerts import app as alerts_app


@pytest.fixture(scope="session")
def app():
    return alerts_app
