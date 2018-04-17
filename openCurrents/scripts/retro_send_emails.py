from django.contrib.auth.models import User
from openCurrents import views
from openCurrents.interfaces.orgs import OrgUserInfo
from openCurrents.models import Token

admin_invites = {
    804: [
        'djsaun@gmail.com',
        'hzh853240936@gmail.com',
        'mozart3186@yahoo.com',
        'smith.juliette@gmail.com',
        'josephk.henderson@gmail.com',
        'fquintero20@gmail.com',
        'mreddaaa@gmail.com',
        'nebiha.said@gmail.com',
        'donnaleehoffman@gmail.com'
    ],
    1028: [
        '23aubreyironshell@gmail.com',
        'alice.lineberry@dlapiper.com',
    ],
    1059: [
        'jionninluke@icloud.com',
        'johnny.1780@icloud.com',
        'mh93680@eanesisd.net',
        'cady.mcnerney@gmail.com',
        'lauranewton@yahoo.com',
        'alannaogara@gmail.com',
        'danielbarrerafl@gmail.com',
        'rahhc@mcffe.org',
        '23aubreyironshell@gmail.com',
        'babygirlgotsthatwater100@gmail.com',
        'pink34655@gmail.com',
        'camilits_8@hotmail.com',
        'meg.partlow@gmail.com',
        'tarabongio@gmail.com',
        'christiecasteel@hotmail.com',
        'mark.kuster@tlc.texas.gov',
        'katherinekuster@outlook.com',
        'nickberard2011@gmail.com',
        'kristengentry37@gmail.com',
        'caitlin.tran1630@gmail.com',
        '19hhowton@gmail.com',
        'moderneffects01@gmail.com',
        'mjwelsh1@gmail.com'
    ],
    1063: [
        'kwerty037@gmail.com',
        'eric@bxdeke.org',
        'lori.kline.designs@gmail.com',
        'freedomwht9@gmail.com',
        'kedreoniaf@yahoo.com',
        'davebsmd@yahoo.com',
        'troncoso.lauren4@gmail.com'
    ],
    1349: [
        'bdiazaustin@gmail.com',
        'audraatkeisson@gmail.com',
        'oualid.mbarki@gmail.com',
        'shaigi@gmail.com',
        'chrismartin.online@gmail.com',
        'mario.valentin@gmail.com',
        'tmarik11@gmail.com',
        'patrick.boersma@gmail.com',
        'stefwithanf1@yahoo.com',
        'smontemorra@yahoo.com',
        'j_steinbon@yahoo.com',
        'amonm17@gmail.com',
        'ms.russellteacher2@yahoo.com',
        'carolina53911@gmail.com',
        'vyun712@gmail.com',
        'afsmike@gmail.com',
        'jeanshaw@gmail.com',
        'jong.josephine@gmail.com',
        'ericawollman@hotmail.com',
        'esanchez939@gmail.com',
        'vanessa.itzel.ayala@gmail.com',
        'jasonp_austin@sbcglobal.net',
        'jbeckage@yahoo.com',
        'belcanto_99@hotmail.com',
        'caseybranthoover@gmail.com',
        'lette33@att.net',
        'nhart624@gmail.com',
        'jpalafox@yahoo.com'
    ]
}

user_verifications = [
    'ricardopal82@gmail.com',
    's0616s@heb.com',
    'lori.kline.designs@gmail.com',
    'hanan78753@gmail.com',
    'mallie.solis@gmail.com'
]


def send_verify_email(user_email):
    try:
        user = User.objects.get(email=user_email)
        token_rec = Token.objects.filter(email=user_email).last()
        views.sendTransactionalEmail(
            'verify-email',
            None,
            [
                {
                    'name': 'FIRSTNAME',
                    'content': user.first_name
                },
                {
                    'name': 'EMAIL',
                    'content': user_email
                },
                {
                    'name': 'TOKEN',
                    'content': str(token_rec.token)
                }
            ],
            user_email
        )
        print 'sent verify-email to {}'.format(user_email)
    except Exception as e:
        print 'error: %s' % {'error': e, 'message': e.message}


def send_admin_invite(admin_id, user_email):
    admin_user = User.objects.get(id=admin_id)
    admin_orguserinfo = OrgUserInfo(admin_id)
    admin_org = admin_orguserinfo.get_org()

    try:
        views.sendTransactionalEmail(
            'invite-volunteer',
            None,
            [
                {
                    'name': 'ADMIN_FIRSTNAME',
                    'content': admin_user.first_name
                },
                {
                    'name': 'ADMIN_LASTNAME',
                    'content': admin_user.last_name
                },
                {
                    'name': 'ORG_NAME',
                    'content': admin_org.name
                }
            ],
            user_email
        )
        print 'sent invite-volunteers from {} to {}'.format(
            admin_user.email,
            user_email
        )
    except Exception as e:
        print 'error: %s' % {'error': e, 'message': e.message}

# send_verify_email('nazniko515@gmail.com')
# for user_email in user_verifications:
#     send_verify_email(user_email)

# do_send(1349, 'nazniko515@gmail.com')
for admin_id in admin_invites.keys():
    for user_email in admin_invites[admin_id]:
        send_admin_invite(admin_id, user_email)
