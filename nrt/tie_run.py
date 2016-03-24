'''
Python Version:    2.7.2 (default, Oct  1 2012, 15:56:20)
@author: smurray@eld264
Created on Jul 31, 2014
Purpose: Called by tie_cron.py to run TIEGCM forecasts daily.
Notes: 		As mentioned in tie_cron, much of this is edited code originally written 
			by ehenley in order to keep consistent for later ease of running with DA.
Problem: 	DA code below needs to be run with very specific folders/files on local machine! 
            I've edited a bit to run on nwp1/data/smurray for now,
            but should really go to HPC etc in long term in a ROSE suite. 
            This might mean abandoning the DA coding below unless its rewritten..
'''

import os
import subprocess
import datetime as dt
import numpy as np
import shutil
import time

#POSSIBLY WANT TO SPIN IT UP FOR 7 DAYS THEN TAKE THAT OUTPUT?

#CENTRAL_DATE = dt.datetime.utcnow()
#CENTRAL_DATE = dt.datetime(2003,3,2)#.utcnow()

def main(start_time, kph, f107h, f107a, prim_hours, firstsource, sourcetime):
#    start_time = dt.datetime.utcnow()
    "Run TIEGCM code using daily indices automatically"
    ties = gimme_settings(firstsource, start_time, prim_hours)
    ties["main_name"] = "{}_auto".format(ties["main_name_prefix"])
    runpath_suffix = "auto"
    auto_path = startup(runpath_suffix, ties, kph, f107h, f107a, sourcetime)   
    for i, datetime in enumerate(ties["datetimes"]):
        job_settings = gimme_job_settings(ties["runname"], ties["modeldir"],
                                           ties["user"], ties["main_name"],
                                           ties["makefile"], ties["tiegcm_data"],
                                           ties["nodes"], ties["tasks_per_node"],
                                           execy = "TRUE", datetimey = datetime,
                                           prim_hours = ties["prim_hours"])    
        if i == 0:
            #First time round, want first source
            input_settings = gimme_input_settings(job_settings, datetime,
                                               ties["prim_hours"], ties["gpi_ncfile"],
                                               source = ties["firstsource"])
            use_zero_temp_incr = True
        else:
            #Normally, want automatic source determination
            input_settings = gimme_input_settings(job_settings, datetime,
                                               ties["prim_hours"], ties["gpi_ncfile"])
        p_file_last, full_pfile_path, da_path, dataout_fullpath = run_job(auto_path, ties["linux_or_hpc"], 
                                                                          ties["stdout"], ties["stderr"],
                                                                          ties["set_tiegcm_data"], job_settings,
                                                                          ties["sleep_secs"], ties["timeout"], 
                                                                          input_settings, ties["tiegcm_data"])
        return p_file_last, full_pfile_path, da_path, dataout_fullpath, ties["firstsourcepath"]

def gimme_settings(firstsource, start_time, prim_hours):
    """Define some common settings for the TIEGCM run"""
    #Name for runname (also gets prefix: tiegcm model & suffix: date simulated)
    runname = (start_time - dt.timedelta(days = 0)).strftime("%Y%m%d")
    
    #Whether to create job files for linux or hpc (supercomputer)
    linux_or_hpc = "linux" #"linux" or "hpc"
    
    #Cycle characteristics: one primary & one secondary file created per cycle
    #Output frequencies: primary: 1 hr; secondary: 15 mins
    starttime = start_time - dt.timedelta(days = 0) #Start NOTE no assim on 1st cycle
    prim_hours = prim_hours #Cycle duration: suggest 1, 6 or 24
    nincr = 1 #How many cycles to run: add prim_hours to start date nincr times
    
    #Where the model is located (full path)
    tiegcm_version = "1.95" #1.94.2 or 1.95
    tiegcm_version_nodots = tiegcm_version.replace(".", "")
    
    #What the first source is called (expected location further down)
    if firstsource is None:
        firstsource = "".join(["tiegcm", tiegcm_version, ".pcntr.",
                           (start_time - dt.timedelta(days = 0)).strftime("%Y%m%d"), ".nc"]) 
    
    #The gpi file to use (eg forecast or not)
    gpi_ncfile = "gpi_2000001-2013120.nc"
    
    #The makefile to use
    makefile = "Make.MetOffice_sam{}".format(tiegcm_version_nodots)
    
    #What to call the main directory.
    #Suggest "Ensemble" for random runs, "Assimilation" for assimilation runs
    main_dir_name = "auto"
    
    #How many nodes to run on, and how many tasks to assign to each node
    nodes = 16 # TODO: this applies to hpc only. Make it apply to mpi linux too?
    tasks_per_node = 32 #hpc only
    
    #How long to sleep between checks for the output file, and when to timeout
    sleep_secs = 10
    timeout = dt.timedelta(hours = 1)
    
    #What to call the stdout & stderr
    # (get one set per run, so only get 1 set for an assim run,
    # but get 1 set for each ensemble member)
    stdout = "stdout.txt"
    stderr = "stderr.txt"
    
    #---vvvvvvvvvv-----Things you probably should leave alone-----vvvvvvvvvv----
    #The job, run & execdir get named with this pattern: helps record settings
    main_name_prefix = "{}_v{}".format(runname, tiegcm_version)
    
    #Various folders which should already exist
    datalocal = os.environ["LOCALDATA"]
    tiegcm_mainfolder = "".join(["tiegcm", tiegcm_version_nodots])
    modelfolder = "tiegcm{}".format(tiegcm_version)
    modeldir = os.path.join(datalocal, tiegcm_mainfolder, modelfolder)
    tiegcm_data = os.path.join(datalocal, tiegcm_mainfolder, "data") 
    set_tiegcm_data = "TGCMDATA={}".format(tiegcm_data) #Bash-like
    #set_tiegcm_data = "setenv TGCMDATA {}".format(tiegcm_data) # csh-like
    
    #Set up the main directory, if doesn't exist yet. Most things kept here
    main_directory = os.path.join(datalocal, tiegcm_mainfolder, main_dir_name) #*SMURRAY: decide if this is where I want it *
    if not os.path.isdir(main_directory):
        os.makedirs(main_directory)
    
    #Where to create the input & job files, and execdir
    inputjob_path = os.path.join(main_directory, "InputJobFiles")
    execdir_path = main_directory
    
    #Where first source should be
    firstsourcepath = main_directory
    if not os.path.isfile(os.path.join(firstsourcepath, firstsource)):
        raise ValueError, "{} not in {}".format(firstsource, firstsourcepath)
    
    #Who is running it (used in the netcdf files)
    user = os.environ["USER"].upper()
    
    #Get the dates we'll be running for
    time_incr = dt.timedelta(hours = prim_hours) #How much to augment each time
    datetimes = np.array([starttime + n*time_incr for n in range(nincr)])
    
    settings={"runname" : runname,
              "linux_or_hpc" : linux_or_hpc,
              "prim_hours" : prim_hours,
              "firstsource" : firstsource,
              "gpi_ncfile" : gpi_ncfile,
              "makefile" : makefile,
              "nodes": nodes,
              "tasks_per_node" : tasks_per_node,
              "sleep_secs" : sleep_secs,
              "timeout" : timeout,
              "stdout" : stdout,
              "stderr" : stderr,
              "main_name_prefix" : main_name_prefix,
              "modeldir" : modeldir,
              "tiegcm_data" : tiegcm_data,
              "set_tiegcm_data" : set_tiegcm_data,
              "inputjob_path" : inputjob_path,
              "execdir_path" : execdir_path,
              "firstsourcepath" : firstsourcepath,
              "user" : user,
              "datetimes" : datetimes,
              }
    return settings


