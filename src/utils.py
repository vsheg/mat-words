from itertools import islice
from typing import Iterable, TypeVar

T = TypeVar('T')


def chunks(it: Iterable[T], size: int) -> Iterable[tuple[T, ...]]:
    it = iter(it)
    while ch := tuple(islice(it, size)):
        yield ch
