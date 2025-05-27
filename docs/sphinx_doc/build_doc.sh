#!/bin/bash
make clean
languages=(en zh_CN)

for lang in "${languages[@]}"; do
    sphinx-multiversion -j 4 source build/$lang -D "language=$lang"
done

