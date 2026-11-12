"""Points mcp-app's shipped conformance suite at this app's ``App`` object."""

import pytest

from alerts import app as alerts_app


@pytest.fixture(scope="session")
def app():
    return alerts_app
