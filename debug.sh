#!/usr/bin/env bash

# Runs Photo Amaze in debug mode.
npm run build
npm run dev &

python main.py
