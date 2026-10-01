from agent.scanner.models import MacIdentity


def test_new_mac_does_not_keep_vendor_from_previous_mac() -> None:
    assert MacIdentity("00:00:00:00:00:01", "Old vendor").merged_with(
        MacIdentity("00:00:00:00:00:02")
    ) == MacIdentity("00:00:00:00:00:02", "unknown")


def test_vendor_for_same_mac_is_preserved_when_new_scan_has_no_vendor() -> None:
    assert MacIdentity("00:00:00:00:00:01", "Known vendor").merged_with(
        MacIdentity("00:00:00:00:00:01", "unknown")
    ) == MacIdentity("00:00:00:00:00:01", "Known vendor")


def test_vendor_is_updated_with_new_mac_when_both_are_observed() -> None:
    assert MacIdentity("00:00:00:00:00:01", "Old vendor").merged_with(
        MacIdentity("00:00:00:00:00:02", "New vendor")
    ) == MacIdentity("00:00:00:00:00:02", "New vendor")


def test_vendor_without_mac_does_not_change_identity() -> None:
    assert MacIdentity("00:00:00:00:00:01", "Known vendor").merged_with(
        MacIdentity(None, "Different vendor")
    ) == MacIdentity("00:00:00:00:00:01", "Known vendor")
