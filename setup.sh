#!/bin/sh



# Install starship if not installed
if ! command -v starship &> /dev/null
then
    curl -sS https://starship.rs/install.sh | sh
fi
