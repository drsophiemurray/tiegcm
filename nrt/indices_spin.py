'''
Python Version:    2.7.2 (default, Oct  1 2012, 15:56:20)
@author: smurray@eld264
Created on Jun 19, 2014
Purpose: Called by tie_cron_job.py to get indices needed to run TIEGCM forecasts.
'''

import datetime
import numpy as np
import os

#CENTRAL_DATE = datetime.datetime.utcnow()
FOLDER_LOC = "".join([os.path.expanduser('~'), "/indices/"])

def main(spin_days):  
    """Get kp and f10.7 values from a week ago
    for a spin up TIEGCM run.
    """
    kph, f107h, f107a = get_values(spin_days) 
    print "F10.7 a week ago was", f107h
    print "Kp a week ago was", kph
    print "Average F10.7 a week ago was", f107a
    return kph, f107h, f107a


def get_values(spin_days): 
    """Get values from indices_record.dat
    .dat file is arranged year[0], month[1], day[2], f10.7[3], kp[4]
    """
    if not os.path.isdir(FOLDER_LOC):
        os.mkdir(FOLDER_LOC)
    data = np.loadtxt("".join((FOLDER_LOC, "indices_record.dat")))
    length = len(data)
    kph  = data[length - (spin_days -1), 4]
    f107h  = data[length - (spin_days - 1), 3]
    f107 = data[:, 3]
    f107a = f107[(len(f107)- (spin_days -2)) - 41 : (len(f107) - (spin_days - 2))].mean()
    return kph, f107h, f107a
