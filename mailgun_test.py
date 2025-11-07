import os
import requests
def send_simple_message():
  	return requests.post(
  		"https://api.mailgun.net/v3/sandbox6bc58548702e43ea989a12b9eb0c4bd0.mailgun.org/messages",
  		auth=("api", os.getenv('MAILGUN_API_KEY', 'MAILGUN_API_KEY')),
  		data={"from": "Mailgun Sandbox <postmaster@sandbox6bc58548702e43ea989a12b9eb0c4bd0.mailgun.org>",
			"to": "Grace Matsuoka <team@campuscares.us>",
  			"subject": "Hello Grace Matsuoka",
  			"text": "Congratulations Grace Matsuoka, you just sent an email with Mailgun! You are truly awesome!"})

if __name__ == "__main__":
    response = send_simple_message()
    print("Status code:", response.status_code)
    print("Response body:", response.text)