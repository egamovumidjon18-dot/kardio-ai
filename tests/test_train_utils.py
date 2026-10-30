import numpy as np
import pytest

pytest.importorskip("torch")
from research.train_pcg import auroc, choose_thresholds  # noqa: E402


def decide(s, low, high):
    return np.where(s >= high, 1, np.where(s <= low, 0, -1))   # -1 = abstain


def test_thresholds_separable_classes_give_perfect_decisions():
    y = np.array([1, 1, 0, 0])
    s = np.array([0.9, 0.8, 0.2, 0.75])
    low, high = choose_thresholds(y, s, min_sens=0.95, min_spec=0.90)
    assert list(decide(s, low, high)) == [1, 1, 0, 0]


def test_thresholds_respect_sensitivity_and_specificity():
    rng = np.random.default_rng(0)
    y = np.r_[np.ones(200), np.zeros(800)].astype(int)
    s = np.r_[rng.beta(5, 2, 200), rng.beta(2, 5, 800)]
    low, high = choose_thresholds(y, s, min_sens=0.95, min_spec=0.90)
    assert low < high
    assert np.mean(s[y == 1] > low) >= 0.95        # ko'p shovqinlar "yo'q" deb o'tkazilmaydi
    assert np.mean(s[y == 0] < high) >= 0.90


def test_auroc_matches_known_values():
    assert auroc(np.array([0, 0, 1, 1]), np.array([0.1, 0.4, 0.35, 0.8])) == pytest.approx(0.75)
    assert auroc(np.array([0, 1]), np.array([0.5, 0.5])) == pytest.approx(0.5)
