from typing import Final

from trackmod.trackers.it.settings import ITSettings
from trackmod.trackers.xm.settings import XMSettings

from midi2tracker.spec import TRACKER_NAME

IT_SETTINGS: Final = ITSettings()
XM_SETTINGS: Final = XMSettings(tracker=TRACKER_NAME)
