'''
Python Version:    2.7.2 (default, Oct  1 2012, 15:56:20)
@author: smurray@eld264
Created on Jul 31, 2014
Purpose: Main code to run TIEGCM daily to produce three-day forecasts.
Notes: Most of tie_run.py is purposely taken from the way ehenley has DA running. Possibly
            not the most robust/quickest method, but at least it makes the code
            easier to integrate with DA in the future..
'''
import indices_input
import indices_spin
import tie_run
import tie_plot
import datetime as dt
import os
import subprocess

#Work out UTC midday for today
utc_now = dt.datetime.utcnow()
utc_midday = dt.datetime(utc_now.year, utc_now.month, utc_now.day, hour=12)

CENTRAL_DATE = utc_midday #Always behave as if script run at UTC midday today
SPIN_DAYS = 7
FORECAST_DAYS = 2  #TODO: start of making below cleaner!
LEVEL = 21

def main():
    """Run this code daily to produce thermospheric forecasts:
    Obtain indices, run code, make plots, put on webpage.
    
    """
    today = CENTRAL_DATE - dt.timedelta(hours = 12)
    tomorrow = today + dt.timedelta(days = 1)
    next_day = today + dt.timedelta(days = 2)
    spin_time =  today - dt.timedelta(days = SPIN_DAYS)
    spin_source, source_time = choose_source(spin_time)
    
    print "Find indices from", spin_time.strftime("%Y %m %d")
    kp, f107, f107a = indices_spin.main(SPIN_DAYS)
    print "Spin up TIEGCM for one week"
    p_file_last, full_pfile_path, da_path, dataout_fullpath, firstsourcepath = tie_run.main(spin_time, 
                                                                                kp, f107, f107a, 
                                                                                prim_hours = 24*SPIN_DAYS, 
                                                                                firstsource = spin_source, sourcetime = source_time)
    new_source_path = clean_spin(p_file_last, full_pfile_path, 
                                 da_path, dataout_fullpath, 
                                 firstsourcepath)
    print "TIEGCM spinned up!"
    
    print "Now get indices for forecast"
    kp, f107, f107a, kpf, f107f, kpff, f107ff = indices_input.main()
    
    print "Running TIEGCM in forecast mode"
    
    print "Running today's forecast"
    p_file_last, new_source_path, new_secstart_path_today = tie_steps(new_source_path, today, 
                                                                      kp, f107, f107a, 
                                                                      p_file_last, 
                                                                      image_name = "today_forecast")
    
    print "Running tomorrow's forecast"
    p_file_last, new_source_path, new_secstart_path_tom = tie_steps(new_source_path, tomorrow, 
                                                                    kpf, f107f, f107a, 
                                                                    p_file_last, 
                                                                    image_name = "tomorrow_forecast")
    
    print "Running next day (day after tomorrow's) forecast"
    p_file_last, new_source_path, new_secstart_path_next = tie_steps(new_source_path, next_day, 
                                                                     kpff, f107ff, f107a, 
                                                                     p_file_last, 
                                                                     image_name = "next_forecast")
    
    print "Doing final clean up"  # NOTE: data could be moved to MOOSE if there is interest
    delete_something(new_source_path, 
                new_secstart_path_today, 
                new_secstart_path_tom,
                new_secstart_path_next)    
    
    print "All done! Images now available online"


def tie_steps(initial_source_path, in_date, kp, f107, f107a, p_file_last, image_name):
    """Start a forecast TIEGCM run, and clean up files when ended"""
    
    print "Note, {} is being used as source file".format(initial_source_path)
    p_file_last_today, full_pfile_path_today, da_path_today, dataout_fullpath_today, firstsourcepath_today = tie_run.main(in_date, 
                                                                                kp, f107, f107a, 
                                                                                prim_hours = 24,  
                                                                                firstsource = p_file_last, sourcetime = None)
    print "Cleaning up data files" 
    new_source_path_today, new_secstart_path_today = clean_up(p_file_last_today, full_pfile_path_today, 
                                                                      da_path_today, dataout_fullpath_today, 
                                                                      firstsourcepath_today, p_file_last, in_date)
    print "Plotting forecast"
    tie_plot.main(new_secstart_path_today, LEVEL, time_element = 2, image_name = image_name)  #time_element = 2 means midday
    return p_file_last_today, new_source_path_today, new_secstart_path_today



