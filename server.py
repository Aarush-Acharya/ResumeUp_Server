from flask import Flask, jsonify, request
from flask_cors import  CORS
from jinja2 import Template
from dotenv import load_dotenv

import os
import base64

import mysql.connector
import requests

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["*"])

cnx = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
)

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getToken', methods=['POST'])
def get():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
            "Select VercelAuthToken FROM VercelAuthTokens Where Uid = '{}';".format(body['Uid']))
    for i in cursor:
        vercel_token = i[0]
    return  jsonify({"VercelToken": vercel_token})

@app.route('/putToken', methods=['POST'])
def create():
    body = request.json
    cnx.reconnect()
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

@app.route('/setStatus', methods=['POST'])
def send_Status():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
            "INSERT INTO DeployStatus(UID, Status) VALUES('{}','{}');".format(body['Uid'], body['Status']))
    cnx.commit()
    return  jsonify({"Executed": "yep"})

@app.route('/getStatus', methods=['POST'])
def get_status():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
            "Select Status FROM DeployStatus Where Uid = '{}';".format(body['Uid']))
    for i in cursor:
        status = i[0]
    return  jsonify({"Status": status})

@app.route("/deploy", methods=['POST'])
def deploy():
    body = request.json

    # Create github repo
    safe_repo_name = body["widgets"]["base_info"]["name"].lower().replace(" ", "") + "-resumup"
    expected_vercel_link = f"https://{safe_repo_name}.vercel.app"
    resp = requests.post(
        "https://api.github.com/user/repos",
        json={
            "name": safe_repo_name,
            "description": "Resume built using ResumUp",
            "homepage": expected_vercel_link
        },
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {body['connections']['github_access_token']}"
        }
    )

    if not resp.status_code == 201:
        return jsonify({"status": False, "error": "failed to create repo"})
    
    print(f"Created repository: {safe_repo_name}")

    # Render template
    template_file = open("template.html")
    template = Template(template_file.read())

    index_html = template.render(**body)

    # Upload files
    username = body["widgets"]["contactme"]["github_username"]
    contents = base64.b64encode(index_html.encode()).decode()
    resp = requests.put(
        f"https://api.github.com/repos/{username}/{safe_repo_name}/contents/index.html",
        json={
            "message": "Initial Commit",
            "content": contents,
            "branch": "master"
        },
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {body['connections']['github_access_token']}"
        }
    )

    if not resp.status_code == 201:
        return jsonify({"status": False, "error": "failed to upload files"})

    print("Uploaded index.html file")
    
    # Create vercel deployment
    resp = requests.post(
        f"https://api.vercel.com/v13/deployments",
        json={
            "name": safe_repo_name,
            "framework": None,
            "gitSource": {
                "org": username,
                "ref": "master",
                "repo": f"{safe_repo_name}",
                "type": "github"
            },
            "projectSettings": {
                "framework": None,
                "outputDirectory": ".",
                "rootDirectory": None
            },
        },
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {body['connections']['vercel_auth_token']}"
        }
    )

    if not resp.status_code == 200:
        return jsonify({"status": False, "error": "failed to create deployment"})

    print("Done creating deployment!")
    
    return jsonify({"status": True, "link": expected_vercel_link, "message": "successfully created deployment", "repo_name": safe_repo_name})


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5666))
