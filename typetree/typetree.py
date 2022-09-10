# -*- coding: utf-8 -*-

import enum
import functools
import json
import re

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

_INF = float('inf')
_DEFAULT_MAX_BRANCHES = 20
_DEFAULT_MAX_DEPTH = 10
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
            case cls.ATTR, _:
                return '.{!s}'.format(value)
            case cls.MAP, _:
                return '[{!r}]'.format(value)
            case cls.SET, int():
                return ''
            case cls.INDEX, int():
                return '[{:d}]'.format(value)
            case cls.INDEX, (int(x), int(y)):
                if x + 1 == y:
                    return '[{:d}]'.format(x)
                # Need unpacking: *value
                return '[{:d}:{:d}]'.format(x, y)
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


class _Node:
    """Non-recursive tree node"""

    def __init__(self, var: Any, node_key: _NodeKey, *,
                 show_lengths: bool = True,
                 show_attributes: bool = True,
                 include_dir: bool = False,
                 include_protected: bool = False,
                 include_special: bool = False):

        self.key: _NodeKey = node_key
        self.path = node_key.path
        self.show_lengths: bool = show_lengths
        self.show_attributes: bool = show_attributes
        self.include_dir: bool = include_dir
        self.include_protected: bool = include_protected
        self.include_special: bool = include_special

        self.type: type = type(var)

        # These refer to the contents of Maps or Sequences
        self.items_key_type: _KeyType
        self.items_len: int | None
        self.items_key_type, self.items_len = self.get_var_items_info(var)

        self.branches: dict[_NodeKey, Any] = {}
        if self.show_attributes and hasattr(var, '__dict__'):
            for key, value in vars(var).items():
                if self.include_attr(key):
                    _node_key = _NodeKey(_KeyType.ATTR, key)
                    self.branches[_node_key] = value
        if self.include_dir:
            for key in dir(var):
                if self.include_attr(key):
                    _node_key = _NodeKey(_KeyType.ATTR, key)
                    if _node_key not in self.branches:
                        try:
                            self.branches[_node_key] = getattr(var, key)
                        except AttributeError:
                            pass
        match self.items_key_type:
            case _KeyType.MAP:
                for key, value in var.items():
                    _node_key = _NodeKey(_KeyType.MAP, key)
                    self.branches[_node_key] = value
            case _KeyType.INDEX:
                for index, value in enumerate(var):
                    _node_key = _NodeKey(_KeyType.INDEX, index)
                    self.branches[_node_key] = value
            case _KeyType.SET:
                for value in var:
                    _node_key = _NodeKey(_KeyType.SET, 1)
                    self.branches[_node_key] = value

        self.var_repr: str
        try:
            self.var_repr = f'<{self.type.__name__}>'
        except AttributeError:
            self.var_repr = repr(self.type)
        if self.show_lengths and self.items_len is not None:
            self.var_repr = f'{self.var_repr}[{self.items_len}]'

    @staticmethod
    def get_var_items_info(var: Any) -> tuple[_KeyType, int | None]:
        """Check which kind of iterable var is, if any, and return the
        _KeyType associated with its content and its size. Return
        (_KeyType.NONE, None) if var is not a simple finite iterable."""
        try:
            size = len(var)
        except TypeError:
            return _KeyType.NONE, None
        if isinstance(var, str | bytes | bytearray):
            return _KeyType.NONE, None
        try:
            # Since Maps are usually also Sequences, the priority is
            # to access the Map items. But some objects might return
            # different lengths for .items() and iter(). In this case,
            # the priority is the iter() values.
            assert len(var.items()) == size
            assert all(var[key] == value for key, value in var.items())
            return _KeyType.MAP, size
        except (AttributeError, TypeError, KeyError, AssertionError):
            pass
        try:
            assert all(var[index] == value for index, value in enumerate(var))
        except (KeyError, TypeError, AssertionError):
            try:
                iter(var)
            except TypeError:
                return _KeyType.NONE, None
            return _KeyType.SET, size
        return _KeyType.INDEX, size

    def include_attr(self, key: str) -> bool:
        if key.startswith('__') and key.endswith('__'):
            return self.include_special
        if key.startswith('_'):
            return self.include_protected
        return True

    def __str__(self) -> str:
        return f'{self.key}{self.var_repr}'

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self})'


