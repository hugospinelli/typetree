import dataclasses
import math
import multiprocessing
import threading
import tkinter as tk
from typing import Any

try:
    from ico import load_ico
except (ModuleNotFoundError, ImportError):
    from .ico import load_ico

# Make text look sharper for displays with scaling different from 100%.
# Only works for Windows.
# WARNING: This is permanently applied to the whole process, not just
# the window or the thread.
SET_DPI_AWARENESS: bool = True
try:
    # This is for calling windll.shcore.SetProcessDpiAwareness(1) on
    # the initialization of a new ViewTreeWindow object.
    from ctypes import windll
except ImportError:
    windll = None  # Not required

_PYPERCLIP_LOADED: bool = True
try:
    import pyperclip
except ModuleNotFoundError:
    _PYPERCLIP_LOADED = False  # Not required


def get_dpi():
    screen = tk.Tk()
    current_dpi = screen.winfo_fpixels('1i')
    screen.destroy()
    return current_dpi


DPI: float = get_dpi()
REFERENCE_DPI: float = 96


class TreeNode:
    font_size: int = 10
    indent_width: int = round(2.3*font_size*DPI/REFERENCE_DPI)
    row_height: int = round(2.1*font_size*DPI/REFERENCE_DPI)
    text_pad: int = round(0.2*font_size*DPI/REFERENCE_DPI)
    font: tuple[str, int] = ('Consolas', font_size)
    # Not true icon size. It picks the image in the .ico files with
    # dimensions closest to the one given by icon_size.
    icon_size: float = font_size*DPI/REFERENCE_DPI
    line_style: dict[str, Any] = {'fill': 'gray60'}  # , 'dash': (1, 1)}
    label_style: dict[str, dict[str, Any]] = {
        'normal': {
            'foreground': '#000000',
            'background': '#ffffff',
        },
        'selected': {
            'foreground': '#000000',
            'background': 'gray60',
        },
    }
    icon_files: dict[str, bytes] = {}  # Class cache for icon files

    def __init__(self, root, parent, object_tree):
        self.icon_images = {}  # Cache of PhotoImage instances for icons
        self.root = root
        self.canvas = root.canvas
        self.statusbar = root.statusbar
        self.parent = parent
        self.object_tree = object_tree
        self.state = 'expanded'
        self.is_visible = True
        self.is_selected = False
        self.children = []
        self.x = self.y = None
        self.label = None
        self.index = len(self.root.all_nodes)

        self.root.n_lines += 1
        self.lines_maxed: bool = False
        if not self.object_tree.too_deep:
            self.root.all_nodes.append(self)
            if self.object_tree.overflowed:
                self.root.n_lines += 1
        for branch in object_tree.visible_branches:
            if self.root.n_lines >= self.object_tree.max_lines:
                self.lines_maxed = True
                break
            self.children.append(TreeNode(self.root, self, branch))
            if branch.too_deep:
                break

    def update(self):
        if self.parent:
            self.parent.update()
        else:
            self.canvas['cursor'] = 'watch'
            self.canvas.update()
            self.canvas.delete(tk.ALL)
            self.draw()
            self.root.on_resize()
            # Cursor should update to 'hand2' if over a node icon
            if self.canvas['cursor'] == 'watch':
                self.canvas['cursor'] = 'arrow'

    def update_cursor(self, event):
        if event.type == tk.EventType.Enter:
            self.canvas['cursor'] = 'hand2'
        elif event.type == tk.EventType.Leave:
            self.canvas['cursor'] = 'arrow'

    def update_visibility(self):
        if self.is_visible and self.state == 'expanded':
            for child in self.children:
                child.is_visible = True
                child.update_visibility()
        else:
            for child in self.children:
                child.is_visible = False
                child.update_visibility()

    def draw(self, x=0, y=0):
        dy = self.row_height//2
        icon_width = self.draw_icon(self, x + dy, y + dy)
        self.x = x + (self.row_height + icon_width)//2 + self.text_pad
        self.y = y
        if self.object_tree.too_deep:
            self.draw_overflow(self.x, y)
            return y + self.row_height
        self.draw_text()
        x2 = x + self.indent_width
        y2 = y + self.row_height

        if not (self.children or self.lines_maxed):
            return y2
        if self.state != 'expanded':
            return y2

        line_x = x + dy
        line_y = y2 + dy
        last_y = line_y
        for child in self.children:
            last_y = line_y
            # Horizontal line
            self.canvas.create_line(line_x, line_y,
                                    line_x + self.indent_width, line_y,
                                    **self.line_style)
            y2 = child.draw(x2, y2)
            line_y = y2 + dy
        # noinspection PyUnboundLocalVariable
        if (self.lines_maxed or (self.object_tree.overflowed
                                 and not child.object_tree.too_deep)):
            self.draw_overflow(line_x - self.text_pad, y2)
            last_y = y2 + self.row_height//4  # Small additional line
            y2 += self.row_height

        # Vertical line
        _id = self.canvas.create_line(line_x, y + dy, line_x, last_y,
                                      **self.line_style)
        self.canvas.tag_lower(_id)  # Display under the icons

        return y2

    def draw_icon(self, node, x, y):
        if not node.object_tree.expandable:
            return 0
        if node.state == 'expanded':
            icon_name = 'minus'
            callback = node.collapse
        else:
            icon_name = 'plus'
            callback = node.expand
        image = self.get_icon_image(icon_name)
        _id = self.canvas.create_image(x, y, image=image)
        self.canvas.tag_bind(_id, '<1>', callback)
        self.canvas.tag_bind(_id, '<Double-1>', callback)
        self.canvas.tag_bind(_id, '<Enter>', self.update_cursor)
        self.canvas.tag_bind(_id, '<Leave>', self.update_cursor)
        x1, y1, x2, y2 = self.canvas.bbox(_id)
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        if x1 <= x <= x2 and y1 <= y <= y2:
            self.canvas['cursor'] = 'hand2'
        return image.width()

    def draw_text(self):
        text_x = self.x
        text_y = self.y
        text = self.object_tree.node_str or ''
        if self.label is None:
            self.label = tk.Label(self.canvas, text=text, bd=0,
                                  padx=self.text_pad, pady=self.text_pad,
                                  font=self.font)
        if self.is_selected:
            self.label.configure(self.label_style['selected'])
        else:
            self.label.configure(self.label_style['normal'])

        height = self.label.winfo_reqheight()
        text_y += (self.row_height - height)//2
        self.canvas.create_window(text_x, text_y,
                                  anchor='nw', window=self.label)
        self.label.bind('<1>', self.select)
        self.label.bind('<Double-1>', self.copy)

    def draw_overflow(self, x, y):
        self.canvas.create_text(
            x, y, text='...', anchor='nw',
            font=self.font, fill=self.label_style['normal']['foreground']
        )

    def select(self, _=None, update_yview=True, update_last_selected=True):
        if self.is_selected:
            return
        self.deselect_all()
        self.is_selected = True
        if update_last_selected:
            self.root.last_selected = self
            path = self.object_tree.path
            text = f'Path: {path}' if path else ''
            self.root.statusbar.config(text=text)
        self.root.selected = self
        self.draw_text()
        if update_yview:
            self.update_yview()

    def deselect(self, _=None):
        if not self.is_selected:
            return
        self.is_selected = False
        self.root.selected = None
        if self.is_visible:
            self.draw_text()

    def deselect_all(self):
        if self.root.selected is None:
            return
        self.root.selected.deselect()

    def expand(self, _=None):
        if not self.object_tree.expandable:
            self.select()
            return
        if self.state != 'expanded':
            self.state = 'expanded'
            self.update_visibility()
            self.update()
            if child := self.has_last_selected():
                child.select(update_yview=False, update_last_selected=False)
            self.update_yview(from_expand=True)

    def collapse(self, _=None):
        if not self.object_tree.expandable:
            return
        if self.state != 'collapsed':
            self.state = 'collapsed'
            self.update_visibility()
            if (self.root.last_selected is not None and
                    self.root.last_selected.is_grandchild(self)):
                self.select(update_last_selected=False)
            self.update()

    def update_yview(self, from_expand=False):
        top = self.y
        if from_expand:
            bottom = self.visible_children_bottom()
            selected = self.root.selected
            if selected is not None and selected.is_grandchild(self):
                selected_bottom = selected.y + self.row_height
            else:
                selected_bottom = self.y + self.row_height
        else:
            bottom = top + self.row_height
            selected_bottom = bottom
        height = bottom - top
        visible_top = self.canvas.canvasy(0)
        visible_height = self.canvas.winfo_height()
        visible_bottom = self.canvas.canvasy(visible_height)
        if visible_top <= top and bottom <= visible_bottom:
            return
        _, y1, _, y2 = map(int, self.canvas['scrollregion'].split())
        canvas_height = y2 - y1
        if top >= visible_top and height <= visible_height:
            rows = (bottom - visible_height)/self.row_height
        elif selected_bottom - top > visible_height:
            rows = (selected_bottom - visible_height)/self.row_height
        else:
            rows = top/self.row_height
        rows = math.ceil(rows)
        self.canvas.yview_moveto(rows*self.row_height/canvas_height)

    def is_grandchild(self, other):
        if self.parent == other:
            return True
        if self.parent is None:
            return False
        return self.parent.is_grandchild(other)

    def has_last_selected(self):
        """Return a visible grandparent if found"""
        if not self.is_selected or not self.is_visible:
            return None
        child = self.root.last_selected
        if child is None or not child.is_grandchild(self):
            return None
        while not child.is_visible:
            child = child.parent
        return child

    def visible_children_bottom(self):
        """Bottom y coordinate of visible children"""
        if self.children and self.state == 'expanded':
            bottom = self.children[-1].visible_children_bottom()
            if self.object_tree.overflowed:
                return bottom + self.row_height
            return bottom
        elif self.object_tree.overflowed:
            return self.y + 2*self.row_height
        return self.y + self.row_height

    def get_icon_image(self, file_name):
        if file_name in self.icon_images:
            return self.icon_images[file_name]
        try:
            icon_data = self.icon_files[file_name]
        except KeyError:
            icon_data = load_ico(file_name, self.icon_size)
            self.icon_files[file_name] = icon_data
        image = tk.PhotoImage(master=self.canvas, data=icon_data)
        self.icon_images[file_name] = image
        return image

    def copy(self, _=None):
        """Called on a double click on the item."""
        if not self.is_selected:
            raise Exception('Copy called without being selected')
        if not (path := self.object_tree.path):
            return 'break'
        if _PYPERCLIP_LOADED:
            # Preferred method
            pyperclip.copy(path)
        else:
            # Tkinter does not really copy to clipboard until a paste
            # occurs before the window is closed.
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.root.update()
        self.root.statusbar.config(text=f'Copied path to clipboard: {path}')
        return 'break'

    def destroy(self):
        for c in self.children[:]:
            self.children.remove(c)
            c.destroy()
        self.parent = None


