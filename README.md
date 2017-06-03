#Install instructions for the Mac
+ Install XCode (to get gcc compiler, done through appstore)
+ Upgrade mac os from 10.10.5 -> 10.12.3 (Sierra), 10.11.x required
+ <del>Used this to install [Python](http://docs.python-guide.org/en/latest/starting/install3/osx/)</del> Not needed as Mac comes default with Python 2.7 which we currently use for oc work

# Install Pip (we are Using version v. 1.11.x)
    sudo easy_install pip
## Upgrade pip: 
    pip install -U pip
## Install Django
    sudo pip install django

    Password:
    The directory '/Users/ronak.rahman/Library/Caches/pip/http' or its parent directory is not owned by the current user and the cache has been disabled. Please check the permissions and owner of that directory. If executing pip with sudo, you may want sudo's -H flag.
    The directory '/Users/ronak.rahman/Library/Caches/pip' or its parent directory is not owned by the current user and caching wheels has been disabled. check the permissions and owner of that directory. If executing pip with sudo, you may want sudo's -H flag.
    Collecting django
    Downloading Django-1.10.5-py2.py3-none-any.whl (6.8MB)
    100% |████████████████████████████████| 6.8MB 107kB/s
    Installing collected packages: django
    Successfully installed django-1.10.5


# Verify Django is installed:

    $ python
    >>> import django
    >>> print(django.get_version())
    1.10
Exit by typing Ctrl + D


# [Virtual env](https://virtualenvwrapper.readthedocs.io/en/latest/)
    sudo su
    pip install virtualenvwrapper --ignore-installed six #on the mac you have to ignore the six install
    #exit sudo

    ## configure your shell
    vi ~/.bash_profile 
    ...
    source /usr/local/bin/virtualenvwrapper.sh

# Install DB
## Install postgres
    brew install postgresql
## add Postgres to your ~/.bash_profile
    vi ~/.bash_profile
    # Add this at the bottom
    # PATH=/usr/local/Cellar/postgresql/9.6.2/bin:$PATH

## Run this to actually source our adds
    source ~/.bash_profile

# Launching site on localhost
## Open a virtual environment (called env)
    mkvirtualenv env1

## install requirements
    sudo pip install -r requirements.txt
## start the server
    python manage.py runserver


# COMMON ISSUES

## Exiting the virtual environment
    deactivate

## Database has not been created
If you see this error after you launch your site (in the terminal):

    return Database.Cursor.execute(self, query, params)
    OperationalError: no such table: auth_user

Then:
Shut down server (go to terminal, and Ctrl + C in the screen running the server)

    python manage.py migrate
    python manage.py runserver

Now try and open your [instance here](http://localhost:8000/)

## Need to create admin user for admin page
    python manage.py createsuperuser
    select name (ex. admin)
    select pass (ex. adminuser)

Once you server is back up and running, you can access the admin page [here](http://localhost:8000/admin/)
