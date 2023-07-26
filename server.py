from flask import Flask, jsonify, request
import os
from flask_cors import  CORS
import mysql.connector

cnx = mysql.connector.connect(host ="gateway01.eu-central-1.prod.aws.tidbcloud.com",user ="Pd5yfUT23Tzbine.root",password ="8fIdoyXs7zyI7bjL",   port="4000",  database="ResumeUp")
cursor = cnx.cursor()

app = Flask(__name__)
CORS(app, origins=["*"])

@app.route('/')
def index():
    return jsonify({"Choo Choo": "Welcome to your Flask app 🚅"})

@app.route('/getToken', methods=['POST'])
def get():
    body = request.json
    cursor.execute(
            "Select VercelAuthToken FROM VercelAuthTokens Where Uid = '{}';".format(body['Uid']))
    for i in cursor:
        VercelToken = i[0]
    return  jsonify({"VercelToken": VercelToken})
@app.route('/putToken', methods=['POST'])
def create():
    body = request.json
    cursor.execute(
            "INSERT INTO VercelAuthTokens(UID, VercelAuthToken) VALUES('{}','{}');".format(body['Uid'], body['VercelToken']))
    cnx.commit()
    return  jsonify({"Status": "pushed successfully"})

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5666))









