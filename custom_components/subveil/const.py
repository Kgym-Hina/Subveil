"""Constants for Subveil."""

DOMAIN = "subveil"

CONF_MEDIA_PLAYER = "media_player"
CONF_OS_API_KEY = "opensubtitles_api_key"
CONF_OS_USERNAME = "opensubtitles_username"
CONF_OS_PASSWORD = "opensubtitles_password"
CONF_LANGUAGES = "languages"
CONF_AUTO_SEARCH = "auto_search"

DEFAULT_PORT = 8765
DEFAULT_LANGUAGES = "en"

MAX_CANDIDATES = 30

STATUS_IDLE = "idle"
STATUS_PLAYING = "playing"
STATUS_SEARCHING = "searching"
STATUS_FOUND = "found"
STATUS_NOT_FOUND = "not_found"
STATUS_SEARCH_FAILED = "search_failed"
STATUS_DOWNLOADING = "downloading"
STATUS_DOWNLOAD_FAILED = "download_failed"
STATUS_LOADED = "loaded"
STATUS_OFF = "off"
STATUS_TV_OFFLINE = "tv_offline"
STATUS_INVALID_SUBTITLE = "invalid_subtitle"
STATUS_NO_API_KEY = "no_api_key"
STATUS_NO_TITLE = "no_title"

STATUSES = [
    STATUS_IDLE,
    STATUS_PLAYING,
    STATUS_SEARCHING,
    STATUS_FOUND,
    STATUS_NOT_FOUND,
    STATUS_SEARCH_FAILED,
    STATUS_DOWNLOADING,
    STATUS_DOWNLOAD_FAILED,
    STATUS_LOADED,
    STATUS_OFF,
    STATUS_TV_OFFLINE,
    STATUS_INVALID_SUBTITLE,
    STATUS_NO_API_KEY,
    STATUS_NO_TITLE,
]
