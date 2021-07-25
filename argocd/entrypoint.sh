#!/bin/sh
if [ -f "Pipfile" ]; then
    pipenv install >/dev/null 2>&1
fi

if [ $# -eq 0 ]; then
    echo "Init /deployments"
    cp -r /build/* /deployments/
else
    cdk8s "$@"
fi

chmod -R 777 /deployments
