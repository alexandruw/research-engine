# users.py
# All related to user login/signup and preferences storage.

from generic import *
import email_messages
import hashlib
from google.appengine.api import mail

LOGIN_COOKIE_MAXAGE = 604800 # In seconds; 604800s = 1 week
EMAIL_RE = r'^[\S]+@[\S]+\.[\S]+$'
USERNAME_RE = r'^[a-zA-Z][a-zA-Z0-9_-]{2,20}$'
PASSWORD_RE = r'^.{3,20}$'
FORBIDDEN_USERNAMES = ["login", "logout", "signup", "settings","recover_password","verify_email",
                       "cron", "new_project", "file", "recover_password"]

class LoginPage(GenericPage):
    def get(self):
        kw = {'user': self.get_login_user(),
              'goback' : self.request.get('goback'),
              'r_error_message' : self.request.get('r_error_message'),
              'info' : self.request.get('info')}
        self.render("login.html", **kw)

    def post(self):
        email_or_username = self.request.get('email_or_username')
        password = self.request.get('password')
        have_error = False
        kw = {'email_or_username' : email_or_username, 'password' : password, 'error_message' : '', 'goback' : self.request.get('goback')}
        if not email_or_username:
            kw["error_message"] += "You must provide a valid email or username. "
            kw["uname_error_p"] = True
            have_error = True
        if not password:
            kw["error_message"] += "You must provide your password. "
            kw["pwd_error_p"] = True
            have_error = True
        if not have_error:
            if re.match(EMAIL_RE, email_or_username):
                u = self.get_user_by_email(email_or_username, "Checking user's login information. ")
            else:
                u = self.get_user_by_username(email_or_username.lower(), "Checking user's login information. ")
            if (not u) or (u.password_hash != hash_str(password + u.salt)):
                kw["error_message"] = 'Invalid password. If you forgot your password try setting a new one with the form below.'
                have_error = True
                kw["pwd_error_p"] = True
        if have_error:
            self.render("login.html", **kw)
        else:
#            u.salt = make_salt()
#            u.password_hash = hash_str(password + u.salt)
#            self.log_and_put(u, "Making new salt. ")
            self.set_cookie("username", u.username, u.salt, max_age = LOGIN_COOKIE_MAXAGE)
            if kw['goback']: 
                self.redirect(kw['goback'])
                return
            self.redirect("/%s" % u.username)


class LogoutPage(GenericPage):
    def get(self):
        self.remove_cookie("username")
        self.redirect("/login")


class UserPage(GenericPage):
    def get(self, username):
        page_user = self.get_user_by_username(username)
        if not page_user:
            self.error(404)
            self.render("404.html", info = "User <em>%s</em> not found." % username)
            return
        user = self.get_login_user()
        projects = page_user.list_of_projects()
        self_user_p = True if (user and user.key == page_user.key) else False
        recent_actv = page_user.get_recent_activity()
        self.render("user.html", page_user = page_user, projects = projects, recent_actv = recent_actv, self_user_p = self_user_p)


class SignupPage(GenericPage):
    def get(self):
        user = self.get_login_user()
        self.render("signup.html", user = user, info = self.request.get("info"))

    def post(self):
        usern = self.request.get('usern')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')
        have_error = False
        kw = {"usern" : usern, "email" : email, "error" : '', "info" : self.request.get("info")}
        # Valid input
        if usern and (usern.lower() in FORBIDDEN_USERNAMES):
            kw['error_username'] = True
            kw['error'] = "That username is not available"
            have_error = True
        if not re.match(USERNAME_RE, usern):
            kw['error_username'] = True
            kw['error'] += "That's not a valid username, it must be from 3 to 20 characters long, start with a letter and contain only letters, numbers, dashes and underscores. "
            have_error = True
        if not re.match(EMAIL_RE, email):
            kw['error_email'] = True
            kw['error'] += "That doesn't seem like a valid email. "
            have_error = True
        if not re.match(PASSWORD_RE, password):
            kw['error_password'] = True
            kw['error'] += "That's not a valid password, it must be between 3 and 20 characters long. "
            have_error = True
        elif password != verify:
            kw['error_verify'] = True
            kw['error'] += "Your passwords didn't match. "
            have_error = True
        if not have_error:
            usern = usern.lower()
            # Available username
            another_user = self.get_user_by_username(usern, "Checking if username is available")
            if not another_user:
                self.log_read(UnverifiedUsers, "Checking if username is available. ")
                another_user = UnverifiedUsers.query(UnverifiedUsers.username == usern).get()
            if another_user:
                have_error = True
                kw['error_username'] = True
                kw['error'] += 'That username is not available. '
            # Available email
            another_email = self.get_user_by_email(email, "Checking if email is available. ")
            if another_email:
                have_error = True
                kw['error_email'] = True
                kw['error'] += 'That email is already in use by someone. Did you <a href="/recover_password?email=%s">forget your password?. </a>' % email
            else:
                self.log_read(UnverifiedUsers, "Checking if email is available. ")
                another_email = UnverifiedUsers.query(UnverifiedUsers.email == email).get()
                if another_email:
                    have_error = True
                    kw['error_email'] = True
                    kw['error'] += 'This email is already registered but it still needs to be verified, click <a href="/verify_email?email=%s">here</a> to send the verification email again.' % email
        # Render
        if have_error:
            self.render('signup.html', **kw)
        else:
            salt = make_salt()
            ph = hash_str(password + salt)
            u = UnverifiedUsers(username = usern, password_hash = ph, salt = salt, email = email)
            self.log_and_put(u, "New user registration")
            email_messages.send_verify_email(u)
            self.render('signup.html', info = "A message has been sent to your email, please follow the instructions provided there.")


