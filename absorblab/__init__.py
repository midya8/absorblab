"""AbsorbLab: exact supplied finite-chain first-hit evidence."""


def analyze(request):
    from .core import analyze as run

    return run(request)


__all__ = ["analyze"]
