#!/bin/bash
action=${1:-"upload"}

if [[ $action == "upload" ]]; then
    rsync -av --exclude '.git/' --exclude 'venv/' --exclude '.idea/' --exclude '*.DS_Store'  --exclude '__pycache__/' . chenbo@pood.xyz:~/collab-edit-demo
elif [[ $action == "download" ]]; then
    cd ..
    rsync -av chenbo@pood.xyz:~/password_guardian .
    cd password_guardian
fi