class SettingsPage(GenericPage):
    def get(self):
        user = self.get_login_user()
        if not user:
            self.redirect("/login", goback = "/settings")
            return
        kw = {"usern": user.username, "email" : user.email}
        if user.about_me: kw["about_me"] = user.about_me
        self.render("settings.html", user = user, **kw)

    def post(self):
        user = self.get_login_user()
        if not user:
            self.redirect("/login", goback = "/settings")
            return
        kw = {"usern"    : self.request.get("usern"),
              "email"    : self.request.get("email"),
              "about_me" : self.request.get("about_me")}
        have_error = False
        if kw["usern"]: kw["usern"] = kw["usern"].lower()
        if user.username != kw["usern"]:
            u2 = self.get_user_by_username(kw["usern"], "Checking if new username is available. ")
            if u2 or (not re.match(USERNAME_RE, kw["usern"])):
                kw["error_username"] = "*"
                kw['error'] = "Sorry, that username is not available. "
                have_error = True
        if user.email != kw["email"]:
            u2 = self.get_user_by_email(kw["email"], "Checking if new email is available. ")
            if u2:
                kw["error_email"] = "*"
                kw["error"] += "That email is already in use by someone. "
                have_error = True
        if not re.match(EMAIL_RE, kw["email"]):
                kw["error_email"] = "*"
                kw["error"] += "That doesn't seem like a valid email. "
                have_error = True
        if have_error:
            self.render("settings.html", **kw)
        else:
            user.username = kw["usern"] 
            user.email = kw["email"]
            user.about_me = kw["about_me"]
            user.profile_image_url = "https://secure.gravatar.com/avatar/" + hashlib.md5(user.email.strip().lower()).hexdigest()
            self.log_and_put(user, "Updating settings.")
            self.set_cookie("username", user.username, user.salt, max_age = LOGIN_COOKIE_MAXAGE)
            self.redirect("/%s" % user.username)


class RecoverPasswordPage(GenericPage):
    def get(self):
        email = self.request.get('email')
        key = self.request.get('k')
        have_error = False
        if (not email) or (not key):
            have_error = True
            error = "Malformed url, please try again. "
        user = self.get_user_by_email(email)
        if not user:
            have_error = True
            error = "There's not a user with that email %s" % email            
        else:
            if not key == hash_str(user.username + user.salt):
                have_error = True
                error = "Malformed url, please try again. "
        if have_error:
            self.redirect("/login?error=%s" % error)
        else:
            self.render("recover_password.html", email = email, key = key, error = self.request.get("error"))

    def post(self):
        action = self.request.get('action')
        have_error = False
        email = self.request.get("email")
        if action == "send_email":
            if (not email) or (not re.match(EMAIL_RE, email)):
                have_error = True
                r_error_message = "Please write a valid email."
            if not have_error:
                user = self.get_user_by_email(email)
                if not user:
                    have_error = True
                    r_error_message = "That's not a registered email."
            if have_error:
                self.redirect("/login?r_error_message=%s" % r_error_message)
            else:
                link = '%s/recover_password?email=%s&k=%s' % (APP_URL, email, hash_str(user.username + user.salt))
                message = mail.EmailMessage(sender = APP_NAME + ' <' + ADMIN_EMAIL + '>',
                                            to = email,
                                            subject = 'Password recovery',
                                            body = render_str('emails/recover_password.txt',  reset_link = link, ADMIN_EMAIL = ADMIN_EMAIL),
                                            html = render_str('emails/recover_password.html', reset_link = link, ADMIN_EMAIL = ADMIN_EMAIL))
                if DEBUG: logging.debug("EMAIL: Sending an email for password recovery. ")
                message.send()
                self.redirect('/login?info=Email sent. To reset your password follow the instructions on the email.')
        elif action == "do_reset":
            password = self.request.get("password")
            p_repeat = self.request.get("p_repeat")
            key = self.request.get("k")
            if not (email and key):
                have_error = True
            if not (password and p_repeat and re.match(PASSWORD_RE, password) and password == p_repeat):
                self.redirect('/recover_password?email=%s&k=%s&error=%s' % (email, key, "Please fill both boxes with the same password. "))
                return
            if not have_error:
                user = self.get_user_by_email(email)
                if not user:
                    have_error = True
                elif not key == hash_str(user.username + user.salt):
                    have_error = True
            if have_error:
                self.error(400)
                error = "Invalid request. "
                self.write(error)
            else:
                salt = make_salt()
                user.salt = salt
                user.password_hash = hash_str(password + salt)
                self.log_and_put(user)
                self.redirect("/login?info=Password successfully changed, you can login now with your new password.")

class VerifyEmailPage(GenericPage):
    def get(self):
        username = self.request.get("username")
        h = self.request.get("h")
        self.log_read(UnverifiedUsers)
        u = UnverifiedUsers.query(UnverifiedUsers.username == username).get()
        if not u:
            logging.warning("Handler VerifyEmailPage attempted to verify an email not in Datastore.")
            self.error(404)
            return 
        if hash_str(username + u.salt) == h:
            new_user = RegisteredUsers(username = u.username,
                                       password_hash = u.password_hash,
                                       salt = u.salt,
                                       email = u.email,
                                       about_me = '',
                                       my_projects = [],
                                       profile_image_url = "https://secure.gravatar.com/avatar/" + hashlib.md5(u.email.strip().lower()).hexdigest())
            self.log_and_put(new_user)
            self.log_and_delete(u)
            self.set_cookie("username", new_user.username, new_user.salt, max_age = LOGIN_COOKIE_MAXAGE)
            self.render("email_verified.html")
        else:
            logging.warning("Handler VerifyEmailPage attempted to verify an email with the wrong hash.")
            self.error(404)
            return
