'''
Python Version:    2.7.2 (default, Oct  1 2012, 15:56:20)
@author: smurray@eld264
Created on Jul 15, 2014
Purpose: Called by tie_cron.py for creating plots for internal webpages. 
            Will update with TIEGCM results daily.
'''
import netCDF4
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import datetime as dt
import numpy as np
import matplotlib.patheffects as PathEffects
import os 
import monty


mpl.rc('font', family = 'serif', weight = 'normal', size = 10)

PUBLIC_LOC = os.path.expanduser('~/public_html/tiegcm_images/')
SAVE_LOC = "".join([os.environ["LOCALDATA"], "/tiegcm_images/"])

def main(source_path, level, time_element, image_name):
    """Run main code, calling various functions"""
    den, temp, ht, time, lat, lon, pres = import_tiegcm(source_path, time_element, level)
    plot_tiegcm(time, lat, lon, den, temp, ht, pres, image_name)
    

def plot_tiegcm(time, lat, lon, den, temp, ht, pres, image_name):
    """Plot density, temperature, and geopotential height
    for all latitudes and longitudes at relevant time"""
    y_values = [-90, -45, 0, 45, 90]
    x_values = [-180, -135, -90, -45, 0, 45, 90, 135, 180]
    fig = plt.figure()
#    fig.subplots_adjust(left = 0.25, right = 0.7, bottom = 0.07, top = 0.9, wspace = 0.2, hspace = 0.08)
    sub_den = fig.add_subplot(3, 1, 1)
    plot_settings(sub_den, den*1e12, lon, lat, 
                  y_values, x_values = [], 
                  ylabel = "", xlabel = "",
                  title = 'Density',
                  ctitle = r"x 10$^{-12}$ kgm$^{-3}$ ",
                  minmax = [2., 4.])
    pres = format(pres, '.2e')
    plt.title('{} at {} Pa'.format(time, pres), fontsize = 11)
    sub_temp = fig.add_subplot(3, 1, 2)
    plot_settings(sub_temp, temp, lon, lat,
                  y_values, x_values = [],
                  ylabel = 'Latitude [$^\circ$]', xlabel = "",
                  title = 'Temperature',
                  ctitle = "Kelvin",
                  minmax = [750., 1250.])
    sub_ht = fig.add_subplot(3, 1, 3)
    plot_settings(sub_ht, ht/100000., lon, lat,
                  y_values, x_values, 
                  ylabel = " ", xlabel = 'Longitude [$^\circ$]', 
                  title = 'Geopotential Height', 
                  ctitle = "km",
                  minmax = [350., 450.])
    plt.figtext(.6, .032, r'$\copyright$ Crown Copyright. Source: Met Office', size = 8)
    plt.tight_layout()
#    insert_logo()
    save_to_web(fig, time, image_name)
    
    
def save_to_web(fig, time, image_name):
    save_image = "".join([SAVE_LOC, time.strftime("%Y%m%d-%H%M"), ".png"])
    if not os.path.isdir(SAVE_LOC):
        os.mkdir(SAVE_LOC)
    latest_image = "".join([PUBLIC_LOC, "{}.png".format(image_name)])
    if not os.path.isdir(PUBLIC_LOC):
        os.mkdir(PUBLIC_LOC)
    fig.savefig(latest_image, format = "png")
    fig.savefig(save_image, format = "png")


def plot_settings(ax, data, lon, lat, y_values, x_values, ylabel, xlabel, title, ctitle, minmax):
    """Generic settings for plot creation"""
    if minmax is None:
        data_min = (data.min()//1.)*1.
        data_max = (data.max()//1.+1.)*1.
    else:
        data_min = minmax[0]
        data_max = minmax[1]
    #print data_min, data_max
    norm = mpl.colors.Normalize(vmin = data_min, vmax = data_max)
    x_lim, y_lim = [-180, 180], [-90, 90]
    im = ax.pcolor(lon, lat, data, norm = norm)
    ax.set_xlim(x_lim)
    ax.set_ylim(y_lim)
    ax.set_xticks(x_values)
    ax.set_yticks(y_values)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.text(-175, 60, title, fontsize = 12, 
            path_effects=[PathEffects.withStroke(linewidth = 1, foreground="w")]) #horizontalalignment = "centered")
    cbar = plt.colorbar(im)
    cbar.set_label(ctitle)
    
    
def import_tiegcm(source_path, time_element, level):
    """Load TIEGCM results to be plotted"""
    tiegcm = netCDF4.Dataset(source_path, 
                             'r', format = 'NETCDF3_CLASSIC')
    tiegcm_den = tiegcm.variables["DEN"]  #time, ilev, lat, lon
    gcm3_to_kgm3 = 1000.
    tiegcm_den = tiegcm_den[:, :, :, :] * gcm3_to_kgm3
    tiegcm_temp = tiegcm.variables["TN"]
    tiegcm_temp = tiegcm_temp[:, :, :, :]
    tiegcm_ht = tiegcm.variables["ZG"]
    tiegcm_ht = tiegcm_ht[:, :, :, :]
    tiegcm_time = tiegcm.variables["time"]
    tiegcm_ref_time = netCDF4.num2date(tiegcm_time[:], tiegcm_time.units)
    tiegcm_time = tiegcm_time[:]
    tiegcm_lat = tiegcm.variables["lat"]
    tiegcm_lat = tiegcm_lat[:]
    tiegcm_lon = tiegcm.variables["lon"]
    tiegcm_lon = tiegcm_lon[:]
    tiegcm_pres = tiegcm.variables["p0"][:] * 100 * np.exp(-1 * tiegcm.variables["lev"][:]) #convert p0 to pascal
    return tiegcm_den[time_element, level, :, :], tiegcm_temp[time_element, level, :, :], tiegcm_ht[time_element, level, :, :], tiegcm_ref_time[time_element], tiegcm_lat, tiegcm_lon, tiegcm_pres[level]


def insert_logo():
    '''
Insert a logo into the current figure

The logo should be a small (say around 100x100 pixels) image whose path+name
is defined in GWV_LOGO (default ~/data/logos/meto_eumetnet_logo.png).
If the logo file is not found, this routine just returns silently, otherwise
the logo file is read and the graphic inserted into the parent plot in the
top left corner.
    '''
    # Save curent axes
    fig = plt.gcf()
    original_axes = plt.gca()
    # Layout parameters
    inset = 0.01             # Distance from edge to logo
    logo_size = 0.1          # Size of logo (height)
    # Source of logo file
    logo_path = os.path.expanduser('~/logos/meto_eumetnet_logo.png')
    # Plot logo if found
    if os.path.exists(logo_path):
        logo = plt.imread(logo_path)
        xpix, ypix = np.shape(logo)[0:2]
        # Plot the logo within dummy axes
        left = inset
        bottom = 1.0 - inset - logo_size
        height = logo_size
        width = height * ypix / xpix
        rect = (left, bottom, width, height)
        logo_axes = _dummy_axes(rect, 'logo')
        logo_axes.imshow(logo, zorder = 20)
        # Reset the current axes
        fig.sca(original_axes)
        
def _dummy_axes(rect, label, frame=False):
    'Set up dummy axes'
    figure = plt.gcf()
    axes = figure.add_axes(rect, label=label, navigate=False, frame_on=frame)
    axes.set_xticks([])
    axes.set_yticks([])
    return axes

#--------------------------------------------------------------------------


if __name__ == '__main__':
    main()
