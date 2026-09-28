"""`applications` stream: current state of every Argo CD application."""
from singer import metrics, utils, write_record

from .common import application_identity, revision_fields, source_records

DROPPED_ANNOTATIONS = {"kubectl.kubernetes.io/last-applied-configuration"}


def application_record(app):
    metadata = app.get("metadata") or {}
    spec = app.get("spec") or {}
    status = app.get("status") or {}
    sync_status = status.get("sync") or {}
    operation_state = status.get("operationState") or {}
    summary = status.get("summary") or {}
    resources = status.get("resources") or []
    owner = next(iter(metadata.get("ownerReferences") or []), {})
    identity = application_identity(app)
    current = revision_fields(sync_status.get("revision"), sync_status.get("revisions"))

    return {
        "uid": identity["app_uid"],
        "name": identity["app_name"],
        "namespace": identity["app_namespace"],
        "project": identity["project"],
        "created_at": metadata.get("creationTimestamp"),
        "labels": metadata.get("labels"),
        "annotations": {
            key: value for key, value in (metadata.get("annotations") or {}).items() if key not in DROPPED_ANNOTATIONS
        },
        "owner_kind": owner.get("kind"),
        "owner_name": owner.get("name"),
        "sources": source_records(spec.get("source"), spec.get("sources")),
        "destination_server": identity["destination_server"],
        "destination_name": identity["destination_name"],
        "destination_namespace": identity["destination_namespace"],
        "automated_sync": bool((spec.get("syncPolicy") or {}).get("automated")),
        "sync_status": sync_status.get("status"),
        "sync_revision": current["revision"],
        "sync_revisions": current["revisions"],
        "health_status": (status.get("health") or {}).get("status"),
        "reconciled_at": status.get("reconciledAt"),
        "operation_phase": operation_state.get("phase"),
        "operation_started_at": operation_state.get("startedAt"),
        "operation_finished_at": operation_state.get("finishedAt"),
        "images": summary.get("images") or [],
        "external_urls": summary.get("externalURLs") or [],
        # App-of-apps parents manage other Applications, they are not deployments themselves
        "manages_applications": any(resource.get("kind") == "Application" for resource in resources),
        "resources_count": len(resources),
        "history_limit": spec.get("revisionHistoryLimit"),
    }


class Applications:
    tap_stream_id = "applications"
    key_properties = ["uid"]
    replication_method = "FULL_TABLE"
    replication_key = None

    def __init__(self, client):
        self.client = client

    def sync(self, state, schema, stream_metadata, transformer):
        inserted_at = utils.now().isoformat()
        with metrics.record_counter(self.tap_stream_id) as counter:
            for app in self.client.list_applications():
                record = application_record(app)
                record["inserted_at"] = inserted_at
                write_record(self.tap_stream_id, transformer.transform(record, schema, stream_metadata))
                counter.increment()
        return state
