"""`syncs` stream: one row per Argo CD sync operation (a deploy attempt).

Argo CD keeps two views of past syncs on each application:
  - status.history: successful syncs only, capped by revisionHistoryLimit (default 10)
  - status.operationState: the latest operation, including failures, until the next one replaces it
Both are merged here and keyed on (app uid, operation start), which Argo CD writes identically
to history.deployStartedAt and operationState.startedAt. Failures are only visible between two
syncs, so the tap has to run more often than an application deploys to catch all of them.
"""
from singer import get_bookmark, metrics, utils, write_bookmark, write_record
from singer.utils import strptime_to_utc

from .common import application_identity, revision_fields, source_records

TERMINAL_PHASES = {"Succeeded", "Failed", "Error"}
FAILED_HOOK_PHASES = {"Failed", "Error"}


def sync_id(app_uid, started_at, history_id):
    if started_at:
        return f"{app_uid}:{started_at}"
    return f"{app_uid}:history:{history_id}"


def empty_sync_record(identity):
    return {
        **identity,
        "history_id": None,
        "revision": None,
        "revisions": [],
        "sources": [],
        "started_at": None,
        "finished_at": None,
        "phase": None,
        "message": None,
        "initiated_by_username": None,
        "initiated_by_automated": None,
        "retry_count": None,
        "dry_run": None,
        "resources_total": None,
        "resources_failed": None,
        "in_history": False,
        "from_operation_state": False,
    }


def apply_operation_state(record, operation_state):
    operation = operation_state.get("operation") or {}
    requested = operation.get("sync") or {}
    result = operation_state.get("syncResult") or {}
    initiated_by = operation.get("initiatedBy") or {}
    resources = result.get("resources") or []

    if not record["revision"]:
        record.update(
            revision_fields(
                result.get("revision") or requested.get("revision"),
                result.get("revisions") or requested.get("revisions"),
            )
        )
    if not record["sources"]:
        record["sources"] = source_records(result.get("source"), result.get("sources"))

    record.update(
        {
            "started_at": record["started_at"] or operation_state.get("startedAt"),
            "finished_at": operation_state.get("finishedAt") or record["finished_at"],
            "phase": operation_state.get("phase"),
            "message": operation_state.get("message"),
            "initiated_by_username": initiated_by.get("username") or record["initiated_by_username"],
            "initiated_by_automated": bool(initiated_by.get("automated")),
            "retry_count": operation_state.get("retryCount"),
            "dry_run": bool(requested.get("dryRun")),
            "resources_total": len(resources),
            "resources_failed": sum(
                1
                for resource in resources
                if resource.get("status") == "SyncFailed" or resource.get("hookPhase") in FAILED_HOOK_PHASES
            ),
            "from_operation_state": True,
        }
    )
    return record


def sync_records(app):
    identity = application_identity(app)
    status = app.get("status") or {}
    operation_state = status.get("operationState") or {}
    operation_done = operation_state.get("phase") in TERMINAL_PHASES
    operation_started_at = operation_state.get("startedAt")
    operation_matched = False
    records = []

    for entry in status.get("history") or []:
        initiated_by = entry.get("initiatedBy") or {}
        record = empty_sync_record(identity)
        record.update(revision_fields(entry.get("revision"), entry.get("revisions")))
        record.update(
            {
                "history_id": entry.get("id"),
                "sources": source_records(entry.get("source"), entry.get("sources")),
                "started_at": entry.get("deployStartedAt"),
                "finished_at": entry.get("deployedAt"),
                # history only ever records successful syncs
                "phase": "Succeeded",
                "initiated_by_username": initiated_by.get("username"),
                "initiated_by_automated": initiated_by.get("automated"),
                "in_history": True,
            }
        )
        if operation_done and operation_started_at and entry.get("deployStartedAt") == operation_started_at:
            apply_operation_state(record, operation_state)
            operation_matched = True
        record["id"] = sync_id(identity["app_uid"], record["started_at"], record["history_id"])
        records.append(record)

    if operation_done and not operation_matched and operation_started_at:
        record = apply_operation_state(empty_sync_record(identity), operation_state)
        record["id"] = sync_id(identity["app_uid"], record["started_at"], None)
        records.append(record)

    return records


class Syncs:
    tap_stream_id = "syncs"
    key_properties = ["id"]
    replication_method = "INCREMENTAL"
    replication_key = "finished_at"

    def __init__(self, client):
        self.client = client

    def sync(self, state, schema, stream_metadata, transformer):
        """Bookmarks are per application: each app's syncs are sequential, so a strict
        `finished_at > bookmark` never skips one, even when two apps finish in the same second."""
        start_date = strptime_to_utc(self.client.start_date)
        inserted_at = utils.now().isoformat()

        with metrics.record_counter(self.tap_stream_id) as counter:
            for app in self.client.list_applications():
                app_uid = (app.get("metadata") or {}).get("uid")
                bookmark = get_bookmark(state, self.tap_stream_id, app_uid)
                floor = strptime_to_utc(bookmark) if bookmark else None
                max_finished = floor

                for record in sync_records(app):
                    if not record["finished_at"]:
                        continue
                    finished = strptime_to_utc(record["finished_at"])
                    if finished < start_date or (floor and finished <= floor):
                        continue
                    record["inserted_at"] = inserted_at
                    write_record(self.tap_stream_id, transformer.transform(record, schema, stream_metadata))
                    counter.increment()
                    max_finished = max(max_finished, finished) if max_finished else finished

                if max_finished and max_finished != floor:
                    state = write_bookmark(state, self.tap_stream_id, app_uid, utils.strftime(max_finished))
        return state
