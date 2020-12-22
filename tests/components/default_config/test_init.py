"""Test the default_config init."""
import pytest

from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa


@pytest.fixture(autouse=True)
def mock_ssdp():
    """Mock ssdp."""
    with patch("homeassistant.components.ssdp.Scanner.async_scan"):
        yield


@pytest.fixture(autouse=True)
def mock_updater():
    """Mock updater."""
    with patch("homeassistant.components.updater.get_newest_version"):
        yield


@pytest.fixture(autouse=True)
def recorder_url_mock():
    """Mock recorder url."""
    with patch("homeassistant.components.recorder.DEFAULT_URL", "sqlite://"):
        yield


async def test_setup(hass, mock_zeroconf):
    """Test setup."""
    assert await async_setup_component(hass, "default_config", {"foo": "bar"})
