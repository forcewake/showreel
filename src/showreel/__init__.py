"""showreel — convert asciinema .cast recordings to SVG, video, GIF, HTML and more."""

__version__ = "0.3.1"


class ShowreelError(Exception):
    """User-facing error: bad input, missing tool, unsupported option."""
