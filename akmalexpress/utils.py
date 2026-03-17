import string
import secrets


def get_random_symbols(length=10):
    """Return a cryptographically secure random suffix for public slugs."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