class ScrollbarFrame(tk.Frame):
    """A frame with vertical and horizontal scrollbars. The horizontal
    one automatically hides when it is disabled."""

    def __init__(self, master, *, row_height=5, mouse_wheel_rows=3, **opts):
        self.row_height = row_height
        self.mouse_wheel_rows = mouse_wheel_rows

        super().__init__(master, **opts)

        self.master = master
        self.canvas = tk.Canvas(self, yscrollincrement=row_height, **opts)
        self.vbar = tk.Scrollbar(self, orient="vertical",
                                 command=self.on_vbar)
        self.hbar = tk.Scrollbar(self, orient="horizontal",
                                 command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.configure(xscrollcommand=self.hbar.set)

        self.vbar.pack(side="right", fill="y")
        self.hbar.pack(side="bottom", fill="x")
        self.is_hbar_packed = True
        self.canvas.pack(side="left", fill="both", expand=True)

        self.frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw",
                                  tags="self.frame")

        self.master.bind("<Configure>", self.on_resize)
        self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind_all('<Button-4>', self.on_mouse_wheel)
        self.canvas.bind_all('<Button-5>', self.on_mouse_wheel)

        self.canvas.bind('<Key-Prior>', self.page_up)
        self.canvas.bind('<Key-Next>', self.page_down)

        self.on_resize()
        self.canvas.focus_set()

    def on_resize(self, _=None):
        """Reset the scroll region to encompass the inner frame"""
        _, _, x, y = self.canvas.bbox(tk.ALL)
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w >= x:
            if self.is_hbar_packed:
                h += self.hbar.winfo_height()
                self.toggle_hbar()
        elif not self.is_hbar_packed:
            h -= self.hbar.winfo_height()
            self.toggle_hbar()

        y = self.row_height*math.ceil(y/self.row_height) + 1
        w = max(w, x)
        h = max(h, y)
        self.canvas.itemconfigure('inner', width=w, height=h)
        self.canvas.configure(scrollregion=(0, 0, w, h))

    def toggle_hbar(self):
        if self.is_hbar_packed:
            self.hbar.pack_forget()
            self.is_hbar_packed = False
            return
        self.canvas.pack_forget()
        self.hbar.pack(side="bottom", fill="x")
        self.hbar.config(command=self.canvas.xview)
        self.is_hbar_packed = True
        self.canvas.pack(side="left", fill="both", expand=True)

    def page_up(self, _):
        self.canvas.yview_scroll(-1, 'pages')
        return 'break'

    def page_down(self, _):
        self.canvas.yview_scroll(1, 'pages')
        return 'break'

    def unit_up(self, _):
        self.canvas.yview_scroll(-1, 'units')
        return 'break'

    def unit_down(self, _):
        self.canvas.yview_scroll(1, 'units')
        return 'break'

    def on_vbar(self, *args):
        _, y1, _, y2 = map(int, self.canvas['scrollregion'].split())
        h = y2 - y1
        y1 = self.canvas.yview()[0]

        match args:
            case 'moveto', str():
                dy = float(args[1]) - y1
            case 'scroll', str(), 'units':
                dy = int(args[1])*self.row_height/h
            case _:
                self.canvas.yview(*args)
                return

        y2 = y1 + self.canvas.winfo_height()/h
        if y1 + dy < 0:
            self.canvas.yview_moveto(0)
        elif y2 + dy > 1:
            d_rows = math.ceil((1 - y2)*h/self.row_height)
            dy = d_rows*self.row_height/h
            self.canvas.yview_moveto(y1 + dy)
        else:
            self.canvas.yview_moveto(y1 + dy)

    def on_mouse_wheel(self, event):
        sign = 0
        if event.type == tk.EventType.MouseWheel:
            sign = 1 if event.delta < 0 else -1
        elif event.type == tk.EventType.ButtonPress:
            if event.num == 4:
                sign = -1
            elif event.num == 5:
                sign = 1
        units = sign*self.mouse_wheel_rows
        self.on_vbar('scroll', str(units), 'units')


