typetree
========

.. image:: https://img.shields.io/pypi/l/typetree
    :target: https://github.com/hugospinelli/typetree/blob/master/LICENSE.txt
    :alt: License
.. image:: https://img.shields.io/pypi/pyversions/typetree
    :target: https://www.python.org/downloads/release/python-3106/
    :alt: Python-Version
.. image:: https://img.shields.io/librariesio/dependents/pypi/typetree
    :target: https://github.com/hugospinelli/typetree/
    :alt: Dependencies
.. image:: https://img.shields.io/pypi/v/typetree
    :alt: PyPI-Server
    :target: https://pypi.org/project/typetree/

Generate a type tree view of a Python object's contents and attributes.
The subtrees with the same type pattern are grouped together as a
repeating structure, which forms a much more compact tree. This is very
useful, for example, for quickly identifying the overall structure of a
JSON object, which often contains many repeating type patterns.

- Includes a GUI with mouse and keyboard navigation through the nodes.

- Has Ctrl+C/double-click support for copying paths to the inner nodes.

- No external dependency.

Installation
------------
::

    pip install typetree

Examples
--------

.. role:: python(code)
   :language: python

**Nested iterables:**

.. code-block:: python

    import typetree

    d = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
    typetree.print_tree(d)

::

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

**Attributes**

Only the mutable attributes returned by :python:`vars()` are shown by default.
If you wish to view the other attributes too, use :python:`include_dir=True`.
This will search the :python:`dir()` attributes, except the special
(:python:`__special__`) and the protected (:python:`_protected`) ones.
This can be changed by setting :python:`include_special=True` and
:python:`include_protected=True`. Beware that this will drastically increase
the tree size, so you should also limit the search depth :python:`max_depth`
and/or number of branches :python:`max_branches`, or the application will
likely freeze.

.. code-block:: python

    typetree.print_tree((0,), include_dir=True, max_depth=3, max_lines=15)

::

 <tuple>[1]
 ├── .count: <builtin_function_or_method>
 ├── .index: <builtin_function_or_method>
 └── [0]: <int>
     ├── .as_integer_ratio: <builtin_function_or_method>
     ├── .bit_count: <builtin_function_or_method>
     ├── .bit_length: <builtin_function_or_method>
     ├── .conjugate: <builtin_function_or_method>
     ├── .denominator: <int>
     │   └── ...
     ├── .from_bytes: <builtin_function_or_method>
     ├── .imag: <int>
     │   └── ...
     ├── .numerator: <int>
 ...

