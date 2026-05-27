import pytest

from simminer.examples import generate


@pytest.fixture(scope="session")
def example_repo(tmp_path_factory):
    """A generated synthetic repository shared across the test session."""
    root = tmp_path_factory.mktemp("simrepo")
    generate(root)
    return root
