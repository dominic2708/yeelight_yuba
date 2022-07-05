import asyncio
from functools import partial
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (LightEntity, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS)
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN, )
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import color, dt
from math import ceil
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Device'
DATA_KEY = 'light.yeelight_yuba'


CONF_UPDATE_INSTANT = 'update_instant'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INSTANT, default=True): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

REQUIREMENTS = ['python-miio>=0.4.5']

ATTR_MODEL = 'model'
ATTR_FIRMWARE_VERSION = 'firmware_version'
ATTR_HARDWARE_VERSION = 'hardware_version'

SUCCESS = ['ok']

SUPPORT_FLAGS = SUPPORT_BRIGHTNESS 
SCAN_INTERVAL = timedelta(seconds=15)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    from miio import Device, DeviceException
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)

        device = YunyiLight(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)


class YunyiLight(LightEntity):

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device

        self._name = config.get(CONF_NAME)

        self._unique_id = "{}-{}".format(device_info.model, device_info.mac_address)
        self._model = device_info.model
        self._available = None
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False
        self._brightness = None
        self._state = None        
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version
        }

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def brightness(self):
        """Return the name of this entity, if any."""
        return self._brightness

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False and self._skip_update:
            self._skip_update = False
            return

        try:
            cover_info = self._device.send('get_prop', 'power,bright')
            self._state = self.ystate(cover_info[0])
            self._available = True
            self._brightness = ceil((255 / 100.0) * cover_info[1])
            self._state_attrs.update({

            })

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    def ystate(self, ystate1):
        if ystate1 == "on":
            return True
        else:
            return False

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        from miio import DeviceException
        try:
            result = await self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.info("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_turn_off(self, **kwargs) -> None:
        """Turn the miio device off."""
        result = yield from self._try_command("Turning the miio device off failed.", self._device.send,'set_power', 'off')
        if result:
            self._state = False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs) -> None:
        """Turn the miio device on."""
        result = yield from self._try_command("Turning the miio device on failed.", self._device.send,'set_power', 'on')
        if result:
            self._state = True
