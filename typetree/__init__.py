"""Main interface for generating and visualizing an object's type tree.

- Use :class:`Tree` to generate the type tree as an object, which can be
  traversed as a subclass of a nested tuple.
- Use :func:`print_tree` to directly print the tree view.
- Use :func:`view_tree` to open the tree view as an interactive GUI.
"""

from .typetree import *

__version__ = '0.1.5'

__all__ = [
    'Tree',
    'Subtree',
    'print_tree',
    'view_tree',
    'Template',
    'DOM',
    'HTML',
    'XML',
    'KeyType'
]
