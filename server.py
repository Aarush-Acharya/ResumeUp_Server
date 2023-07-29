from flask import Flask, jsonify, request
from flask_cors import  CORS
from jinja2 import Template
import requests

import os
import mysql.connector

app = Flask(__name__)
CORS(app, origins=["*"])


cnx = mysql.connector.connect(host ="gateway01.eu-central-1.prod.aws.tidbcloud.com",user ="Pd5yfUT23Tzbine.root",password ="8fIdoyXs7zyI7bjL",   port="4000",  database="ResumeUp", connect_timeout=60)

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getToken', methods=['POST'])
def get():
    body = request.json

    cursor = cnx.cursor()
    cursor.execute(
            "Select VercelAuthToken FROM VercelAuthTokens Where Uid = '{}';".format(body['Uid']))
    for i in cursor:
        vercel_token = i[0]
    return  jsonify({"VercelToken": vercel_token})

@app.route('/putToken', methods=['POST'])
def create():
    body = request.json

    cursor = cnx.cursor()
    cursor.execute(
            "INSERT INTO VercelAuthTokens(UID, VercelAuthToken) VALUES('{}','{}');".format(body['Uid'], body['VercelToken']))
    cnx.commit()
    return  jsonify({"Status": "pushed successfully"})

@app.route('/getChart', methods=['POST'])
def getChart():
    body = request.json
    url = "https://github-contributions-api.deno.dev/{}.svg?no-total=true&no-legend=true&frame=FFBF00".format(body['Uname'])
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    return  jsonify({"Svg": response.content.decode('utf-8')})

@app.route("/deploy")
def deploy():
    # body = request.json

    body = {
      "widgets": {
        "base_info": {
            "name": "Syed Ahkam",
            "description": "Some description"
        },
        "avatar": {
            "url": "https://avatars.githubusercontent.com/u/52673095?v=4"
        },
        "github_activity": {},
        "vercel": {},
        "contactme": {
            "email_address": "email@email.com",
            "github_username": "github_username",
            "twitter_username": "twitter_username",
            "linkedin_username": "linkedin_username",
        },
        "github_chart": {},
      },
      "connections": {
        "github_access_token": "github_token",
        "vercel_auth_token": "vercel_token"
      }
    }

    template_file = open("template.html")
    template = Template(template_file.read())

    rendered = template.render(**body)

    return rendered

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5666))


