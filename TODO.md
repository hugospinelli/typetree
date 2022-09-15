# TODO

## Main

- [X] Standardize how subtrees of `INDEX` type with different lengths
are grouped together when using `show_lengths=False`.
  - Idea: use `[:]` as keys.
- [X] Identify self-referential trees.
  - Idea: use a set of previously visited `id()`. Use `<...>` instead
of the type to represent infinite recursions.
- [X] Make `Tree` an iterable with index access to child nodes.
- [X] Helpers for XML, DOM, and HTML configurations.
- [X] Improve interface with the Tree stats.
- [X] Create save to file option.
- [X] Improve other input and output options for Tree.

## PyCharm

- [X] Remove the `# noinspection PyUnresolvedReferences` in `Config`
class after the PyCharm bug is fixed (probably in version 2022.2.2).
  - Not required anymore.