import PIL
import numpy
import argparse
import tkinter as tk

import math
import queue
import threading

from tkinter import Event, PhotoImage, filedialog, ttk
from PIL import Image, ImageTk

from internal.methods import get_method, get_methods
from internal.sorter import Sorter
from internal.tracker import Tracker, track


# An image view object, that implements zooming and panning.
class ImageView(tk.Canvas):
  MIN_ZOOM = 0.1
  MAX_ZOOM = 64.0
  MARGIN = 256  
  GRID_MIN_ZOOM = 8.0  
  GRID_FULL_ZOOM = 16.0

  def __init__(self, parent, image: Image.Image | None = None, **kwargs):
    super().__init__(parent, highlightthickness=0, **kwargs)

    self.original: Image.Image | None = None
    if image is not None:
      self.original = image.convert("RGB")

    self.zoom = 1.0
    self.offset = [0.0, 0.0]
    self.canvas_image = self.create_image(0, 0, anchor="nw")
    self.image_tk = None
    self._img_pos = (0, 0)

    self._drag_start = None
    self._rendered = None
    self._render_pending = False

    self.bind("<Configure>", lambda e: self._schedule_render())
    self.bind("<MouseWheel>", self._on_zoom_event)
    self.bind("<Button-4>", self._on_zoom_event)  # Linux: scroll up
    self.bind("<Button-5>", self._on_zoom_event)
    self.bind("<ButtonPress-1>", self._on_pan_start)
    self.bind("<B1-Motion>", self._on_pan_move)
    self.bind("<ButtonRelease-1>", self._on_pan_end)

    self.bind("<Control-plus>", lambda e: self._zoom_at(1.25, self._center()))
    self.bind("<Control-minus>", lambda e: self._zoom_at(1 / 1.25, self._center()))
    self.bind("<Control-0>", self._reset_zoom)
    self.bind("<Enter>", lambda e: self.focus_set())
    self.focus_set()

  def set_image(self, image: Image.Image):
    self.original = image
    self._render()

  def _center(self):
    return (self.winfo_width() / 2, self.winfo_height() / 2)

  def _schedule_render(self):
    """Coalesce many requests into one render per UI cycle."""
    if not self._render_pending:
      self._render_pending = True
      self.after_idle(self._render)

  def _reset_zoom(self, e=None):
    if self.original is None: return

    w, h = self.original.size
    self.zoom = 1.0
    self.offset[0] = (self.winfo_width() - w) / 2
    self.offset[1] = (self.winfo_height() - h) / 2
    self._schedule_render()

  def _zoom_at(self, factor, at):
    if self.original is None: return

    zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
    actual = zoom / self.zoom
    if actual == 1.0:
      return

    self.offset[0] = at[0] - (at[0] - self.offset[0]) * actual
    self.offset[1] = at[1] - (at[1] - self.offset[1]) * actual
    self.zoom = zoom
    self._schedule_render()

  def _on_zoom_event(self, event):
    if event.num == 4 or event.delta > 0:
      factor = 1.1
    elif event.num == 5 or event.delta < 0:
      factor = 1 / 1.1
    else:
      return
    self._zoom_at(factor, (event.x, event.y))

  def _on_pan_start(self, event):
    if self.original is None: return

    self._drag_start = (event.x, event.y, self.offset[0], self.offset[1])
    self.config(cursor="fleur")

  def _on_pan_move(self, event):
    if self._drag_start is None:
      return
    sx, sy, ox, oy = self._drag_start
    self.offset[0] = ox + (event.x - sx)
    self.offset[1] = oy + (event.y - sy)
    self._apply_pan()

  def _on_pan_end(self, event):
    if self.original is None: return

    self._drag_start = None
    self.config(cursor="")
    self._schedule_render()  # recentre the margin around where we ended up

  def _apply_pan(self):
    if self.original is None: return

    """Move the existing rendered image; only re-render if it no longer covers the view."""
    r = self._rendered
    if r is None:
      self._schedule_render()
      return

    x0, y0, x1, y1, rox, roy = r
    dx = self.offset[0] - rox
    dy = self.offset[1] - roy

    # Where the rendered pixels are now, in screen coordinates
    sx0, sy0, sx1, sy1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy

    # What must be covered: the part of the image inside the viewport
    w, h = self.original.size
    cw, ch = self.winfo_width(), self.winfo_height()
    nx0 = max(0.0, self.offset[0])
    ny0 = max(0.0, self.offset[1])
    nx1 = min(float(cw), self.offset[0] + w * self.zoom)
    ny1 = min(float(ch), self.offset[1] + h * self.zoom)

    # 1 px tolerance for the floor/ceil rounding done in _render
    if nx0 < sx0 - 1 or ny0 < sy0 - 1 or nx1 > sx1 + 1 or ny1 > sy1 + 1:
      self._schedule_render()  # ran out of margin
      # keep moving it meanwhile so the drag never stalls

    self._draw_grid(x0, y0, x1, y1)
    self.coords(self.canvas_image, round(sx0), round(sy0))

  def _render(self):
    if self.original is None: return

    self._render_pending = False

    cw, ch = self.winfo_width(), self.winfo_height()
    if cw <= 1 or ch <= 1:
      return

    w, h = self.original.size
    z = self.zoom
    ox, oy = self.offset
    m = self.MARGIN

    # Viewport + margin, clipped to the image. Round inwards so the source box stays inside it.
    x0 = max(math.ceil(ox), -m)
    y0 = max(math.ceil(oy), -m)
    x1 = min(math.floor(ox + w * z), cw + m)
    y1 = min(math.floor(oy + h * z), ch + m)

    if x1 <= x0 or y1 <= y0:
      self.itemconfigure(self.canvas_image, image="")
      self.delete("grid")
      self.image_tk = None
      self._rendered = None
      return

    box = (
      max(0.0, (x0 - ox) / z),
      max(0.0, (y0 - oy) / z),
      min(float(w), (x1 - ox) / z),
      min(float(h), (y1 - oy) / z),
    )

    resample = Image.Resampling.NEAREST if z >= 2 else Image.Resampling.BILINEAR
    resized = self.original.resize((x1 - x0, y1 - y0), resample, box=box)

    self.image_tk = ImageTk.PhotoImage(resized)
    self.coords(self.canvas_image, x0, y0)
    self.itemconfigure(self.canvas_image, image=self.image_tk)

    self._rendered = (x0, y0, x1, y1, ox, oy)
    self._img_pos = (x0, y0)

    self._draw_grid(x0, y0, x1, y1)

  def _draw_grid(self, x0, y0, x1, y1):
    if self.original is None: return

    """Draw pixel borders over the rendered region (viewport + margin)."""
    self.delete("grid")

    z = self.zoom
    if z < self.GRID_MIN_ZOOM:
      return

    w, h = self.original.size
    ox, oy = self.offset

    # Fade in between GRID_MIN_ZOOM and GRID_FULL_ZOOM
    t = min(1.0, (z - self.GRID_MIN_ZOOM) / (self.GRID_FULL_ZOOM - self.GRID_MIN_ZOOM))
    level = int(60 + 80 * t)
    color = f"#{level:02x}{level:02x}{level:02x}"

    # Pixel index range covered by the rendered region (borders 0..w and 0..h)
    i0 = max(0, math.ceil((x0 - ox) / z))
    i1 = min(w, math.floor((x1 - ox) / z))
    j0 = max(0, math.ceil((y0 - oy) / z))
    j1 = min(h, math.floor((y1 - oy) / z))

    for i in range(i0, i1 + 1):
      x = round(ox + i * z)
      self.create_line(x, y0, x, y1, fill=color, tags="grid")

    for j in range(j0, j1 + 1):
      y = round(oy + j * z)
      self.create_line(x0, y, x1, y, fill=color, tags="grid")


