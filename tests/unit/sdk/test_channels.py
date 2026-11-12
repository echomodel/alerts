"""Channel configuration: parsing, sources, and what is (never) exposed."""

from alerts.sdk import channels


def test_parse_names_and_urls():
    defs = channels.parse(
        "# a comment\n"
        "\n"
        "phone = capture://a/\n"
        "work, phone = capture://b/\n"
        "capture://unnamed/\n"
    )
    assert [(d.names, d.url, d.line) for d in defs] == [
        (["phone"], "capture://a/", 3),
        (["work", "phone"], "capture://b/", 4),
        ([], "capture://unnamed/", 5),
    ]


def test_build_groups_destinations_by_channel():
    built = channels.build("phone = capture://a/\nwork, phone = capture://b/\ncapture://x/\n")
    assert built.names() == ["phone", "work"]
    assert len(built.servers["phone"]) == 2
    assert len(built.servers["work"]) == 1
    assert built.unnamed == 1
    assert built.invalid == {}


def test_build_reports_invalid_lines_by_name_only():
    built = channels.build("bad = nosuchscheme://x\nok = capture://a/")
    assert built.names() == ["ok"]
    assert built.invalid == {"bad": [1]}


def test_slack_webhook_url_is_accepted_as_pasted():
    url = "https://hooks.slack.com/services/T00000000/B00000000/" + "x" * 24
    built = channels.build(f"claude = {url}")
    assert built.services("claude") == ["Slack"]


def test_services_never_include_urls():
    secret = "supersecrettopic"
    built = channels.build(f"phone = ntfys://ntfy.sh/{secret}")
    assert built.services("phone") == ["ntfy"]
    assert secret not in repr(built.services("phone"))


def test_env_wins_over_file(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = channels.config_path()
    path.parent.mkdir(parents=True)
    path.write_text("file = capture://f/\n")
    monkeypatch.delenv("ALERTS_CHANNELS", raising=False)
    text, source = channels.load_text()
    assert source == str(path) and "file" in text
    monkeypatch.setenv("ALERTS_CHANNELS", "env = capture://e/\n")
    text, source = channels.load_text()
    assert source == "env" and "env" in text


def test_unconfigured_is_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ALERTS_CHANNELS", raising=False)
    assert channels.load_text() is None
    assert channels.load() is None


def test_channel_types_carry_docs_and_are_one_way():
    types = channels.channel_types()
    by_type = {t["type"]: t for t in types}
    assert {"slack-webhook", "ntfy", "email"} <= set(by_type)
    for t in types:
        assert t["receives_replies"] is False
        assert t["apprise_docs"], t["type"]
        assert t["url_form"]
    assert "ntfys" in by_type["ntfy"]["schemes"]
