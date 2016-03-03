'''
Python Version:    2.7.2 (default, Oct  1 2012, 15:56:20)
@author: smurray@eld264
Created on Jun 19, 2014
Purpose: Grab latest indices forecasts everday from NOAA/SWPC and BGS, and save to a .dat file
            for later use with running TIEGCM in nrt.
'''

import datetime
import numpy as np
import os

CENTRAL_DATE = datetime.datetime.utcnow()
FOLDER_LOC = "".join([os.path.expanduser('~'), "/indices/"])


def main():  
    """Download latest F10.7 and Kp values and forecasts,
    then record yesterdays observed values and calculate
    81 day average, and finally return values for 'tiegcm_run'.
    (these values will be inputted to TIEGCM, the results
    of which to be plotted on a webpage).
    """
    try:
        dsd, dgd, forecast = download_data()
    except IOError:
        print 'Download error from NOAA and/or BGS site'
    f107h, f107, f107f, f107ff = get_f107(dsd, forecast) 
    kph, kp, kpf, kpff = get_kp(dgd) 
    print "F10.7 yesterday was", f107h
    print "Kp yesterday was", kph
    print "F10.7 today will be", f107
    print "Kp today will be", kp
    print "F10.7 tomorrow will be", f107f
    print "Kp tomorrow will be", kpf
    print "F10.7 next day will be", f107ff
    print "Kp next day will be", kpff
    record_file = "".join((FOLDER_LOC,"indices_record.dat"))
    if os.path.isfile(record_file) is True:
        record_values(f107h, kph)
    else:
        save_values(f107h, kph)
    f107a = calc_av()
    print "Average F10.7 is", f107a
    return kp, f107, f107a, kpf, f107f, kpff, f107ff


def save_values(f107h, kph):
    """Only used to save values in first instance
    when .dat file doesn't yet exist.
    (see "record_values" function for more information.)
    """
    yesterday = (CENTRAL_DATE - datetime.timedelta(days = 1))
    array = np.empty((1, 5))
    array[0, :] = yesterday.year, yesterday.month, yesterday.day, f107h, kph
    np.savetxt("".join((FOLDER_LOC, "indices_record.dat")), 
               array, 
               fmt = "%i  %i  %i  %i  %0.1f", 
               header = "year month day f107 kp")


def record_values(f107h, kph): #should add a 'check if date is saved' here
    """Save Kp and F10.7 values for yesterday to a .dat file
    for 81-day averaging and general record-keeping.
    """
    orig = np.loadtxt("".join((FOLDER_LOC, "indices_record.dat")))
    yesterday = (CENTRAL_DATE - datetime.timedelta(days = 1))
    new = np.empty((1, 5))
    new[0, :] = yesterday.year, yesterday.month, yesterday.day, f107h, kph
    orig = np.concatenate((orig, new), axis = 0)
    np.savetxt("".join((FOLDER_LOC,"indices_record.dat")), 
               orig, 
               fmt = "%i  %i  %i  %i  %0.1f", 
               header = "year month day f107 kp")


def calc_av():
    """Cannot calculate 81-day centered average,
    so instead calculate mean over previous 40 days"""
    data = np.loadtxt("".join((FOLDER_LOC, "indices_record.dat")))
    f107 = data[:, 3]
    f107a = f107[len(f107)-41:len(f107)].mean()
    return round(f107a, 1)
    

def get_f107(dsd, forecast):
    """Obtain yesterday, today,
    and tomorrows F10.7 flux.
    """
    past_date = (CENTRAL_DATE - datetime.timedelta(days = 1)).strftime("%Y %m %d") 
    today = CENTRAL_DATE.strftime("%Y %b %d") 
    forecast_date = (CENTRAL_DATE + datetime.timedelta(days = 1)).strftime("%Y %b %d") 
    next_date = (CENTRAL_DATE + datetime.timedelta(days = 2)).strftime("%Y %b %d") 
    width = 3
    try:
        with open(dsd, "r") as inp:
            for line in inp:
                if line.startswith(past_date):
                    f107h = (line[len(past_date):].strip())[0 : width + 1]
    except IOError:
        print "Cannot find file", dsd
    try:
        with open(forecast, "r") as inp:
            for line in inp:
                if line.startswith(today):
                    fore = line[len(today):].strip()
                    f107 = fore[0: width + 1]
    except IOError:
        raise "Cannot find file", forecast
    try:
        with open(forecast, "r") as inp:
            for line in inp:
                if line.startswith(forecast_date):
                    fore = line[len(forecast_date):].strip()
                    f107f = fore[0: width + 1]
    except IOError:
        raise "Cannot find file", forecast
    try:
        with open(forecast, "r") as inp:
            for line in inp:
                if line.startswith(next_date):
                    fore = line[len(next_date):].strip()
                    f107ff = fore[0: width + 1]
    except IOError:
        raise "Cannot find file", forecast
    del fore
    return int(f107h), int(f107), int(f107f), int(f107ff)   #not sure if need to do this but may as well


