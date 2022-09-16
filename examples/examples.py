import json
import urllib.request
import xml.dom.minidom
import xml.etree.ElementTree

import typetree

d1 = [{'a', 'b', 1, 2, (3, 4), (5, 6), 'c', .1}, {'a': 0, 'b': ...}]
typetree.print_tree(d1)
print()

typetree.print_tree((0,), include_dir=True, max_depth=2, max_lines=15)
print()

url1 = 'https://www.w3schools.com/xml/simple.xml'
with urllib.request.urlopen(url1) as response1:
    r1 = response1.read()
text1 = str(r1, encoding='utf-8')
tree1 = xml.etree.ElementTree.fromstring(text1)
typetree.print_tree(tree1, template=typetree.XML)
print()

dom1 = xml.dom.minidom.parseString(text1)
typetree.print_tree(dom1, template=typetree.DOM, max_lines=10)
print()

obj1 = typetree.Tree(0)
typetree.print_tree(obj1, include_dir=True, max_depth=3, max_lines=15)
print()

url2 = 'https://archive.org/metadata/TheAdventuresOfTomSawyer_201303'
with urllib.request.urlopen(url2) as response2:
    r2 = response2.read()
text2 = str(r2, encoding='utf-8')
json2 = json.loads(text2)
typetree.view_tree(json2)
