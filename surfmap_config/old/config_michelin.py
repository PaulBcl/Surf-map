#!/usr/bin/env python
# coding: utf-8

# ### Fonction de geocoding

# Source : https://www.shanelynn.ie/batch-geocoding-in-python-with-google-geocoding-api/

# In[2]:

import requests

# Fonction Michelin
import xml.etree.ElementTree as ET
from copy import copy

def dictify(r,root=True):
    if root:
        return {r.tag : dictify(r, False)}
    d=copy(r.attrib)
    if r.text:
        d["_text"]=r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag]=[]
        d[x.tag].append(dictify(x,False))
    return d

def get_michelin_results(url, header = None):
    try:
        get = requests.get(url)
        results_raw = get.text
        root = ET.fromstring(results_raw)
        results = dictify(root)
        return results
    except:
        print('Erreur')
