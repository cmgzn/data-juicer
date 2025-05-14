#!/bin/bash
sphinx-apidoc -f -o source ../../data_juicer -t _templates
python ./create_symlinks.py
make clean
languages=("en" "zh_CN")

for lang in "${languages[@]}"; do
    sphinx-build -D language=$lang -b html source build/html/$lang
done