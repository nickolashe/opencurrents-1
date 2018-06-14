release: ./heroku-release-tasks.sh
web: echo $GOOGLE_APPLICATION_CREDENTIALS_KEY | base64 --decode -o gcloud-key.json && gunicorn oc.wsgi --log-file -
