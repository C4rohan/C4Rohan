import xml.etree.ElementTree as ET
from pathlib import Path

def test_unique_ids():
    svg_path = Path(__file__).resolve().parents[1] / 'lines.svg'
    tree = ET.parse(svg_path)
    ids = []
    for elem in tree.iter():
        if 'id' in elem.attrib:
            ids.append(elem.attrib['id'])
    assert len(ids) == len(set(ids)), 'Duplicate ids found in lines.svg'

