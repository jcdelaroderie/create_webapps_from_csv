########################################################################
# 
# Usage: % python3 create_webapps_from_csv.py <csv file>
#
# Example: python3 create_webapps_from_csv.py mylist.csv
#
# Requirements:  Python3 
#                Python3 packages as listed in import section
#                WAS subscription
#                Qualys API subscription
#
##########################################################################


import base64, csv, getpass, queue, re, requests, signal, sys, threading, time, urllib3, xml.etree.ElementTree as ET
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from datetime import datetime
from dateutil.relativedelta import relativedelta

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Global Variables

threads             = 250

config              = {"username":"",
                       "password":"",
                       "base_url":"",
                       "platform":""}
headers             = {"Content-type":"text/xml"}

##################
# ERROR HANDLING #
##################

def signal_handler(sig, frame):
    print('\n\nExiting\n\n')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def failure(api_request, response, payload):
    with lock:
        print("\nAn error was encountered processing the API request to {0}".format(api_request))
        print("\nFull response below\n--------------------\n")
        print("{0}\n\n".format(response))
        print("")
        if len(payload) > 0:
            print(payload)

def escape2(data): 
 
    if "&" in data: data = data.replace("&", "&amp;") 
    if "<" in data: data = data.replace("<", "&lt;") 
    if ">" in data: data = data.replace(">", "&gt;") 
    if '"' in data: data = data.replace('"', '&quot;') 
    if "'" in data: data = data.replace("'", "&apos;") 

    return data

########################
# API HELPER FUNCTIONS # 
########################

def get_status_code(data):
    tree    = ET.ElementTree(ET.fromstring(data))
    root    = tree.getroot()

    for item in root.findall("responseCode"):
        status = item.text
        return status
    else:
        return "SUCCESS"

def request_get(endpoint):

    username = config["username"]
    password = config["password"]
    base_url = config["base_url"]
    url      = base_url + endpoint

    response          = requests.get(url, headers=headers, auth=(username, password), verify=False)
    response.encoding = "utf-8"
    data              = response.text
    status            = get_status_code(data)

    if status != "SUCCESS":
        failure(url, data, "")

    return data

def request_post(endpoint, payload):

    username = config["username"]
    password = config["password"]
    base_url = config["base_url"]
    url      = base_url + endpoint

    if payload != "":
        response          = requests.post(url, headers=headers, data=payload.encode("utf-8"), auth=(username, password), verify=False)
    else:
        response          = requests.post(url, headers=headers, auth=(username, password), verify=False)
    response.encoding = "utf-8"
    data              = response.text
    status            = get_status_code(data)


    if status != "SUCCESS":
        failure(url, data, payload)

    return data

################################
# SETUP API CONNECTION DETAILS # 
################################

def get_api_server():

    platforms = {
            1 : ["US Platform 1", "https://qualysapi.qualys.com"],
            2 : ["US Platform 2", "https://qualysapi.qg2.apps.qualys.com"],
            3 : ["US Platform 3", "https://qualysapi.qg3.apps.qualys.com"],
            4 : ["US Platform 4", "https://qualysapi.qg4.apps.qualys.com"],
            5 : ["EU Platform 1", "https://qualysapi.qualys.eu"],
            6 : ["EU Platform 2", "https://qualysapi.qg2.apps.qualys.eu"],
            7 : ["IN Platform 1", "https://qualysapi.qg1.apps.qualys.in"]
            }

    print("\nSelect Platform")
    print("---------------")
    for x in range(1,len(platforms)+1):
        print ("{0}. {1}".format(x, platforms[x][0]))
    while True:
        selection = input("\nSelect Platform 1-{0}: ".format(len(platforms)+1))
        selection = is_int(selection)
        if selection != False:
            if selection > 0 and selection < (len(platforms)+1):
                url         = platforms[selection][1]
                platform    = platforms[selection][0]
                break
    return url, platform

def is_int(val):
    try:
        val = int(val)
        return val
    except:
        return False

def get_connection_details():

    global config

    base_url, platform    = get_api_server()
    username, password    = get_credentials(platform)
    response_code         = test_connection(username, password, base_url, headers)

    if response_code == "SUCCESS":
        print ("\nConnection to {0} successful".format(platform))
        config["base_url"] = base_url
        config["username"] = username
        config["password"] = password
        config["platform"] = platform
        return
    else:
        print ("\nConnection to {0} failed: {1}\nPlease check your credentials and try again.\n".format(platform, response_code))
        sys.exit()

def get_credentials(platform):
    print("Enter Credentials for {0}".format(platform))

    while True:
        user      = input("\nUsername: ")
        passwd    = getpass.getpass("Password: ")

        if len(user) > 0 and len(passwd) > 0:
            break
    return user, passwd

def test_connection(username, password, baseurl, headers):
    url         = baseurl + "/qps/rest/3.0/count/was/webapp"
    response    = requests.get(url, headers=headers, auth=(username, password), verify=False)
    data        = response.text
    data        = data.encode('ascii','ignore')
    status      = get_status_code(data)

    return status

#################
# API ENDPOINTS #
#################
def get_webapp_details(myCSV):

    webapp_list = []
    
    with open(myCSV, mode='r') as file:
        csvFile = csv.reader(file)
        for lines in csvFile:
            myDetails = {"myURL":lines[0], "myName":lines[1]}
            webapp_list.append(myDetails)
 
    return webapp_list


def create_webapp(myWebApp):

    endpoint = "/qps/rest/3.0/create/was/webapp/" 
    payload = """<ServiceRequest>
                 <data>
                 <WebApp>
                 <name><![CDATA[{0}]]></name>
                 <url><![CDATA[{1}]]></url>
                 </WebApp>
                 </data>
                 </ServiceRequest>""".format(myWebApp["myName"],myWebApp["myURL"])

    data = request_post(endpoint, payload)
    tree = ET.ElementTree(ET.fromstring(data))
    root = tree.getroot()

    try:
        for item in root.findall("./data/WebApp/id"):
            with lock:
                print("Created {0} : {1} {2}".format(item.text, myWebApp["myName"], myWebApp["myURL"]))
    except:
        pass


#######################
# Threading functions #
#######################

def next_target(q, thread_no):

    try:
        while q.qsize() != 0:
            target = q.get()
            create_webapp(target)
            next_target(q, thread_no)
            q.task_done()
    except:
        q.task_done()



########
# MAIN # 
########

if __name__ == "__main__":

    if len(sys.argv) != 2: 
        print ("\nUsage:  python3 create_webapps_from_csv.py <csv file>\n")
        sys.exit()

    lock = threading.Lock()    
    get_connection_details()
    targets = get_webapp_details(sys.argv[1])
    q = queue.Queue()
    for target in targets:
        q.put(target)

    for n in range(1,threads+1):
        while q.qsize() != 0:
            try:
                worker = threading.Thread(target=next_target, args=(q, n,), daemon=True)
                worker.start()
                time.sleep(0.5)
            except:
                pass
    
    q.join()

    print ("\nFinished")