def startup(runpath_suffix, settings, kph, f107h, f107a, sourcetime):
    "Set up stuff for running job"
    #Get what we need from settings
    s = settings
    inputjob_path = s["inputjob_path"]
    runname, user = s["runname"], s["user"]
    linux_or_hpc, main_name = s["linux_or_hpc"], s["main_name"]
    tiegcm_data, modeldir = s["tiegcm_data"], s["modeldir"]
    nodes, tasks_per_node = s["nodes"], s["tasks_per_node"]
    gpi_ncfile, makefile = s["gpi_ncfile"], s["makefile"]
    firstsource, firstsourcepath = s["firstsource"], s["firstsourcepath"]
    
    prim_hours, datetimes = s["prim_hours"], s["datetimes"]
    stdout, stderr = s["stdout"], s["stderr"]
    
    #Create the folder where we want to run, and move there
    #Recursive creation with makedirs
    runpath = os.path.join(inputjob_path,
                           "{}_{}".format(runname, runpath_suffix))
    if os.path.isdir(runpath):
        errmsg="\n".join(["Run path already exists: \n{}".format(runpath),
                          "Remove this & the corresponding data folder"])
        raise ValueError, errmsg
    else:
        os.makedirs(runpath)
    os.chdir(runpath)
    
    msg = "\n".join(["",
     "Using TIEGCM version-appropriate TGCMDATA = {}".format(tiegcm_data),
     "Operating in working directory {}".format(runpath),
     "To monitor stdout : tail -f {}".format(os.path.join(runpath, stdout)),
     "To monitor stderr : tail -f {}".format(os.path.join(runpath, stderr)),
                     "",])
    print(msg)
    
    #---------------First time round (if supercomputer)--------------
    #For 1st time on hpc, need to compile the code only, not run, so exec=False
    if linux_or_hpc == "hpc":
        print("Compiling for 1st time use on supercomputer\n")
        #Write the job file
        job_settings = gimme_job_settings(runname, modeldir, user,
                                      main_name, makefile, tiegcm_data,
                                      nodes, tasks_per_node,
                                      execy = "FALSE", datetimey = datetimes[0],
                                      prim_hours = prim_hours)
        job_file, job_file_contents = gimme_job_file_hpc(job_settings)
        job_pathfile = os.path.join(runpath, job_file)
        write_list(job_pathfile, job_file_contents)
        
        #Load up hpc compilers (ifort etc), and run jobfile to compile
        compiler_load = ". prg_13_1_0_8"
        compile_call = "./{}".format(job_file) #./tiegcm1.94.2_somename_ibm.job
        stdoe_append = ">>{} 2>>{}".format(stdout, stderr)
        sys_call = "".join(["",
                           "TGCMDATA={} {}; ".format(tiegcm_data, stdoe_append),
                           "{} {}; ".format(compiler_load, stdoe_append),
                           "{} {}".format(compile_call, stdoe_append),
                           ])
#        os.system(sys_call)
        subprocess.call(sys_call, shell = True)
    
    #---------------Afterwards (common to Linux & supercomputer)--------------
    #Create all the job & input files
    print("Creating job & input files")
    for i, datetime in enumerate(datetimes):
        #Get settings (job ones overwrite the 0th ones we've done above. Good)
        job_settings = gimme_job_settings(runname, modeldir, user,
                                           main_name, makefile, tiegcm_data,
                                           nodes, tasks_per_node,
                                           execy = "TRUE", datetimey = datetime,
                                           prim_hours = prim_hours)
        if i == 0:
            #First time round, want firstsource
            input_settings = gimme_input_settings(job_settings, datetime,
                                                  prim_hours, gpi_ncfile,
                                                  source = firstsource)
            
            #Make sure firstsource is copied to the data directory
            dataout_fullpath = gimme_dataout_fullpath(job_settings, tiegcm_data)
            if not os.path.isdir(dataout_fullpath):
                os.makedirs(dataout_fullpath) #Create dataout_fullpath if nec
            firstsource_pathfile = os.path.join(firstsourcepath, firstsource)
            shutil.copy2(firstsource_pathfile, dataout_fullpath)
            
        else:
            #Normally, want automatic source determination
            input_settings = gimme_input_settings(job_settings, datetime,
                                                  prim_hours, gpi_ncfile)
        
        #Write the job & input files
        if linux_or_hpc == "linux":
            job_file, job_file_contents = gimme_job_file_linux(job_settings)
        elif linux_or_hpc == "hpc":
            job_file, job_file_contents = gimme_job_file_hpc(job_settings)
        else:
            raise ValueError, "Unknown linux_or_hpc = {}".format(linux_or_hpc)
        job_pathfile = os.path.join(runpath, job_file)
        write_list(job_pathfile, job_file_contents)
        
        input_file, input_file_contents=gimme_input_file(input_settings, kph, f107h, f107a, sourcetime)
        input_pathfile = os.path.join(runpath, input_file)
        write_list(input_pathfile, input_file_contents)
    return runpath


