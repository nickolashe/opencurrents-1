#!/bin/sh
echo $GOOGLE_APPLICATION_CREDENTIALS_KEY > ./gcloud-key.json
cat ./gcloud-key.json
./manage.py migrate
