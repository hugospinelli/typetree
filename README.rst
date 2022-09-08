Generate a tree view for a Python object by recursively showing their
content types. Equivalent sub-trees are grouped together to represent
repeating structures.

- Includes a GUI with mouse and keyboard navigation through the nodes.

- Has Ctrl+C/double-click support for copying paths to the inner nodes.

- No external dependency.

Example:

.. code-block:: python

   d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
   print_tree(d1)

Output::

 <list>[2]
 ├── [0]: <set>[8]
 │   ├── (×1) <float>
 │   ├── (×2) <int>
 │   ├── (×2) <tuple>[2]
 │   │   └── [0:2]: <int>
 │   └── (×3) <str>
 └── [1]: <dict>[2]
     ├── ['a']: <int>
     └── ['b']: <ellipsis>