def gimme_input_settings(job_settings, datetimey, prim_hours, gpi_ncfile,
                         source=None):
    
    #For convenience, share various variables with job settings
    user = job_settings["user"]
    prim_name = job_settings["main_name"]
    input_filename = job_settings["input"]
    
    #Get the source
    #This could be a starting source, e.g. source="TGCM.tiegcm1.95.psth_smin.nc"
    #But if none is provided, assumes we're using output from the previous cycle
    if source is None:
        prev_date = datetimey - dt.timedelta(hours = prim_hours)
        if 0 < prim_hours < 24:
            prev_date_str = prev_date.strftime("%Y_%j_%H")
        elif prim_hours >= 24:
            prev_date_str = prev_date.strftime("%Y_%j")
        else:
            errmsg="".join(["Unknown value: prim_hours={}".format(prim_hours)])
            raise ValueError, errmsg
        #Make the source, based on the previous date
        source="{}.{}_p{}.nc".format(user, prim_name, prev_date_str)
    
    input_settings = {}
    #Who we are
    input_settings["user"] = user
    
    #The source file to replace.
    input_settings["source"] = source
    
    #Start and end datetimes for primary (p) & secondary (s)
    input_settings["start_datetime_p"] = datetimey
    input_settings["end_datetime_p"] = datetimey + dt.timedelta(hours = prim_hours)
    input_settings["start_datetime_s"] = input_settings["start_datetime_p"]
    input_settings["end_datetime_s"] = input_settings["end_datetime_p"]

    #How often to save primary & secondary histories (day, hour, min)
    input_settings["p_hist_DHM"] = [1, 0, 0] #Once an day  - changed from 1 hour
    input_settings["s_hist_DHM"] = [0, 6, 0] #Once every 6 hours - changed from 15 mins

    #The name for primary & the filename
    input_settings["name"] = prim_name
    input_settings["filename"] = input_filename
    
    #SMURRAY: how many primary histories per .nc file.
    #EMH: need +1 as adds the start time too
    #Assume want one file per cycle. Primary cadence: hourly; secondary: 15 mins
    #For hourly files use prim_hours = 1 for primaries; for daily files, use 24
    input_settings["mxhist_prim"] = 1 
    input_settings["mxhist_sech"] = 4  #24 for 1hour, 96 for 15mins etc
    #If want hourly primary & secondary history file, use 1 for primaries,
    #& 4 for 2ndaries (1hr x 1 -> 1hrs; 15mins x 4 -> 1hrs: hourly for both)
    #If want daily primary & secondary history file, use 24 for primaries, 
    #& 96 for 2ndaries (1hr x 24 -> 24hrs; 15mins x 96 -> 24hrs: daily for both)
    
    #The gpi netcdf file to use: may want to swap in one w forecast f10.7 & kp
    input_settings["gpi_ncfile"] = gpi_ncfile
    
    return input_settings


def gimme_job_settings(runname, modeldir, user, main_name,
                       makefile, tiegcm_data, nodes, tasks_per_node,
                       execy=None, datetimey=None, prim_hours=None):
    """
    On first call, override execy with "FALSE" to just compile, & give the name
    of the input file (without .inp) in inputoutput
    
    """
    #Defaults (inputoutput done below, as it depends on main_name)
    if execy is None: #Just compile code ("FALSE"), or compile & run ("TRUE")
        execy = "TRUE" #Most of the time we'll want to run the code
    
    #At the moment, I've got the datetime in the input & output files, as I want
    #to be sure they're updating properly.
    # TODO strip this once we think things are working: avoid a file explosion
    if datetimey is None:
        inputoutput_suffix = ""
    else: #NB this raises ValueError if prim_hours is None
        if 0 < prim_hours < 24:
            inputoutput_suffix = datetimey.strftime("_%Y-%j-%H")
        elif prim_hours >= 24:
            inputoutput_suffix = datetimey.strftime("_%Y-%j")
        else:
            errmsg="".join(["Unknown value: prim_hours={}".format(prim_hours)])
            raise ValueError, errmsg
    
    job_settings = {}
    job_settings["modeldir"] = modeldir
    job_settings["user"] = user
    
    #Sort out name of job, executive directory, input & output files
    check_main_name(user, main_name, datetimey, tiegcm_data, runname)
    job_settings["main_name"] = main_name
    job_settings["execdir"] = main_name
    
    inputoutput = "{}{}".format(main_name,inputoutput_suffix)
    job_settings["filename"] = "{}.job".format(inputoutput)
    job_settings["input"] = "{}.inp".format(inputoutput)
    job_settings["output"] = "{}.out".format(inputoutput)
    job_settings["makefile"] = makefile
    
    #Do you want to compile & run the code (TRUE) or just compile (FALSE)
    job_settings["exec"] = execy
    
    #How many nodes do you want to use, and how many tasks per node?
    job_settings["nodes"] = nodes
    job_settings["tasks_per_node"] = tasks_per_node
    
    return job_settings


def run_job(da_path, linux_or_hpc, stdout, stderr, 
            set_tiegcm_data, job_settings, 
            sleep_secs, timeout, 
            input_settings, tiegcm_data,
            debug = None):
    "Actual running of code"
    job_filename = job_settings["filename"]
    stdoe_append = ">>{} 2>>{}".format(stdout, stderr)
    if linux_or_hpc == "linux": #Ampersand so runs in background (like llsubmit)
        command = "".join(["",
                         "{} {}; ".format(set_tiegcm_data, stdoe_append),
                         "chmod u+x {} {}; ".format(job_filename, stdoe_append),
                         "./{} {} &".format(job_filename, stdoe_append),
                          ])
    elif linux_or_hpc == "hpc":
        command = "".join(["",
                         "{} {}; ".format(set_tiegcm_data, stdoe_append),
                         "llsubmit {} {}".format(job_filename, stdoe_append),
                          ])
    else:
        raise ValueError, "Unknown linux_or_hpc value = {}".format(linux_or_hpc)
    print("Executing:\n{}\n".format(command))
#    os.system(command) #defunct in python 3 - use subprocess instead
    subprocess.call(command, shell = True)

    #Wait for .out file from this loop to appear before getting to end of loop
    print "Now waiting for run to finish"
    outfile = job_settings["output"]
    outpathfile = os.path.join(da_path, outfile)
    starttime = dt.datetime.utcnow()
    while True:
        timenow = dt.datetime.utcnow()
        if os.path.isfile(outpathfile):
            print("{} : found {}".format(timenow, outpathfile))
            break
        else:
            msg = "\n".join(["{} : not found {}".format(timenow, outpathfile),
                             "Sleeping for {}s".format(sleep_secs)])
            print(msg)
            time.sleep(sleep_secs)
        delay = timenow - starttime
        if delay > timeout:
            errmsg = "\n".join(["{} : timeout waiting for".format(timenow),
                                "{}".format(outpathfile),
                                "Waited for {}".format(delay)])
            raise ValueError, errmsg
    #Wait for the secondary to be created
    dataout_fullpath = gimme_dataout_fullpath(job_settings, tiegcm_data)
