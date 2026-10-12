import math
import numpy as np
from typing import Dict, List, Tuple

from internal import imagedata
from internal.sorter import Sorter, SortHasher

_registry: Dict[str,SortHasher] = dict()

def get_method(name: str) -> SortHasher | None:
  return _registry.get(name)

def get_methods():
  return _registry.keys()


def assign_method(*, name: str):
  def decorator(cb: SortHasher) -> SortHasher:
    _registry[name] = cb  
    return cb
  return decorator

@assign_method(name="value")
def _(d: np.ndarray, xy: Tuple[int,int]):
  return d[xy].sum(dtype=np.int32) / 4

RAD = 2

def make_weights(rad: int) -> np.ndarray:
  ys, xs = np.mgrid[-rad:rad + 1, -rad:rad + 1]
  dist = np.abs(xs) + np.abs(ys)
  return 1 - dist / (2 * rad + 1)

_WEIGHTS = make_weights(RAD)

@assign_method(name="closeness")
def _(d: np.ndarray, xy: Tuple[int, int]):
  r, c = xy                      # same convention as your d[xy]
  h, w = d.shape[:2]

  # Clip the window to the image
  r0, r1 = max(0, r - RAD), min(h, r + RAD + 1)
  c0, c1 = max(0, c - RAD), min(w, c + RAD + 1)
  area = d[r0:r1, c0:c1].astype(np.int32)

  # Matching slice of the weight kernel, so the center stays aligned
  wts = _WEIGHTS[r0 - (r - RAD):r1 - (r - RAD),
                 c0 - (c - RAD):c1 - (c - RAD)]

  diff = np.abs(area - d[r, c].astype(np.int32))
  if diff.ndim == 3:             # RGB: sum the channels
    diff = diff.sum(axis=2)

  return float((wts * diff).sum())

@assign_method(name="random")
def _(d: np.ndarray, xy: Tuple[int, int]):
  return np.random.randint(0,255)

def fib(n):
  if n <= 0:
    return 0
  elif n == 1:
    return 1
  else:
    return fib(n - 1) + fib(n - 2)

@assign_method(name="fibonacci")
def _(d: np.ndarray, xy: Tuple[int, int]):
  i = 0
  value = d[xy].sum(dtype=np.int32) / 4
  while True:
    n = fib(i)
    i += 1
    if n > value:
      break

  fib1 = fib(i)
  fib2 = fib(i-1)
  
  return min(abs(value - fib1),abs(value - fib2))

  
@assign_method(name="@position-y")
def _(d: np.ndarray, xy: Tuple[int, int]):
  WAVES = 4
  xmax, ymax = imagedata.size(d)
  
  return ymax/WAVES % (xy[1] if xy[1] != 0 else 1)

@assign_method(name="@sine-1")
def _(d: np.ndarray, xy: Tuple[int, int]):
  value = d[xy].sum(dtype=np.int32) / 4
  return math.sin((xy[0]+xy[1]) / value)
