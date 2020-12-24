from datetime import timedelta
import logging

from pytracktry.tracker import Tracking
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY, CONF_NAME, HTTP_OK
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Information provided by TrackTry"
ATTR_TRACKINGS = "trackings"

BASE = "https://tracktry.com/"

CONF_CARRIER_CODE = "carrier_code"
CONF_TITLE = "title"
CONF_COMMENT = "comment"
CONF_TRACKING_NUMBER = "tracking_number"

DEFAULT_NAME = "tracktry"
UPDATE_TOPIC = f"{DOMAIN}_update"

ICON = "mdi:package-variant-closed"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

SERVICE_ADD_TRACKING = "add_tracking"
SERVICE_REMOVE_TRACKING = "remove_tracking"

ADD_TRACKING_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TRACKING_NUMBER): cv.string,
        vol.Required(CONF_CARRIER_CODE): cv.string,
        vol.Optional(CONF_TITLE): cv.string,
        vol.Optional(CONF_COMMENT): cv.string
    }
)

REMOVE_TRACKING_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(CONF_CARRIER_CODE): cv.string, vol.Required(CONF_TRACKING_NUMBER): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the TrackTry sensor platform."""
    apikey = config[CONF_API_KEY]
    name = config[CONF_NAME]

    session = async_get_clientsession(hass)
    tracktry = Tracking(hass.loop, session, apikey)

    await tracktry.get_trackings()

    instance = TrackTrySensor(tracktry, name)

    async_add_entities([instance], True)

    async def handle_add_tracking(call):
        """Call when a user adds a new TrackTry tracking from Home Assistant."""
        title = call.data.get(CONF_TITLE)
        comment = call.data.get(CONF_COMMENT)
        carrier_code = call.data[CONF_CARRIER_CODE]
        tracking_number = call.data[CONF_TRACKING_NUMBER]

        await tracktry.add_package_tracking(tracking_number, carrier_code, title, comment)
        async_dispatcher_send(hass, UPDATE_TOPIC)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TRACKING,
        handle_add_tracking,
        schema=ADD_TRACKING_SERVICE_SCHEMA,
    )

    async def handle_remove_tracking(call):
        """Call when a user removes an TrackTry tracking from Home Assistant."""
        carrier_code = call.data[CONF_CARRIER_CODE]
        tracking_number = call.data[CONF_TRACKING_NUMBER]

        await tracktry.remove_package_tracking(carrier_code, tracking_number)
        async_dispatcher_send(hass, UPDATE_TOPIC)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TRACKING,
        handle_remove_tracking,
        schema=REMOVE_TRACKING_SERVICE_SCHEMA,
    )

class TrackTrySensor(Entity):
    """Representation of a TrackTry sensor."""

    def __init__(self, tracktry, name):
        """Initialize the sensor."""
        self._attributes = {}
        self._name = name
        self._state = None
        self.tracktry = tracktry

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "packages"

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                UPDATE_TOPIC, self._force_update
            )
        )

    async def _force_update(self):
        """Force update of data."""
        await self.async_update(no_throttle=True)
        self.async_write_ha_state()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Get the latest data from the TrackTry API."""
        await self.tracktry.get_trackings()

        status_to_ignore = {"delivered"}
        status_counts = {}
        trackings = []
        not_delivered_count = 0

        for track in self.tracktry.trackings:
            status = track['status'].lower()
            name = (
                track['tracking_number'] if track['title'] is None else track['title']
            )
            last_update_time = (
                'Never Updated' if track['lastUpdateTime'] is None else track['lastUpdateTime']
            )
            trackings.append(
                {
                    "name": name,
                    "comment": track['comment'],
                    "tracking_number": track['tracking_number'],
                    "carrier_code": track['carrier_code'],
                    "last_update_time": track['lastUpdateTime'],
                    "status": track['status'],
                    "last_event": track['lastEvent'],
                }
            )

            if status not in status_to_ignore:
                not_delivered_count += 1
            else:
                _LOGGER.debug("Ignoring %s as it has status: %s", name, status)

        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            **status_counts,
            ATTR_TRACKINGS: trackings,
        }

        self._state = not_delivered_count
