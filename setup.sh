#!/bin/sh



# Install miniforge (conda & mamba distribution) if conda & mamba are not installed
if ! command -v conda &> /dev/null && ! command -v mamba &> /dev/null
then
    # Download and install miniforge
    wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
    sh Miniforge3-$(uname)-$(uname -m).sh -b

    # Initialize conda
    $HOME/miniforge3/bin/conda init zsh
    $HOME/miniforge3/bin/mamba shell init -s zsh
fi

# Install starship if not installed
if ! command -v starship &> /dev/null
then
    curl -sS https://starship.rs/install.sh | sh
fi
