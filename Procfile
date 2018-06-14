release: ./heroku-release-tasks.sh
web: echo $GOOGLE_APPLICATION_CREDENTIALS_KEY > ./gcloud-key.json &&
gunicorn oc.wsgi --log-file -
