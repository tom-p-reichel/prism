"""
Provides (sequence) alignment algorithms and utilities.
"""
import heapq
from typing import Callable, List, Optional, Sequence, Tuple, TypeVar, Union

import numpy as np

T = TypeVar('T')
LeftMatch = Tuple[T, Optional[T]]
"""
A pair of aligned items that is guaranteed to have a non-null left item.
"""
RightMatch = Tuple[Optional[T], T]
"""
A pair of aligned items that is guaranteed to have a non-null right
item.
"""


def lazy_align(
        a: Sequence[T],
        b: Sequence[T],
        calign: Callable[[T,
                          T],
                         float],
        cskip: Callable[[T],
                        float],
        return_cost: bool = False) -> List[Union[LeftMatch,
                                                 RightMatch]]:
    """
    Align two sequences according to provided cost functions.

    A generic implementation of the global alignment algorithm.

    Parameters
    ----------
    a : Sequence[T]
        A sequence of elements.
    b : Sequence[T]
        Another sequence of elements.
    calign : Callable[[T,T], float]
        A function that defines the cost of aligning two elements.
        Must be nonnegative, e.g., ``lambda x, y: x != y``, which
        returns a cost of 1 for matching two elements that are not the
        same, and a cost of 0 for matching two elements that are the
        same.
    cskip : Callable[[T], float]
        A function that defines the cost of skipping an element in an
        alignment.
        Must be nonnegative, e.g., ``lambda x: len(x)``, which defines
        the cost of skipping an element as the length of that element.
    return_cost : bool, optional
        If True, then return the cost of the alignment in addition to
        the alignment.

    Returns
    -------
    cost : float, optional
        The total cost of the alignment.
        Returned only if `return_cost` is True.
    alignment : List[Union[LeftMatch, RightMatch]]
        The 'alignment'.
        For example, here is an edit distance alignment between
        ``'smarts'`` and ``'cat'``::

            [('s', 'c'),
             ('m', None),
             ('a', 'a'),
             ('r', None),
             ('t', 't'),
             ('s', None)]

        What this alignment means, in order:

        #. Misaligned 's' and 'c', incurring a penalty of 1.

        #. Aligned 'm' in 'smart' with nothing in 'cat',
           incurring a penalty of 1.

        #. Aligned 'a''s from both words. no penalty.

        #. Aligned 'r' from 'smart' with nothing in 'cat'. Penalty of 1.

        #. Aligned 't''s from both words, finishing 'cat'.

        #. forced to align 's' from 'smarts' with nothing

        An alignment represents a transformation from one string to
        another incurring the minimum cost, where cost is defined by the
        functions given as arguments.

        It is a list of tuples whose first element is an element from
        the first sequence, and the second element is an element from
        the second sequence.

        Elements may be None if the algorithm has decided to skip/insert
        an element.

    Notes
    -----
    This implementation is LAZY, and has linear best case performance,
    but falls back to the quadratic worst case time of the typical
    alignment algorithm if the things it is asked to align
    are very different.
    """
    # DP table
    D = np.zeros([len(a) + 1, len(b) + 1]) + np.infty
    D[0, 0] = 0

    # backtracking table
    BT = np.zeros([len(a) + 1, len(b) + 1, 2], dtype="int32")

    heap = [(0, 0, 0)]

    neighbors = np.array([[1, 0], [1, 1], [0, 1]])

    cx, cy = None, None

    end = (len(a), len(b))

    while (cx, cy) != end:
        candidate = heapq.heappop(heap)
        # x,y are inverted so that heap properly tiebreaks.
        # we prefer things closer to the end.
        nc, cx, cy = candidate[0], -candidate[1], -candidate[2]
        costs = (
            cskip(a[cx]) if cx < len(a) else np.infty,
            calign(a[cx],
                   b[cy]) if cx < len(a) and cy < len(b) else np.infty,
            cskip(b[cy]) if cy < len(b) else np.infty)
        for c, (x, y) in zip(costs, (cx, cy) + neighbors):
            # bounds check
            if (x > len(a) or y > len(b)):
                continue
            nc = c + D[cx, cy]
            if (nc < D[x, y]):
                D[x, y] = nc
                BT[x, y] = (cx, cy)
                heapq.heappush(heap, (nc, -x, -y))

    x, y = len(a), len(b)

    alignment = []

    while (x, y) != (0, 0):
        # backtrack once.
        nx, ny = BT[x, y]
        alignment.append((a[nx] if nx < x else None, b[ny] if ny < y else None))
        x, y = nx, ny

    if return_cost:
        return D[-1, -1], alignment[::-1]
    else:
        return alignment[::-1]