def normalize(arr: numpy.ndarray) -> numpy.ndarray:
  lo, hi = arr.min(), arr.max()
  if hi == lo:
    return numpy.zeros_like(arr)
  return (arr - lo) / (hi - lo)


# WARN: current sorting does not work.
class App(tk.Tk):
  POLL_TIME = 10

  def __init__(self,
    start = False,
    method: str | None = None,
    file: str | None = None
  ):
    super().__init__()

    self.title("Pixler - Pixel Sorter")
    self.geometry("600x600")

    self.menubar = tk.Menu(self)

    # file menu
    filemenu = tk.Menu(self.menubar, tearoff=False)
    filemenu.add_command(label="Open",command=self.user_open_image)
    filemenu.add_command(label="Save",command=self.user_save_image)
    filemenu.add_separator()
    filemenu.add_command(label="Exit",command=self.quit)
    self.menubar.add_cascade(label="File",menu=filemenu)

    # tool menu
    toolmenu = tk.Menu(self.menubar, tearoff=False)
    toolmenu.add_command(label="Sort...",command=self.sort_image)

    self.method_var = tk.StringVar(self, method or "value")
    methodmenu = tk.Menu(toolmenu, tearoff=False)

    for method in get_methods():
      methodmenu.add_radiobutton(
        variable=self.method_var,
        label=method,
        value=method
      )

    toolmenu.add_cascade(label="Methods",menu=methodmenu)

    viewmenu = tk.Menu(self.menubar,tearoff=False)
    viewmenu.add_command(label="View Hashdata",command=self._view_hashdata)
    viewmenu.add_command(label="View Sorted",command=self._view_sorted)
    viewmenu.add_command(label="View Original",command=self._view_original)
    
    self.menubar.add_cascade(label="View",menu=viewmenu)
    self.menubar.add_cascade(label="Sort",menu=toolmenu)
    self.config(menu=self.menubar)

    self.imageview = ImageView(self)
    self.imageview.pack(fill="both",expand=True)
    
    # Initialize image.
    self.image: numpy.ndarray | None
    if file is not None:
      self.open_image(file)

    self.sort_result = queue.Queue()
    self.sorted_image: numpy.ndarray | None = None
    self.sorting = False

    if start: 
      self.sort_image()

  def _view_hashdata(self):
    if self.sorter is None:
      print("No hashdata available.")
      return # TODO: error

    hashdata = self.sorter.peek_hashdata()
    arr = numpy.array(hashdata, dtype=numpy.float32)
    img8 = (normalize(arr) * 255).round().astype(numpy.uint8)
    self.set_image(img8)

  def _view_sorted(self):
    if self.sorted_image is None:
      print("No sorted image available.")
      return # TODO: error

    self.set_image(self.sorted_image)

  def _view_original(self):
    if self.image is None:
      print("No image available.")
      return # TODO: error
    
    self.set_image(self.image)

  # Sets the image by a numpy matrix.
  def set_image(self, image: numpy.ndarray):
    image_PIL = Image.fromarray(image)
    self.imageview.set_image(image=image_PIL)

    self.geometry(f"{min(image_PIL.size[0],900)}x{min(image_PIL.size[1],900)}")

  # Opens an image path.
  def open_image(self, file: str):
    self.sorter = None
    self.image = numpy.array(Image.open(file).convert("RGBA"))
    self.set_image(self.image)

  def user_open_image(self):
    file = filedialog.askopenfilename(
      title="Open image.",
      filetypes=[
        ("Image Files", "*.{png,jpg,jpeg}"),
        ("All Files", "*"),
      ]
    )
    self.open_image(file)


  def user_save_image(self):
    pass # TODO: user dialogue

  def sort_image(self):
    if self.sorting is None: 
      return

    hasher = get_method(self.method_var.get())
    if hasher is None or self.image is None: 
      return

    self.sorter = Sorter(data=self.image.copy(),hasher=hasher)
    tracker = track(self.sorter)

    self.sorting = True

    def work():
      try:
        if self.sorter is None: raise Exception()
        result = self.sorter.sort(tracker=tracker)
        self.sort_result.put(("OK", result))
      except Exception as e:
        self.sort_result.put(("ERROR",e))

    threading.Thread(target=work,daemon=True).start()
    self.after(self.POLL_TIME, self._poll_sort, tracker)

  def _poll_sort(self, tracker: Tracker):
    progress = tracker.snapshot()
    print(progress.message)

    if self.sorter is not None:
      hashdata = self.sorter.peek_hashdata()
      arr = numpy.array(hashdata, dtype=numpy.float32)
      img8 = (normalize(arr) * 255).round().astype(numpy.uint8)
      self.set_image(img8)

    try:
      status, value = self.sort_result.get_nowait()
    except queue.Empty:
      self.after(self.POLL_TIME, self._poll_sort, tracker)
      return

    self.sorting = False
    self.sorted_image = value
    self.imageview.set_image(Image.fromarray(value))


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-f","--file",type=str,help="The input image.")
  parser.add_argument("-m","--method",type=str,help="The hashing method.")
  parser.add_argument("-s","--start",help="The hashing method.",action=argparse.BooleanOptionalAction)
  args = parser.parse_args()

  App(
    file=args.file, 
    method=args.method, 
    start=args.start
  ).mainloop()
