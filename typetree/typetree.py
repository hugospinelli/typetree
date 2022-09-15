# -*- coding: utf-8 -*-

import dataclasses
import enum
import functools
import json
import re

from collections.abc import Callable
from typing import Any, Type

try:
    from viewer import tree_viewer
except (ModuleNotFoundError, ImportError):
    from .viewer import tree_viewer

__all__ = [
    'Tree',
    'print_tree',
    'view_tree',
    'Template',
    'DOM',
    'HTML',
    'XML',
]

_DEFAULT_MAX_LINES = 1000
_DEFAULT_MAX_SEARCH = 100_000
_DEFAULT_MAX_DEPTH = 20
_DEFAULT_MAX_BRANCHES = float('inf')

# Pre-compiled format for _KeyType.INDEX and _KeyType.SLICE
_RANGE_REGEX = re.compile(r'^\[(\d+)(?::(\d+))?]$')


@functools.total_ordering
class _KeyType(enum.Enum):
    """Node key types. When printed, each type will display
    the key differently based on their type.
    """
    # For the root node, which has no key
    NONE = 0
    # For object attributes (starts with a dot)
    # Example: .attr
    ATTR = 1
    # For Mapping keys
    # Examples: ['key'], [datetime.date(1970, 1, 1)]
    MAP = 2
    # For Sequence indices or slices
    # Examples: [2], [4:7], [:3], [:]
    INDEX = 3
    # For Collection, which has no key, but has an item counter
    # Example: (×3)
    SET = 4

    @classmethod
    def path(cls, key_type: '_KeyType', value: Any = None) -> str:
        match key_type, value:
            case cls.NONE, None:
                return ''
            case cls.NONE, str(x):
                return x
            case cls.ATTR, _:
                return f'.{value!s}'
            case cls.MAP, _:
                return f'[{value!r}]'
            case cls.SET, int():
                return ''
            case cls.INDEX, int(x):
                return f'[{x}]'
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
            case cls.SET, int(x):
                return '(×{:d}) '.format(x)
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
            assert isinstance(value, int)
            self._counter = value
        self._slice: tuple[int, int] | None = None
        if key_type == _KeyType.INDEX:
            if isinstance(value, int):
                self._slice = value, value + 1
            else:
                self._slice = value
        # Hash is unique for Sets
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
    def slice(self) -> tuple[int, int] | None:
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            raise NotImplementedError
        if self._type == other._type == _KeyType.SET:
            return False
        return self._str == other._str

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            raise NotImplementedError
        if self._str == other._str:
            return False
        if self._slice is not None:
            if other._slice is None:
                return self._type < other._type
            return self._slice < other._slice
        if self._type == other._type:
            if self._type == _KeyType.SET:
                return self._hash < other._hash
            return self._str < other._str
        return self._type < other._type

    def __hash__(self) -> int:
        return self._hash


@dataclasses.dataclass(slots=True, frozen=True)
class Template:
    """Default template class for configuration properties of a new Tree"""

    items_lookup: Callable[[Any], Any] = lambda var: var
    type_name_lookup: Callable[[Any], str] = lambda var: type(var).__name__
    value_lookup: Callable[[Any], Any] = lambda var: var
    sort_keys: bool = True
    show_lengths: bool = True
    include_attributes: bool = True
    include_dir: bool = False
    include_protected: bool = False
    include_special: bool = False
    max_search: float = _DEFAULT_MAX_SEARCH
    max_depth: float = _DEFAULT_MAX_DEPTH
    max_branches: float = _DEFAULT_MAX_BRANCHES


@dataclasses.dataclass(slots=True, frozen=True)
class DOM(Template):
    items_lookup: Callable[[Any], Any] = lambda x: x.childNodes
    type_name_lookup: Callable[[Any], str] = lambda x: x.nodeName
    value_lookup: Callable[[Any], Any] = lambda x: x.text


