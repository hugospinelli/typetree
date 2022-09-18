import json
import urllib.request
import xml.dom.minidom
import xml.etree.ElementTree

import typetree


d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
result = typetree.Tree(d1).to_string()
expected_result = """ <list>[2]
 ├── [0]: <set>[8]
 │   ├── (×1) <float>
 │   ├── (×2) <int>
 │   ├── (×2) <tuple>[2]
 │   │   └── [:2]: <int>
 │   └── (×3) <str>
 └── [1]: <dict>[2]
     ├── ['a']: <int>
     └── ['b']: <ellipsis>"""
assert result == expected_result

result = typetree.Tree((0,), include_dir=True, max_depth=2,
                       max_lines=15).to_string()
expected_result = """ <tuple>[1]
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
 ..."""
assert result == expected_result

url1 = 'https://www.w3schools.com/xml/simple.xml'
with urllib.request.urlopen(url1) as response1:
    r1 = response1.read()
text1 = str(r1, encoding='utf-8')
tree1 = xml.etree.ElementTree.fromstring(text1)
result = typetree.Tree(tree1, template=typetree.XML).to_string()
expected_result = """ <breakfast_menu>[5]
 └── [:5]: <food>[4]
     ├── [0]: <name>
     ├── [1]: <price>
     ├── [2]: <description>
     └── [3]: <calories>"""
assert result == expected_result

dom1 = xml.dom.minidom.parseString(text1)
result = typetree.Tree(dom1, template=typetree.DOM, max_lines=10).to_string()
expected_result = """ <#document>[1]
 └── [0]: <breakfast_menu>[11]
     ├── [0]: <#text>
     ├── [1]: <food>[9]
     │   ├── [0]: <#text>
     │   ├── [1]: <name>[1]
     │   │   └── [0]: <#text>
     │   ├── [2]: <#text>
     │   ├── [3]: <price>[1]
 ..."""
assert result == expected_result

url2 = 'https://archive.org/metadata/TheAdventuresOfTomSawyer_201303'
with urllib.request.urlopen(url2) as response2:
    r2 = response2.read()
text2 = str(r2, encoding='utf-8')
json2 = json.loads(text2)
result = typetree.Tree(json2).to_string()
expected_result = """ <dict>[13]
 ├── ['created']: <int>
 ├── ['d1']: <str>
 ├── ['d2']: <str>
 ├── ['dir']: <str>
 ├── ['files']: <list>[15]
 │   ├── [:2]: <dict>[9]
 │   │   ├── ['crc32']: <str>
 │   │   ├── ['format']: <str>
 │   │   ├── ['md5']: <str>
 │   │   ├── ['mtime']: <str>
 │   │   ├── ['name']: <str>
 │   │   ├── ['rotation']: <str>
 │   │   ├── ['sha1']: <str>
 │   │   ├── ['size']: <str>
 │   │   └── ['source']: <str>
 │   ├── [2:4]: <dict>[8]
 │   │   ├── ['crc32']: <str>
 │   │   ├── ['format']: <str>
 │   │   ├── ['md5']: <str>
 │   │   ├── ['mtime']: <str>
 │   │   ├── ['name']: <str>
 │   │   ├── ['sha1']: <str>
 │   │   ├── ['size']: <str>
 │   │   └── ['source']: <str>
 │   ├── [4:10]: <dict>[9]
 │   │   ├── ['btih']: <str>
 │   │   ├── ['crc32']: <str>
 │   │   ├── ['format']: <str>
 │   │   ├── ['md5']: <str>
 │   │   ├── ['mtime']: <str>
 │   │   ├── ['name']: <str>
 │   │   ├── ['sha1']: <str>
 │   │   ├── ['size']: <str>
 │   │   └── ['source']: <str>
 │   ├── [10]: <dict>[5]
 │   │   ├── ['format']: <str>
 │   │   ├── ['md5']: <str>
 │   │   ├── ['name']: <str>
 │   │   ├── ['source']: <str>
 │   │   └── ['summation']: <str>
 │   ├── [11:14]: <dict>[8]
 │   │   ├── ['crc32']: <str>
 │   │   ├── ['format']: <str>
 │   │   ├── ['md5']: <str>
 │   │   ├── ['mtime']: <str>
 │   │   ├── ['name']: <str>
 │   │   ├── ['sha1']: <str>
 │   │   ├── ['size']: <str>
 │   │   └── ['source']: <str>
 │   └── [14]: <dict>[9]
 │       ├── ['crc32']: <str>
 │       ├── ['format']: <str>
 │       ├── ['md5']: <str>
 │       ├── ['mtime']: <str>
 │       ├── ['name']: <str>
 │       ├── ['original']: <str>
 │       ├── ['sha1']: <str>
 │       ├── ['size']: <str>
 │       └── ['source']: <str>
 ├── ['files_count']: <int>
 ├── ['item_last_updated']: <int>
 ├── ['item_size']: <int>
 ├── ['metadata']: <dict>[21]
 │   ├── ['addeddate']: <str>
 │   ├── ['backup_location']: <str>
 │   ├── ['collection']: <list>[3]
 │   │   └── [:3]: <str>
 │   ├── ['creator']: <str>
 │   ├── ['curation']: <str>
 │   ├── ['description']: <str>
 │   ├── ['identifier']: <str>
 │   ├── ['identifier-access']: <str>
 │   ├── ['identifier-ark']: <str>
 │   ├── ['language']: <str>
 │   ├── ['mediatype']: <str>
 │   ├── ['ocr']: <str>
 │   ├── ['openlibrary_edition']: <str>
 │   ├── ['openlibrary_work']: <str>
 │   ├── ['ppi']: <str>
 │   ├── ['publicdate']: <str>
 │   ├── ['repub_state']: <str>
 │   ├── ['scanner']: <str>
 │   ├── ['subject']: <list>[8]
 │   │   └── [:8]: <str>
 │   ├── ['title']: <str>
 │   └── ['uploader']: <str>
 ├── ['reviews']: <list>[1]
 │   └── [0]: <dict>[7]
 │       ├── ['createdate']: <str>
 │       ├── ['reviewbody']: <str>
 │       ├── ['reviewdate']: <str>
 │       ├── ['reviewer']: <str>
 │       ├── ['reviewer_itemname']: <str>
 │       ├── ['reviewtitle']: <str>
 │       └── ['stars']: <str>
 ├── ['server']: <str>
 ├── ['uniq']: <int>
 └── ['workable_servers']: <list>[2]
     └── [:2]: <str>"""
assert result == expected_result

print('All passed!')
