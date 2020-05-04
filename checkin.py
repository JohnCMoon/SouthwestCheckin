#!/usr/bin/env python
"""Southwest Checkin.

Usage:
  checkin.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME [CONF_EMAIL] [-v | --verbose]
  checkin.py (-h | --help)
  checkin.py --version

Options:
  -h --help     Show this screen.
  -v --verbose  Show debugging information.
  --version     Show version.

"""
from datetime import datetime
from datetime import timedelta
from dateutil.parser import parse
from docopt import docopt
from math import trunc
from pytz import utc
from southwest import Reservation, openflights
from threading import Thread
import sys
import time
import sendgrid
import os
from sendgrid.helpers.mail import *

CHECKIN_EARLY_SECONDS = 5
ACTIVE_CHECKINS = os.path.dirname(os.path.realpath(__file__)) + "/active_checkins.csv"
SG_API_KEY = os.environ.get('SENDGRID_API_KEY')
SG_FROM_EMAIL = os.environ.get('SG_FROM_EMAIL')

def schedule_checkin(flight_time, reservation, email=""):
    checkin_time = flight_time - timedelta(days=1)
    current_time = datetime.utcnow().replace(tzinfo=utc)
    # check to see if we need to sleep until 24 hours before flight
    if checkin_time > current_time:
        # calculate duration to sleep
        delta = (checkin_time - current_time).total_seconds() - CHECKIN_EARLY_SECONDS
        # pretty print our wait time
        m, s = divmod(delta, 60)
        h, m = divmod(m, 60)
        print("Too early to check in.  Waiting {} hours, {} minutes, {} seconds".format(trunc(h), trunc(m), s))
        # CSV line representing this reservation
        csv = reservation_number + "," + first_name + "," + last_name + ","
        if email is not None:
            csv += email + ","
        csv += str(flight_time) + "\n"

        # Since we're waiting for this checking, add ourselves to a list of active checkins
        # allowing us to get reset if this thread dies for some reason
        with open(ACTIVE_CHECKINS, "w+") as f:
            for line in f:
                if line == csv:
                    break
            else:
                f.write(csv);
        try:
            time.sleep(delta)
        except OverflowError:
            print("System unable to sleep for that long, try checking in closer to your departure date")
            sys.exit(1)

    data = reservation.checkin()
    for flight in data['flights']:
        for doc in flight['passengers']:
            s = "{} got {}{}!".format(doc['name'], doc['boardingGroup'], doc['boardingPosition']);
            email_body += s

    # Remove from CSV file once reservation is completed
    active_tmp =  ACTIVE_CHEKINS + '.bak'
    with open(ACTIVE_CHECKINS, 'r') as active, open(active_tmp, 'w') as tmp:
        for line in active:
            if line != csv:
                write_obj.write(line)
    os.remove(active)
    os.rename(tmp, active)

    if email is not None and email_body is not None:
        send_confirmation_email(email, email_body)

def auto_checkin(reservation_number, first_name, last_name, email="", verbose=False):
    r = Reservation(reservation_number, first_name, last_name, verbose)
    body = r.lookup_existing_reservation()

    # Get our local current time
    now = datetime.utcnow().replace(tzinfo=utc)
    tomorrow = now + timedelta(days=1)

    threads = []

    # find all eligible legs for checkin
    for leg in body['bounds']:
        # calculate departure for this leg
        airport = "{}, {}".format(leg['departureAirport']['name'], leg['departureAirport']['state'])
        takeoff = "{} {}".format(leg['departureDate'], leg['departureTime'])
        airport_tz = openflights.timezone_for_airport(leg['departureAirport']['code'])
        date = airport_tz.localize(datetime.strptime(takeoff, '%Y-%m-%d %H:%M'))
        if date > now:
            # found a flight for checkin!
            print("Flight information found, departing {} at {}".format(airport, date.strftime('%b %d %I:%M%p')))
            # Checkin with a thread
            t = Thread(target=schedule_checkin, args=(date, r, email))
            t.daemon = True
            t.start()
            threads.append(t)

    time.sleep(0.2)
    print("No more flights associated with this reservation")
    # cleanup threads while handling Ctrl+C
    while True:
        if len(threads) == 0:
            break
        for t in threads:
            t.join(5)
            if not t.is_alive():
                threads.remove(t)
                break

def send_confirmation_email(email, email_body):
    sg = sendgrid.SendGridAPIClient(api_key=SG_API_KEY)
    from_email = Email(SG_FROM_EMAIL)
    to_email = To(email)
    subject = "You're checked in!"
    content = Content("text/plain", email_body)
    mail = Mail(from_email, to_email, subject, content)
    response = sg.client.mail.send.post(request_body=mail.get())

if __name__ == '__main__':

    arguments = docopt(__doc__, version='Southwest Checkin 3')
    reservation_number = arguments['CONFIRMATION_NUMBER']
    first_name = arguments['FIRST_NAME']
    last_name = arguments['LAST_NAME']
    email = arguments['CONF_EMAIL']
    verbose = arguments['--verbose']

    try:
        print("Attempting to check in {} {}. Confirmation: {}\n".format(first_name, last_name, reservation_number))
        auto_checkin(reservation_number, first_name, last_name, email, verbose)
    except KeyboardInterrupt:
        print("Ctrl+C detected, canceling checkin")
        sys.exit()
