# TODO

## Main

- [X] Standardize how subtrees of `INDEX` type with different lengths
are grouped together when using `show_lengths=False`.
  - Idea: use `[:]` as keys.
- [ ] Remove the `# noinspection PyUnresolvedReferences` in `Config`
class after the PyCharm bug is fixed (probably in version 2022.2.2).
- [ ] Identify self-referential trees.
  - Idea: use a set of previously visited `id()`. Use `<...>` instead
of the type to represent infinite recursions.
- [ ] Make `Tree` an iterable with index access to child nodes.
- [ ] Helpers for XML, DOM, and HTML configurations.
