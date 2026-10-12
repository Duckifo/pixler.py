import math
import numpy as np
from typing import Any, Dict, List, Protocol, Tuple

from internal import imagedata
from internal.sorter import SortHasher
from dataclasses import dataclass

# _registry: Dict[str,SortHasher] = dict()
#
# def get_method(name: str) -> SortHasher | None:
#   return _registry.get(name)
#
# def get_methods():
#   return _registry.keys()

class HashMethodRule(Protocol):
  def Check(self, v) -> bool: ...


@dataclass(frozen=False)
class HashMethod():
  arguments: Tuple[str, HashMethodRule, Any]
  description: str | None = None


def assign_method(*, name: str, args: List[Tuple[str,HashMethodRule,Any]]):
  def decorator(cb: SortHasher) -> SortHasher:
    _registry[name] = cb  
    return cb
  return decorator

@assign_method(name="", args=[
  ("derived", IntRange, 12)
])
