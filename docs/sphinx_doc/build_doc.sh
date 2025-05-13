#!/bin/bash
sphinx-apidoc -f -o source ../../data_juicer -t _templates
make gettext
python ./create_symlinks.py
make clean html