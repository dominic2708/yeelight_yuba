import enum
import logging
import asyncio
from functools import partial
from datetime import timedelta
import voluptuous as vol

from homeassistant.core import callback

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (ClimateEntity, PLATFORM_SCHEMA, )
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN, TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady

from homeassistant.components.climate.const import (
    DOMAIN,
    SUPPORT_FAN_MODE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Device'
DATA_KEY = 'cover.yeelight_yuba'


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

from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow


REQUIREMENTS = ['python-miio>=0.4.5']

ATTR_MODEL = 'model'
ATTR_FIRMWARE_VERSION = 'firmware_version'
ATTR_HARDWARE_VERSION = 'hardware_version'

SUPPORT_FLAGS = SUPPORT_FAN_MODE 
class OperationMode(enum.Enum):
    Heat = "heat"
    Cool = "cool"
    Dehumidify = "dry"
    Ventilate = "fan_only"
    Off = "off"
class OperationFanMode(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    tophigh = "tophigh"

SUCCESS = ['ok']

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

        device = YeelightYuba(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)


class YeelightYuba(ClimateEntity):

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device

        self._name = config.get(CONF_NAME)

        self._unique_id = "{}-{}".format(device_info.model, device_info.mac_address)
        self._model = device_info.model
        self._available = None
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._state = None
        self._fan_mode = None
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
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        return self._state

    @property
    def hvac_mode(self):
        """Return new hvac mode ie. heat, cool, fan only."""
        return self._hvac_mode
        
    @property
    def hvac_modes(self):
        """Return the list of available hvac modes."""
        return [mode.value for mode in OperationMode]

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [mode.value for mode in OperationFanMode]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

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
            cover_info = self._device.send('get_prop', 'bh_mode,fan_speed_idx')

            
            self._state = self.yeelight_state(cover_info[0])
            self._fan_mode = self.yeelight_speed(str(cover_info[1]))
            self._available = True
            self._state_attrs.update({

            })

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    def yeelight_state(self, ystate):
        if ystate == "bh_off":
            return "off"
        elif ystate == "warmwind":
            return "heat"
        elif ystate == "venting":
            return "cool"
        elif ystate == "drying":
            return "dry"
        elif ystate == "drying_cloth":
            return "dry"
        elif ystate == "coolwind":
            return "fan_only"

    def yeelight_speed(self, speed):
        if self._state == "heat":
        	  if speed[-1] == "0":
        	  	  return "low"
        	  elif speed[-1] == "1":
        	  	  return "medium"
        	  elif speed[-1] == "2":
        	  	  return "high"
        elif self._state == "cool":
        	  if speed[-2:-1] == "0":
        	  	  return "low"
        	  elif speed[-2:-1] == "1":
        	  	  return "medium"
        	  elif speed[-2:-1] == "2":
        	  	  return "high"
        	  elif speed[-2:-1] == "9":
        	  	  return "tophigh"
        elif self._state == "dry":
        	  if speed[-3:-2] == "0":
        	  	  return "low"
        	  elif speed[-3:-2] == "1":
        	  	  return "medium"
        	  elif speed[-3:-2] == "2":
        	  	  return "high"
        elif self._state == "fan_only":
        	  if speed[-4:-3] == "0":
        	  	  return "low"
        	  elif speed[-4:-3] == "1":
        	  	  return "medium"
        	  elif speed[-4:-3] == "2":
        	  	  return "high"
        else:
        	  return "low"

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
    def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == "off":
            result = yield from self._try_command(
                "Turning the miio device off failed.", self._device.send,
                'set_bh_mode', 'bh_off')
            if result:
                self._state = False
                self._hvac_mode = "off"
        else:
            if hvac_mode == "heat":
            	  ymode = "warmwind"
            elif hvac_mode == "cool":
                ymode = "venting"
            elif hvac_mode == "dry":
                ymode = "drying"
            elif hvac_mode == "fan_only":
                ymode = "coolwind"
            result = yield from self._try_command(
                "Turning the miio device on failed.", self._device.send,
                'set_bh_mode', [ymode])
            if result:
            	  self._state = hvac_mode

    @asyncio.coroutine
    def async_set_fan_mode(self, fan_mode):
    	  if self._state == "heat":
    	  	  if fan_mode == "low":
    	  	  	  y_fan_mode = 0
    	  	  elif fan_mode == "medium":
    	  	  	  y_fan_mode = 1
    	  	  elif fan_mode == "high":
    	  	  	  y_fan_mode = 2
    	  	  else :
    	  	  	  y_fan_mode = 8
    	  elif self._state == "cool":
    	  	  if fan_mode == "low":
    	  	  	  y_fan_mode = 0
    	  	  elif fan_mode == "medium":
    	  	  	  y_fan_mode = 1
    	  	  elif fan_mode == "high":
    	  	  	  y_fan_mode = 2
    	  	  elif fan_mode == "tophigh":
    	  	  	  y_fan_mode = 9
    	  	  else :
    	  	  	  y_fan_mode = 8
    	  elif self._state == "dry":
    	  	  if fan_mode == "low":
    	  	  	  y_fan_mode = 0
    	  	  elif fan_mode == "medium":
    	  	  	  y_fan_mode = 1
    	  	  elif fan_mode == "high":
    	  	  	  y_fan_mode = 2
    	  	  else :
    	  	  	  y_fan_mode = 8
    	  elif self._state == "fan_only":
    	  	  if fan_mode == "low":
    	  	  	  y_fan_mode = 0
    	  	  elif fan_mode == "medium":
    	  	  	  y_fan_mode = 1
    	  	  elif fan_mode == "high":
    	  	  	  y_fan_mode = 2
    	  	  else:
    	  	  	  y_fan_mode = 8
    	  else:
    	  	  y_fan_mode = 8
    	  if y_fan_mode != 8:
            result = yield from self._try_command(
                "Turning the miio device off failed.", self._device.send,
                'set_gears_idx', [y_fan_mode])

    @asyncio.coroutine
    def async_turn_off(self, **kwargs) -> None:
        """Turn the miio device off."""
        result = yield from self._try_command("Turning the miio device off failed.", self._device.send,'set_bh_mode', 'bh_off')
        if result:
            self._state = False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs) -> None:
        """Turn the miio device on."""
        result = yield from self._try_command("Turning the miio device on failed.", self._device.send,'set_bh_mode', 'drying')
        if result:
            self._state = True