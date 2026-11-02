import pytest

from app.services.analysis.languages import detect_language
from app.services.ingestion import file_filter
from app.services.ingestion.secrets import PLACEHOLDER, redact_secrets


class TestFileFilter:
    @pytest.mark.parametrize(
        "path",
        [
            ".env",
            ".env.local",
            ".env.production",
            "config/.env",
            "deploy/server.pem",
            "keys/private.key",
            "id_rsa",
            "home/.ssh/id_ed25519",
            ".npmrc",
            "aws/credentials.json",
            "store.p12",
            "infra/terraform.tfvars",
        ],
    )
    def test_sensitive_files_are_flagged(self, path):
        assert file_filter.skip_reason(path) == file_filter.SENSITIVE

    @pytest.mark.parametrize(
        "path", [".env.example", ".env.sample", ".env.template", "backend/.env.example"]
    )
    def test_env_templates_are_kept(self, path):
        assert file_filter.skip_reason(path) is None

    @pytest.mark.parametrize(
        ("path", "reason"),
        [
            ("logo.png", file_filter.BINARY),
            ("fonts/inter.woff2", file_filter.BINARY),
            ("lib/app.jar", file_filter.BINARY),
            ("package-lock.json", file_filter.LOCKFILE),
            ("poetry.lock", file_filter.LOCKFILE),
            ("uv.lock", file_filter.LOCKFILE),
            ("ios/Podfile.lock", file_filter.LOCKFILE),
            ("static/app.min.js", file_filter.GENERATED),
            ("static/app.js.map", file_filter.GENERATED),
        ],
    )
    def test_non_source_files(self, path, reason):
        assert file_filter.skip_reason(path) == reason

    @pytest.mark.parametrize("path", ["app.py", "src/Main.java", "README.md", "Dockerfile", "a.ts"])
    def test_source_files_are_kept(self, path):
        assert file_filter.skip_reason(path) is None

    @pytest.mark.parametrize(
        "path",
        [
            "node_modules/react/index.js",
            "web/node_modules/x/y.js",
            ".git/config",
            "venv/lib/site.py",
            "dist/bundle.js",
            "build/output.txt",
            "target/classes/A.class",
            "__pycache__/m.cpython-311.pyc",
            ".aws/credentials",
        ],
    )
    def test_ignored_directories(self, path):
        assert file_filter.in_ignored_directory(path) is True

    def test_a_file_named_like_an_ignored_directory_is_not_ignored(self):
        assert file_filter.in_ignored_directory("docs/build") is False
        assert file_filter.in_ignored_directory("src/builder/app.py") is False


class TestRedaction:
    def test_private_key_block_is_removed_and_line_count_is_kept(self):
        key = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\nDEFghi\n-----END RSA PRIVATE KEY-----"
        text = f"a = 1\n{key}\nb = 2\n"

        redacted, count = redact_secrets(text)

        assert count == 1
        assert "MIIabc" not in redacted
        assert redacted.count("\n") == text.count("\n")
        assert redacted.startswith("a = 1\n") and redacted.endswith("\nb = 2\n")

    @pytest.mark.parametrize(
        "secret",
        [
            "AKIAIOSFODNN7EXAMPLE",
            "ghp_" + "a" * 36,
            "github_pat_" + "b" * 60,
            "xoxb-1234567890-abcdefghij",
            "sk_live_" + "c" * 24,
            "AIza" + "d" * 35,
            "sk-" + "e" * 40,
        ],
    )
    def test_known_token_formats(self, secret):
        redacted, count = redact_secrets(f'token = "{secret}"  # do not commit')

        assert secret not in redacted
        assert count >= 1

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ('password = "hunter2hunter2"', f'password = "{PLACEHOLDER}"'),
            ("API_KEY: 'k3y-v4lue-9981'", f"API_KEY: '{PLACEHOLDER}'"),
            ('db_password="s3cr3t-pass"', f'db_password="{PLACEHOLDER}"'),
            ('"client_secret": "abcd1234efgh"', f'"client_secret": "{PLACEHOLDER}"'),
            ('STRIPE_SECRET_KEY = "abcd1234efgh"', f'STRIPE_SECRET_KEY = "{PLACEHOLDER}"'),
        ],
    )
    def test_assigned_secret_values(self, line, expected):
        # Only the value is replaced; the name stays so the code still reads sensibly.
        assert redact_secrets(line) == (expected, 1)

    @pytest.mark.parametrize(
        "line",
        [
            'password = "changeme"',
            'password = "your-password-here"',
            'api_key = "${API_KEY}"',
            'api_key = "<your key>"',
            'secret = "********"',
            "password = os.environ['DB_PASSWORD']",
            'password = "short"',
            "def check_password(password): pass",
        ],
    )
    def test_placeholders_and_code_are_left_alone(self, line):
        assert redact_secrets(line) == (line, 0)

    def test_normal_source_is_untouched(self):
        source = "def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n"

        assert redact_secrets(source) == (source, 0)


class TestLanguages:
    @pytest.mark.parametrize(
        ("path", "language"),
        [
            ("app.py", "Python"),
            ("src/index.js", "JavaScript"),
            ("src/App.tsx", "TypeScript"),
            ("src/Main.java", "Java"),
            ("Dockerfile", "Dockerfile"),
            ("docs/README.MD", "Markdown"),
            ("noextension", None),
            ("weird.xyz", None),
        ],
    )
    def test_detect_language(self, path, language):
        assert detect_language(path) == language
