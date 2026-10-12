from typing import Tuple

import numpy as np

# Returns the aspects of the image in pixels. 
def size(img: np.ndarray):
  return (len(img), len(img[1]))

def crop(img: np.ndarray, xy: Tuple[int, int], rad: int) -> np.ndarray:
    x, y = xy
    h, w = img.shape[:2]

    out = np.empty((2 * rad + 1, 2 * rad + 1, 4), dtype=img.dtype)
    out[:] = img[y, x]

    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            sx, sy = x + dx, y + dy

            if 0 <= sx < w and 0 <= sy < h:
                out[dy + rad, dx + rad] = img[sy, sx]

    return out
