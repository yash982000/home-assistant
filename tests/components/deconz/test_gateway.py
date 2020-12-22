"""Test deCONZ gateway."""

from copy import deepcopy

import pydeconz
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.deconz.config_flow import DECONZ_MANUFACTURERURL
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.deconz.gateway import (
    get_gateway,
    get_gateway_from_config_entry,
)
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, SOURCE_SSDP
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry

API_KEY = "1234567890ABCDEF"
BRIDGEID = "01234E56789A"

ENTRY_CONFIG = {CONF_API_KEY: API_KEY, CONF_HOST: "1.2.3.4", CONF_PORT: 80}

ENTRY_OPTIONS = {}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "ipaddress": "1.2.3.4",
    "mac": "00:11:22:33:44:55",
    "modelid": "deCONZ",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "uuid": "1234",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {
    "config": DECONZ_CONFIG,
    "groups": {},
    "lights": {},
    "sensors": {},
}


async def setup_deconz_integration(
    hass,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    get_state_response=DECONZ_WEB_REQUEST,
    entry_id="1",
    source="user",
):
    """Create the deCONZ gateway."""
    config_entry = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        source=source,
        data=deepcopy(config),
        connection_class=CONN_CLASS_LOCAL_PUSH,
        options=deepcopy(options),
        entry_id=entry_id,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pydeconz.DeconzSession.request", return_value=deepcopy(get_state_response)
    ), patch("pydeconz.DeconzSession.start", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_gateway_setup(hass):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await setup_deconz_integration(hass)
        gateway = get_gateway_from_config_entry(hass, config_entry)
        assert gateway.bridgeid == BRIDGEID
        assert gateway.master is True
        assert gateway.option_allow_clip_sensor is False
        assert gateway.option_allow_deconz_groups is True
        assert gateway.option_allow_new_devices is True

        assert len(gateway.deconz_ids) == 0
        assert len(hass.states.async_all()) == 0

        assert forward_entry_setup.mock_calls[0][1] == (
            config_entry,
            BINARY_SENSOR_DOMAIN,
        )
        assert forward_entry_setup.mock_calls[1][1] == (config_entry, CLIMATE_DOMAIN)
        assert forward_entry_setup.mock_calls[2][1] == (config_entry, COVER_DOMAIN)
        assert forward_entry_setup.mock_calls[3][1] == (config_entry, FAN_DOMAIN)
        assert forward_entry_setup.mock_calls[4][1] == (config_entry, LIGHT_DOMAIN)
        assert forward_entry_setup.mock_calls[5][1] == (config_entry, LOCK_DOMAIN)
        assert forward_entry_setup.mock_calls[6][1] == (config_entry, SCENE_DOMAIN)
        assert forward_entry_setup.mock_calls[7][1] == (config_entry, SENSOR_DOMAIN)
        assert forward_entry_setup.mock_calls[8][1] == (config_entry, SWITCH_DOMAIN)


async def test_gateway_retry(hass):
    """Retry setup."""
    with patch(
        "homeassistant.components.deconz.gateway.get_gateway",
        side_effect=CannotConnect,
    ):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_gateway_setup_fails(hass):
    """Retry setup."""
    with patch(
        "homeassistant.components.deconz.gateway.get_gateway", side_effect=Exception
    ):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_connection_status_signalling(hass):
    """Make sure that connection status triggers a dispatcher send."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    event_call = Mock()
    unsub = async_dispatcher_connect(hass, gateway.signal_reachable, event_call)

    gateway.async_connection_status_callback(False)
    await hass.async_block_till_done()

    assert gateway.available is False
    assert len(event_call.mock_calls) == 1

    unsub()


async def test_update_address(hass):
    """Make sure that connection status triggers a dispatcher send."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)
    assert gateway.api.host == "1.2.3.4"

    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.config_entries.flow.async_init(
            DECONZ_DOMAIN,
            data={
                ATTR_SSDP_LOCATION: "http://2.3.4.5:80/",
                ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                ATTR_UPNP_SERIAL: BRIDGEID,
                ATTR_UPNP_UDN: "uuid:456DEF",
            },
            context={"source": SOURCE_SSDP},
        )
        await hass.async_block_till_done()

    assert gateway.api.host == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reset_after_successful_setup(hass):
    """Make sure that connection status triggers a dispatcher send."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    result = await gateway.async_reset()
    await hass.async_block_till_done()

    assert result is True


async def test_get_gateway(hass):
    """Successful call."""
    with patch("pydeconz.DeconzSession.initialize", return_value=True):
        assert await get_gateway(hass, ENTRY_CONFIG, Mock(), Mock())


async def test_get_gateway_fails_unauthorized(hass):
    """Failed call."""
    with patch(
        "pydeconz.DeconzSession.initialize",
        side_effect=pydeconz.errors.Unauthorized,
    ), pytest.raises(AuthenticationRequired):
        assert await get_gateway(hass, ENTRY_CONFIG, Mock(), Mock()) is False


async def test_get_gateway_fails_cannot_connect(hass):
    """Failed call."""
    with patch(
        "pydeconz.DeconzSession.initialize",
        side_effect=pydeconz.errors.RequestError,
    ), pytest.raises(CannotConnect):
        assert await get_gateway(hass, ENTRY_CONFIG, Mock(), Mock()) is False