@dataclasses.dataclass(slots=True, frozen=True)
class HTML(Template):
    type_name_lookup: Callable[[Any], str] = lambda x: x.tag
    value_lookup: Callable[[Any], Any] = lambda x: x.text


@dataclasses.dataclass(slots=True, frozen=True)
class XML(Template):
    type_name_lookup: Callable[[Any], str] = lambda x: x.tag
    value_lookup: Callable[[Any], Any] = lambda x: x.text


class _MaxSearchError(Exception):
    """Reached maximum number of nodes to be searched"""
    pass


class _NodeInfo:
    """Non-recursive tree node info"""

    def __init__(self, obj: Any, node_key: _NodeKey, config: Template,
                 nodes_searched: int, ancestors_ids: set[int], depth: int):

        self.key: _NodeKey = node_key
        self.path: str = node_key.path
        self.config: Template = config
        self.nodes_searched: int = nodes_searched
        self.maxed_search: bool = False
        # For displaying an ellipsis indicating possible inner content
        self.maxed_depth: bool = depth >= config.max_depth
        is_infinite_recursion: bool = id(obj) in ancestors_ids

        self.type_name: str
        try:
            # noinspection PyArgumentList
            self.type_name = self.config.type_name_lookup(obj)
        except AttributeError:
            self.type_name = '?'
        original_var: Any = obj
        # noinspection PyArgumentList
        obj = self.config.items_lookup(obj)

        # These refer to the contents of Maps or Sequences
        self.items_key_type: _KeyType = _KeyType.NONE
        self.items_len: int | None = None
        self.get_items_info(obj, original_var)

        self.branches: dict[_NodeKey, Any] = {}
        if not is_infinite_recursion:
            try:
                self.add_branches(obj)
            except _MaxSearchError:
                pass

        self.var_repr: str = f'<{self.type_name}>'
        if is_infinite_recursion:
            self.var_repr = f'<...> {self.var_repr}'
        if self.config.show_lengths and self.items_len is not None:
            self.var_repr = f'{self.var_repr}[{self.items_len}]'

    def get_items_info(self, var: Any, original_var: Any):
        """Check which kind of iterable var is, if any, and return the
        _KeyType associated with its content and its size. Return
        (_KeyType.NONE, None) if var is not a simple finite iterable.
        """
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

    def add_branches(self, var: Any):
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
        # Success -- do not display ellipsis indicating max depth exceeded
        self.maxed_depth = False

    def add_branch(self, key_type: _KeyType, key: Any, value: Any):
        if self.nodes_searched >= self.config.max_search:
            self.maxed_search = True
            if not self.branches:  # empty
                # For displaying an ellipsis indicating possible inner content
                self.maxed_depth = True
            raise _MaxSearchError
        if self.maxed_depth:
            raise _MaxSearchError
        node_key = _NodeKey(key_type, key)
        self.branches[node_key] = value
        self.nodes_searched += 1

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


class _InfoTree:
    """A recursive tree builder of _NodeInfo"""

    def __init__(self, obj: Any, node_key: _NodeKey, config: Template,
                 nodes_searched: int, ancestors_ids: set[int], depth: int = 0):
        self.config: Template = config
        self.ancestors_ids: set[int] = ancestors_ids.copy()
        self.depth: int = depth
        self.node_info: _NodeInfo = _NodeInfo(
            obj, node_key, config, nodes_searched, ancestors_ids, self.depth
        )
        self.nodes_searched: int = self.node_info.nodes_searched
        self.ancestors_ids.add(id(obj))
        self.is_complete: bool = not self.node_info.branches
        self.maxed_depth: bool = (bool(self.depth >= config.max_depth
                                       and self.node_info.branches)
                                  or self.node_info.maxed_depth)
        self.has_maxed_depth: bool = self.maxed_depth
        self.branches: list[_InfoTree] = []
        self.updated: bool = False

    def update(self):
        """Recursively call to update the deepest _InfoTree"""
        if self.is_complete:
            return
        elif self.updated:
            for info_tree in self.branches:
                info_tree.nodes_searched = self.nodes_searched
                info_tree.update()
                self._update_info_tree(info_tree)
        else:
            self.updated = True
            for key, var in self.node_info.branches.items():
                info_tree: _InfoTree = _InfoTree(
                    var, key, self.config, self.nodes_searched,
                    self.ancestors_ids, self.depth + 1,
                )
                self.branches.append(info_tree)
                self._update_info_tree(info_tree)
        self.is_complete = all(info_tree.is_complete
                               for info_tree in self.branches)

    def _update_info_tree(self, info_tree: '_InfoTree'):
        if info_tree.has_maxed_depth:
            self.has_maxed_depth = True
        if self.nodes_searched == info_tree.nodes_searched:
            info_tree.is_complete = True
        self.nodes_searched = info_tree.nodes_searched


