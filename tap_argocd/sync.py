"""Sync selected streams."""
import singer

from tap_argocd.client import Client
from tap_argocd.streams import STREAMS

LOGGER = singer.get_logger()


def sync(config, state, catalog):
    client = Client(config)
    state = state or {}

    with singer.Transformer() as transformer:
        for stream in catalog.get_selected_streams(state):
            stream_obj = STREAMS[stream.tap_stream_id](client)
            schema = stream.schema.to_dict()
            LOGGER.info("Starting sync for stream: %s", stream.tap_stream_id)
            state = singer.set_currently_syncing(state, stream.tap_stream_id)
            singer.write_state(state)
            singer.write_schema(stream.tap_stream_id, schema, stream_obj.key_properties, stream_obj.replication_key)
            state = stream_obj.sync(state, schema, singer.metadata.to_map(stream.metadata), transformer)
            singer.write_state(state)

    state = singer.set_currently_syncing(state, None)
    singer.write_state(state)
