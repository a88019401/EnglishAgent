import requests
import json


url = "https://script.google.com/macros/s/AKfycbyJFFavEZajjACFuQPphh21YjvdU4OloU7LNfowRWEdj-Bvvc-2Nk3rbFKclVjB61XS/exec"

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