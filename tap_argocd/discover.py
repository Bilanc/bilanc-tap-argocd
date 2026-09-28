"""Catalog discovery."""
import json
from pathlib import Path

from singer import metadata
from singer.catalog import Catalog

from tap_argocd.client import Client
from tap_argocd.streams import STREAMS

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(stream_name):
    with open(SCHEMAS_DIR / f"{stream_name}.json", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def discover(config=None):
    if config:
        Client(config).check_access()

    streams = []
    for stream_name, stream in STREAMS.items():
        schema = load_schema(stream_name)
        stream_metadata = metadata.get_standard_metadata(
            schema=schema,
            key_properties=stream.key_properties,
            valid_replication_keys=[stream.replication_key] if stream.replication_key else None,
            replication_method=stream.replication_method,
        )
        stream_metadata = metadata.to_map(stream_metadata)
        # Selected by default: both streams are needed to model deployments
        stream_metadata = metadata.write(stream_metadata, (), "selected", True)
        streams.append(
            {
                "stream": stream_name,
                "tap_stream_id": stream.tap_stream_id,
                "key_properties": stream.key_properties,
                "schema": schema,
                "metadata": metadata.to_list(stream_metadata),
            }
        )
    return Catalog.from_dict({"streams": streams})
