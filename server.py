from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from github import Github, Auth
from cookiecutter.main import cookiecutter
from git import Repo

import os
import json

import mysql.connector
import requests

TEMPLATE_REPO_LINK = "https://github.com/TiDB-Hacks/resumeup_template"

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


@app.route("/")
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})


@app.route("/getToken", methods=["POST"])
def get():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
        "Select VercelAuthToken FROM VercelAuthTokens Where Uid = '{}';".format(
            body["Uid"]
        )
    )
    for i in cursor:
        vercel_token = i[0]
    return jsonify({"VercelToken": vercel_token})


@app.route("/putToken", methods=["POST"])
def create():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
        "INSERT INTO VercelAuthTokens(UID, VercelAuthToken) VALUES('{}','{}');".format(
            body["Uid"], body["VercelToken"]
        )
    )
    cnx.commit()
    return jsonify({"Status": "pushed successfully"})


@app.route("/getChart", methods=["POST"])
def getChart():
    body = request.json
    url = "https://github-contributions-api.deno.dev/{}.svg?no-total=true&no-legend=true&frame=FFBF00".format(
        body["Uname"]
    )
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    return jsonify({"Svg": response.content.decode("utf-8")})


@app.route("/setStatus", methods=["POST"])
def send_Status():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
        "INSERT INTO DeployStatus(UID, Status) VALUES('{}','{}');".format(
            body["Uid"], body["Status"]
        )
    )
    cnx.commit()
    return jsonify({"Executed": "yep"})


@app.route("/getStatus", methods=["POST"])
def get_status():
    body = request.json
    cnx.reconnect()
    cursor = cnx.cursor()
    cursor.execute(
        "Select Status FROM DeployStatus Where Uid = '{}';".format(body["Uid"])
    )

    for i in cursor:
        status = i[0]

    return jsonify({"Status": status})


@app.route("/deploy", methods=["POST"])
def deploy():
    body = request.json

    # Create github instance
    github = Github(auth=Auth.Token(body["connections"]["github_access_token"]))

    safe_repo_name = (
        body["widgets"]["base_info"]["name"].lower().replace(" ", "") + "-resumup"
    )
    expected_vercel_link = f"https://{safe_repo_name}.vercel.app"

    # Remove existing output dir, if any
    if os.path.exists("/tmp/" + safe_repo_name):
        os.system(f"rm -rf /tmp/{safe_repo_name}")

    username = body["widgets"]["contactme"]["github_username"]
    github_access_token = body["connections"]["github_access_token"]
    vercel_auth_token = body["connections"]["vercel_auth_token"]

    context = {
        "project_name": safe_repo_name,
        "author_name": body["widgets"]["base_info"]["name"],
        "is_vercel_active": body["widgets"]["vercel"],
        "is_profile_active": body["widgets"]["avatar"],
        "is_github_activity_active": body["widgets"]["github_activity"],
        "is_github_chart_active": body["widgets"]["github_chart"],
        "twitter_uname": body["widgets"]["contactme"]["twitter_username"],
        "linkedIn_uname": body["widgets"]["contactme"]["linkedin_username"]
    }
    output_dir = cookiecutter(
        TEMPLATE_REPO_LINK, no_input=True, extra_context=context, output_dir="/tmp"
    )
    if not output_dir:
        return jsonify({"status": False, "error": "failed to template"})

    print(f"Templated successfully to {output_dir}")

    # Create github repo
    try:
        repo = github.get_user().create_repo(
            safe_repo_name,
            description="Resume built using ResumUp",
            homepage=expected_vercel_link,
        )
    except Exception as e:
        print(e)
        return jsonify({"status": False, "error": "failed to create repo"})
    print(repo)

    print(f"Created repository: {safe_repo_name}")

    # Upload files
    local_repo = Repo.init(output_dir)
    remote = local_repo.create_remote(
        "origin",
        f"https://{username}:{github_access_token}@github.com/{username}/{safe_repo_name}",
    )

    local_repo.git.add(".")
    local_repo.index.commit("Initial commit")
    remote.push(refspec="master:master")

    print("Files uploaded successfully.")

    vercel_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {vercel_auth_token}",
    }

    resp = requests.post(
        "https://api.vercel.com/v9/projects",
        json={
            "name": safe_repo_name,
            "buildCommand": "flutter/bin/flutter build web --release --no-tree-shake-icons",
            "outputDirectory": "build/web",
            "environmentVariables": [
                {
                    "key": "GITHUB_ACCESS_TOKEN",
                    "target": "production",
                    "value": github_access_token,
                    "type": "plain",
                },
                {
                    "key": "VERCEL_AUTH_TOKEN",
                    "target": "production",
                    "value": vercel_auth_token,
                    "type": "plain",
                },
            ],
            "installCommand": "if cd flutter; then git pull && cd .. ; else git clone https://github.com/flutter/flutter.git; fi && ls && flutter/bin/flutter doctor && flutter/bin/flutter clean && flutter/bin/flutter config --enable-web",
        },
        headers=vercel_headers,
    )

    if not resp.status_code == 200:
        print(resp.json())
        return jsonify({"status": False, "error": "failed to create vercel profject"})

    # Create vercel deployment
    resp = requests.post(
        f"https://api.vercel.com/v13/deployments",
        json={
            "name": safe_repo_name,
            "gitSource": {
                "org": username,
                "ref": "master",
                "repo": safe_repo_name,
                "type": "github",
            },
        },
        headers=vercel_headers,
    )

    if not resp.status_code == 200:
        print(resp.json())
        return jsonify({"status": False, "error": "failed to create deployment"})

    print("Done creating deployment!")

    return jsonify(
        {
            "status": True,
            "link": expected_vercel_link,
            "message": "successfully created deployment",
            "repo_name": safe_repo_name,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5666))
