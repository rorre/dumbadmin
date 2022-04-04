#!/bin/sh

set -e

. /venv/bin/activate

export QUART_APP=dumbadmin:app
export QUART_SECRET_KEY=$(openssl rand -hex 16)
quart init_db
echo $QUART_SECRET_KEY
exec hypercorn --bind '0.0.0.0:8000' $QUART_APP