#    pathfile_prev_prim_nc =  os.path.join(dataout_fullpath,
#                                         input_settings["source"])
#    prev_prim_nc = os.path.basename(pathfile_prev_prim_nc)
#    pathy = os.path.dirname(pathfile_prev_prim_nc)
#    prefix, p, suffix = prev_prim_nc.rpartition("p") #Split from right!
#    prev_sec_nc = "".join([prefix, "s", suffix])
#    pathfile_prev_sec_nc = os.path.join(pathy, prev_sec_nc)
    p_file_last = "{0}.{1}_p{2}.nc".format(input_settings["user"], input_settings["name"], input_settings["end_datetime_p"].strftime("%Y_%j"))
    full_pfile_path = os.path.join(da_path, job_settings["execdir"], p_file_last)
    while True:
        if os.path.isfile(full_pfile_path):
            break
        else:
            time.sleep(1)
            if debug: 
                print("Waiting for creation of {}".format(full_pfile_path))
            else:
                pass
        
    #Wait until it's the right size... NOTE make sure this is up-to-date!
    expected_megabytes = 3.3 # NOTE this gets floored below
    while True:
        sec_size_bytes = os.stat(full_pfile_path).st_size
        sec_size_megabytes = sec_size_bytes / float(1024 * 1024)
        min_expected_size = np.floor(expected_megabytes)
        if sec_size_megabytes >= min_expected_size:
            break
        else:
            msg = "\n".join(["Waiting for {}".format(full_pfile_path),
                "Current / {} min expected size: {:.4g} / {:.4g} MB".format("~",
                                        sec_size_megabytes, min_expected_size),
                             ])
            if debug: print(msg)
            time.sleep(1)
    return p_file_last, full_pfile_path, da_path, dataout_fullpath

def write_list(pathfile, listy):
    with open(pathfile, "wb") as fo:
        for line in listy:
            line_newline = "{}\n".format(line)
            fo.write(line_newline)


def gimme_dataout_fullpath(job_settings, tiegcm_data):
    TGCMDATA = tiegcm_data # TODO : check this works on hpc
    dataout_path = job_settings["execdir"] # NOTE this != the full path. So...
    dataout_fullpath = os.path.join(TGCMDATA, dataout_path) #...make full path!
    return dataout_fullpath


def check_main_name(user, main_name, datetimey, tiegcm_data, runname):
    """Check runname length is short enough for TIEGCM to read the source"""
    
    #Might as well be paranoid & include the hours
    dummy_netcdf="{0}.{1}_p{2}.nc".format(user, main_name,
                                          datetimey.strftime("%Y_%j_%H"))
    fullsource=os.path.join(tiegcm_data, main_name, dummy_netcdf)
    lfullsource = len(fullsource)
    max_lfullsource = 120 #Seems to be hardcoded in TIEGCM
    
    if lfullsource > max_lfullsource:
        lrunname = len(runname)
        lconstant = lfullsource - 2*lrunname
        ok_lrunname = ( max_lfullsource - lconstant ) // 2 #Floor the division
        errmsg="\n".join([""
           "TIEGCM's maximum fullsource length = {}".format(max_lfullsource),
           "Currently fullsource = {}".format(fullsource),
           "len(fullsource) = {} chars".format(lfullsource),
           "This'll cause problems with the source reading - will be read as:",
           "{}".format(fullsource[0 : max_lfullsource]),
           "Main problem: runname is too long: len({}) = {}".format(runname,
                                                                    lrunname),
           "Abbreviate runname: OK if len(runname) <= {}".format(ok_lrunname),
                         ""])
        raise ValueError, errmsg


