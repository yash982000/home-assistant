"""Services for the Plex integration."""
import json
import logging

from plexapi.exceptions import NotFound
import voluptuous as vol

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)

REFRESH_LIBRARY_SCHEMA = vol.Schema(
    {vol.Optional("server_name"): str, vol.Required("library_name"): str}
)

_LOGGER = logging.getLogger(__package__)


async def async_setup_services(hass):
    """Set up services for the Plex component."""

    async def async_refresh_library_service(service_call):
        await hass.async_add_executor_job(refresh_library, hass, service_call)

    async def async_scan_clients_service(_):
        _LOGGER.debug("Scanning for new Plex clients")
        for server_id in hass.data[DOMAIN][SERVERS]:
            async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        async_refresh_library_service,
        schema=REFRESH_LIBRARY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_CLIENTS, async_scan_clients_service
    )

    return True


def refresh_library(hass, service_call):
    """Scan a Plex library for new and updated media."""
    plex_server_name = service_call.data.get("server_name")
    library_name = service_call.data["library_name"]

    plex_server = get_plex_server(hass, plex_server_name)
    if not plex_server:
        return

    try:
        library = plex_server.library.section(title=library_name)
    except NotFound:
        _LOGGER.error(
            "Library with name '%s' not found in %s",
            library_name,
            [x.title for x in plex_server.library.sections()],
        )
        return

    _LOGGER.debug("Scanning %s for new and updated media", library_name)
    library.update()


def get_plex_server(hass, plex_server_name=None):
    """Retrieve a configured Plex server by name."""
    plex_servers = hass.data[DOMAIN][SERVERS].values()

    if plex_server_name:
        plex_server = next(
            (x for x in plex_servers if x.friendly_name == plex_server_name), None
        )
        if plex_server is not None:
            return plex_server
        _LOGGER.error(
            "Requested Plex server '%s' not found in %s",
            plex_server_name,
            [x.friendly_name for x in plex_servers],
        )
        return None

    if len(plex_servers) == 1:
        return next(iter(plex_servers))

    _LOGGER.error(
        "Multiple Plex servers configured, choose with 'plex_server' key: %s",
        [x.friendly_name for x in plex_servers],
    )
    return None


def lookup_plex_media(hass, content_type, content_id):
    """Look up Plex media using media_player.play_media service payloads."""
    content = json.loads(content_id)

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = DOMAIN

    plex_server_name = content.pop("plex_server", None)
    shuffle = content.pop("shuffle", 0)

    plex_server = get_plex_server(hass, plex_server_name=plex_server_name)
    if not plex_server:
        return (None, None)

    media = plex_server.lookup_media(content_type, **content)
    if media is None:
        _LOGGER.error("Media could not be found: %s", content)
        return (None, None)

    playqueue = plex_server.create_playqueue(media, shuffle=shuffle)
    return (playqueue, plex_server)