class ViewTreeWindow(tk.Tk):
    width = 540
    height = 720

    def __init__(self, object_tree):

        # Make text look sharper for displays with scaling different
        # from 100%. Only works for Windows.
        # WARNING: This is permanently applied to the whole process, not
        # just the window or the thread.
        if SET_DPI_AWARENESS and windll is not None:
            windll.shcore.SetProcessDpiAwareness(1)

        super().__init__()
        self.title('Tree View')
        self.geometry(f'{self.width}x{self.height}')

        self.sf = ScrollbarFrame(self, row_height=TreeNode.row_height,
                                 bg='white', borderwidth=0,
                                 highlightthickness=0, takefocus=1)
        self.canvas = self.sf.canvas
        self.statusbar = tk.Label(self, text='', bd=1,
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.sf.pack(expand=True, fill='both', side=tk.TOP)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.sf.on_resize()

        self.selected = None
        self.last_selected = None
        self.all_nodes = []
        self.n_lines: int = 0
        self.object_tree = object_tree
        self.node = TreeNode(self, None, object_tree)
        self.node.update()
        self.node.expand()
        self.node.select()

        self.bind('<Control-c>', self.copy)
        self.bind('<Key-Up>', self.move_up)
        self.bind('<Key-Down>', self.move_down)
        self.bind('<Key-Left>', self.collapse)
        self.bind('<Key-Right>', self.expand)

        try:
            images_data = load_ico('icon.ico')
            images = [tk.PhotoImage(data=data) for data in images_data]
            self.iconphoto(False, *images)
        except (FileNotFoundError, tk.TclError):
            pass

        self.focus_force()

    def on_resize(self):
        self.sf.on_resize()

    def copy(self, _=None):
        if self.selected is None:
            return 'break'
        self.selected.copy()

    def move_up(self, _=None):
        if self.selected is None:
            return 'break'
        index = max(self.selected.index, 1)
        for node in self.all_nodes[index - 1::-1]:
            if node.is_visible:
                node.select()
                return

    def move_down(self, _=None):
        if self.selected is None:
            return 'break'
        index = self.selected.index
        for node in self.all_nodes[index + 1:]:
            if node.is_visible:
                node.select()
                break

    def collapse(self, _=None):
        if self.selected is None:
            return 'break'
        if self.selected.is_visible:
            self.selected.collapse()
        else:
            self.move_up()

    def expand(self, _=None):
        if self.selected is None:
            return 'break'
        if self.selected.is_visible:
            self.selected.expand()
        else:
            self.move_down()


@dataclasses.dataclass
class PicklableObjectTree:
    visible_branches: tuple['PicklableObjectTree', ...]
    node_str: str
    path: str
    expandable: bool
    overflowed: bool
    too_deep: bool
    max_lines: float

    def __init__(self, object_tree):
        self.visible_branches = tuple(map(PicklableObjectTree,
                                          object_tree.visible_branches))
        self.node_str = object_tree.node_str
        self.path = object_tree.path
        self.expandable = object_tree.expandable
        self.overflowed = object_tree.overflowed
        self.too_deep = object_tree.too_deep
        self.max_lines = object_tree.max_lines


def tree_window_loop(object_tree):
    window = ViewTreeWindow(object_tree)
    window.mainloop()


def tree_viewer(object_tree, *, spawn_thread=True, spawn_process=False):
    object_tree = PicklableObjectTree(object_tree)
    if spawn_process:
        multiprocessing.Process(target=tree_window_loop,
                                args=(object_tree,)).start()
    elif spawn_thread:
        threading.Thread(target=tree_window_loop, args=(object_tree,),
                         daemon=True).start()
    else:
        tree_window_loop(object_tree)
