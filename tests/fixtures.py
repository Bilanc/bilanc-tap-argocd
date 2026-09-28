import copy

APP = {
    "metadata": {
        "uid": "0b5c7d6e-uid",
        "name": "payments-prod",
        "namespace": "argocd",
        "creationTimestamp": "2025-01-10T09:00:00Z",
        "labels": {"team": "payments"},
        "annotations": {
            "kubectl.kubernetes.io/last-applied-configuration": "{...}",
            "bilanc.co/repository": "acme/payments",
        },
        "ownerReferences": [{"kind": "ApplicationSet", "name": "services"}],
    },
    "spec": {
        "project": "default",
        "source": {
            "repoURL": "https://github.com/acme/deploy-config.git",
            "path": "apps/payments/prod",
            "targetRevision": "main",
        },
        "destination": {"server": "https://kubernetes.default.svc", "namespace": "payments"},
        "syncPolicy": {"automated": {"prune": True}},
    },
    "status": {
        "sync": {"status": "Synced", "revision": "c3"},
        "health": {"status": "Healthy"},
        "reconciledAt": "2026-09-20T10:05:00Z",
        "summary": {"images": ["ghcr.io/acme/payments:1.4.2"]},
        "resources": [{"kind": "Deployment"}, {"kind": "Service"}],
        "history": [
            {
                "id": 1,
                "revision": "c1",
                "deployStartedAt": "2026-09-18T10:00:00Z",
                "deployedAt": "2026-09-18T10:01:00Z",
                "source": {"repoURL": "https://github.com/acme/deploy-config.git", "path": "apps/payments/prod"},
                "initiatedBy": {"automated": True},
            },
            {
                "id": 2,
                "revision": "c3",
                "deployStartedAt": "2026-09-20T10:00:00Z",
                "deployedAt": "2026-09-20T10:02:00Z",
                "source": {"repoURL": "https://github.com/acme/deploy-config.git", "path": "apps/payments/prod"},
                "initiatedBy": {"automated": True},
            },
        ],
        "operationState": {
            "phase": "Succeeded",
            "message": "successfully synced (all tasks run)",
            "startedAt": "2026-09-20T10:00:00Z",
            "finishedAt": "2026-09-20T10:02:05Z",
            "operation": {"sync": {"revision": "c3"}, "initiatedBy": {"automated": True}},
            "syncResult": {
                "revision": "c3",
                "resources": [{"status": "Synced"}, {"status": "Synced"}],
            },
        },
    },
}


def app(**status_overrides):
    result = copy.deepcopy(APP)
    result["status"].update(status_overrides)
    return result


FAILED_OPERATION = {
    "phase": "Failed",
    "message": "one or more objects failed to apply",
    "startedAt": "2026-09-21T08:00:00Z",
    "finishedAt": "2026-09-21T08:00:40Z",
    "retryCount": 2,
    "operation": {"sync": {"revision": "c4"}, "initiatedBy": {"username": "alice"}},
    "syncResult": {
        "revision": "c4",
        "source": {"repoURL": "https://github.com/acme/deploy-config.git", "path": "apps/payments/prod"},
        "resources": [{"status": "Synced"}, {"status": "SyncFailed"}, {"status": "Synced", "hookPhase": "Error"}],
    },
}
