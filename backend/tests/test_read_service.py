from __future__ import annotations

import inspect

from api.services import read


def test_read_service_functions_importable_and_callable():
    for name in ("list_hosts", "get_host_detail", "get_scan_detail", "list_findings"):
        func = getattr(read, name)
        assert callable(func)
        assert "session" in inspect.signature(func).parameters
