import os

ICON_DIR = 'icons'

# Look for Icons subdirectory in the same directory as this module
try:
    _icon_dir = os.path.join(os.path.dirname(__file__), ICON_DIR)
except NameError:
    _icon_dir = ICON_DIR
if os.path.isdir(_icon_dir):
    ICON_DIR = _icon_dir
elif not os.path.isdir(ICON_DIR):
    raise RuntimeError('Icon directory not found: '
                       f'"{os.path.normpath(ICON_DIR)}"')


class FileError(Exception):
    pass


def fix_extension(file_path: str, ext: str) -> str:
    folder, file_name = os.path.split(file_path)
    if not file_name:
        raise FileError('File name is required')
    file_root, file_ext = os.path.splitext(file_name)
    if file_ext != ext:
        return file_path + ext
    return file_path


def load_ico(file_name: str, size: float | None = None) -> bytes | list[bytes]:
    """If no size is given, return all images in the ICO file.
    Otherwise, return the image in the ICO file that closest match
    the given size."""

    ico_path = os.path.join(ICON_DIR, fix_extension(file_name, '.ico'))
    with open(ico_path, 'rb') as f:
        b = f.read()

    pos = 4
    n_images = int(b[pos])
    offset = 6 + 16*n_images
    file_sizes = []
    best_match_index = 0
    best_match_error = float('inf')
    pos += 2
    n = 4
    for index in range(n_images):
        width = int(b[pos])
        height = int(b[pos + 1])

        pos += 8
        file_sizes.append(int.from_bytes(b[pos:pos + n], 'little'))

        pos += n
        if offset != int.from_bytes(b[pos:pos + n], 'little'):
            raise FileError('Image file size not consistent with byte offset')
        offset += file_sizes[-1]
        pos += n

        if size is None:
            continue
        error = abs((width - size)*(height - size))
        if error < best_match_error:
            best_match_index = index
            best_match_error = error

    if size is not None:
        pos += sum(file_sizes[:best_match_index])
        return b[pos:pos + file_sizes[best_match_index]]

    images = []
    for file_size in file_sizes:
        images.append(b[pos:pos + file_size])
        pos += file_size
    return images