def gimme_job_file_hpc(job_settings):
    js = job_settings #Short, for convenience
    hpc_job_file = [\
    '#! /bin/csh',
    '#',
    '# User set LSF resource directives for IBM/AIX batch job:',
    '#',
    '#@ shell = /usr/bin/csh',
    '#@ job_type = parallel',
    '#@ class = parallel',
    '#@ job_name = {}_hpc'.format(js["main_name"]), #SMURRAY: what to call the job run on hpc so you can identify it if needed
    '#@ output = $(job_name).$(jobid).out', #SMURRAY: what to call output file
    '#@ error = $(job_name).$(jobid)_error.out', #SMURRAY: what to call output file that notes any errors that occured
    '#@ node = {}'.format(js["nodes"]), #SMURRAY: number of nodes to run
    '##@ tasks_per_node = {}'.format(js["tasks_per_node"]),
    '#@ queue',
    '#',
    '# User set shell variables for TIEGCM IBM/AIX job:',
    '# (modeldir, execdir, and utildir may be relative or absolute paths)',
    '#',
    '#   modeldir: Root directory to model source (may be SVN working dir)',
    '#   execdir:  Directory in which to build and execute (will be created if necessary)',
    '#   input:    Namelist input file (will use default if not provided)',
    '#   output:   Stdout file from model execution (will be created)',
    '#   make:     Build file with platform-specific compile parameters (see scripts dir)',
    '#   mpi:      TRUE/FALSE for MPI or non-MPI run',
    '#   nproc:    Number of processors for 64-bit Linux MPI run',
    '#   modelres: Model resolution (5.0 or 2.5)',
    '#   debug:    If TRUE, build and execute a "debug" run',
    '#   exec:     If TRUE, execute the model (build only if FALSE)',
    '#   utildir:  Dir containing supporting scripts (usually $modeldir/scripts)',
    '#',
    'set modeldir = {}'.format(js["modeldir"]), #EMH: full path & easy switching
    'set execdir  = {}'.format(js["execdir"]), #SMURRAY: name executive directory (code will be compiled here, and files will be saved here)
    'set input    = {}'.format(js["input"]), #SMURRAY: call input file
    'set output   = {}'.format(js["output"]), #SMURRAY: name output file with information on run
    'set make     = {}'.format(js["makefile"]), #EMH: need the right makefile
    'set modelres = 5.0',
    'set mpi      = TRUE',
    'set debug    = FALSE',
    'set exec     = {}'.format(js["exec"]), #SMURRAY: if FALSE, will only compile, not run (see note below)
    'set utildir  = $modeldir/scripts',
    '',#SMURRAY: First need to compile the code, with 'set exec FALSE' after loading the compilers,
       #         e.g. type '. prg_13_1_0_8' then './tiegcm1.94.2_march2009_weimer_ibm.job'
    '',#SMURRAY: Then can reset 'set exec TRUE' and submit, e.g. type 'llsubmit tiegcm1.94.2_march2009_weimer_ibm.job'
    '#',
    '#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -',
    '#                        Shell Script for TIEGCM IBM/AIX job',
    '#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -',
    '#',
    '# Env vars for AIX:',
    '#',
    'setenv MP_LABELIO YES',
    'setenv MP_STDINMODE 0',
    'setenv MP_SHARED_MEMORY yes',
    'setenv MEMORY_AFFINITY MCM',
    'setenv AIXTHREAD_SCOPE S',
    'setenv MALLOCMULTIHEAP true',
    '#',
    'set mycwd = `pwd`',
    'echo "" ; echo "${0}:"',
    'echo "  Begin execution at `date`"',
    'echo "  Current working directory: $mycwd"',
    'echo "  System: `uname -a`"',
    'echo ""',
    '#',
    '# Verify directories and make_machine file (make execdir if necessary).',
    '# Get absolute path for dirs that are accessed from the execdir.',
    '#',
    'if (! -d $modeldir) then',
    '  echo ">>> Cannot find model directory $modeldir <<<"',
    '  exit 1',
    'endif',
    'set model = $modeldir:t',
    '',
    'if (! -d $utildir) then',
    '  echo ">>> Cannot find model scripts directory $utildir <<<"',
    '  exit 1',
    'endif',
    'set utildir = `perl $utildir/abspath $utildir`',
    '',
    'set srcdir  = $modeldir/src',
    'if (! -d $srcdir) then',
    '  echo ">>> Cannot find model source directory $srcdir <<<"',
    '  exit 1',
    'endif',
    'set srcdir = `perl $utildir/abspath $srcdir`',
    '',
    'if (! -d $execdir) then',
    '  echo "Making exec directory $execdir"',
    '  mkdir -p $execdir',
    'endif',
    'if (! -f $make) set make = $utildir/$make',
    'if (! -f $make) then',
    '  echo ">>> Cannot find make_machine file $make <<<"',
    '  exit 1',
    'endif',
    'set make = `perl $utildir/abspath $make`',
    'if ($modelres != 5.0 && $modelres != 2.5) then',
    '  echo ">>> Unknown model resolution $modelres <<<"',
    '  exit 1',
    'endif',
    '#',
    '# Copy make files to execdir if necessary:',
    '#',
    'if (! -f $execdir/$make)     cp $make $execdir',
    'if (! -f $execdir/Makefile)  cp $utildir/Makefile $execdir',
    'if (! -f $execdir/mkdepends) cp $utildir/mkdepends $execdir',
    '#',
    '# Make default namelist input file if not provided by user:',
    '#',
    'if ($?input) then',
    '  if (! -f $input) then',
    '    echo ">>> Cannot find namelist input file $input <<<"',
    '    exit 1',
    '  endif',
    'else',
    '  set input = \\', #EMH: escaping backslash so backslash still gets printed
    '    `perl $utildir/mknamelist -model=$model -modelres=$modelres` || \\', #EMH: ibid
    '     echo ">>> Error from mknamelist: fileout = $input" && exit 1',
    'endif',
    'set input  = `perl $utildir/abspath $input`',
    'set output = `perl $utildir/abspath $output`',
    '#',
    '# Report to stdout:',
    '#',
    '#set svnversion = `svnversion $modeldir` || set svnversion = "[none]"',
    ' set svnversion = 1.94.2',
    'echo -n "  Model directory:   $modeldir" && echo " (SVN revision $svnversion)"',
    'echo "  Exec directory:    $execdir"',
    'echo "  Source directory:  $srcdir"',
    'echo "  Make machine file: $make"',
    'echo "  Namelist input:    $input"',
    'echo "  Model resolution:  $modelres"',
    '#',
    '# Copy defs header file to execdir, if necessary, according to',
    '# requested resolution. This should seamlessly switch between',
    '# resolutions according to $modelres.',
    '#',
    'set defs = $srcdir/defs5.0',
    'if ($modelres == 2.5) set defs = $srcdir/defs2.5',
    'if (-f $execdir/defs.h) then',
    '  cmp -s $execdir/defs.h $defs',
    '  if ($status == 1) then # files differ -> switch resolutions',
    '    echo "Switching defs.h for model resolution $modelres"',
    '    cp $defs $execdir/defs.h',
    '  else',
    '    echo "defs.h already set for model resolution $modelres"',
    '  endif',
    'else # defs.h does not exist in execdir -> copy appropriate defs file',
    '  echo "Copying $defs to $execdir/defs.h for resolution $modelres"',
    '  cp $defs $execdir/defs.h',
    'endif',
    '#',
    '# cd to execdir and run make:',
    '#',
    'cd $execdir || echo ">>> Cannot cd to execdir $execdir" && exit 1',
    'echo ""',
    'echo "Begin building $model in `pwd`"',
    '#',
    '# Build Make.env file in exec dir, containing needed env vars for Makefile:',
    '#',
    'cat << EOF >! Make.env',
    'MAKE_MACHINE = $make',
    'DIRS         = . $srcdir',
    'MPI          = $mpi',
    'EXECNAME     = $model',
    'NAMELIST     = $input',
    'OUTPUT       = $output',
    'DEBUG        = $debug',
    'SVN_VERSION  = $svnversion',
    'EOF',
    '#',
    '# Build the model:',
    '#',
    'gmake -j4 all || echo ">>> Error return from gmake all" && exit 1',
    '#',
    '#',
    '# Load Sharing Facility batch job execution:',
    '#',
    'if ($exec == "TRUE") then',
    '  set model = ./$model',
    '  echo "IBM/AIX job: Executing $model"',
    '  echo "Model output will go to $output"',
    '  if ($?LSF_ENVDIR && $mpi == "TRUE") then  # MPI LSF job',
    '    echo "" ; echo "Executing model $model with mpirun.lsf from `pwd` at `date`"',
    '    echo "Model output will go to $output"',
    '    setenv TARGET_CPU_LIST "-1"',
    '    mpirun.lsf /usr/local/bin/launch $model < $input >&! $output || \\', #EMH: backslash escaping
    '      echo ">>> ${0} Execution of mpirun.lsf $model FAILED at `date`" && \\', #EMH: ibid
    '      echo "See output in $output"',
    '#',
    '# non-LSF job -- try interactive execution',
    '"#',
    '  else',
    '    echo "" ; echo "Executing model $model on command line from `pwd` at `date`"',
    '    echo "Model output will go to $output"',
    '    $model < $input >&! $output || \\',  #EMH: backslash escaping
    '      echo ">>> ${0} Execution of $model FAILED at `date`" && \\', #EMH: ibid
    '      echo "See output in $output"',
    '  endif',
    'else',
    '  echo "I am NOT executing $model (exec was not set)"',
    'endif',
    '#',
    '# Separate output files by MPI task:',
    '# (we are still in $execdir, but $output contains full path to $wrkdir)',
    '#',
    'perl $utildir/mklogs $output || \\' ,#EMH: backslash escaping
    '  echo ">>> ${0}: Error from $execdir/mklogs on output $output"',
    '',
    ]
    
    return js["filename"], hpc_job_file


