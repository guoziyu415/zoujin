#!/bin/sh
# local test copy: same files as the publish folder, but three.js served locally (jsdelivr is blocked in this container)
rm -rf /tmp/spk/s7test && mkdir -p /tmp/spk/s7test
for d in tex lm data; do ln -s /tmp/spk/s7page/$d /tmp/spk/s7test/$d; done
ln -s /tmp/spk/three/node_modules/three /tmp/spk/s7test/three
sed -e 's#https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js#/three/build/three.module.js#' \
    -e 's#https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/libs/basis/#/three/examples/jsm/libs/basis/#' \
    -e 's#https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/#/three/examples/jsm/#' /tmp/spk/s7page/index.html > /tmp/spk/s7test/index.html
grep -c jsdelivr /tmp/spk/s7test/index.html
