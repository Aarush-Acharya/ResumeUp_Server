from flask import Flask, jsonify, request
from flask_cors import  CORS
from dotenv import load_dotenv
from github import Github, Auth
from cookiecutter.main import cookiecutter
from git import Repo

import os
import json

import mysql.connector
import requests

TEMPLATE_REPO_LINK="https://github.com/TiDB-Hacks/resumeup_template"

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

    status = False
    for i in cursor:
        status = i[0]
    
    return  jsonify({"Status": status})

@app.route("/deploy", methods=['POST'])
def deploy():
    body = request.json

    # Create github instance
    github = Github(auth=Auth.Token(body["connections"]["github_access_token"]))

    safe_repo_name = body["widgets"]["base_info"]["name"].lower().replace(" ", "") + "-resumup"
    expected_vercel_link = f"https://{safe_repo_name}.vercel.app"

    # Remove existing output dir, if any
    if os.path.exists("/tmp/" + safe_repo_name):
        os.system(f"rm -rf /tmp/{safe_repo_name}")

    username = body["widgets"]["contactme"]["github_username"]
    access_token = body["connections"]["github_access_token"]

    context = {
        "project_name": safe_repo_name,
        "author_name": body["widgets"]["base_info"]["name"],
        "vercel_token": body["connections"]["vercel_auth_token"],
        "github_token": body["connections"]["github_access_token"]
    }
    output_dir = cookiecutter(
        TEMPLATE_REPO_LINK,
        no_input=True,
        extra_context=context,
        output_dir="/tmp"
    )
    if not output_dir:
        return jsonify({"status": False, "error": "failed to template"})
    
    print(f"Templated successfully to {output_dir}")

    # Create github repo
    try: 
        repo = github.get_user().create_repo(safe_repo_name, description="Resume built using ResumUp", homepage=expected_vercel_link)
    except Exception as e:
        print(e)
        return jsonify({"status": False, "error": "failed to create repo"})
    print(repo)

    print(f"Created repository: {safe_repo_name}")

    # Upload files
    local_repo = Repo.init(output_dir)
    remote = local_repo.create_remote("origin", f"https://{username}:{access_token}@github.com/{username}/{safe_repo_name}")
    
    local_repo.git.add(".")
    local_repo.index.commit("Initial commit")
    remote.push(refspec="master:master")
    

    print("Files uploaded successfully.")

    # Create vercel deployment
    env = json.dumps({
        "VERCEL_AUTH_TOKEN": body['connections']['vercel_auth_token'],
        "GITHUB_ACCESS_TOKEN": body['connections']['github_access_token']
    })
    resp = requests.post(
        f"https://api.vercel.com/v13/deployments",
        json={
            "name": safe_repo_name,
            "framework": None,
            "env": env,
            "gitSource": {
                "org": username,
                "ref": "master",
                "repo": f"{safe_repo_name}",
                "type": "github"
            },
            "projectSettings": {
                "framework": None,
                "rootDirectory": None,
                "buildCommand": "flutter/bin/flutter build web --release --no-tree-shake-icons",
                "outputDirectory": "build/web",
                "installCommand": "if cd flutter; then git pull && cd .. ; else git clone https://github.com/flutter/flutter.git; fi && ls && flutter/bin/flutter doctor && flutter/bin/flutter clean && flutter/bin/flutter config --enable-web"
            },
        },

        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {body['connections']['vercel_auth_token']}"
        }
    )

    if not resp.status_code == 200:
        print(resp.json())
        return jsonify({"status": False, "error": "failed to create deployment"})

    print("Done creating deployment!")
    return jsonify({"status": True, "link": expected_vercel_link, "message": "successfully created deployment", "repo_name": safe_repo_name})


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5666))
