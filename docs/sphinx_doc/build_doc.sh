#!/bin/bash
make clean
languages=(en zh-CN)

for lang in "${languages[@]}"; do
    sphinx-multiversion source build/$lang -D "language=$lang" --dump-metadata
done

