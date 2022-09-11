# -*- coding: utf-8 -*-

import dataclasses
import enum
import functools
import json
import re

from collections.abc import Callable
from typing import Any

try:
    from viewer import tree_viewer
except (ModuleNotFoundError, ImportError):
    from .viewer import tree_viewer

__all__ = [
    'Tree',
    'print_tree',
    'view_tree',
]

_DEFAULT_MAX_BRANCHES = 20
_DEFAULT_MAX_DEPTH = 10
_DEFAULT_MAX_SEARCH = 1000
_DEFAULT_MAX_LINES = 1000

# Pre-compiled format for _KeyType.INDEX and _KeyType.SLICE
_RANGE_REGEX = re.compile(r'^\[(\d+)(?::(\d+))?]$')


@functools.total_ordering
class _KeyType(enum.Enum):
    """Node key types. When printed, each type will display
    the key differently based on their type."""

    # For the root node, which has no key
    NONE = 0

    # For object attributes (starts with a dot)
    # Example: .attr
    ATTR = 1

    # For Mapping keys
    # Examples: ['key'], [datetime.date(1970, 1, 1)]
    MAP = 2

    # For Sequence indices or slices
    # Examples: [2], [4:7]
    INDEX = 3

    # For Collection, which has no key, but has an item counter
    # Example: (×3)
    SET = 4

    @classmethod
    def path(cls, key_type: '_KeyType', value: Any = None) -> str:
        match key_type, value:
            case cls.NONE, None:
                return ''
            case cls.NONE, str():
                return value
            case cls.ATTR, _:
                return f'.{value!s}'
            case cls.MAP, _:
                return f'[{value!r}]'
            case cls.SET, int():
                return ''
            case cls.INDEX, int():
                return f'[{value}]'
            case cls.INDEX, None:
                return '[:]'
            case cls.INDEX, (int(x), int(y)):
                if x + 1 == y:
                    return f'[{x}]'
                if x == 0:
                    return f'[:{y}]'
                return f'[{x}:{y}]'
        raise TypeError(f"Invalid key type '{key_type}' or value '{value}'")

    @classmethod
    def str(cls, key_type: '_KeyType', value: Any = None) -> str:
        match key_type, value:
            case cls.NONE, None:
                return ''
            case cls.SET, int():
                return '(×{:d}) '.format(value)
            case _:
                return f'{cls.path(key_type, value)}: '

    def __lt__(self, other: '_KeyType'):
        if not isinstance(other, type(self)):
            return TypeError
        return self.value < other.value


@functools.total_ordering
class _NodeKey:
    """Node key for string representation and for sorting"""

    def __init__(self, key_type: _KeyType, value: Any = None):
        self._str: str = _KeyType.str(key_type, value)
        self._path: str = _KeyType.path(key_type, value)
        self._type: _KeyType = key_type
        self._counter: int = 1
        if key_type == _KeyType.SET:
            self._counter = value
        self._slice: tuple[int, int] | None = None
        if key_type == _KeyType.INDEX:
            if isinstance(value, int):
                self._slice = value, value + 1
            else:
                self._slice = value
        self._hash: int = hash((
            type(self),
            self._type,
            self._slice,
            id(self)*(self._type == _KeyType.SET)
        ))

    @property
    def path(self) -> str:
        return self._path

    @property
    def type(self) -> _KeyType:
        return self._type

    @property
    def counter(self) -> int:
        return self._counter

    @property
    def slice(self) -> tuple[int, int]:
        return self._slice

    def reset_counter(self):
        self._counter = 1
        self._str = _KeyType.str(self.type, self._counter)

    def increment_counter(self):
        self._counter += 1
        self._str = _KeyType.str(self.type, self._counter)

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self})'

    def __eq__(self, other: '_NodeKey') -> bool:
        if not isinstance(other, type(self)):
            raise TypeError
        if self._type == other._type == _KeyType.SET:
            return False
        return self._str == other._str

    def __lt__(self, other: '_NodeKey') -> bool:
        if not isinstance(other, type(self)):
            raise TypeError
        if self._str == other._str:
            return False
        if self._slice is not None:
            if other._slice is None:
                return self._type < other._type
            return self._slice < other._slice
        if self._type == other._type:
            return self._str < other._str
        return self._type < other._type

    def __hash__(self) -> int:
        return self._hash


