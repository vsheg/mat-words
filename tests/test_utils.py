from src.utils import chunks


def test_iter_chunks():
    assert list(chunks([], 1)) == []
    assert list(chunks([1, 2, 3], 1)) == [(1,), (2,), (3,)]
    assert list(chunks([1, 2, 3], 2)) == [(1, 2), (3,)]
    assert list(chunks([1, 2, 3], 3)) == [(1, 2, 3)]
    assert list(chunks([1, 2, 3], 4)) == [(1, 2, 3)]
