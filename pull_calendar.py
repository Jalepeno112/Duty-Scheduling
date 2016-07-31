from __future__ import print_function
import httplib2
import os

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

import datetime

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

import pandas as pd

import calendar
import duty_scheduling
# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'config/client_secret.json'
APPLICATION_NAME = 'Duty Schedule'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def pullCalendar():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of the next
    10 events on the user's calendar.
    """
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    #now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    beginning = datetime.datetime(2015, 9, 18).isoformat() + 'Z'
    print('Getting all events')
    eventsResult = service.events().list(
        calendarId="scu.edu_mlcu96o2hthn0o9qkhchlk2qlc@group.calendar.google.com", timeMin=beginning, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    if not events:
        print('No upcoming events found.')

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])

    return events


def main():
    events = pullCalendar()
    event_dict = {event['start'].get('dateTime', event['start'].get('date')): event['summary'].split(' & ') for event in events if len(event['summary'].split(' & ')) > 1}

    nameToEmail = {
        "Adam": "aspencley",
        "Zerreen": "zkazi",
        "Conary": "cmeyer",
        "Nicole": "nfite",
        "Logan": "lokawachi",
        "Lyndsey": "lkincaid",
        "Ella": "ekobelt",
        "Kelly": "clymberopoulos",
        "Isaac": "ijorgensen",
        "Amanda": "atorrez"
    }

    df = pd.DataFrame(event_dict).T
    df.columns = ['CF1', 'CF2']

    df.replace({"CF1":nameToEmail, "CF2":nameToEmail}, inplace=True)

    days = [duty_scheduling.day_type(calendar.day_name[datetime.datetime.strptime(d, "%Y-%m-%d").weekday()]) for d in df.index.values]
    df['Type'] = days
    index_values = [d.split("-") for d in df.index.values]
    index_values_fmt = [d[1] +"/"+d[2] for d in index_values]
    df.index = index_values_fmt
    type_order = ['Weekend', 'Wednesday', 'Weekday']
    users = nameToEmail.values()

    day_breakdown = duty_scheduling._dayBreakdown(df, users, type_order)
    print("CF Stats: \n{0}\n---------------------------".format(day_breakdown))

    duty_scheduling.writeToSheet(df, users, type_order, "output/FINAL_TEST.xlsx")


    return df



if __name__ == '__main__':
    main()