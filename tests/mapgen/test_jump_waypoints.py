"""A 16 ly hop cannot span 16.4 ly; a midpoint can."""

from starroute.mapgen.jump_waypoints import hop_count, waypoints_between, gap_fillers_for_pairs


def test_sixteen_cannot_span_sixteen_point_four():
    assert hop_count(16.4, 16) == 2
    pts = waypoints_between(0, 0, 0, 16.4, 0, 0, 16)
    assert len(pts) == 1
    x, y, z = pts[0]
    assert abs(x - 8.2) < 1e-9
    assert y == 0 and z == 0
    assert x <= 16
    assert 16.4 - x <= 16


def test_one_filler_when_gap_is_just_over_the_hop():
    fillers = gap_fillers_for_pairs(
        [{"a": "HD 141004", "b": "GJ 649", "ax": 0, "ay": 0, "az": 0, "bx": 16.38, "by": 0, "bz": 0}],
        16,
    )
    assert len(fillers) == 1
    assert fillers[0]["legs"] == 2
    assert fillers[0]["x"] == 8.19


def test_no_filler_when_already_in_range():
    assert waypoints_between(0, 0, 0, 15.9, 0, 0, 16) == []
    assert hop_count(15.9, 16) == 1


def test_prefers_existing_low_score_star_over_inventing():
    from starroute.mapgen.jump_waypoints import find_existing_bridge

    hosts = [
        {"hostname": "Hub", "x": 8.2, "y": 0, "z": 0, "sy_pnum": 4, "combined_score": 9},
        {"hostname": "Dim", "x": 8.0, "y": 0.2, "z": 0, "sy_pnum": 0, "combined_score": 0.1},
        {"hostname": "Far", "x": 40, "y": 0, "z": 0, "sy_pnum": 0, "combined_score": 0},
    ]
    pick = find_existing_bridge(0, 0, 0, 16.4, 0, 0, hosts, 16)
    assert pick["hostname"] == "Dim"


def test_no_existing_bridge_when_nearest_neighbor_already_over_the_hop():
    """If A's nearest star is 16.4 ly, nothing else is within 16 ly of A."""
    from starroute.mapgen.jump_waypoints import find_existing_bridge

    hosts = [
        {"hostname": "A", "x": 0, "y": 0, "z": 0, "sy_pnum": 1, "combined_score": 1},
        {"hostname": "B", "x": 16.4, "y": 0, "z": 0, "sy_pnum": 1, "combined_score": 1},
    ]
    assert find_existing_bridge(0, 0, 0, 16.4, 0, 0, hosts, 16, skip={"A", "B"}) is None
