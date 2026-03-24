"""Tests for transport resolution logic."""

from src.server import _resolve_transport


class TestResolveTransport:
    """Tests for _resolve_transport()."""

    def test_default_is_stdio(self):
        assert _resolve_transport(argv=[], env={}) == "stdio"

    def test_cli_sse_flag(self):
        assert _resolve_transport(argv=["server.py", "--sse"], env={}) == "sse"

    def test_cli_streamable_http_flag(self):
        assert (
            _resolve_transport(argv=["server.py", "--streamable-http"], env={}) == "streamable-http"
        )

    def test_env_var_sse(self):
        assert _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": "sse"}) == "sse"

    def test_env_var_streamable_http(self):
        assert (
            _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": "streamable-http"})
            == "streamable-http"
        )

    def test_env_var_stdio_explicit(self):
        assert _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": "stdio"}) == "stdio"

    def test_env_var_case_insensitive(self):
        assert _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": "SSE"}) == "sse"

    def test_cli_takes_precedence_over_env(self):
        assert (
            _resolve_transport(
                argv=["server.py", "--sse"], env={"TAIGA_TRANSPORT": "streamable-http"}
            )
            == "sse"
        )

    def test_unknown_env_var_falls_back_to_stdio(self):
        assert _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": "websocket"}) == "stdio"

    def test_empty_env_var_falls_back_to_stdio(self):
        assert _resolve_transport(argv=[], env={"TAIGA_TRANSPORT": ""}) == "stdio"

    def test_no_env_var_falls_back_to_stdio(self):
        assert _resolve_transport(argv=[], env={"OTHER_VAR": "value"}) == "stdio"
