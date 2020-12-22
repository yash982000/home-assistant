"""Light conftest."""

import pytest

from homeassistant.components.light import Profiles

from tests.async_mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def mock_light_profiles():
    """Mock loading of profiles."""
    data = {}

    def mock_profiles_class(hass):
        profiles = Profiles(hass)
        profiles.data = data
        profiles.async_initialize = AsyncMock()
        return profiles

    with patch(
        "homeassistant.components.light.Profiles",
        SCHEMA=Profiles.SCHEMA,
        side_effect=mock_profiles_class,
    ):
        yield data
