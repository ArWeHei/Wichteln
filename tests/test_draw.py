import collections
import random

import pytest

from wichteln.draw import NoValidAssignment, draw


@pytest.mark.parametrize("n", [2, 3, 4, 10, 50])
def test_everyone_gives_and_receives_once_never_self(n):
    people = list(range(n))
    for _ in range(50):
        result = draw(people)
        assert set(result) == set(people)
        assert sorted(result.values()) == people
        assert all(g != r for g, r in result.items())


def test_exclusions_are_respected():
    exclusions = {("a", "b"), ("b", "a")}
    for _ in range(50):
        result = draw(["a", "b", "c", "d"], exclusions)
        assert ("a", result["a"]) not in exclusions
        assert ("b", result["b"]) not in exclusions


def test_impossible_exclusions_raise():
    exclusions = {("a", "b"), ("a", "c")}
    with pytest.raises(NoValidAssignment):
        draw(["a", "b", "c"], exclusions, max_attempts=200)


def test_needs_two_people():
    with pytest.raises(NoValidAssignment):
        draw(["a"])


def test_roughly_uniform_for_three():
    rng = random.Random(1)
    counts = collections.Counter(tuple(draw([0, 1, 2], rng=rng).items()) for _ in range(2000))
    assert len(counts) == 2
    assert all(800 < c < 1200 for c in counts.values())