# noinspection PyUnresolvedReferences
@dataclasses.dataclass(slots=True, frozen=True)
class Config:
    """Configuration class for generating a new Tree.

    Attributes:
        items_lookup: Function used to access the node's content.
        type_name_lookup: Function used to get the type name.
        value_lookup: Function used to get the value when the node's
            content is empty (tree leaves).
        sort_keys: Flag for sorting keys alphabetically.
        show_lengths: Flag for displaying lengths of iterables. This
            affects how subtrees are grouped together, since sequences
            with different sizes but same content types will be
            considered equivalent.
        include_attributes: Flag for including the mutable attributes
            returned by vars().
        include_dir: Flag for including the attributes returned by
            dir(), except the protected (_protected) and special
            (__special__) ones.
        include_protected: Flag for including the protected (_protected)
            attributes.
        include_special: Flag for including the special (__special__)
            attributes.
        max_branches: Maximum number of branches displayed on each node.
            This only applies after grouping. Can be disabled by setting
            it to float('inf') or math.inf.
        max_depth: Maximum display depth. Beware that the true search
            depth is one higher than specified. Can be disabled by
            setting it to float('inf') or math.inf (not recommended).
        max_search: Maximum number of nodes searched. Can be disabled
            by setting it to float('inf') or math.inf.
        max_lines: Maximum number of lines to be printed. For the GUI,
            it is the maximum number of rows to be displayed, not
            including the extra ellipsis at the end. Can be disabled by
            setting it to float('inf') or math.inf.
    """
    items_lookup: Callable[[Any], Any] = lambda var: var
    type_name_lookup: Callable[[Any], str] = lambda var: type(var).__name__
    value_lookup: Callable[[Any], Any] = lambda var: var
    sort_keys: bool = True
    show_lengths: bool = True
    include_attributes: bool = True
    include_dir: bool = False
    include_protected: bool = False
    include_special: bool = False
    max_branches: float = _DEFAULT_MAX_BRANCHES
    max_depth: float = _DEFAULT_MAX_DEPTH
    max_search: float = _DEFAULT_MAX_SEARCH
    max_lines: float = _DEFAULT_MAX_LINES


class _MaxSearchError(Exception):
    """Reached maximum number of nodes to be searched"""
    pass


class _Node:
    """Non-recursive tree node"""

    def __init__(self, var: Any, node_key: _NodeKey, config: Config,
                 nodes_visited: int, ancestors_ids: set):

        self.key: _NodeKey = node_key
        self.path: str = node_key.path
        self.config: Config = config
        self.nodes_visited: int = nodes_visited
        self.ancestors_ids: set = ancestors_ids
        var_id: int = id(var)
        # TODO: check for infinite recursion
        if var_id in self.ancestors_ids:
            ...
        self.ancestors_ids.add(var_id)

        self.type_name: str
        try:
            # noinspection PyArgumentList
            self.type_name = self.config.type_name_lookup(var)
        except AttributeError:
            self.type_name = '?'
        original_var: Any = var
        # noinspection PyArgumentList
        var = self.config.items_lookup(var)

        # These refer to the contents of Maps or Sequences
        self.items_key_type: _KeyType = _KeyType.NONE
        self.items_len: int | None = None
        self.get_items_info(var, original_var)

        self.branches: dict[_NodeKey, Any] = {}
        try:
            if self.config.include_attributes and hasattr(var, '__dict__'):
                for key, value in vars(var).items():
                    if self.include_attr(key):
                        self.add_branch(_KeyType.ATTR, key, value)
            if self.config.include_dir:
                for key in dir(var):
                    if self.include_attr(key):
                        try:
                            value = getattr(var, key)
                        except AttributeError:
                            continue
                        self.add_branch(_KeyType.ATTR, key, value)
            match self.items_key_type:
                case _KeyType.MAP:
                    for key, value in var.items():
                        self.add_branch(_KeyType.MAP, key, value)
                case _KeyType.INDEX:
                    for index, value in enumerate(var):
                        self.add_branch(_KeyType.INDEX, index, value)
                case _KeyType.SET:
                    for value in var:
                        self.add_branch(_KeyType.SET, 1, value)
        except _MaxSearchError:
            pass

        self.var_repr: str = f'<{self.type_name}>'
        if self.config.show_lengths and self.items_len is not None:
            self.var_repr = f'{self.var_repr}[{self.items_len}]'

    def get_items_info(self, var: Any, original_var: Any):
        """Check which kind of iterable var is, if any, and return the
        _KeyType associated with its content and its size. Return
        (_KeyType.NONE, None) if var is not a simple finite iterable."""
        try:
            size = len(var)
        except TypeError:
            return
        if size == 0:
            try:
                # noinspection PyArgumentList
                var = self.config.value_lookup(original_var)
            except AttributeError:
                return
            # Continue: value_lookup might return itself and var might
            # be an empty Sequence
            try:
                size = len(var)
            except TypeError:
                return
        if isinstance(var, str | bytes | bytearray):
            return
        try:
            # Since Maps are usually also Sequences, the priority is
            # to access the Map items. But if the keys do not match
            # their Sequence values, the priority inverts.
            assert size == len(var.keys()) == len(var.items())
            assert all(key1 == key2 for key1, key2 in zip(var, var.keys()))
            assert all(var[key] == value for key, value in var.items())
            self.items_key_type = _KeyType.MAP
            self.items_len = size
            return
        except (AttributeError, TypeError, KeyError, AssertionError):
            pass
        try:
            assert all(var[index] == value for index, value in enumerate(var))
        except (KeyError, TypeError, AssertionError):
            try:
                next(iter(var))
            except (TypeError, KeyError):
                return
            except StopIteration:
                pass
            self.items_key_type = _KeyType.SET
            self.items_len = size
            return
        self.items_key_type = _KeyType.INDEX
        self.items_len = size
        return

    def add_branch(self, key_type: _KeyType, key: Any, value: Any):
        if self.nodes_visited >= self.config.max_search:
            raise _MaxSearchError
        node_key = _NodeKey(key_type, key)
        self.branches[node_key] = value
        self.nodes_visited += 1

    def include_attr(self, key: str) -> bool:
        if key.startswith('__') and key.endswith('__'):
            return self.config.include_special
        if key.startswith('_'):
            return self.config.include_protected
        return True

    def __str__(self) -> str:
        return f'{self.key}{self.var_repr}'

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self})'