class _SubtreeCreator:
    """Create a Subtree instance. Used for pre-computing and analysing
    the branches. Needed because Subtree inherits from tuple, which is
    immutable, and the creation process is too complex to be done
    inside __new__.
    """
    def __init__(self, cls: Type['Subtree'], info_tree: _InfoTree):
        self.config: Template = info_tree.config
        info: _NodeInfo = info_tree.node_info
        node_key: _NodeKey = info.key
        self.all_branches: tuple[Subtree, ...] = tuple(
            Subtree(sub_info_tree) for sub_info_tree in info_tree.branches
        )
        self.group_branches()
        max_branches: int = int(min(float(len(self.all_branches)),
                                    self.config.max_branches))
        overflowed: bool = info.maxed_search or (len(self.all_branches)
                                                 > self.config.max_branches)
        self.subtree: Subtree = tuple.__new__(
            cls, self.all_branches[:max_branches]
        )
        self.subtree._key = node_key
        self.subtree._config = self.config
        self.subtree._info = info
        self.subtree._node_text = str(info)
        self.subtree._overflowed = overflowed
        self.subtree._maxed_depth = info.maxed_depth

    @staticmethod
    def group_to_map(v: list[set[int]]) -> dict[tuple[int, int], int]:
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
        (5, 6): 0, (6, 7): 1}.
        """
        if not v:
            return {}
        u: dict[tuple[int, int], int] = {}
        for k, s in enumerate(v):
            if not s:
                continue
            sv: list[int] = list(sorted(s))
            su: list[tuple[int, int]] = [(sv[0], sv[0] + 1)]
            for x in sv[1:]:  # type: int
                if x == su[-1][1]:
                    su[-1] = (su[-1][0], x + 1)
                else:
                    su.append((x, x + 1))
            for t in su:  # type: tuple[int, int]
                u[t] = k
        # noinspection PyTypeChecker
        return dict(sorted(u.items()))

    # noinspection PyProtectedMember
    def group_branches(self):
        """Group equivalent branches (with the same type structure)"""
        if not self.all_branches:
            return
        # Group unique consecutive Sequence branches and
        # unique Collection branches
        unique_index_branches: list[Subtree] = []
        all_index_branches: list[list[Subtree]] = []
        index_keys: list[set[int]] = []
        unique_set_branches: list[Subtree] = []
        added_branches: list[Subtree] = []
        for branch in self.all_branches:
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
        for _range, index in self.group_to_map(index_keys).items():
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

        self.all_branches = tuple(added_branches
                                  + unique_index_branches
                                  + unique_set_branches)
        if self.config.sort_keys:
            self.all_branches = tuple(sorted(self.all_branches,
                                             key=lambda x: x.key))
        else:
            self.all_branches = tuple(sorted(self.all_branches,
                                             key=lambda x: x.key.type))


@functools.total_ordering
class Subtree(tuple):
    """A recursive object tree structure"""

    # Initialized by _SubtreeCreator
    _key: _NodeKey
    _config: Template
    _info: _NodeInfo
    _node_text: str
    _overflowed: bool
    _maxed_depth: bool
    # Initialized by __init__
    _hash: int
    _path: str
    _is_expandable: bool

    def __new__(cls, info_tree: _InfoTree):
        return _SubtreeCreator(cls, info_tree).subtree

    def __init__(self, *_args, **_kwargs):
        self._update_paths()
        # Hash is unique if overflowed or max depth reached because
        # the tree is incomplete and equality between incomplete trees
        # cannot be established.
        self._hash = hash((
            self._info.var_repr,
            self._info.key.type,
            id(self)*(self._overflowed or self._maxed_depth),
            tuple(map(hash, self)),
        ))
        self._path = self._key.path
        self._update_paths()
        self._is_expandable = bool(self or self._overflowed
                                   or self._maxed_depth)

    @property
    def config(self) -> Template:
        return self._config

    @property
    def is_expandable(self) -> bool:
        return self._is_expandable

    @property
    def key(self) -> _NodeKey:
        return self._key

    @property
    def maxed_depth(self) -> bool:
        return self._maxed_depth

    @property
    def node_text(self) -> str:
        return self._node_text

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    @property
    def path(self) -> str:
        return self._path

    def _update_key(self, new_key: _NodeKey):
        self._key = new_key
        self._info.key = new_key
        self._node_text = str(self._info)
        self._update_paths()

    def _update_paths(self, parent_path: str = ''):
        if self._key.type == _KeyType.SET:
            self._path = f'{parent_path}.copy().pop()'
        else:
            self._path = f'{parent_path}{self._key.path}'
        for branch in self:  # type: Subtree
            branch._update_paths(self._path)

    def _get_tree_lines(self, max_lines: float,
                        root_pad: str = '',
                        branch_pad: str = '') -> list[str]:
        lines: list[str] = [f'{root_pad}{self._node_text}']
        if self._maxed_depth and self._is_expandable:
            lines.append(f'{branch_pad}└── ...')
            return lines
        if not self:  # empty
            return lines

        end: int = len(self)
        if not self._overflowed:
            end -= 1
        for branch in self[:end]:  # type: Subtree
            lines.extend(branch._get_tree_lines(
                max_lines=max_lines,
                root_pad=f'{branch_pad}├── ',
                branch_pad=f'{branch_pad}│   ',
            ))
        if self._overflowed:
            lines.append(f'{branch_pad}...')
        else:
            last_branch: Subtree = self[-1]
            lines.extend(last_branch._get_tree_lines(
                max_lines=max_lines,
                root_pad=f'{branch_pad}└── ',
                branch_pad=f'{branch_pad}    ',
            ))
        if len(lines) > max_lines:
            del lines[int(max_lines) - 1:]
            lines.append(' ...')
        return lines

    def to_dict(self, max_lines: float) -> str | dict[str, str | dict]:
        if not self:  # empty
            return str(self._info)
        branch: Subtree
        return {
            str(branch._info): branch.to_dict(max_lines)
            for branch in self
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            raise NotImplementedError
        if self._hash != other._hash:
            return False
        if self._info.var_repr != other._info.var_repr:
            return False
        if self._info.key.type != other._info.key.type:
            return False
        if self._overflowed or self._maxed_depth:
            return False
        return super().__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            raise NotImplementedError
        if self == other:
            return False
        if self._info.key.type != other._info.key.type:
            if self._info.key.type is None:
                return True
            if other._info.key.type is None:
                return False
            return self._info.key.type < other._info.key.type
        if self._info.var_repr != other._info.var_repr:
            return self._info.var_repr < other._info.var_repr
        if len(self) != len(other):
            return len(self) < len(other)
        for x, y in zip(self, other):
            if x != y:
                return x < y
        return self._hash < other._hash

    def __str__(self) -> str:
        return f'{self._info!s}{{...}}'

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self!s})'

    def __hash__(self) -> int:
        return self._hash


class Tree(Subtree):
    _nodes_searched: int
    max_lines: float

    def __new__(cls, obj: Any, *, key_text: str | None = None,
                max_lines: float = _DEFAULT_MAX_LINES,
                template: Type[Template] = Template, **kwargs):
        # noinspection PyArgumentList
        config: Template = template(**kwargs)
        info_tree: _InfoTree = _InfoTree(
            obj, _NodeKey(_KeyType.NONE, key_text), config,
            nodes_searched=0, ancestors_ids=set(), depth=0
        )
        while not info_tree.is_complete:
            info_tree.update()
        tree: Tree = super().__new__(cls, info_tree)
        tree._nodes_searched = info_tree.nodes_searched
        tree.max_lines = max_lines
        return tree

    def __init__(self, obj: Any, **kwargs):
        """Build a recursive object tree structure.

        Arguments:
            :param obj: Any Python object to be analysed
            :type obj: Any
            :param key_text: Placeholder text for the root key node
                Defaults to None
            :type key_text: str, optional
            :param template: A configuration template for common
                object types. Currently supported: `Template` (default),
                `DOM`, `HTML`, and `XML`
            :param items_lookup: Function used to access the node's
                content. Defaults to `lambda var: var`
            :type items_lookup: Callable[[Any], Any], optional
            :param type_name_lookup: Function used to get the type name.
                Defaults to `lambda var: type(var).__name__`
            :type type_name_lookup: Callable[[Any], Any], optional
            :param value_lookup: Function used to get the value when the
                node's content is empty (tree leaves). Defaults to
                `lambda var: var`
            :type value_lookup: Callable[[Any], Any], optional
            :param sort_keys: Flag for sorting keys alphabetically.
                Defaults to `True`
            :type sort_keys: bool, optional
            :param show_lengths: Flag for displaying lengths of
                iterables. This affects how subtrees are grouped together,
                since sequences with different sizes but same content types
                will be considered equivalent. Defaults to `True`
            :type show_lengths: bool, optional
            :param include_attributes: Flag for including the mutable
                attributes returned by `vars()`. Defaults to `True`
            :type include_attributes: bool, optional
            :param include_dir: Flag for including the attributes
                returned by `dir()`, except the protected (`_protected`) and
                the special (`__special__`) ones. Defaults to `False`
            :type include_dir: bool, optional
            :param include_protected: Flag for including the protected
                (`_protected`) attributes.  Defaults to `False`
            :type include_protected: bool, optional
            :param include_special`: Flag for including the special
                (`__special__`) attributes.  Defaults to `False`
            :type include_special: bool, optional
            :param max_lines: Maximum number of lines to be printed
                For the GUI, it is the maximum number of rows to be
                displayed, not including the extra ellipsis at the end.
                Can be disabled by setting it to infinity
                (`float('inf')` or `math.inf`). Defaults to 1000
            :type max_lines: float, optional
            :param max_search: Maximum number of nodes searched. Defaults
                to 100,000
            :type max_search: float, optional
            :param max_depth: Maximum search depth. Defaults to 20
            :type max_depth: float, optional
            :param max_branches: Maximum number of branches displayed on
                each node. This only applies after grouping. Defaults to
                infinity
            :type max_branches: float, optional
        """
        super().__init__(obj, **kwargs)

    @property
    def nodes_searched(self) -> int:
        return self._nodes_searched

    def to_dict(self, max_lines: float | None = None
                ) -> str | dict[str, str | dict]:
        if max_lines is None:
            max_lines = self.max_lines
        return super().to_dict(max_lines)

    def to_json(self, *args, max_lines: float | None = None, **kwargs) -> str:
        if max_lines is None:
            max_lines = self.max_lines
        return json.dumps(self.to_dict(max_lines), *args, **kwargs)

    def save_as_json(self, filename, *args,
                     max_lines: float | None = None,
                     encoding: str = 'utf-8',
                     ensure_ascii: bool = False,
                     indent: int = 4,
                     **kwargs):
        if max_lines is None:
            max_lines = self.max_lines
        with open(filename, 'w', encoding=encoding) as file:
            json.dump(self.to_dict(max_lines), file, *args,
                      ensure_ascii=ensure_ascii,
                      indent=indent,
                      **kwargs)

    def to_string(self, max_lines: float | None = None) -> str:
        """Get a tree view of the object's type structure as a string.

            Arguments:
                :param max_lines: Maximum number of lines to be printed.
                    Can be disabled by setting it to infinity
        """
        if max_lines is None:
            max_lines = self.max_lines
        return '\n'.join(self._get_tree_lines(max_lines, ' ', ' '))

    def print(self, max_lines: float | None = None):
        """Print a tree view of the object's type structure.

            Arguments:
                :param max_lines: Maximum number of lines to be printed.
                    Can be disabled by setting it to infinity
        """
        print(self.to_string(max_lines))

    def view(self, spawn_thread: bool = True, spawn_process: bool = False,
             max_lines: float | None = None):
        """Show a tree view of the object's type structure in an
        interactive Tkinter window

            Arguments:
                :param spawn_thread: Run the GUI in a separate thread
                :type spawn_thread: bool
                :param spawn_process: Run the GUI in a separate process
                :type spawn_process: bool
                :param max_lines: Maximum number of rows to be displayed,
                    not including the extra ellipsis at the end. Can be
                    disabled by setting it to infinity
        """
        if max_lines is None:
            max_lines = self.max_lines
        tree_viewer(self, max_lines,
                    spawn_thread=spawn_thread,
                    spawn_process=spawn_process)


def print_tree(obj: Any, **kwargs):
    """Print a tree view of the object's type structure

        Arguments:
            :param obj: Any Python object to be analysed
            :type obj: Any
            :param kwargs: Same as :class:`Tree`. Type `help(Tree.__init__)`
                for the full list
    """
    Tree(obj, **kwargs).print()


def view_tree(obj: Any, *,
              spawn_thread: bool = True,
              spawn_process: bool = False,
              **kwargs):
    """
    Show a tree view of the object's type structure in an interactive
    Tkinter window (GUI).

        Arguments:
            :param obj: Any Python object to be analysed
            :type obj: Any
            :param spawn_thread: Run the GUI in a separate thread
            :type spawn_thread: bool
            :param spawn_process: Run the GUI in a separate process
            :type spawn_process: bool
            :param kwargs: Same as `Tree`. Type `help(Tree.__init__)`
                for the full list
    """
    Tree(obj, **kwargs).view(spawn_thread=spawn_thread,
                             spawn_process=spawn_process)


if __name__ == '__main__':
    d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
    print_tree(d1)
    print()

    print_tree((0,), include_dir=True, max_depth=2, max_lines=15)
    print()

    import urllib.request
    import xml.etree.ElementTree
    url1 = 'https://www.w3schools.com/xml/simple.xml'
    with urllib.request.urlopen(url1) as response1:
        r1 = response1.read()
    text1 = str(r1, encoding='utf-8')
    tree1 = xml.etree.ElementTree.fromstring(text1)
    print_tree(tree1, template=XML)
    print()

    import xml.dom.minidom
    dom1 = xml.dom.minidom.parseString(text1)
    print_tree(dom1, template=DOM, max_lines=10)
    print()

    obj1 = Tree(0)
    print_tree(obj1, include_dir=True, max_depth=3, max_lines=15)
    print()

    url2 = 'https://archive.org/metadata/TheAdventuresOfTomSawyer_201303'
    with urllib.request.urlopen(url2) as response2:
        r2 = response2.read()
    text2 = str(r2, encoding='utf-8')
    json2 = json.loads(text2)
    view_tree(json2)
