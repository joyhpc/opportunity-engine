import asyncio


def test_command_catalog_exposes_registry_metadata():
    from web.bridge import command_catalog

    catalog = command_catalog()
    status = next(item for item in catalog if item["name"] == "status")

    assert status["read_only"] is True
    assert status["description"]


def test_run_command_uses_service_registry(tmp_path, monkeypatch):
    from web.bridge import run_command

    monkeypatch.setenv("ODE_ROOT", str(tmp_path))

    result = asyncio.run(run_command("status", {}))

    assert result["ok"] is True
    assert result["data"]["total"] == 0


def test_run_command_rejects_non_object_params():
    from web.bridge import run_command

    result = asyncio.run(run_command("status", []))

    assert result["ok"] is False
    assert "params" in result["message"]