@functools.total_ordering
class SubTree:
    """A recursive object tree structure"""

    def __init__(self, obj: Any, node_key: _NodeKey, config: Config,
                 nodes_visited: int, ancestors_ids: set, depth: int):
        self._key: _NodeKey = node_key
        self.config: Config = config
        nodes_visited += 1  # Include itself
        self._overflowed: bool = False
        if nodes_visited >= self.config.max_search:
            self._overflowed = True
        self._node: _Node = _Node(obj, self._key, self.config,
                                  nodes_visited, ancestors_ids)

        self._node_text: str = ' . . .'
        self._branches: tuple[SubTree, ...] = ()
        self._visible_branches: tuple[SubTree, ...] = ()
        depth += 1  # Include itself
        self._too_deep: bool = depth > self.config.max_depth
        branches: list[SubTree] = []
        if not (self._too_deep or self._overflowed):
            for _node_key, var in self._node.branches.items():
                branch: SubTree = SubTree(var, _node_key, self.config,
                                          nodes_visited, ancestors_ids, depth)
                nodes_visited = branch._node.nodes_visited
                branches.append(branch)
                if nodes_visited >= self.config.max_search:
                    self._overflowed = True
                    break
            self._branches = tuple(branches)
            self._group_branches()
            self._node_text = str(self._node)
            # noinspection PyTypeChecker
            max_branches: int = min(len(self._branches),
                                    self.config.max_branches)
            self._visible_branches = tuple(self._branches[:max_branches])
        self._overflowed = self._overflowed or (len(self._branches)
                                                > self.config.max_branches)
        self._expandable: bool = bool(self._visible_branches)

        self._hash: int = hash((
            self._node.var_repr,
            self._node.key.type,
            tuple(map(hash, self._branches))
        ))

        self._path: str = self._key.path
        self._update_paths()

    @property
    def key(self) -> _NodeKey:
        return self._key

    @property
    def branches(self) -> tuple['SubTree', ...]:
        return self._branches

    @property
    def node_text(self) -> str:
        return self._node_text

    @property
    def path(self) -> str:
        return self._path

    @property
    def expandable(self) -> bool:
        return self._expandable

    @property
    def too_deep(self) -> bool:
        return self._too_deep

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    @property
    def visible_branches(self) -> tuple['SubTree', ...]:
        return self._visible_branches

    @staticmethod
    def _group_to_map(v: list[set[int]]) -> dict[tuple[int, int], int]:
        """Argument v is a list of indices grouped in sets that map to
        the same structure in a Sequence tree. Their positions indicate
        where they map to. Example:
            branches = [A, B, A, A, C, A, B]
            unique_branches = [A, B, C]
            v = [{0, 2, 3, 5}, {1, 6}, {4}]
        means that A shows in indices v[0] = {0, 2, 3, 5}, B shows in
        indices v[1] = {1, 6}, and C shows in v[2] = {4}.
            The return value is a dict of sequential ranges of indices
        as keys and their mapping to unique_branches. In the previous
        case it will return {(0, 1): 0, (1, 2): 1, (2, 4): 0, (4, 5): 2,
        (5, 6): 0, (6, 7): 1}."""

        if not v:
            return {}
        u = {}
        for k, s in enumerate(v):
            if not s:
                continue
            sv = list(sorted(s))
            su = [(sv[0], sv[0] + 1)]
            for x in sv[1:]:
                if x == su[-1][1]:
                    su[-1] = (su[-1][0], x + 1)
                else:
                    su.append((x, x + 1))
            for x in su:
                u[x] = k
        # noinspection PyTypeChecker
        return dict(sorted(u.items()))

    def _group_branches(self):
        if not self._branches:
            return
        # Group unique consecutive Sequence branches and
        # unique Collection branches
        unique_index_branches: list[SubTree] = []
        all_index_branches: list[list[SubTree]] = []
        index_keys: list[set[int]] = []
        unique_set_branches: list[SubTree] = []
        added_branches: list[SubTree] = []
        for branch in self._branches:
            if branch._key.type == _KeyType.INDEX:
                range_key = range(*branch._key.slice)
                try:
                    index = unique_index_branches.index(branch)
                except ValueError:
                    unique_index_branches.append(branch)
                    all_index_branches.append([branch])
                    index_keys.append(set(range_key))
                else:
                    all_index_branches[index].append(branch)
                    index_keys[index].update(range_key)
            elif branch._key.type == _KeyType.SET:
                try:
                    index = unique_set_branches.index(branch)
                except ValueError:
                    branch._key.reset_counter()
                    unique_set_branches.append(branch)
                else:
                    unique_set_branches[index]._key.increment_counter()
            else:
                added_branches.append(branch)

        unique_index_branches.clear()
        for _range, index in self._group_to_map(index_keys).items():
            branch = all_index_branches[index].pop()
            if self.config.show_lengths:
                branch._update_key(_NodeKey(_KeyType.INDEX, _range))
            else:
                branch._update_key(_NodeKey(_KeyType.INDEX, None))
            unique_index_branches.append(branch)
        unique_index_branches = list(sorted(unique_index_branches,
                                            key=lambda x: x.key))

        for branch in unique_set_branches:
            branch._update_key(branch._key)

        self._branches = tuple(added_branches + unique_index_branches
                               + unique_set_branches)
        if self.config.sort_keys:
            self._branches = tuple(sorted(self._branches,
                                          key=lambda x: x.key))
        else:
            self._branches = tuple(sorted(self._branches,
                                          key=lambda x: x.key.type))

    def _update_key(self, new_key: _NodeKey):
        self._key = new_key
        self._node.key = new_key
        self._node_text = str(self._node)
        self._update_paths()

    def _update_paths(self, parent_path: str = ''):
        if self._key.type == _KeyType.SET:
            self._path = f'{parent_path}.copy().pop()'
        else:
            self._path = f'{parent_path}{self._key.path}'
        for branch in self._branches:
            branch._update_paths(self._path)

    def _get_tree_lines(self, root_pad: str = '',
                        branch_pad: str = '') -> list[str]:
        if self._too_deep and self._node.branches:
            return [f'{root_pad}{self._node}',
                    f'{branch_pad}└── ...']

        lines: list[str] = [f'{root_pad}{self._node}']
        if not self._visible_branches:
            return lines

        branches: tuple[SubTree, ...] = self._visible_branches
        if not self._overflowed:
            branches = self._visible_branches[:-1]
        for branch in branches:
            lines.extend(branch._get_tree_lines(
                root_pad=f'{branch_pad}├── ',
                branch_pad=f'{branch_pad}│   ',
            ))
        if self._overflowed:
            lines.append(f'{branch_pad}...')
        else:
            # noinspection PyProtectedMember
            lines.extend(self._branches[-1]._get_tree_lines(
                root_pad=f'{branch_pad}└── ',
                branch_pad=f'{branch_pad}    ',
            ))
        if len(lines) > self.config.max_lines:
            del lines[self.config.max_lines - 1:]
            lines.append(' ...')
        return lines

    def get_dict(self) -> str | dict[str, str | dict]:
        if not self._branches:
            return str(self._node)
        return {
            str(branch._node): branch.get_dict()
            for branch in self._branches
        }

    def __eq__(self, other: 'SubTree') -> bool:
        if not isinstance(other, type(self)):
            raise TypeError
        if self._hash != other._hash:
            return False
        if self._node.var_repr != other._node.var_repr:
            return False
        if self._node.key.type != other._node.key.type:
            return False
        return self._branches == other._branches

    def __lt__(self, other: 'SubTree') -> bool:
        if not isinstance(other, type(self)):
            raise TypeError
        if self == other:
            return False
        if self._node.key.type != other._node.key.type:
            if self._node.key.type is None:
                return True
            if other._node.key.type is None:
                return False
            return self._node.key.type < other._node.key.type
        if self._node.var_repr != other._node.var_repr:
            return self._node.var_repr < other._node.var_repr
        if len(self._branches) != len(other._branches):
            return len(self._branches) < len(other._branches)
        for x, y in zip(self._branches, other._branches):
            if x != y:
                return x < y
        return False

    def __str__(self) -> str:
        return f'{self._node!s}{{...}}'

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self!s})'

    def __hash__(self) -> int:
        return self._hash