def choose_source(time):
    """Figure out what TIEGCM source file to use, based on the month of the year
    Also return appropriate source time for .inp file.
    # TODO: update this to change to *_smin when in solar min, *_smax when in solar max
    # TODO: update this to be TIEGCM version independent?
    # TODO: see if want to be more centred about solstices/equinoxes: currently
            apply file for period 21 days before, 2 months & ~10 days after
    
    """
    
    #Determine which solstice/equinox file to use
    if 1 <= time.month < 3:
        firstsource = "TGCM.tiegcm1.95.pcntr_decsol_smax.nc"   #or 'smin'
        source_time = "355, 0, 0"
    elif 3 <= time.month < 6:
        firstsource = "TGCM.tiegcm1.95.pcntr_mareqx_smax.nc"
        source_time = "80, 0, 0"
    elif 6 <= time.month < 9:
        firstsource = "TGCM.tiegcm1.95.pcntr_junsol_smax.nc"
        source_time = "172, 0, 0"
    elif 9 <= time.month < 12:
        firstsource = "TGCM.tiegcm1.95.pcntr_sepeqx_smax.nc"
        source_time = "264, 0, 0"
    elif time.month == 12:
        firstsource = "TGCM.tiegcm1.95.pcntr_decsol_smax.nc"
        source_time = "355, 0, 0"
    else:
        ValueError, "Unexpected value for time.month: {}".format(time.month)
    
    return firstsource, source_time


def clean_spin(p_file_last, full_pfile_path, 
               da_path, dataout_fullpath, 
               firstsourcepath):
    """Copy p file back to main folder for forecast run, then delete input & 
    data files used for spin-up
    
    """

    new_source_path = os.path.join(firstsourcepath, p_file_last)
    sys_call = "".join(['cp {} {} '.format(full_pfile_path, new_source_path)])
    subprocess.call(sys_call, shell = True)

    delete_something(da_path, dataout_fullpath)

    return new_source_path


def clean_up(p_file_last, full_pfile_path, 
             da_path, dataout_fullpath, 
             firstsourcepath, p_file_last_old, in_date):
    """Copy p file back to main folder for next forecast run, then delete input 
    and data files used for previous forecast
    
    """
    
    new_source_path = os.path.join(firstsourcepath, p_file_last)     #copy primary file for new source
    sys_call = "".join(['cp {} {} '.format(full_pfile_path, new_source_path)])
    subprocess.call(sys_call, shell = True)
   
    sec_start, sec_end, main_name = get_sec_names(in_date) #then copy secondaries
    secstart_path = os.path.join(da_path, main_name, sec_start)
    new_secstart_path = os.path.join(firstsourcepath, sec_start)
    sys_call = "".join(['cp {} {} '.format(secstart_path, new_secstart_path)])
    subprocess.call(sys_call, shell = True)

#    secend_path  = os.path.join(da_path, main_name, sec_end)   #dont need this for now, but left in case need in future
#    new_secend_path  = os.path.join(firstsourcepath, sec_end)   
#    sys_call = "".join(['cp {} {} '.format(secend_path, new_secend_path)])
#    subprocess.call(sys_call, shell = True)

    old_p_path = os.path.join(firstsourcepath, p_file_last_old)
    delete_something(old_p_path, da_path, dataout_fullpath) #now delete stuff
        
    return new_source_path, new_secstart_path


def delete_something(*kwargs):
    """Deleting files..."""
    for path in kwargs:
        sys_call = "".join(['rm -r {}'.format(path)])     
        subprocess.call(sys_call, shell = True)
    

def get_sec_names(in_date):
    """Define names of TIEGCM secondary data files"""
    user = os.environ["USER"].upper()
    runname = in_date.strftime("%Y%m%d")
    tiegcm_version = "1.95" #1.94.2 or 1.95
    main_name_prefix = "{}_v{}".format(runname, tiegcm_version)
    main_name = "{}_auto".format(main_name_prefix)
    sec_start = '{0}.{1}_s{2}.nc'.format(user, main_name, in_date.strftime("%Y_%j"))
    sec_end = '{0}.{1}_s{2}.nc'.format(user, main_name, (in_date + dt.timedelta(days = 1)).strftime("%Y_%j"))
    return sec_start, sec_end, main_name 

if __name__ == '__main__':
    main()
