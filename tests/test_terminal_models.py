import pytest
from pydantic import ValidationError


class TestWSMessageModels:
    def test_input_message_valid(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="input", session_id="abc123", data="ls -la\n")
        assert msg.type == "input"
        assert msg.session_id == "abc123"
        assert msg.data == "ls -la\n"

    def test_input_message_requires_data(self):
        from stratus.terminal.models import WSMessage

        with pytest.raises(ValidationError):
            WSMessage(type="input", session_id="abc123")

    def test_resize_message_valid(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="resize", session_id="abc123", cols=120, rows=40)
        assert msg.type == "resize"
        assert msg.cols == 120
        assert msg.rows == 40

    def test_resize_message_requires_cols_rows(self):
        from stratus.terminal.models import WSMessage

        with pytest.raises(ValidationError):
            WSMessage(type="resize", session_id="abc123")

    def test_create_message_valid(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="create", cols=80, rows=24)
        assert msg.type == "create"
        assert msg.cols == 80
        assert msg.rows == 24

    def test_create_message_defaults(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="create")
        assert msg.cols == 80
        assert msg.rows == 24

    def test_create_message_custom_cwd(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="create", cols=120, rows=30, cwd="/home/user/project")
        assert msg.cwd == "/home/user/project"

    def test_ping_message_valid(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="ping")
        assert msg.type == "ping"

    def test_invalid_type_rejected(self):
        from stratus.terminal.models import WSMessage

        with pytest.raises(ValidationError):
            WSMessage(type="invalid_type")

    def test_session_id_optional_for_create(self):
        from stratus.terminal.models import WSMessage

        msg = WSMessage(type="create")
        assert msg.session_id is None


class TestWSServerMessage:
    def test_created_message(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(
            type="created", session_id="abc123", shell="/bin/bash", cwd="/home/user"
        )
        assert msg.type == "created"
        assert msg.session_id == "abc123"
        assert msg.shell == "/bin/bash"
        assert msg.cwd == "/home/user"

    def test_output_message(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(type="output", session_id="abc123", data="Hello World\n")
        assert msg.type == "output"
        assert msg.data == "Hello World\n"

    def test_exit_message(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(type="exit", session_id="abc123", code=0)
        assert msg.type == "exit"
        assert msg.code == 0

    def test_error_message(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(type="error", message="Session not found", code=404)
        assert msg.type == "error"
        assert msg.message == "Session not found"
        assert msg.code == 404

    def test_error_message_defaults_code(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(type="error", message="Unknown error")
        assert msg.code == 500

    def test_pong_message(self):
        from stratus.terminal.models import WSServerMessage

        msg = WSServerMessage(type="pong")
        assert msg.type == "pong"


class TestTerminalSession:
    def test_terminal_session_creation(self):
        from stratus.terminal.models import TerminalSession

        session = TerminalSession(
            id="abc123",
            pid=12345,
            master_fd=10,
            cols=120,
            rows=40,
            shell="/bin/bash",
            cwd="/home/user",
        )
        assert session.id == "abc123"
        assert session.pid == 12345
        assert session.master_fd == 10
        assert session.cols == 120
        assert session.rows == 40
        assert session.shell == "/bin/bash"
        assert session.cwd == "/home/user"

    def test_terminal_session_defaults(self):
        from stratus.terminal.models import TerminalSession

        session = TerminalSession(
            id="abc123",
            pid=12345,
            master_fd=10,
            cols=80,
            rows=24,
            shell="/bin/bash",
            cwd="/home/user",
        )
        assert session.active is True
        assert session.created_at is not None
