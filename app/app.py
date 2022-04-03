import json
import os
import sqlite3
import requests as req

from flask import Flask, redirect, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from oauthlib.oauth2 import WebApplicationClient
import requests

from db import init_db_command
from user import User

# GOOGLE_CLIENT_ID = "14095007572-viha18f565t0hc5msuejhnm7mpu4886t.apps.googleusercontent.com"
# GOOGLE_CLIENT_SECRET = "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"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or None
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or None

print(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)

GOOGLE_DISCOVERY_URL = ("https://accounts.google.com/.well-known/openid-configuration")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

try:
    init_db_command()
except sqlite3.OperationalError: 
    pass # Assume it's already been created

client = WebApplicationClient(GOOGLE_CLIENT_ID)


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    return '''
        <ul>
            <li><a class="button" href="/login">Google Login</a></li>
            <li><a href="/useragent">User Agent</a></li>
            <li><a href="/list/Moscow">Weather in Moscow (or another if you will type)</a></li>
            <li><a href="/list/Moscow/25">Weather in Moscow at 25 day (or another if you will type)</a></li>
        </ul>'''


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


@app.route("/login")
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/about")
def about():
    if current_user.is_authenticated:
        return (
                "<p>Hello, {}! You're logged in! Email: {}</p>"
                "<div><p>Google Profile Picture:</p>"
                '<img src="{}" alt="Google profile pic"></img></div>'
                '<a class="button" href="/logout">Logout</a>'.format(
                    current_user.name, current_user.email, current_user.profile_pic
                )
            )
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/list/<city>")
def city_weather(city):
    try:
        res = req.get("http://api.openweathermap.org/data/2.5/find",
                    params={'q': city, 'type': 'like', 'units': 'metric', 'APPID': "d4e49d520fbd572ccf5bf52e6755fbd9"})
        
        data = res.json()
        city_id = data['list'][0]['id']

        res = requests.get("http://api.openweathermap.org/data/2.5/forecast",
                        params={'id': city_id, 'units': 'metric', 'lang': 'ru', 'APPID': "d4e49d520fbd572ccf5bf52e6755fbd9"})
        data = res.json()
        text = ""
        for i in data['list']:
            text += "<p>" + str(i['dt_txt']) + '{0:+3.0f}'.format(i['main']['temp']) + str(i['weather'][0]['description']) + "</p>"
        
        return text
    except Exception as e:
        return "Exception (forecast): " + e.__str__()


@app.route("/list/<city>/<int:day>")
def city_weather_from_day(city, day):
    try:
        res = req.get("http://api.openweathermap.org/data/2.5/find",
                    params={'q': city, 'type': 'like', 'units': 'metric', 'APPID': "d4e49d520fbd572ccf5bf52e6755fbd9"})
        data = res.json()
        city_id = data['list'][0]['id']

        res = requests.get("http://api.openweathermap.org/data/2.5/forecast",
                        params={'id': city_id, 'units': 'metric', 'lang': 'ru', 'APPID': "d4e49d520fbd572ccf5bf52e6755fbd9"})
        data = res.json()
        text = ""

        for i in data['list']:
            if int(str(i['dt_txt']).split(" ")[0].split("-")[2]) == day:
                text += "<p>" + str(i['dt_txt']) + '{0:+3.0f}'.format(i['main']['temp']) + str(i['weather'][0]['description']) + "</p>"
        
        return text
    except Exception as e:
        return "Exception (forecast): " + e.__str__()

@app.route("/useragent")
def useragent():
    return request.headers.get('User-Agent')


@app.route("/login/callback")
def callback():
    code = request.args.get("code")

    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)

    login_user(user)

    return redirect(url_for("about"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', ssl_context="adhoc")