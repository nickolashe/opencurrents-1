#!/bin/sh
echo $GOOGLE_APPLICATION_CREDENTIALS_KEY | base64 --decode -o gcloud-key.json
cat ./gcloud-key.json
./manage.py migrate