class Tree(SubTree):
    """Build a recursive object tree structure"""

    def __init__(self, obj: Any, key_text: str | None = None, **kwargs):
        config = Config(**kwargs)
        super().__init__(obj, _NodeKey(_KeyType.NONE, key_text), config,
                         nodes_visited=1, ancestors_ids={id(obj)}, depth=0)

    def json(self, *args, **kwargs) -> str:
        return json.dumps(self.get_dict(), *args, **kwargs)

    def save_json(self, filename, *args,
                  encoding='utf-8',
                  ensure_ascii=False,
                  indent=4,
                  **kwargs):

        with open(filename, 'w', encoding=encoding) as file:
            json.dump(self.get_dict(), file, *args,
                      ensure_ascii=ensure_ascii,
                      indent=indent,
                      **kwargs)

    def get_tree_str(self) -> str:
        return '\n'.join(self._get_tree_lines(' ', ' '))

    def print(self):
        """Print a tree view of the object's type structure"""
        print(self.get_tree_str())

    def view(self, spawn_thread: bool = True, spawn_process: bool = False):
        """Show a tree view of the object's type structure in an
        interactive Tkinter window."""
        tree_viewer(self,
                    spawn_thread=spawn_thread,
                    spawn_process=spawn_process)


def print_tree(obj: Any, **kwargs):
    """Print a tree view of the object's type structure"""
    Tree(obj, **kwargs).print()


