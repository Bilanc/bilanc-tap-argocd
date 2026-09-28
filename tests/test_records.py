from tap_argocd.streams.applications import application_record
from tap_argocd.streams.syncs import sync_records

from .fixtures import FAILED_OPERATION, app


def test_application_record():
    record = application_record(app())

    assert record["uid"] == "0b5c7d6e-uid"
    assert record["sources"][0]["repo_url"] == "https://github.com/acme/deploy-config.git"
    assert record["annotations"] == {"bilanc.co/repository": "acme/payments"}
    assert record["owner_kind"] == "ApplicationSet"
    assert record["automated_sync"] is True
    assert record["sync_revision"] == "c3"
    assert record["images"] == ["ghcr.io/acme/payments:1.4.2"]
    assert record["manages_applications"] is False


def test_app_of_apps_is_flagged():
    record = application_record(app(resources=[{"kind": "Application"}]))
    assert record["manages_applications"] is True


def test_latest_history_entry_is_enriched_by_operation_state():
    first, latest = sync_records(app())

    assert first["id"] == "0b5c7d6e-uid:2026-09-18T10:00:00Z"
    assert first["phase"] == "Succeeded"
    assert first["from_operation_state"] is False

    assert latest["id"] == "0b5c7d6e-uid:2026-09-20T10:00:00Z"
    assert latest["from_operation_state"] is True
    assert latest["in_history"] is True
    assert latest["finished_at"] == "2026-09-20T10:02:05Z"
    assert latest["message"] == "successfully synced (all tasks run)"
    assert latest["resources_total"] == 2
    assert latest["resources_failed"] == 0


def test_failed_operation_becomes_its_own_record():
    records = sync_records(app(operationState=FAILED_OPERATION))
    assert len(records) == 3

    failed = records[-1]
    assert failed["id"] == "0b5c7d6e-uid:2026-09-21T08:00:00Z"
    assert failed["phase"] == "Failed"
    assert failed["in_history"] is False
    assert failed["revision"] == "c4"
    assert failed["sources"][0]["path"] == "apps/payments/prod"
    assert failed["initiated_by_username"] == "alice"
    assert failed["initiated_by_automated"] is False
    assert failed["retry_count"] == 2
    assert failed["resources_failed"] == 2


def test_running_operation_is_not_emitted():
    running = dict(FAILED_OPERATION, phase="Running", finishedAt=None)
    assert len(sync_records(app(operationState=running))) == 2


def test_multi_source_history():
    entry = {
        "id": 7,
        "revisions": ["r-chart", "r-values"],
        "sources": [{"repoURL": "https://charts.acme.io", "chart": "payments"}, {"repoURL": "git@github.com:acme/values"}],
        "deployStartedAt": "2026-09-22T00:00:00Z",
        "deployedAt": "2026-09-22T00:01:00Z",
    }
    (record,) = sync_records(app(history=[entry], operationState=None))

    assert record["revision"] == "r-chart"
    assert record["revisions"] == ["r-chart", "r-values"]
    assert [source["repo_url"] for source in record["sources"]] == ["https://charts.acme.io", "git@github.com:acme/values"]


def test_history_without_start_time_falls_back_to_history_id():
    entry = {"id": 3, "revision": "old", "deployedAt": "2020-01-01T00:00:00Z"}
    (record,) = sync_records(app(history=[entry], operationState=None))
    assert record["id"] == "0b5c7d6e-uid:history:3"
