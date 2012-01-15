#!/bin/bash
python classdepgraph.py
dot -Tsvg classdepgraph.dot -o classdepgraph.svg
