import pytest


@pytest.fixture(autouse=True, scope="session")
def formsDir(tmp_path_factory):
    """Testler gerçek şablon deposuna dokunmasın (modül kapsamlı fixture'lardan önce kurulur)."""
    path = tmp_path_factory.mktemp("forms")
    patch = pytest.MonkeyPatch()
    patch.setattr("omr.store.FORMS_DIR", path)
    yield path
    patch.undo()