def gimme_job_file_linux(job_settings):
    js = job_settings #Short, for convenience
    linux_job_file = [\
    '#! /bin/csh',
    '##SMURRAY: run code by simply typing "./whatever_job_name_is.job"',
    '#',
    '# User set shell variables for TIEGCM Linux job:',
    '# (modeldir, execdir, and utildir may be relative or absolute paths)',
    '#',
    '#   modeldir: Root directory to model source (may be an SVN working dir)',
    '#   execdir:  Directory in which to build and execute (will be created if necessary)',
    '#   input:    Namelist input file (will use default if not provided)',
    '#   output:   Stdout file from model execution (will be created)',
    '#   make:     Build file with platform-specific compile parameters (in scripts dir)',
    '#   mpi:      TRUE/FALSE for MPI or non-MPI run',
    '#   nproc:    Number of processors for 64-bit Linux MPI run',
    '#   modelres: Model resolution (5.0 or 2.5)',
    '#   debug:    If TRUE, build and execute a "debug" run',
    '#   exec:     If TRUE, execute the model (build only if FALSE)',
    '#   utildir:  Dir containing supporting scripts (usually $modeldir/scripts)',
    '#',
    'set modeldir = {}'.format(js["modeldir"]), #EMH: full path & easy switching
    'set execdir  = {}'.format(js["execdir"]), #SMURRAY: name executive directory (code will be compiled here, and files will be saved here)
    'set input    = {}'.format(js["input"]), #SMURRAY: call input file 
    'set output   = {}'.format(js["output"]), #SMURRAY: name output file with information on run
    'set make     = {}'.format(js["makefile"]), #EMH: need the right makefile
    'set modelres = 5.0',
    'set mpi      = TRUE',
    #SMURRAY: if mpi TRUE, how many processes to run. EMH: leaving this for now. TODO: check can we up this on server? Link to nodes if so?
    #2015-04-24: SMURRAY: switched to 1 for testing on science servers...
    'set nproc    = 1',
    'set debug    = FALSE',
    'set exec     = {}'.format(js["exec"]), #SMURRAY: if FALSE, will only compile, not run (EMH: see note in HPC version)
    'set utildir  = $modeldir/scripts',
    '#',
    "# TGCMDATA can be set here, or in user's shell init file (e.g., .cshrc):",
    '#setenv TGCMDATA /data/local/smurray/tiegcm195/data/tiegcm1.95',
    '#',
    '#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -',
    '#                        Shell Script for TIEGCM Linux job',
    '#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -',
    '#',
    'set mycwd = `pwd`',
    'echo "" ; echo "${0}:"',
    'echo "  Begin execution at `date`"',
    'echo "  Current working directory: $mycwd"',
    'echo "  System: `uname -a`"  ',
    'echo ""',
    '#',
    '# Verify directories and make_machine file (make execdir if necessary).',
    '# Get absolute path for dirs that are accessed from the execdir.',
    '#',
    'if (! -d $modeldir) then',
    '  echo ">>> Cannot find model directory $modeldir <<<"',
    '  exit 1',
    'endif',
    'set model = $modeldir:t',
    '',
    'if ($model == '') then',
    '  echo "Please remove trailing slash from modeldir $modeldir"',
    '  exit',
    'endif',
    '',
    'if (! -d $utildir) then',
    '  echo ">>> Cannot find model scripts directory $utildir <<<"',
    '  exit 1',
    'endif',
    '',
    'set srcdir  = $modeldir/src',
    'if (! -d $srcdir) then',
    '  echo ">>> Cannot find model source directory $srcdir <<<"',
    '  exit 1',
    'endif',
    'set srcdir = `perl $utildir/abspath $srcdir`',
    '',
    'if (! -d $execdir) then',
    '  echo "Making exec directory $execdir"',
    '  mkdir -p $execdir',
    'endif',
    '',
    'if ($modelres != 5.0 && $modelres != 2.5) then',
    '  echo ">>> Unknown model resolution $modelres <<<"',
    '  exit 1',
    'endif',
    '#',
    '# Copy make files to execdir if necessary:',
    '#',
    'if (! -f $execdir/$make)     cp $utildir/$make $execdir',
    'if (! -f $execdir/Makefile)  cp $utildir/Makefile $execdir',
    'if (! -f $execdir/mkdepends) cp $utildir/mkdepends $execdir',
    '#',
    '# Make default namelist input file if not provided by user:',
    '#',
    'if ($?input) then',
    '  if (! -f $input) then',
    '    echo ">>> Cannot find namelist input file $input <<<"',
    '    exit 1',
    '  endif',
    'else',
    '  set input = \\', #EMH: escaping backslash so backslash still gets printed
    '    `perl $utildir/mknamelist -model=$model -modelres=$modelres` || \\', #EMH backslash
    '     echo ">>> Error from mknamelist: fileout = $input" && exit 1',
    'endif',
    'set input  = `perl $utildir/abspath $input`',
    'set output = `perl $utildir/abspath $output`',
    'set mklogs = `perl $utildir/abspath $utildir`',
    'set mklogs = $mklogs/mklogs',
    '#',
    '# Report to stdout:',
    '#',
    'set svnversion = `svnversion $modeldir` || set svnversion = "[none]"',
    'echo -n "  Model directory:   $modeldir" && echo " (SVN revision $svnversion)"',
    'echo "  Exec directory:    $execdir"',
    'echo "  Source directory:  $srcdir"',
    'echo "  Make machine file: $make"',
    'echo "  Namelist input:    $input"',
    'echo "  Model resolution:  $modelres"',
    'echo "  Debug flag:        $debug"',
    '#',
    '# If debug flag has changed from last gmake, clean execdir',
    '# and reset debug file:',
    '#',
    'if (-f $execdir/debug) then',
    '  set lastdebug = `cat $execdir/debug`',
    '  if ($lastdebug != $debug) then',
    '    echo "Clean execdir $execdir because debug flag switched from $lastdebug to $debug"',
    '    set mycwd = `pwd` ; cd $execdir ; gmake clean ; cd $mycwd',
    '    echo $debug >! $execdir/debug',
    '  endif',
    'else',
    '  echo $debug >! $execdir/debug',
    '  echo "Created file debug with debug flag = $debug"',
    'endif',
    '#',
    '# Copy defs header file to execdir, if necessary, according to',
    '# requested resolution. This should seamlessly switch between',
    '# resolutions according to $modelres.',
    '#',
    'set defs = $srcdir/defs5.0',
    'if ($modelres == 2.5) set defs = $srcdir/defs2.5',
    'if (-f $execdir/defs.h) then',
    '  cmp -s $execdir/defs.h $defs',
    '  if ($status == 1) then # files differ -> switch resolutions',
    '    echo "Switching defs.h for model resolution $modelres"',
    '    cp $defs $execdir/defs.h',
    '  else',
    '    echo "defs.h already set for model resolution $modelres"',
    '  endif',
    'else # defs.h does not exist in execdir -> copy appropriate defs file',
    '  echo "Copying $defs to $execdir/defs.h for resolution $modelres"',
    '  cp $defs $execdir/defs.h',
    'endif',
    '#',
    '# cd to execdir and run make:',
    '#',
    'cd $execdir || echo ">>> Cannot cd to execdir $execdir" && exit 1',
    'echo ""',
    'echo "Begin building $model in `pwd`"',
    '#',
    '# Build Make.env file in exec dir, containing needed env vars for Makefile:',
    '#',
    'cat << EOF >! Make.env',
    'MAKE_MACHINE = $make',
    'DIRS         = . $srcdir',
    'MPI          = $mpi',
    'NPROC        = $nproc',
    'EXECNAME     = $model',
    'NAMELIST     = $input',
    'OUTPUT       = $output',
    'DEBUG        = $debug',
    'SVN_VERSION  = $svnversion',
    'EOF',
    '#',
    '# Build the model:',
    'gmake -j4 all || echo ">>> Error return from gmake all" && exit 1',
    '#',
    '# Execute Linux job (MPI or non-MPI run):',
    '#',
    'if ($exec == "TRUE") then',
    '  set model = ./$model',
    '  echo "$model output will go to $output"',
    '  if ($mpi == "TRUE") then',
    '#',
    '# Files machines.ini and mpirun.command are made by the Make.machines file.',
    '    gmake machines.ini',
    '    gmake mpirun.command',
    '    set mpirun = `cat mpirun.command`',
    '    echo "Executing $mpirun with -np $nproc for Linux MPI run."',
    '#',
    '# Execute mpirun (Intel or PGI) for MPI run:',
    '    $mpirun -machinefile machines.ini -np $nproc $model < $input >&! $output || \\', #EMH backslash
    '      echo ">>> ${0} mpirun execution of $model FAILED at `date`" && \\', #EMH backslash
    '      echo "See output in $output"',
    '    echo "Linux MPI run of $model completed at `date`"',
    '    perl $mklogs $output',
    '  else # MPI is FALSE',
    '    echo "Executing $model for Linux non-MPI run."',
    '    $model < $input >&! $output || \\',#EMH backslash
    '      echo ">>> ${0} Execution of $model FAILED at `date`" && \\',#EMH backslash
    '      echo "See output in $output"',
    '    echo "Linux non-MPI run of $model completed at `date`"',
    '  endif',
    'else',
    '  echo "I am NOT executing $model (exec was not set)"',
    'endif',
    'exit 0',
    '',
    ]

    return js["filename"], linux_job_file