def get_kp(dgd):
    """Obtain yesterday, today,
    and tomorrows planetary Kp values"""
    past_date = (CENTRAL_DATE - datetime.timedelta(days = 1)).strftime("%d/%m/%Y") 
    today = CENTRAL_DATE.strftime("%d/%m/%Y") 
    forecast_date = (CENTRAL_DATE + datetime.timedelta(days = 1)).strftime("%d/%m/%Y") 
    next_date = (CENTRAL_DATE + datetime.timedelta(days = 2)).strftime("%d/%m/%Y") 
    width = 3
    try:
        with open(dgd, "r") as inp:
            for line in inp:
                if line.startswith(past_date):
                    kph = (line[len(past_date):].strip())[width::]
    except IOError:
        raise "Cannot find file", dgd
    try:
        with open(dgd, "r") as inp:
            for line in inp:
                if line.startswith(today):
                    kp = (line[len(today):].strip())[width::]
    except IOError:
        raise "Cannot find file", dgd
    try:
        with open(dgd, "r") as inp:
            for line in inp:
                if line.startswith(forecast_date):
                    kpf = (line[len(forecast_date):].strip())[width::]
    except IOError:
        raise "Cannot find file", dgd
    try:
        with open(dgd, "r") as inp:
            for line in inp:
                if line.startswith(next_date):
                    kpff = (line[len(next_date):].strip())[width::]
    except IOError:
        raise "Cannot find file", dgd
    return float(kph), float(kp), float(kpf), float(kpff)


def download_data():
    """Download latest data from NOAA/SWPC and BGS
    to indices folder in home area.
    """
    forecast = download("http://legacy-www.swpc.noaa.gov/ftpdir/latest/27DO.txt")
    dsd = download("http://legacy-www.swpc.noaa.gov/ftpdir/latest/DSD.txt")
    dgd = download_pass("http://www.geomag.bgs.ac.uk/SpaceWeather/dailyKp.out", "user", "password")
    return dsd, dgd, forecast


def download(url): 
    """Copy the contents of a file from a given URL.
    """
    import urllib2
    import os
    web_file = urllib2.Request(url)
    web_file.add_header('Cache-Control', 'max-age=0')   #so this makes sure the latest version is downloaded
    web_file = urllib2.build_opener().open(web_file)
    folder = "".join([os.path.expanduser('~'), "/indices/"])
    file_loc = "".join([os.path.expanduser('~'), "/indices/", url.split('/')[-1]])
    if not os.path.isdir(folder):
        os.mkdir(folder)
    save_file = open(file_loc, 'w')
    save_file.write(web_file.read())
    web_file.close()
    save_file.close()
    del folder
    return file_loc


def download_pass(url, user, passw): 
    """Copy the contents of a file from a given URL
    that is password protected
    """
    import urllib2
    import os
    #first set up authentication
    passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
    passman.add_password(None, url, user, passw)
    handler = urllib2.HTTPBasicAuthHandler(passman)
    opener = urllib2.build_opener(handler)
    urllib2.install_opener(opener)
    #now ensure not cached
    web_file = urllib2.Request(url)
    web_file.add_header('Cache-Control', 'max-age=0')
    #write file
    web_file = urllib2.urlopen(url)
    folder = "".join([os.path.expanduser('~'), "/indices/"])
    file_loc = "".join([os.path.expanduser('~'), "/indices/", url.split('/')[-1]])
    if not os.path.isdir(folder):
        os.mkdir(folder)
    save_file = open(file_loc, 'w')
    save_file.write(web_file.read())
    web_file.close()
    save_file.close()
    del folder
    return file_loc


def parsefix(line, offsets):
    """Better method to extract values 
    in get_values - to be written in maybe eventually!.
    """
    fields = []
    start = offsets[0]
    for end in offsets[1:]:
        f = line[start:end].strip()
        fields.append(f)
        start = end       
    return fields


if __name__ == '__main__':
    main()
