|icon| typetree
===============

.. |icon| image:: https://raw.githubusercontent.com/hugospinelli/typetree/master/typetree/icons/icon.ico

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

Install only typetree (no external dependency)::

    pip install typetree

Include pyperclip_ for better clipboard support (optional)::

    pip install typetree[clipboard]

.. _pyperclip: https://pypi.org/project/pyperclip/

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
 │   │   └── [:2]: <int>
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

    typetree.print_tree((0,), include_dir=True, max_depth=2, max_lines=15)

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
     ├── .imag: <...> <int>
     │   └── ...
     ├── .numerator: <...> <int>
 ...

Note that the last two items have a special tag :code:`<...>` which means it
has identified an infinite recursion.

**XML etree integration**

Use :python:`type_name_lookup` to specify how to retrieve the string to be
displayed as the type name. End nodes of XML etrees are empty tuples, so
the parameter :python:`value_lookup` should also be given to specify how to
retrieve their values.

.. code-block:: python

    import urllib.request
    import xml.etree.ElementTree

    url = 'https://www.w3schools.com/xml/simple.xml'
    with urllib.request.urlopen(url) as response:
        r = response.read()
    text = str(r, encoding='utf-8')
    tree = xml.etree.ElementTree.fromstring(text)

    typetree.print_tree(
        tree,
        type_name_lookup=lambda x: x.tag,
        value_lookup=lambda x: x.text,
    )

::

 <breakfast_menu>[5]
 └── [:5]: <food>[4]
     ├── [0]: <name>
     ├── [1]: <price>
     ├── [2]: <description>
     └── [3]: <calories>

**DOM integration**

DOM objects are not directly iterable. Child nodes must be accessed through
attribute lookup, which can be specified by the parameter
:python:`items_lookup`:

.. code-block:: python

    import xml.dom.minidom

    dom = xml.dom.minidom.parseString(text)

    typetree.print_tree(
        dom,
        items_lookup=lambda x: x.childNodes,
        type_name_lookup=lambda x: x.nodeName,
        value_lookup=lambda x: x.text,
        max_lines=10,
    )

::

 <#document>[1]
 └── [0]: <breakfast_menu>[11]
     ├── [0]: <#text>
     ├── [1]: <food>[9]
     │   ├── [0]: <#text>
     │   ├── [1]: <name>[1]
     │   │   └── [0]: <#text>
     │   ├── [2]: <#text>
     │   ├── [3]: <price>[1]
 ...

Alternatively, you can use configuration templates:

.. code-block:: python

    typetree.print_tree(dom, template=typetree.DOM, max_lines=10)

Which gives the same output.

**Interactive GUI**

.. code-block:: python

    import json

    url2 = 'https://archive.org/metadata/TheAdventuresOfTomSawyer_201303'

    with urllib.request.urlopen(url2) as response2:
        r2 = response2.read()
    text2 = str(r2, encoding='utf-8')
    json2 = json.loads(text2)

    typetree.view_tree(json2)

.. image:: https://raw.githubusercontent.com/hugospinelli/typetree/master/docs/source/_static/GUI_Example1.png
   :align: center

- Double click or press Ctrl+C to copy the path to the selected node.
- Use right-click on the plus/minus icons to expand/collapse each of the inner
  nodes without affecting the node you clicked on.
- You can use the arrow keys to navigate and the space bar instead of
  the right-click.

Parameters
----------

**Configuration parameters**

.. code-block:: python

    items_lookup: Callable[[Any], Any] = lambda var: var
    type_name_lookup: Callable[[Any], str] = lambda var: type(var).__name__
    value_lookup: Callable[[Any], Any] = lambda var: var
    sort_keys: bool = True
    show_lengths: bool = True
    include_attributes: bool = True
    include_dir: bool = False
    include_protected: bool = False
    include_special: bool = False
    max_lines: float = 1000
    max_search: float = 100_000
    max_depth: float = 20
    max_branches: float = float('inf')

- :python:`items_lookup`: Function used to access the node's content.
- :python:`type_name_lookup`: Function used to get the type name.
- :python:`value_lookup`: Function used to get the value when the node's
  content is empty (tree leaves).
- :python:`sort_keys`: Flag for sorting keys alphabetically.
- :python:`show_lengths`: Flag for displaying lengths of iterables. This
  affects how subtrees are grouped together, since sequences with different
  sizes but same content types are considered equivalent.
- :python:`include_attributes`: Flag for including the mutable attributes
  returned by :python:`vars`.
- :python:`include_dir`: Flag for including the attributes returned by
  :python:`dir`, except the protected (:python:`_protected`) and the special
  (:python:`__special__`) ones.
- :python:`include_protected`: Flag for including the protected
  (:python:`_protected`) attributes.
- :python:`include_special`: Flag for including the special
  (:python:`__special__`) attributes.
- :python:`max_lines`: Maximum number of lines to be printed. For the GUI,
  it is the maximum number of rows to be displayed, not including the extra
  ellipsis at the end. Can be disabled by setting it to infinity
  (:python:`float('inf')` or :python:`math.inf`).
- :python:`max_search`: Maximum number of nodes searched.
- :python:`max_depth`: Maximum search depth.
- :python:`max_branches`: Maximum number of branches displayed on each
  node. This only applies after grouping.

Additionally, there are also helper classes of configuration templates for
common object types. Currently, the templates are:

- :python:`Template` (default)
- :python:`DOM`
- :python:`HTML`
- :python:`XML`

These templates can be passed to the parameter :python:`template`.

**GUI**

For the GUI, both the :python:`Tree(...).view` method and the
:python:`view_tree` function accept two additional arguments to configure
whether the new window is created asynchronously and by which method
(threading or multiprocessing):

.. code-block:: python

    spawn_thread: bool = True
    spawn_process: bool = False

