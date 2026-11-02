import pytest

from app.services.ingestion.errors import InvalidRepositoryUrl
from app.services.ingestion.github_url import parse_github_url


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/pallets/flask",
        "https://github.com/pallets/flask/",
        "https://github.com/pallets/flask.git",
        "http://github.com/pallets/flask",
        "https://www.github.com/pallets/flask",
        "HTTPS://GITHUB.COM/pallets/flask",
        "github.com/pallets/flask",
        "  https://github.com/pallets/flask  ",
        "https://github.com/pallets/flask/tree/main/src",
        "https://github.com/pallets/flask/blob/main/README.md#L10",
        "https://github.com/pallets/flask?tab=readme-ov-file",
    ],
)
def test_accepts_github_repository_urls(raw):
    ref = parse_github_url(raw)

    assert (ref.owner, ref.name) == ("pallets", "flask")
    assert ref.url == "https://github.com/pallets/flask"


def test_key_ignores_case_so_duplicates_are_detected():
    assert parse_github_url("https://github.com/Pallets/Flask").key == "github:pallets/flask"
    assert parse_github_url("https://github.com/pallets/FLASK").key == "github:pallets/flask"


def test_allows_dots_underscores_and_hyphens_in_repository_names():
    assert parse_github_url("https://github.com/user-1/my_repo.js").name == "my_repo.js"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "flask",
        "pallets/flask",
        "https://github.com",
        "https://github.com/pallets",
        # other hosts, including look-alikes
        "https://gitlab.com/pallets/flask",
        "https://github.com.evil.com/pallets/flask",
        "https://evilgithub.com/pallets/flask",
        "https://evil.com/github.com/pallets/flask",
        "https://evil.com/?u=https://github.com/pallets/flask",
        "https://api.github.com/repos/pallets/flask",
        "https://raw.githubusercontent.com/pallets/flask/main/x.py",
        # internal and special addresses
        "http://localhost/pallets/flask",
        "http://127.0.0.1/pallets/flask",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/pallets/flask",
        # credentials, ports, other schemes
        "https://user:pass@github.com/pallets/flask",
        "https://pallets@github.com/pallets/flask",
        "https://github.com:8080/pallets/flask",
        "https://github.com:badport/pallets/flask",
        "ftp://github.com/pallets/flask",
        "file:///etc/passwd",
        "javascript:alert(1)",
        # malformed names
        "https://github.com/-bad/flask",
        "https://github.com/bad-/flask",
        "https://github.com/pal lets/flask",
        "https://github.com/pallets/fla sk",
        "https://github.com/pallets/..",
        "https://github.com/pallets/.",
        "https://github.com/pallets/%2e%2e",
        "https://github.com/pallets/flask%00",
        "https://github.com/pall;ets/flask",
        "https://github.com/" + "a" * 40 + "/flask",
        "https://github.com/pallets/" + "r" * 101,
        "https://github.com/pallets/flask/" + "x" * 400,
    ],
)
def test_rejects_everything_else(raw):
    with pytest.raises(InvalidRepositoryUrl):
        parse_github_url(raw)
