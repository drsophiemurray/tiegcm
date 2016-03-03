tiegcm
======

Edited version of the Thermosphere Ionosphere Electrodynamics General Circulation Model [(TIEGCMv1.95)](http://www.hao.ucar.edu/modeling/tgcm), developed by NCAR. This version allows lower boundary forcing with the Met Office [Unified Model](http://www.metoffice.gov.uk/research/modelling-systems/unified-model). The following parameters can be used:
  * Zonal component of wind (u) on pressure levels and uv grid
  * Meridional component of wind (v) on pressure levels and uv grid
  * Temperature (T) on pressure levels and uv grid
  * Geopotential height (Z) on pressure levels and uv grid

These parameters can be inputted directly at the lowest pressure level, or as a monthly average.



Directory list:
---------------

| Subdir | Description | Summary of Contents |
| ------ | :---------: | :------------------:|
| inputs/ | Example files | Input files *.inp, job files *.job |
| scripts/ | Support scripts | Default job scripts, make files, utilities |
| src/ | Source code | Source files *.F, *.h |



See the main TGCM [website](http://www.hao.ucar.edu/modeling/tgcm/download.php) to download the full code and required data, as well as instructions for installation and user guide. 
