from __future__ import annotations

import argparse

from api.db.session import get_session
from api.services.hosts import (
    find_ambiguous_mac_identities,
    repair_ambiguous_mac_identities,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend-repair-host-identities")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="relink scan history and rebuild the affected inventory",
    )
    args = parser.parse_args(argv)

    for session in get_session():
        groups = find_ambiguous_mac_identities(session)
        print(f"mac_collisions_found={len(groups)}")
        for scan, mac, ips in groups:
            print(f"scan_id={scan.scan_id} mac={mac} ips={','.join(sorted(ips))}")
        if args.apply:
            repaired = repair_ambiguous_mac_identities(session)
            session.commit()
            print(f"mac_collisions_repaired={repaired}")
        else:
            print("dry_run=true; pass --apply to commit the repair")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
