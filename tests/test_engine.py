"""Unit tests for the violation engine. Run from project root:  python -m pytest tests -q"""
from ai.violations.engine import NoHelmet, WrongWay, RedLight


def veh(i, box, cls="motorcycle", conf=0.9):
    return dict(cls=cls, conf=conf, box=box, id=i)


def head(box, cls="Without Helmet", conf=0.8):
    return dict(cls=cls, conf=conf, box=box, id=None)


def test_no_helmet_needs_confirm_frames():
    r = NoHelmet(confirm=3)
    m = [veh(1, [100, 200, 200, 300])]
    h = [head([130, 150, 170, 190])]
    assert r.check(m, h) == [] and r.check(m, h) == []
    out = r.check(m, h)
    assert len(out) == 1 and out[0]["type"] == "No Helmet"


def test_no_helmet_low_conf_ignored():
    r = NoHelmet(confirm=1)
    assert r.check([veh(1, [100, 200, 200, 300])], [head([130, 150, 170, 190], conf=0.3)]) == []


def test_with_helmet_is_not_violation():
    r = NoHelmet(confirm=1)
    assert r.check([veh(1, [100, 200, 200, 300])], [head([130, 150, 170, 190], cls="With Helmet")]) == []


def test_wrong_way_detected():
    r = WrongWay(allowed=(1, 0), window=5, min_px=40)
    out = []
    for k in range(6):  # moves right->left, allowed is left->right
        out = r.check([veh(7, [500 - 20 * k, 100, 540 - 20 * k, 140], cls="car")])
    assert out and out[0]["type"] == "Wrong Way"


def test_right_way_not_flagged():
    r = WrongWay(allowed=(1, 0), window=5, min_px=40)
    out = []
    for k in range(6):
        out = r.check([veh(7, [100 + 20 * k, 100, 140 + 20 * k, 140], cls="car")])
    assert out == []


def test_red_light_crossing_only_when_red():
    r = RedLight(((0, 400), (1280, 400)))
    r.check([veh(3, [100, 300, 140, 380], cls="car")], True)       # above line
    out = r.check([veh(3, [100, 420, 140, 500], cls="car")], True)  # crossed
    assert out and out[0]["type"] == "Red Light"
    r2 = RedLight(((0, 400), (1280, 400)))
    r2.check([veh(3, [100, 300, 140, 380], cls="car")], False)
    assert r2.check([veh(3, [100, 420, 140, 500], cls="car")], False) == []
