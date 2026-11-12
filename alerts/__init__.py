"""alerts: an MCP server that lets agents push a notification to a person.

One ``App`` object is the whole server (mcp-app). The tool surface is in
``alerts.mcp.tools``; every behaviour is in ``alerts.sdk``.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

try:
    # Derived from the git tag at build time (setuptools-scm); see CONTRIBUTING "Releases".
    __version__ = _dist_version("alerts")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from mcp_app import App

import alerts as _self
from alerts.mcp import tools

app = App(
    name="alerts",
    tools_module=tools,
    sdk_package=_self,
)

__all__ = ["app", "__version__"]
