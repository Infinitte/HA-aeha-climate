from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "aeha_climate"
PLATFORMS = ["climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  hass.data.setdefault(DOMAIN, {})

  await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
  return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
  return unload_ok
