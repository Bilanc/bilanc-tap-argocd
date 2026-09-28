from .applications import Applications
from .syncs import Syncs

STREAMS = {
    Applications.tap_stream_id: Applications,
    Syncs.tap_stream_id: Syncs,
}
