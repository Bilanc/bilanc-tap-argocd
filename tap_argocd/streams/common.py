"""Helpers shared by the stream record builders."""


def source_record(source):
    if not source:
        return None
    return {
        "repo_url": source.get("repoURL"),
        "path": source.get("path"),
        "target_revision": source.get("targetRevision"),
        "chart": source.get("chart"),
        "ref": source.get("ref"),
        "name": source.get("name"),
    }


def source_records(single, multiple):
    """Multi-source apps use `sources`, single-source apps `source`."""
    if multiple:
        return [source_record(source) for source in multiple]
    if single:
        return [source_record(single)]
    return []


def revision_fields(single, multiple):
    revisions = list(multiple or ([single] if single else []))
    return {"revision": single or (revisions[0] if revisions else None), "revisions": revisions}


def application_identity(app):
    metadata = app.get("metadata") or {}
    spec = app.get("spec") or {}
    destination = spec.get("destination") or {}
    return {
        "app_uid": metadata.get("uid"),
        "app_name": metadata.get("name"),
        "app_namespace": metadata.get("namespace"),
        "project": spec.get("project"),
        "destination_server": destination.get("server"),
        "destination_name": destination.get("name"),
        "destination_namespace": destination.get("namespace"),
    }
