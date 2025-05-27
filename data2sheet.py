import requests
import json


url = "https://script.google.com/macros/s/AKfycbx-Ca5biY12JxXfL2SEJvdieknqChjUxdZ4c5OtOp0a2phNm62edD7m6wH_ogYNFlHsqQ/exec"

# get data
def doGet():
    response = requests.get(url)
    data = response.json()

    print(data)
    return data


# post data

def doPost(payload):

    response = requests.post(url, json=payload)
    # print(response.text)
    return response.text