@functools.total_ordering
class Tree:
    """Build a recursive object tree structure"""

    def __init__(self, obj: Any, *,
                 sort_keys: bool = True,
                 show_lengths: bool = True,
                 show_attributes: bool = True,
                 include_dir: bool = False,
                 include_protected: bool = False,
                 include_special: bool = False,
                 max_branches: float | None = _DEFAULT_MAX_BRANCHES,
                 max_depth: float | None = _DEFAULT_MAX_DEPTH,
                 max_lines: float | None = _DEFAULT_MAX_LINES,
                 node_key: _NodeKey | None = None):

        self._key: _NodeKey
        if node_key is None:
            self._key = _NodeKey(_KeyType.NONE)
        else:
            self._key = node_key
        self._sort_keys: bool = sort_keys
        self._show_lengths: bool = show_lengths
        self._show_attributes: bool = show_attributes
        self._include_dir: bool = include_dir
        self._include_protected: bool = include_protected
        self._include_special: bool = include_special

        self._max_branches: float = _INF
        if max_branches is not None:
            self._max_branches = max_branches

        self._max_depth: float = _INF
        if max_depth is not None:
            self._max_depth = max_depth

        self._max_lines: float = _INF
        if max_lines is not None:
            self._max_lines = max_lines

        self._node: _Node = _Node(
            obj, self._key,
            show_lengths=self._show_lengths,
            show_attributes=self._show_attributes,
            include_dir=self._include_dir,
            include_protected=self._include_protected,
            include_special=self._include_special
        )

        if branch_max_depth := self._max_depth:
            branch_max_depth -= 1
        self._node_str: str = ' . . .'
        self._branches: tuple[Tree, ...] = tuple()
        self._visible_branches: tuple[Tree, ...] = tuple()
        self._too_deep: bool = self._max_depth < 1
        if not self._too_deep:
            self._branches = tuple(
                Tree(
                    var,
                    sort_keys=self._sort_keys,
                    show_lengths=self._show_lengths,
                    show_attributes=self._show_attributes,
                    include_dir=self._include_dir,
                    include_protected=self._include_protected,
                    include_special=self._include_special,
                    max_branches=self._max_branches,
                    max_depth=branch_max_depth,
                    max_lines=self._max_lines,
                    node_key=_node_key,
                ) for _node_key, var in self._node.branches.items()
            )
            self._group_branches()
            self._node_str = str(self._node)
            # noinspection PyTypeChecker
            max_branches: int = min(len(self._branches), self._max_branches)
            self._visible_branches = tuple(self._branches[:max_branches])
        self._overflowed: bool = len(self._branches) > self._max_branches
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
    def sort_keys(self) -> bool:
        return self._sort_keys

    @property
    def show_lengths(self) -> bool:
        return self._show_lengths

    @property
    def show_attributes(self) -> bool:
        return self._show_attributes

    @property
    def include_dir(self) -> bool:
        return self._include_dir

    @property
    def include_protected(self) -> bool:
        return self._include_protected

    @property
    def include_special(self) -> bool:
        return self._include_special

    @property
    def max_branches(self) -> float:
        return self._max_branches

    @property
    def max_depth(self) -> float:
        return self._max_depth

    @property
    def max_lines(self) -> float:
        return self._max_lines

    @property
    def branches(self) -> tuple['Tree', ...]:
        return self._branches

    @property
    def node_str(self) -> str:
        return self._node_str

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
    def visible_branches(self) -> tuple['Tree', ...]:
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
        unique_index_branches: list[Tree] = []
        all_index_branches: list[list[Tree]] = []
        index_keys: list[set[int]] = []
        unique_set_branches: list[Tree] = []
        added_branches: list[Tree] = []
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
            branch._update_key(_NodeKey(_KeyType.INDEX, _range))
            unique_index_branches.append(branch)
        unique_index_branches = list(sorted(unique_index_branches,
                                            key=lambda x: x.key))

        for branch in unique_set_branches:
            branch._update_key(branch._key)

        self._branches = tuple(added_branches + unique_index_branches
                               + unique_set_branches)
        if self._sort_keys:
            self._branches = tuple(sorted(self._branches,
                                          key=lambda x: x.key))
        else:
            self._branches = tuple(sorted(self._branches,
                                          key=lambda x: x.key.type))

    def _update_key(self, new_key: _NodeKey):
        self._key = new_key
        self._node.key = new_key
        self._node_str = str(self._node)
        self._update_paths()

    def _update_paths(self, parent_path: str = ''):
        if self._key.type == _KeyType.SET:
            self._path = f'{parent_path}.copy().pop()'
        else:
            self._path = f'{parent_path}{self._key.path}'
        for branch in self._branches:
            branch._update_paths(self._path)

    def _get_tree_lines(self, root_pad: str = '', branch_pad: str = '', *,
                        max_depth: float | None = None,
                        max_branches: float | None = None,
                        max_lines: float | None = None, ) -> list[str]:
        if max_depth is None:
            max_depth = self._max_depth
        elif max_depth > self._max_depth:
            raise ValueError('Maximum depth cannot be increased')

        if max_branches is None:
            max_branches = self._max_branches

        if max_lines is None:
            max_lines = self._max_lines

        max_depth -= 1
        if max_depth < 1 and self._node.branches:
            return [f'{root_pad}{self._node}',
                    f'{branch_pad}└── ...']

        lines = [f'{root_pad}{self._node}']
        if not self._branches:
            return lines

        last_index = int(min(max_branches, len(self._branches) - 1))
        for branch in self._branches[:last_index]:
            lines.extend(branch._get_tree_lines(
                root_pad=f'{branch_pad}├── ',
                branch_pad=f'{branch_pad}│   ',
                max_depth=max_depth,
                max_branches=max_branches,
                max_lines=max_lines
            ))
        if len(self._branches) > max_branches:
            lines.append(f'{branch_pad}...')
        elif last_index >= 0:
            # noinspection PyProtectedMember
            lines.extend(self._branches[last_index]._get_tree_lines(
                root_pad=f'{branch_pad}└── ',
                branch_pad=f'{branch_pad}    ',
                max_depth=max_depth,
                max_branches=max_branches,
                max_lines=max_lines
            ))
        if len(lines) > max_lines:
            del lines[max_lines - 1:]
            lines.append(' ...')
        return lines

    def get_tree_str(self) -> str:
        return '\n'.join(self._get_tree_lines(' ', ' '))

    def print(self):
        """Print a tree view of the object's type structure"""
        print(self.get_tree_str())

    def get_dict(self) -> str | dict[str, str | dict]:
        if not self._branches:
            return str(self._node)
        return {
            str(branch._node): branch.get_dict()
            for branch in self._branches
        }

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

    def view(self, spawn_thread=True, spawn_process=False):
        """Show a tree view of the object's type structure in an
        interactive Tkinter window."""
        tree_viewer(self, spawn_thread=spawn_thread,
                    spawn_process=spawn_process)

    def __eq__(self, other: 'Tree') -> bool:
        if not isinstance(other, type(self)):
            raise TypeError
        if self._hash != other._hash:
            return False
        if self._node.var_repr != other._node.var_repr:
            return False
        if self._node.key.type != other._node.key.type:
            return False
        return self._branches == other._branches

    def __lt__(self, other: 'Tree') -> bool:
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


