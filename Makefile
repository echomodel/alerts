.PHONY: venv test framework-test install uninstall clean help

# Create the venv with the package installed editable (once).
venv:
	@if [ ! -d ".venv" ]; then \
		python3 -m venv .venv && \
		. .venv/bin/activate && pip install --upgrade pip && pip install -e '.[dev]'; \
	fi

# Unit tests and the mcp-app framework suite; no credentials, no network.
test: venv
	@. .venv/bin/activate && pytest

# Install alerts-mcp and alerts-admin with pipx, editable, for local use.
install:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx not found; install with: pip install pipx"; exit 1)
	@pipx install -e . --force
	@echo "Installed: alerts-mcp, alerts-admin"

uninstall:
	pipx uninstall alerts 2>/dev/null || true

clean:
	rm -rf .venv build/ dist/ *.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help:
	@echo "  test       - unit + framework tests (creates .venv on first run)"
	@echo "  install    - pipx install -e . (alerts-mcp, alerts-admin)"
	@echo "  uninstall  - remove the pipx install"
	@echo "  clean      - remove venv and build artifacts"