def view_tree(obj: Any, *,
              spawn_thread: bool = True,
              spawn_process: bool = False,
              **kwargs):
    """Show a tree view of the object's type structure in an interactive
    Tkinter window."""
    Tree(obj, **kwargs).view(spawn_thread=spawn_thread,
                             spawn_process=spawn_process)


if __name__ == '__main__':
    d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
    print_tree(d1, show_lengths=False)
    print()

    obj1 = Tree(0)
    print_tree(obj1, include_dir=True, max_depth=3, max_lines=15)
    print()

    import urllib.request
    import xml.etree.ElementTree
    url1 = 'https://www.w3schools.com/xml/simple.xml'
    with urllib.request.urlopen(url1) as response1:
        r1 = response1.read()
    text1 = str(r1, encoding='utf-8')
    tree1 = xml.etree.ElementTree.fromstring(text1)
    print_tree(
        tree1,
        type_name_lookup=lambda x: x.tag,
        value_lookup=lambda x: x.text,
    )
    print()

    import xml.dom.minidom
    dom1 = xml.dom.minidom.parseString(text1)
    print_tree(
        dom1,
        items_lookup=lambda x: x.childNodes,
        type_name_lookup=lambda x: x.nodeName,
        value_lookup=lambda x: x.text,
        max_search=15,
    )
    print()

    print_tree((0,), include_dir=True, max_depth=2, max_lines=15)
    print()

    url2 = 'https://archive.org/metadata/TheAdventuresOfTomSawyer_201303'
    with urllib.request.urlopen(url2) as response2:
        r2 = response2.read()
    text2 = str(r2, encoding='utf-8')
    json2 = json.loads(text2)
    view_tree(json2)
