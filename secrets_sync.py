import os
import json
import requests
import base64
import urllib.parse


############ Get some variables from the OS
# Get the Bearertoken for the Service Account
with open("/var/run/secrets/kubernetes.io/serviceaccount/token","r") as f:
    token=f.readlines()[0]


# Get the OS Environmental data
k8s_ip=os.environ["KUBERNETES_SERVICE_HOST"]
k8s_port=os.environ["KUBERNETES_SERVICE_PORT"]

# Get the secrets we need to sync
with open("/etc/config/secrets.txt","r") as f:                                                                                                                            
    secrets=f.readlines()                                                                                                                                                                            

######################### Secret Server area #####################
# Get the creds for connecting to Secret Server and Secret Server's URL and assign them to variables
with open("/etc/secrets/.creds.json","r") as f:
    secret_srv_creds=f.readlines()

secret_srv_url=json.loads(secret_srv_creds[0])["url"]
secret_srv_user=json.loads(secret_srv_creds[0])["username"]
sercet_srv_passwd=json.loads(secret_srv_creds[0])["passwd"]

# Get Authentication token for Secret Server
payload = 'username='+urllib.parse.quote(secret_srv_user)+'&password='+urllib.parse.quote(sercet_srv_passwd)+'&grant_type=password'
secret_srv_headers = {
  'Content-Type': 'application/x-www-form-urlencoded'
}
response = requests.post(secret_srv_url+"/oauth2/token", headers=secret_srv_headers, data=payload)
bearertoken=json.loads(response.text)['access_token']

########### Setup the needed information to be able to connect to k8s API server
# Set the cert file we need to connect to k8s
cert_file="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

# Construct the headers we need for Authentication towards k8s
k8s_headers={'Authorization':'Bearer '+token}

########### Get the Secrets we need to synchronize according to the ConfigMap if they exist in k8s
for secret_raw in secrets:
    secret=secret_raw.rstrip()
    response=requests.get("https://"+k8s_ip+":"+k8s_port+"/api/v1/namespaces/default/secrets/"+secret, headers=k8s_headers, verify=cert_file)
    if response.status_code != 404:
        # Secret exists, need to be updated
        print("Updating existing Secret")
        
        try:
            # Getting the Secret Id for the secret from Secret Server
            secret_srv_headers={'Authorization':'Bearer '+bearertoken}
            secret_resp=requests.get(secret_srv_url+"/api/v2/secrets?filter.searchText="+secret, headers=secret_srv_headers)
            secret_id=json.loads(secret_resp.text)['records'][0]['id']

            # Get the associated password for the secret
            secret_resp=requests.get(secret_srv_url+"/api/v2/secrets/"+str(secret_id), headers=secret_srv_headers)
            secret_items_list=json.loads(secret_resp.text)['items']
            for item in secret_items_list:
                if item['slug']=="password":
                    secret_passwd=item['itemValue']
        except:
            print("No access to secret in Secret Server")

        # Create the secret in k8s with the correct password
        k8s_headers={"Content-Type":"application/merge-patch+json","Authorization":"Bearer "+token}
        passwd_b64=base64.b64encode(secret_passwd.encode("ascii")).decode('utf-8')         
        payload={"data":{"password":str(passwd_b64)}}
        try:
            create_resp=requests.patch("https://"+k8s_ip+":"+k8s_port+"/api/v1/namespaces/default/secrets/"+secret, data=json.dumps(payload),headers=k8s_headers, verify=cert_file)
        except:
            print("Could not update the secret in k8s! Error message is "+create_resp.text)
    else:
        # New secret, need to be created
        print("New secret needs to be created")
       
        # Getting the Secret Id for the secret from Secret Server
        try:
            secret_srv_headers={'Authorization':'Bearer '+bearertoken}
            secret_resp=requests.get(secret_srv_url+"/api/v2/secrets?filter.searchText="+secret, headers=secret_srv_headers)
            secret_id=json.loads(secret_resp.text)['records'][0]['id']
            
            # Get the associated password for the secret
            secret_resp=requests.get(secret_srv_url+"/api/v2/secrets/"+str(secret_id), headers=secret_srv_headers)
            secret_items_list=json.loads(secret_resp.text)['items']
            for item in secret_items_list:
                if item['slug']=="password":
                    secret_passwd=item['itemValue']
        except:
            print("No access to secret in secret server")
            
        # Create the secret in k8s with the correct password
        passwd_b64=base64.b64encode(secret_passwd.encode("ascii")).decode('utf-8')         
        payload={"apiVersion":"v1","kind":"Secret","metadata":{"name":secret.rstrip()},"data":{"password":str(passwd_b64)}, "type":"Opaque"}
        k8s_headers={"Content-Type":"application/json",'Authorization':'Bearer '+token}
        try:
            create_resp=requests.post("https://"+k8s_ip+":"+k8s_port+"/api/v1/namespaces/default/secrets/", data=json.dumps(payload),headers=k8s_headers, verify=cert_file)
        except:
            print("Could not create the secret in k8s! Error message is "+create_resp.text)