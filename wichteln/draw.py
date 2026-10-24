import secrets


class NoValidAssignment(Exception):
    pass


def draw(participants, exclusions=frozenset(), rng=None, max_attempts=10_000):
    """Lost eine Zuordnung giver -> receiver aus.

    Jede Person beschenkt genau eine andere und wird genau einmal beschenkt.
    `exclusions` ist eine Menge von (giver, receiver)-Paaren, die verboten sind.
    Es wird eine zufällige Permutation gemischt, bis sie alle Regeln erfüllt;
    so ist jede gültige Zuordnung gleich wahrscheinlich.
    """
    rng = rng or secrets.SystemRandom()
    participants = list(participants)
    if len(participants) < 2:
        raise NoValidAssignment("Mindestens zwei Personen nötig.")
    for _ in range(max_attempts):
        receivers = participants[:]
        rng.shuffle(receivers)
        pairs = list(zip(participants, receivers, strict=True))
        if all(g != r and (g, r) not in exclusions for g, r in pairs):
            return dict(pairs)
    raise NoValidAssignment("Mit diesen Ausschlüssen ist keine Auslosung möglich.")
