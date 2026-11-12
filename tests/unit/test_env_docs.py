"""Every environment variable the server reads is documented in the README table.

The README's "Environment variables" table is the configuration contract.
This test collects the variable names the app and mcp-app read and fails
when one is missing from the table, so a new variable cannot ship
undocumented.
"""

import pathlib
import re

import mcp_app.auth
import mcp_app.usage
from alerts.sdk import channels

README = pathlib.Path(__file__).resolve().parents[2] / "README.md"

# Read by mcp-app through os.environ.get with a literal name rather than a constant.
FRAMEWORK_LITERALS = {"APP_USERS_PATH", "REQUIRED_FS_TYPE", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}


def _env_constants(*modules) -> set[str]:
    names = set()
    for module in modules:
        for attr, value in vars(module).items():
            if attr.startswith("ENV_") and isinstance(value, str):
                names.add(value)
    return names


def _table_variables() -> set[str]:
    text = README.read_text()
    section = text.split("## Environment variables", 1)[1].split("### Variable reference", 1)[0]
    return set(re.findall(r"^\| `([A-Z_]+)` \|", section, flags=re.M))


def test_every_variable_read_is_in_the_readme_table():
    read = _env_constants(mcp_app.auth, mcp_app.usage, channels) | FRAMEWORK_LITERALS
    missing = sorted(read - _table_variables())
    assert not missing, f"Add to README 'Environment variables': {missing}"


def test_every_table_variable_has_a_reference_entry():
    text = README.read_text()
    reference = text.split("### Variable reference", 1)[1]
    undocumented = sorted(v for v in _table_variables() if f"`{v}`" not in reference)
    assert not undocumented, f"Add a reference entry for: {undocumented}"
