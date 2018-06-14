#!/bin/sh
echo cat $GOOGLE_APPLICATION_CREDENTIALS_KEY > ./gcloud-key.json
cat ./gcloud-key.json
./manage.py migrate