def gimme_input_file(input_settings, kph, f107h, f107a, sourcetime):
    
    #Irritatingly, it looks like we'll have to embed ensemble name before date,
    #as mkhvols.F routine called in input.F only does addition to final digit.
    #So files sorted first by ens member then time, rather than desirable
    #time, then ens member. Stupid Fortran. Never mind, can rename w Python.
    
    iss = input_settings #Short for convenience
    
    #Dividing into various sections which we'll join at the end
    start_sec = [\
    "&tgcm_input",
    ";",
    "; Namelist input file for model tiegcm",
    ";",
    " LABEL = 'tiegcm res=5.0'",
    " START_YEAR = {}".format(iss["start_datetime_p"].strftime("%Y")), #SMURRAY: define year
    " START_DAY  = {}".format(iss["start_datetime_p"].strftime("%j")), #SMURRAY: define start day (must match start below)
    " CALENDAR_ADVANCE = 1",
    ";",
    "; SOURCE:       Start-up history file (for initial runs only)",
    "; SOURCE_START: Time of history on start-up file (initial runs only)",
    ";",
    " SOURCE = '$TGCMDATA/{}/{}'".format(iss["name"],iss["source"])] #SMURRAY: this is the source file to replace.
    if sourcetime is None:
        extra_sec = [\
        " SOURCE_START = {}".format(iss["start_datetime_p"].strftime("%j,%H,%M")),] #TODO: FIX!!!!
    else:
        extra_sec = [\
        " SOURCE_START = {}".format(sourcetime)] #TODO: FIX!!!!

#    " SOURCE_START = 172, 0, 0", #SMURRAY: what is the start time of file above (jd, hour, min)
    continue_sec = [\
    ";",
    "; START: Start time (day,hour,minute)",
    "; STOP:  Stop time (day,hour,minute)",
    "; STEP:  Timestep (seconds)",
    ";",
    " START = {}".format(iss["start_datetime_p"].strftime("%j,%H,%M")), #SMURRAY: when do you want model to start (jd, hour, min)
    " STOP  = {}".format(iss["end_datetime_p"].strftime("%j,%H,%M")), #SMURRAY: when do you want model to end (jd, hour, min)
    " STEP  = 60",
    ";",
    "; Primary History parameters:",
    ";",
    " HIST = {},{},{}".format(*iss["p_hist_DHM"]), #SMURRAY: how often to save a primary history (day, hour, min) - here every 6hours!
    ]
    
    #SMURRAY: name the primary history output files to whatever you want
#    if 0 < iss["mxhist_prim"] < 24:
#        #One per hour /six hours
#        output_sec = [\
#        " OUTPUT = '{0}.{1}_p{2}.nc'".format(iss["user"], iss["name"], iss["start_datetime_p"].strftime("%Y_%j_%H")), #$TGCMDATA/{1}/
#                     ]
#    elif iss["mxhist_prim"] >= 24:
        #One per day (here it cycles through the jd, should be the same start & end file)
    output_sec = [\
    " OUTPUT = '{0}.{1}_p{2}.nc','to'".format(iss["user"], iss["name"], iss["start_datetime_p"].strftime("%Y_%j")),   #$TGCMDATA/{1}/
    "          '{0}.{1}_p{2}.nc','by','1'".format(iss["user"], iss["name"], iss["end_datetime_p"].strftime("%Y_%j")), #$TGCMDATA/{1}/
                    ]
#    else:
#        raise ValueError, "Don't know how to cope with iss['mxhist_prim'] = {}".format(iss["mxhist_prim"])
    
    mid_sec = [\
    #SMURRAY: how many primary histories per .nc file, 4 at 6hr intervals gives a daily primary history file (6 x 4 -> 24hours)
    " MXHIST_PRIM = {}".format(iss["mxhist_prim"]),
    ";",
    "; Secondary History parameters:",
    ";",
    " SECSTART = {}".format(iss["start_datetime_s"].strftime("%j,%H,%M")), #SMURRAY: when to start saving secondary histories for analysis
    " SECSTOP  = {}".format(iss["end_datetime_s"].strftime("%j,%H,%M")), #SMURRAY: when to stop (jd, hour, min)
    " SECHIST  = {},{},{}".format(*iss["s_hist_DHM"]),     #SMURRAY: how often do you want a history (eg every 15 minutes)
              ]
    
    #SMURRAY: what to name secondary histories
