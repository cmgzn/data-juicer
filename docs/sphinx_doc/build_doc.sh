#!/bin/bash
sphinx-apidoc -f -o source ../../data_juicer -t _templates
python ./create_symlinks.py
make clean html