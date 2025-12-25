import ast
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
  HVACMode,
  ClimateEntityFeature
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
  "AUTO": 0x00,
  "COOL": 0x80,
  "DRY": 0x40,
  "FAN": 0xC0,
  "HEAT": 0x20
}
FAN_MAP = {
  "AUTO": 0x00,
  "HIGH": 0x80,
  "MED": 0x40,
  "LOW": 0xC0,
  "QUIET": 0x20
}

def reverse_8bits(n):
  return int('{:08b}'.format(n & 0xFF)[::-1], 2)

def reverse_4bits(n):
  res = 0
  for i in range(4):
    res = (res << 1) | (n & 1)
    n >>= 1
  return res

def calculate_frame(temp, modo, fan):
  byte_11_mode = MODE_MAP.get(modo.upper(), 0x00)
  byte_12_temp = reverse_4bits(temp - 16)+128
  byte_13_fan  = FAN_MAP.get(fan.upper(), 0x00)

  add_fix_rev = 32

  total_add_rev = (
    add_fix_rev + 
    reverse_8bits(byte_11_mode) + 
    reverse_8bits(byte_12_temp) + 
    reverse_8bits(byte_13_fan)
  )

  diff_result = (208 - total_add_rev) % 256

  checksum = reverse_8bits(diff_result)

  return {
    "Mode": hex(byte_11_mode),
    "Temp": hex(byte_12_temp),
    "Fan":  hex(byte_13_fan),
    "Checksum": hex(checksum)
  }

def frame_from_data(temp, mode, fan):
  if mode == "off":
    return "[0,8,8,64,191]"
  res = calculate_frame(temp, mode, fan)
  return f"[0,8,8,127,144,12,{reverse_4bits(temp - 16)+128},{MODE_MAP.get(mode.upper(), 0x00)},{FAN_MAP.get(fan.upper(), 0x00)},0,0,0,4,{res['Checksum']}]"

async def async_setup_entry(hass, entry, async_add_entities):
  name = entry.data.get("name")
  service = entry.data.get("service")
  async_add_entities([AEHAClimate(hass, name, entry.entry_id, service)])

class AEHAClimate(ClimateEntity):
  def __init__(self, hass, name, entry_id, service_call):
    self.hass = hass
    self._name = name
    self._attr_unique_id = f"aeha_{entry_id}"
    self._service_call = service_call
    self._attr_target_temperature = 24
    self._attr_hvac_mode = HVACMode.OFF
    self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT]
    self._attr_fan_mode = "Auto"
    self._attr_fan_modes = ["Auto", "High", "Med", "Low", "Quiet"]
    self._attr_temperature_unit = UnitOfTemperature.CELSIUS
    self._attr_supported_features = (
      ClimateEntityFeature.TARGET_TEMPERATURE | 
      ClimateEntityFeature.FAN_MODE
    )
  @property
  def name(self):
    return self._name

  async def _send_command(self):
    frame = frame_from_data(
      int(self._attr_target_temperature),
      self._attr_hvac_mode.value,
      self._attr_fan_mode
    )
    try:
      if isinstance(self._service_call, list) and len(self._service_call) > 0:
        action = self._service_call[0]
        service_full_name = action.get("action")
      elif isinstance(self._service_call, dict):
        service_full_name = self._service_call.get("action")

      if not service_full_name:
        _LOGGER.error(f"No se encontró el nombre del servicio en la configuración: {self._service_call}")
        return
      domain, service = service_full_name.split(".")
      frame_list = ast.literal_eval(frame)
      await self.hass.services.async_call(
        domain,
        service,
        {"data": frame_list},
      )
    except Exception as e:
      _LOGGER.error(f"Error converting frame: {e}")

  async def async_set_hvac_mode(self, hvac_mode):
    self._attr_hvac_mode = hvac_mode
    await self._send_command()
    self.async_write_ha_state()

  async def async_set_temperature(self, **kwargs):
    if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
      self._attr_target_temperature = temp
      await self._send_command()
    self.async_write_ha_state()

  async def async_set_fan_mode(self, fan_mode):
    self._attr_fan_mode = fan_mode
    await self._send_command()
    self.async_write_ha_state()