#    if 0 < iss["mxhist_prim"] < 24: #EMH: intentionally wrt mxhist_prim, for convenience
#        #One per hour/six hours
#        secout_sec = [\
#        " SECOUT   = '{0}.{1}_s{2}.nc'".format(iss["user"], iss["name"], iss["start_datetime_s"].strftime("%Y_%j_%H")), #$TGCMDATA/{1}/
#                     ]
        #One per day
    secout_sec = [\
    " SECOUT   = '{0}.{1}_s{2}.nc','to'".format(iss["user"], iss["name"], iss["start_datetime_s"].strftime("%Y_%j")), #$TGCMDATA/{1}/
    "            '{0}.{1}_s{2}.nc','by','1'".format(iss["user"], iss["name"], iss["end_datetime_s"].strftime("%Y_%j")), #$TGCMDATA/{1}/
                    ]
#    else:
#        raise ValueError, "Don't know how to cope with iss['mxhist_prim'] = {}".format(iss["mxhist_prim"])
    
    end_sec = [\
    #SMURRAY: maximimum number of histories per file (96 if 15 mins as 96*15min ->24hours, so again saved daily!)
    " MXHIST_SECH = {}".format(iss["mxhist_sech"]),
    #SMURRAY: what fields to save, probably wont need to change. Note, one more thing to change in the file below!
    #EMH: adding 'O2', 'O1', 'ZMAG', as it complained that these weren't present
    " SECFLDS = 'TN','DEN','Z','ZG','SCHT','TEC','BARM', 'O2', 'O1', 'ZMAG'",
    "; SECFLDS = 'TN','UN','VN','O1','NO','N4S','NE','TE','TI','TEC',",
    ";           'O2','O2P','OMEGA','POTEN','UI_ExB','VI_ExB','WI_ExB',",
    ";           'DEN','QJOULE','Z','ZG'",
    ";",
    "; Diagnostic fields available with this release:",
    ";SECFLDS = 'CO2_COOL','NO_COOL','DEN','HEATING','QJOULE','QJOULE_INTEG',",
    ";          'SIGMA_PED','SIGMA_HAL','TEC','UI_ExB','VI_ExB','WI_ExB',",
    ";          'LAMDA_PED','LAMDA_HAL','HMF2','NMF2','SCHT','MU_M','O_N2','WN',",
    ";          'BX','BY','BZ','BMAG','EX','EY','EZ','ED1','ED2','PHIM2D'",
    ";",
    "; These diagnostic currents are available only if icalkqlam==1 (dynamo.F)",
    ";      'KQPHI','KQLAM','JQR','JE13D','JE23D'",
    ";",
    "; If HPSS_PATH is set, a csh script will be made in the execdir that,",
    "; when executed, will copy history disk files to the NCAR HPSS in the",
    "; directory HPSS_PATH (must have an HPSS account at NCAR CISL)",
    ";",
    ";HPSS_PATH = '/home/[user]/tiegcm'",
    ";",
    " TIDE = 0.,0.,0.,0.,0.,0.,0.,0.,0.,0.",
    " TIDE2 = 0.,0.",
    ";",
    "; At 5 deg resolution, use gswm migrating tides only.",
    "; At 2.5 deg resolution, optionally use both migrating",
    ";   and non-migrating tides.",
    ";",
    " GSWM_MI_DI_NCFILE  = '$TGCMDATA/gswm_diurn_5.0d_99km.nc'",
    " GSWM_MI_SDI_NCFILE = '$TGCMDATA/gswm_semi_5.0d_99km.nc'",
    ";GSWM_NM_DI_NCFILE  = '$TGCMDATA/gswm_nonmig_diurn_5.0d_99km.nc'",
    ";GSWM_NM_SDI_NCFILE = '$TGCMDATA/gswm_nonmig_semi_5.0d_99km.nc'",
    ";",
    "; Potential model can be 'HEELIS' (optionally with GPI data),",
    "; or 'WEIMER' (optionally with IMF data). If WEIMER, both IMF",
    "; and GPI may be specified, but only f10.7 will be used from GPI.",
    ";",
    " POTENTIAL_MODEL = 'HEELIS'",
    "; POTENTIAL_MODEL = 'WEIMER'",
    ";",
    "; If potential model is HEELIS, GPI data can be used to calculate",
    "; POWER and CTPOTEN from Kp data, and to use data for f10.7 flux.",
    "; If GPI_NCFILE is specified, one or more of POWER,CTPOTEN,F107,F107A",
    "; must be commented out (data will be used for those that are commented",
    "; out, otherwise the user-provided values will be used).",
    ";",
    ";GPI_NCFILE = '$TGCMDATA/{}'".format(iss["gpi_ncfile"]),
    ";",
    "; If KP is specified, and POWER and/or CTPOTEN are commented,",
    "; then the given KP will be used to calculate POWER and/or CTPOTEN",
    ";",
    "KP = {}".format(kph),                                                      
    "; POWER   = 18.",
    "; CTPOTEN = 30.",
    " F107    = {}".format(f107h),
    " F107A   = {}".format(f107a),
    ";",
    "; If potential model is WEIMER, data file IMF_NCFILE can be specified",
    "; to read one or more of BXIMF,BYIMF,BZIMF,SWVEL,SWDEN. If IMF_NCFILE",
    "; is specified and POWER is not provided, it will be calculated from",
    "; BZ,SWVEL. Also, if IMF_NCFILE is provided, user cannot provide CTPOTEN",
    "; (it will be calculated from the Weimer potential).",
    ";",
    #SMURRAY: this will need to be changed depending on the run year! EMH: can't span years. Below tests we're not (no file if span)!
    ";IMF_NCFILE = '$TGCMDATA/imf_OMNI_{}001-{}365.nc'".format(iss["start_datetime_p"].strftime("%Y"),iss["end_datetime_p"].strftime("%Y")),
    ";",
    ";BXIMF   = 0.",
    ";BYIMF   = 0.",
    ";BZIMF   = -5.",
    ";SWVEL   = 400.",
    ";SWDEN   = 4.0",
    ";SEE_NCFILE = '$TGCMDATA/see__L3_merged_2005007_007.nc'",
    " AURORA = 1",
    " COLFAC = 1.5 ;default 1.5",
    "/",
    "",
    ]
    
    #Join the sections
    input_file = start_sec + extra_sec + continue_sec + output_sec + mid_sec + secout_sec + end_sec
    
    return iss["filename"], input_file