def print_tree(obj: Any, *,
               sort_keys: bool = True,
               show_lengths: bool = True,
               show_attributes: bool = True,
               include_dir: bool = False,
               include_protected: bool = False,
               include_special: bool = False,
               max_branches: float | None = _DEFAULT_MAX_BRANCHES,
               max_depth: float | None = _DEFAULT_MAX_DEPTH,
               max_lines: float | None = _DEFAULT_MAX_LINES):
    """Print a tree view of the object's type structure"""
    Tree(
        obj,
        sort_keys=sort_keys,
        show_lengths=show_lengths,
        show_attributes=show_attributes,
        include_dir=include_dir,
        include_protected=include_protected,
        include_special=include_special,
        max_branches=max_branches,
        max_depth=max_depth,
        max_lines=max_lines
    ).print()


def view_tree(obj: Any, spawn_thread=True, spawn_process=False, *,
              sort_keys: bool = True,
              show_lengths: bool = True,
              show_attributes: bool = True,
              include_dir: bool = False,
              include_protected: bool = False,
              include_special: bool = False,
              max_branches: float | None = _DEFAULT_MAX_BRANCHES,
              max_depth: float | None = _DEFAULT_MAX_DEPTH,
              max_lines: float | None = _DEFAULT_MAX_LINES):
    """Show a tree view of the object's type structure in an interactive
    Tkinter window."""
    Tree(
        obj,
        sort_keys=sort_keys,
        show_lengths=show_lengths,
        show_attributes=show_attributes,
        include_dir=include_dir,
        include_protected=include_protected,
        include_special=include_special,
        max_branches=max_branches,
        max_depth=max_depth,
        max_lines=max_lines
    ).view(spawn_thread=spawn_thread, spawn_process=spawn_process)


if __name__ == '__main__':
    d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
    print_tree(d1)
    print()

    obj1 = Tree(0)
    view_tree(obj1, include_dir=True, max_depth=3, max_lines=50)
