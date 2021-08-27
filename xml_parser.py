#!/usr/bin/python
# -*- coding: UTF-8 -*-

from xml.dom.minidom import parse
import xml.dom.minidom

# 使用minidom解析器打开 XML 文档
DOMTree = xml.dom.minidom.parse("detector_modified.add.xml")
collection = DOMTree.documentElement

# 在集合中获取所有电影
e1Detectors = collection.getElementsByTagName("e1Detector")

# 打印每部电影的详细信息
for detector in e1Detectors:
    print("*****Movie*****")
    if detector.hasAttribute("id"):
        print("id: %s" % detector.getAttribute("id"))
    elif detector.hasAttribute("freq"):
        print("freq: %s" % detector.getAttribute("freq"))

    oldFile = detector.getAttribute('file')
    newFile = "e1Detector_output.xml"
    detector.attributes['file'].value = newFile
    print("File: {} -> {}".format(oldFile, newFile))

    oldFreq = detector.getAttribute('freq')
    newFreq = "300.00" # 5 * 60 s
    detector.attributes['freq'].value = newFreq

with open("detector_modified.add.xml", "w+") as f:
    DOMTree.writexml(f)
