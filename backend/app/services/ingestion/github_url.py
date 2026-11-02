"""Turn whatever a user pasted into a validated GitHub owner/repo pair.

The user's URL is never requested. We only extract two strictly validated names from
it and build our own API URL from them, which is what prevents SSRF here.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.services.ingestion.errors import InvalidRepositoryUrl

ALLOWED_HOSTS = {"github.com", "www.github.com"}

# GitHub usernames: letters, digits and single hyphens, up to 39 characters.
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
# Repository names: letters, digits, dot, underscore, hyphen, up to 100 characters.
_REPO = re.compile(r"[A-Za-z0-9._-]{1,100}")

MESSAGE = "Enter a public GitHub repository URL, such as https://github.com/owner/repo"


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def key(self) -> str:
        """Identity used to detect duplicates. GitHub ignores case in names."""
        return f"github:{self.owner.lower()}/{self.name.lower()}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_github_url(raw: str) -> RepoRef:
    text = raw.strip()
    if not text or len(text) > 300:
        raise InvalidRepositoryUrl(MESSAGE)

    # People often paste "github.com/owner/repo" without the scheme.
    if "://" not in text and text.lower().startswith(("github.com/", "www.github.com/")):
        text = f"https://{text}"

    try:
        parts = urlsplit(text)
        port = parts.port  # raises ValueError for a malformed port
    except ValueError:
        raise InvalidRepositoryUrl(MESSAGE) from None

    if parts.scheme not in ("http", "https"):
        raise InvalidRepositoryUrl(MESSAGE)
    # Exact host match: "github.com.evil.com" and "evil.com/github.com" both fail.
    if (parts.hostname or "").lower() not in ALLOWED_HOSTS:
        raise InvalidRepositoryUrl(MESSAGE)
    if parts.username is not None or parts.password is not None or port is not None:
        raise InvalidRepositoryUrl(MESSAGE)

    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        raise InvalidRepositoryUrl(MESSAGE)

    owner, name = segments[0], segments[1]
    name = name.removesuffix(".git")
    if not _OWNER.fullmatch(owner) or not _REPO.fullmatch(name) or name in (".", ".."):
        raise InvalidRepositoryUrl(MESSAGE)

    # Anything after owner/repo (/tree/main, /blob/..., ?tab=...) is deliberately ignored.
    return RepoRef(owner=owner, name=name)
