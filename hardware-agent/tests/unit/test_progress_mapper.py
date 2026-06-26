from __future__ import annotations

import pytest
from agent.scanner.progress import (
    STAGE_WEIGHTS,
    ProgressMapper,
    ScanEvent,
    target_pct,
)

ALL_MODES = ["quick", "standard", "extensive", "nspi", "max"]


def _weights(mode: str):
    return STAGE_WEIGHTS[mode]


class TestStageWeightsTable:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_row_sums_to_100(self, mode: str) -> None:
        w = _weights(mode)
        assert w.discovery + w.port_scan + w.deep_inspection + w.normalize == 100

    def test_table_has_exactly_five_modes(self) -> None:
        assert set(STAGE_WEIGHTS) == set(ALL_MODES)


class TestBandBoundaries:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_hosts_found_hits_discovery_band(self, mode: str) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        assert mapper.update(ScanEvent(kind="hosts_found")) == float(w.discovery)

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_port_stage_done_hits_discovery_plus_port(self, mode: str) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        expected = float(w.discovery + w.port_scan)
        assert mapper.update(ScanEvent(kind="port_stage_done")) == expected

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_deep_stage_started_hits_discovery_plus_port(self, mode: str) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        expected = float(w.discovery + w.port_scan)
        assert mapper.update(ScanEvent(kind="deep_stage_started")) == expected

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_normalize_started_hits_discovery_plus_port_plus_deep(
        self, mode: str
    ) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        expected = float(w.discovery + w.port_scan + w.deep_inspection)
        assert mapper.update(ScanEvent(kind="normalize_started")) == expected

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_completed_hits_100(self, mode: str) -> None:
        mapper = ProgressMapper(mode)
        assert mapper.update(ScanEvent(kind="completed")) == 100.0


class TestMidStageInterpolation:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_port_batch_half_done(self, mode: str) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        expected = float(w.discovery) + float(w.port_scan) * 0.5
        result = mapper.update(
            ScanEvent(kind="port_batch_done", batches_done=2, batches_total=4)
        )
        assert result == expected

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_host_inspected_quarter_done(self, mode: str) -> None:
        w = _weights(mode)
        mapper = ProgressMapper(mode)
        expected = (
            float(w.discovery)
            + float(w.port_scan)
            + float(w.deep_inspection) * 0.25
        )
        result = mapper.update(
            ScanEvent(kind="host_inspected", hosts_done=3, hosts_total=12)
        )
        assert result == expected


class TestMonotonic:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_regressing_event_never_lowers(self, mode: str) -> None:
        mapper = ProgressMapper(mode)
        high = mapper.update(ScanEvent(kind="normalize_started"))
        after = mapper.update(ScanEvent(kind="hosts_found"))
        assert after == high

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_out_of_order_sequence_only_advances(self, mode: str) -> None:
        mapper = ProgressMapper(mode)
        seen = []
        for kind in (
            "port_stage_done",
            "discovery_started",
            "hosts_found",
            "host_inspected",
        ):
            seen.append(mapper.update(ScanEvent(kind=kind)))
        assert seen == sorted(seen)


class TestHonestFailure:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_failed_returns_prior_value(self, mode: str) -> None:
        mapper = ProgressMapper(mode)
        prior = mapper.update(ScanEvent(kind="port_stage_done"))
        after = mapper.update(ScanEvent(kind="failed"))
        assert after == prior

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_failed_never_reaches_100(self, mode: str) -> None:
        mapper = ProgressMapper(mode)
        mapper.update(ScanEvent(kind="normalize_started"))
        assert mapper.update(ScanEvent(kind="failed")) != 100.0

    def test_target_pct_failed_is_none(self) -> None:
        assert target_pct(ScanEvent(kind="failed"), _weights("standard")) is None


class TestZeroTotalGuards:
    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_port_batch_zero_total_is_band_floor(self, mode: str) -> None:
        w = _weights(mode)
        result = target_pct(
            ScanEvent(kind="port_batch_done", batches_done=0, batches_total=0),
            w,
        )
        assert result == float(w.discovery)

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_host_inspected_zero_total_is_band_floor(self, mode: str) -> None:
        w = _weights(mode)
        result = target_pct(
            ScanEvent(kind="host_inspected", hosts_done=0, hosts_total=0),
            w,
        )
        assert result == float(w.discovery + w.port_scan)
