from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from agent.scanner.models import OperatingSystemInfo
from agent.utils.nmap_xml import parse_operating_system


def _host(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_selects_best_match_and_best_class() -> None:
    host = _host(
        """
        <host>
          <os>
            <osmatch name="Lower match" accuracy="88">
              <osclass accuracy="88"><cpe>cpe:/o:excluded:lower:1</cpe></osclass>
            </osmatch>
            <osmatch name="  Linux 5.4 - 5.10  " accuracy="96">
              <osclass accuracy="91" vendor="Old" osfamily="Old family">
                <cpe> cpe:/o:linux:linux_kernel:5 </cpe>
                <cpe>cpe:/o:linux:linux_kernel</cpe>
              </osclass>
              <osclass accuracy="99" vendor=" Linux " osfamily=" Linux "
                       osgen=" 5.X " type=" general purpose ">
                <cpe>cpe:/o:linux:linux_kernel:5</cpe>
                <cpe>  </cpe>
              </osclass>
            </osmatch>
          </os>
        </host>
        """
    )

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="Linux 5.4 - 5.10",
        accuracy=96,
        vendor="Linux",
        family="Linux",
        generation="5.X",
        device_type="general purpose",
        cpes=["cpe:/o:linux:linux_kernel", "cpe:/o:linux:linux_kernel:5"],
    )


def test_match_accuracy_tie_retains_first_candidate() -> None:
    host = _host(
        """
        <host><os>
          <osmatch name="First" accuracy="95" />
          <osmatch name="Second" accuracy="95" />
        </os></host>
        """
    )

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="First", accuracy=95
    )


def test_class_accuracy_tie_retains_first_class() -> None:
    host = _host(
        """
        <host><os><osmatch name="Linux" accuracy="98">
          <osclass accuracy="97" vendor="First" />
          <osclass accuracy="97" vendor="Second" />
        </osmatch></os></host>
        """
    )

    result = parse_operating_system(host)

    assert result is not None
    assert result.vendor == "First"


def test_malformed_class_accuracy_is_ignored() -> None:
    host = _host(
        """
        <host><os><osmatch name="Linux" accuracy="98">
          <osclass accuracy="invalid" vendor="Ignored" />
          <osclass accuracy="80" vendor="Supported" />
        </osmatch></os></host>
        """
    )

    result = parse_operating_system(host)

    assert result is not None
    assert result.vendor == "Supported"


@pytest.mark.parametrize("accuracy", [None, "invalid", "-1", "101", "99.5"])
def test_invalid_class_accuracy_does_not_supply_optional_attributes(
    accuracy: str | None,
) -> None:
    attributes = "" if accuracy is None else f' accuracy="{accuracy}"'
    host = _host(
        f"""
        <host><os><osmatch name="Linux" accuracy="98">
          <osclass{attributes} vendor="Must not be used" osfamily="Invented">
            <cpe> cpe:/o:linux:linux_kernel </cpe>
          </osclass>
        </osmatch></os></host>
        """
    )

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="Linux",
        accuracy=98,
        cpes=["cpe:/o:linux:linux_kernel"],
    )


def test_blank_optional_class_attributes_become_none() -> None:
    host = _host(
        """
        <host><os><osmatch name="Linux" accuracy="100">
          <osclass accuracy="100" vendor=" " osfamily="" osgen="  " type="" />
        </osmatch></os></host>
        """
    )

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="Linux", accuracy=100
    )


def test_valid_match_without_class_is_supported() -> None:
    host = _host('<host><os><osmatch name="Appliance" accuracy="0" /></os></host>')

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="Appliance", accuracy=0
    )


@pytest.mark.parametrize(
    "xml",
    [
        "<host />",
        "<host><os /></host>",
        '<host><os><osmatch name="" accuracy="90" /></os></host>',
        '<host><os><osmatch name="Linux" /></os></host>',
        '<host><os><osmatch name="Linux" accuracy="high" /></os></host>',
        '<host><os><osmatch name="Linux" accuracy="-1" /></os></host>',
        '<host><os><osmatch name="Linux" accuracy="101" /></os></host>',
        '<host><os><osmatch name="Linux" accuracy="99.5" /></os></host>',
    ],
)
def test_absent_or_malformed_evidence_returns_none(xml: str) -> None:
    assert parse_operating_system(_host(xml)) is None


def test_ignores_malformed_candidate_when_valid_candidate_exists() -> None:
    host = _host(
        """
        <host><os>
          <osmatch name="Invalid" accuracy="not-a-number" />
          <osmatch name="Valid" accuracy="72" />
        </os></host>
        """
    )

    assert parse_operating_system(host) == OperatingSystemInfo(
        name="Valid", accuracy=72
    )


def test_service_cpe_is_not_treated_as_os_evidence() -> None:
    host = _host(
        """
        <host>
          <ports><port portid="80"><service>
            <cpe>cpe:/a:vendor:app</cpe>
          </service></port></ports>
        </host>
        """
    )

    assert parse_operating_system(host) is None


def test_raw_fingerprint_is_not_treated_as_os_evidence() -> None:
    host = _host(
        """
        <host><os>
          <osfingerprint fingerprint="a raw fingerprint" />
        </os></host>
        """
    )

    assert parse_operating_system(host) is None
