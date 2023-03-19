FROM python:3.8-slim

# install google chrome
RUN apt-get -y update
RUN apt-get -y install curl wget unzip gnupg
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
RUN apt-get update -qqy --no-install-recommends && apt-get install -qqy --no-install-recommends google-chrome-stable

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

# install selenium wire ca certificate
RUN apt-get install libnss3-tools
RUN python3 -m seleniumwire extractcert
RUN certutil -d sql:$HOME/.pki/nssdb -A -t TC -n "Selenium Wire" -i ca.crt

CMD ["python3", "./bot.py"]
