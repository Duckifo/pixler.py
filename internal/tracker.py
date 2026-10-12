import math
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy

@dataclass(frozen=False)
class Progress:
  completed: int
  start_time_ms: float
  total: int | None = None
  message: str | None = None

  @property
  def fraction(self) -> float | None:
    if not self.total: return None
    return min(self.completed / self.total, 1.0)

  @property
  def age(self) -> float:
    return time.time() * 1000.0 - self.start_time_ms
  
@runtime_checkable
class Trackable(Protocol):
  def total_operations(self) -> int: ...
    

# Poll driven operation tracker.
class Tracker:
  def __init__(self, total: int):
    self._completed = 0
    self._total = total
    self._message: str | None = None
    self._start_time_ms = time.time() * 1000.0

  def snapshot(self):
    return Progress(
      completed = self._completed,
      total = self._total,
      message = self._message,
      start_time_ms=self._start_time_ms
    )

  def iterate(self, message: str | None,  steps: int = 1):
    self._completed += steps
    self._message = message


# Create an tracker from a class object that implements Trackable.
def track(object: Trackable) -> Tracker:
  return Tracker(object.total_operations()) 
