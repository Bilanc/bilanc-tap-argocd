import json
from unittest import mock

import pytest

from tap_argocd.client import ArgoCDError, Client
from tap_argocd.discover import discover
from tap_argocd.sync import sync

from .fixtures import FAILED_OPERATION, app

CONFIG = {"base_url": "https://argocd.acme.io/", "token": "t", "start_date": "2026-01-01T00:00:00Z"}


def run_sync(applications, state=None):
    with mock.patch.object(Client, "list_applications", return_value=applications), mock.patch(
        "singer.messages.write_message"
    ) as write_message:
        sync(CONFIG, state or {}, discover())
    messages = [call.args[0] for call in write_message.call_args_list]
    records = [m.record for m in messages if m.__class__.__name__ == "RecordMessage"]
    states = [m.value for m in messages if m.__class__.__name__ == "StateMessage"]
    return records, states[-1]


def test_full_sync_then_incremental():
    records, state = run_sync([app()])

    assert sum("uid" in r for r in records) == 1
    sync_rows = [r for r in records if "app_uid" in r]
    assert len(sync_rows) == 2
    assert state["bookmarks"]["syncs"]["0b5c7d6e-uid"] == "2026-09-20T10:02:05.000000Z"

    # Nothing new: only the applications snapshot is re-emitted
    records, state = run_sync([app()], state)
    assert not [r for r in records if "app_uid" in r]

    # A failed sync lands after the last success
    records, state = run_sync([app(operationState=FAILED_OPERATION)], state)
    sync_rows = [r for r in records if "app_uid" in r]
    assert [r["phase"] for r in sync_rows] == ["Failed"]
    assert state["bookmarks"]["syncs"]["0b5c7d6e-uid"] == "2026-09-21T08:00:40.000000Z"


def test_start_date_filters_old_history():
    entry = {"id": 1, "revision": "old", "deployStartedAt": "2025-06-01T00:00:00Z", "deployedAt": "2025-06-01T00:01:00Z"}
    records, _ = run_sync([app(history=[entry], operationState=None)])
    assert not [r for r in records if "app_uid" in r]


def test_catalog_selects_both_streams():
    catalog = discover()
    assert sorted(s.tap_stream_id for s in catalog.get_selected_streams({})) == ["applications", "syncs"]
    json.dumps(catalog.to_dict())


def test_client_rejects_anonymous_session():
    client = Client(CONFIG)
    with mock.patch.object(Client, "get", return_value={"loggedIn": False}):
        with pytest.raises(ArgoCDError):
            client.check_access()


def test_client_passes_project_filter():
    client = Client({**CONFIG, "projects": "payments, platform", "selector": "env=prod"})
    with mock.patch.object(client.session, "get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"items": None}
        assert client.list_applications() == []
    url = get.call_args.args[0]
    assert url == "https://argocd.acme.io/api/v1/applications"
    assert get.call_args.kwargs["params"] == {"projects": ["payments", "platform"], "selector": "env=prod"}
