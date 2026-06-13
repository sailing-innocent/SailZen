#!/bin/sh

PORT=3005
env LOG_LEVEL=info sail launchEngineServer --init --port $PORT

#| tee /tmp/out.txt
