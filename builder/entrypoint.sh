#!/bin/sh
set -eu
umask 022
exec python -m builder.main "$@"
