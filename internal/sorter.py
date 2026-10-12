import numpy as np

from internal import tracker, imagedata
from typing import Callable, List, Tuple

SortHasher = Callable[[np.ndarray, Tuple[int,int]],float]

class Sorter:
  def __init__(self, 
    data: np.ndarray,
    hasher: SortHasher,
  ):
    self._data = data
    self._hasher = hasher

    xmax, ymax = imagedata.size(self._data)
    self._hashdata = np.zeros((xmax,ymax),dtype=np.float32)

  def total_operations(self) -> int:
    return len(self._data) # TODO: update later...

  def peek_hashdata(self):
    return self._hashdata

  def _hash(self, *,
    tracker: tracker.Tracker | None = None
  ) -> np.ndarray:
    xmax, ymax = imagedata.size(self._data)

    for x in range(xmax):
        for y in range(ymax):
            self._hashdata[x,y] = self._hasher(self._data,(x,y))
        if tracker is not None: 
            tracker.iterate(f"Hashing line {x}.")

    return self._hashdata

  def sort(self, *, tracker: tracker.Tracker | None = None):
      image = self._data
      hashes = self._hash(tracker=tracker)

      order = np.argsort(hashes, axis=None)
      return image.reshape(-1, image.shape[-1])[order].reshape(image.shape)
